"""
操盘平台 - Flask Web 主应用
"""
import json
import os
from datetime import date, datetime, timedelta
from flask import Flask, render_template, jsonify, request, send_from_directory

from database.db_manager import DatabaseManager
from database.models import get_connection
from engine.hot_spot import HotSpotEngine
from engine.main_force import MainForceAnalyzer
from engine.breakout import BreakoutAnalyzer
from engine.risk_control import RiskController
from engine.policy_analyzer import PolicyAnalyzer
from engine.stock_selector import StockSelector
from engine.portfolio import PortfolioManager
from engine.recommender import DailyRecommender
from engine.leader_selector import LeaderSelector
from engine.sim_trade import SimTradeEngine
from engine.ths_sync import sync_ths_to_pool
from engine.breaking_events import BreakingEventEngine
from engine.data_fetcher import (
    tencent_quote, get_kline, get_index_data,
    get_hot_sectors, get_fund_flow_120d,
    get_fund_flow_minute, get_global_news, get_stock_news,
    get_technical_indicators
)
from config import BASE_DIR

app = Flask(__name__,
            template_folder=os.path.join(BASE_DIR, "templates"),
            static_folder=os.path.join(BASE_DIR, "static"))

# 强制UTF-8编码（Windows兼容）
app.config['JSON_AS_ASCII'] = False
app.config['JSONIFY_MIMETYPE'] = 'application/json; charset=utf-8'

# 初始化各模块
db = DatabaseManager()
hot_spot_engine = HotSpotEngine(db)
main_force_analyzer = MainForceAnalyzer()
breakout_analyzer = BreakoutAnalyzer()
risk_controller = RiskController(db)
policy_analyzer = PolicyAnalyzer(db)
stock_selector = StockSelector(db)
portfolio_manager = PortfolioManager(db)
daily_recommender = DailyRecommender(db)
leader_selector = LeaderSelector(db)
sim_trader = SimTradeEngine(db)
breaking_events = BreakingEventEngine(db)


# ==================== API 路由 ====================

@app.route("/")
def index():
    """主页面"""
    return render_template("index.html")


@app.route("/api/overview")
def api_overview():
    """概览数据 — 整合行情+热点+股票池+风险预警"""
    pool_stats = db.get_buy_pool_stats()
    trade_stats = db.get_trade_stats()

    # 指数数据（腾讯财经行情可用）
    indices = get_index_data()

    # 市场环境（从DB读取已缓存的TDX数据）
    market_env = db.get_latest_market_env()

    # 股票池个股风险评估
    pool = db.get_buy_pool()
    pool_alerts = _generate_pool_alerts(pool, indices)

    # 综合风险评分
    risk_score = _calc_overall_risk(indices, market_env, pool_alerts)

    # 风险等级
    if risk_score >= 70:
        risk_level = "high"
    elif risk_score >= 40:
        risk_level = "medium"
    else:
        risk_level = "low"

    sentiment_map = {"bullish": "市场乐观", "slightly_bullish": "市场偏暖",
                     "neutral": "市场中性", "slightly_bearish": "市场偏弱", "bearish": "市场恐慌"}
    sentiment = market_env.get("market_sentiment", "neutral") if market_env else "neutral"

    return jsonify({
        "pool_stats": pool_stats,
        "trade_stats": trade_stats,
        "risk_env": {
            "level": risk_level,
            "score": risk_score,
            "sentiment": {
                "status": sentiment,
                "description": sentiment_map.get(sentiment, "未知"),
            },
            "alerts": pool_alerts[:5],
        },
        "indices": {
            "sh": indices.get("sh", {}).get("change_pct", 0),
            "sz": indices.get("sz", {}).get("change_pct", 0),
            "cyb": indices.get("cyb", {}).get("change_pct", 0),
        },
        "market_env": {
            "sh_index": market_env.get("sh_index") if market_env else None,
            "sz_index": market_env.get("sz_index") if market_env else None,
            "cyb_index": market_env.get("cyb_index") if market_env else None,
            "up_count": market_env.get("up_count") if market_env else 0,
            "down_count": market_env.get("down_count") if market_env else 0,
            "limit_up": market_env.get("limit_up_count") if market_env else 0,
            "limit_down": market_env.get("limit_down_count") if market_env else 0,
            "event_impact": market_env.get("event_impact") if market_env else "",
        },
    })


def _generate_pool_alerts(pool: list, indices: dict) -> list:
    """生成股票池个股实时风险预警"""
    alerts = []
    sh_chg = indices.get("sh", {}).get("change_pct", 0)
    sz_chg = indices.get("sz", {}).get("change_pct", 0)

    # 大盘预警
    if sh_chg < -0.02 or sz_chg < -0.02:
        alerts.append({"type": "index", "level": "critical",
                       "message": f"⚠️ 大盘大幅下跌！上证{sh_chg:.2%} 深证{sz_chg:.2%}，建议减仓控制风险"})
    elif sh_chg < -0.01 or sz_chg < -0.01:
        alerts.append({"type": "index", "level": "warning",
                       "message": f"大盘较弱，操作需谨慎"})

    # 个股预警
    high_risk_stocks = []
    for s in pool:
        phase = s.get("main_force_phase", 0)
        name = s.get("name", "")
        code = s.get("code", "")

        if phase >= 5:
            high_risk_stocks.append(f"{name}({code})主力进入末期/出货阶段")
        elif phase == 6:
            high_risk_stocks.append(f"{name}({code})主力出货中，建议清仓")

    if high_risk_stocks:
        alerts.append({"type": "stock", "level": "warning",
                       "message": "⚠️ " + "；".join(high_risk_stocks[:3])})

    # 板块集中度预警
    pool_stats = db.get_buy_pool_stats()
    sectors = pool_stats.get("sectors", [])
    if sectors and sectors[0].get("count", 0) >= 3:
        alerts.append({"type": "concentration", "level": "info",
                       "message": f"板块集中度较高：{sectors[0]['name']}占{sectors[0]['count']}只"})

    return alerts


def _calc_overall_risk(indices: dict, market_env: dict, pool_alerts: list) -> float:
    """计算综合风险评分(0-100)"""
    score = 30
    sh = indices.get("sh", {}).get("change_pct", 0) or 0
    sz = indices.get("sz", {}).get("change_pct", 0) or 0
    avg_idx = (sh + sz) / 2 if (sh or sz) else 0

    if avg_idx < -0.02: score += 30
    elif avg_idx < -0.01: score += 15
    elif avg_idx > 0.01: score -= 10
    elif avg_idx > 0.02: score -= 15

    for alert in pool_alerts:
        if alert["level"] == "critical": score += 20
        elif alert["level"] == "warning": score += 10

    return min(100, max(0, score))


@app.route("/api/quotes")
def api_quotes():
    """获取股票行情"""
    codes = request.args.get("codes", "")
    if codes:
        code_list = codes.split(",")
    else:
        pool = db.get_pool()
        code_list = [s["code"] for s in pool[:20]]

    quotes = tencent_quote(code_list)
    return jsonify({"quotes": quotes})


@app.route("/api/kline")
def api_kline():
    """获取K线数据"""
    code = request.args.get("code", "")
    period = request.args.get("period", "day")
    count = int(request.args.get("count", 60))

    if not code:
        return jsonify({"error": "缺少股票代码"}), 400

    klines = get_kline(code, period, count)
    return jsonify({"code": code, "period": period, "klines": klines})


@app.route("/api/stock_pool")
def api_stock_pool():
    """获取买入池"""
    phase = request.args.get("phase", "")
    pool = db.get_buy_pool(phase=phase if phase else None)

    # 附加实时行情
    if pool:
        codes = [s["code"] for s in pool]
        quotes = tencent_quote(codes)
        for stock in pool:
            q = quotes.get(stock["code"], {})
            stock["price"] = q.get("price", stock.get("entry_price", 0))
            stock["change_pct"] = q.get("change_pct", 0)
            stock["pe_ttm_current"] = q.get("pe_ttm", stock.get("pe_ttm", 0))

    return jsonify({"pool": pool, "stats": db.get_buy_pool_stats()})


@app.route("/api/pools/summary")
def api_pools_summary():
    """获取三层池总览"""
    summary = db.get_all_pools_summary()
    return jsonify(summary)


@app.route("/api/pools/liquidate")
def api_liquidate_pool():
    """获取清仓池"""
    pool = db.get_liquidate_pool()
    if pool:
        codes = [s["code"] for s in pool]
        quotes = tencent_quote(codes)
        for stock in pool:
            q = quotes.get(stock["code"], {})
            stock["current_price"] = q.get("price", stock.get("liquidate_price", 0))
            stock["change_from_entry"] = round(
                (q.get("price", 0) / stock.get("entry_price", 1) - 1) * 100, 2
            ) if stock.get("entry_price") else 0
    return jsonify({"pool": pool})


@app.route("/api/pools/eliminated")
def api_eliminated_pool():
    """获取淘汰池"""
    limit = int(request.args.get("limit", 50))
    pool = db.get_eliminated_pool(limit)
    stats = db.get_eliminated_stats()
    return jsonify({"pool": pool, "stats": stats})


@app.route("/api/stock_pool/add", methods=["POST"])
def api_add_to_pool():
    """添加股票到买入池（自动触发智能淘汰机制）"""
    data = request.json or {}
    code = data.get("code", "")
    if not code:
        return jsonify({"error": "缺少股票代码"}), 400

    quotes = tencent_quote([code])
    if code not in quotes:
        return jsonify({"error": "获取行情失败"}), 400

    q = quotes[code]
    force = main_force_analyzer.analyze(code)
    stage, _ = main_force_analyzer.is_main_wave(code)

    fund_flows = get_fund_flow_120d(code)
    fund_20d = sum(f.get("main_net", 0) for f in fund_flows[-20:]) / 1e8 if fund_flows else 0

    # 计算综合评分
    score = _calc_stock_score(force, fund_20d, q)

    stock = {
        "code": code,
        "name": q.get("name", ""),
        "sector": data.get("sector", ""),
        "sub_sector": data.get("sub_sector", ""),
        "market_cap": q.get("mcap_yi", 0),
        "pe_ttm": q.get("pe_ttm", 0),
        "pb": q.get("pb", 0),
        "phase": stage if stage in ["early", "mid"] else "watch",
        "main_wave_start_date": date.today().isoformat(),
        "main_wave_gain": 0,
        "main_force_phase": force["phase"],
        "entry_price": q.get("price", 0),
        "hot_topics": data.get("hot_topics", []),
        "institution_rating": "",
        "risk_score": 50 - force["confidence"] * 0.3,
        "total_score": score,
        "volume_trend": force.get("volume_analysis", {}).get("recent_volume_trend", ""),
        "fund_flow_20d": round(fund_20d, 2),
    }

    # 使用智能淘汰机制
    result = db.smart_eliminate_and_add(stock)
    return jsonify({"success": True, "stock": stock, "elimination": result})


@app.route("/api/stock_pool/remove", methods=["POST"])
def api_remove_from_pool():
    """从买入池淘汰指定股票"""
    data = request.json or {}
    code = data.get("code", "")
    reason = data.get("reason", "手动淘汰")
    if not code:
        return jsonify({"error": "缺少股票代码"}), 400

    quotes = tencent_quote([code])
    price = quotes.get(code, {}).get("price", 0)

    db.eliminate_from_buy_pool(code, reason, price)
    return jsonify({"success": True, "code": code, "eliminated_price": price})


@app.route("/api/stock_pool/move_to_liquidate", methods=["POST"])
def api_move_to_liquidate():
    """移入清仓池"""
    data = request.json or {}
    code = data.get("code", "")
    reason = data.get("reason", "触发卖出信号")
    if not code:
        return jsonify({"error": "缺少股票代码"}), 400

    quotes = tencent_quote([code])
    price = quotes.get(code, {}).get("price", 0)

    success = db.move_to_liquidate_pool(code, reason, price)
    return jsonify({"success": success, "code": code, "liquidate_price": price})


@app.route("/api/stock_pool/confirm_liquidate", methods=["POST"])
def api_confirm_liquidate():
    """确认清仓→移入淘汰池"""
    data = request.json or {}
    code = data.get("code", "")
    reason = data.get("reason", "已清仓")
    if not code:
        return jsonify({"error": "缺少股票代码"}), 400

    success = db.liquidate_to_eliminated(code, reason)
    return jsonify({"success": success})


@app.route("/api/stock_pool/review_eliminated", methods=["POST"])
def api_review_eliminated():
    """复盘评价淘汰股票"""
    data = request.json or {}
    code = data.get("code", "")
    evaluation = data.get("evaluation", "")  # correct/wrong/uncertain
    notes = data.get("notes", "")
    if not code:
        return jsonify({"error": "缺少股票代码"}), 400

    success = db.update_eliminated_review(code, evaluation, notes)
    return jsonify({"success": success})


@app.route("/api/stock_pool/estimate_score", methods=["POST"])
def api_estimate_score():
    """预估股票评分（不入池）"""
    data = request.json or {}
    code = data.get("code", "")
    if not code:
        return jsonify({"error": "缺少股票代码"}), 400

    quotes = tencent_quote([code])
    if code not in quotes:
        return jsonify({"error": "获取行情失败"}), 400

    q = quotes[code]
    force = main_force_analyzer.analyze(code)
    stage, _ = main_force_analyzer.is_main_wave(code)
    fund_flows = get_fund_flow_120d(code)
    fund_20d = sum(f.get("main_net", 0) for f in fund_flows[-20:]) / 1e8 if fund_flows else 0
    score = _calc_stock_score(force, fund_20d, q)

    return jsonify({
        "code": code,
        "name": q.get("name", ""),
        "price": q.get("price", 0),
        "market_cap": q.get("mcap_yi", 0),
        "pe_ttm": q.get("pe_ttm", 0),
        "main_force_phase": force["phase"],
        "phase_name": force["phase_name"],
        "main_wave_stage": stage,
        "fund_flow_20d": round(fund_20d, 2),
        "estimated_score": score,
    })


def _calc_stock_score(force: dict, fund_20d: float, quote: dict) -> float:
    """计算股票综合评分(0-100)"""
    score = 0
    phase = force["phase"]
    phase_score = {3: 30, 4: 25, 1: 10, 2: 15, 5: 5, 6: 0}
    score += phase_score.get(phase, 0)
    score += force.get("confidence", 0) * 0.15

    if fund_20d > 5: score += 20
    elif fund_20d > 2: score += 15
    elif fund_20d > 0.5: score += 10
    elif fund_20d > 0: score += 5
    elif fund_20d < -1: score -= 10

    ma_position = force.get("ma_position", {})
    if all(ma_position.values()): score += 15
    elif ma_position.get("price_above_ma20"): score += 8

    turnover = quote.get("turnover_pct", 0)
    if 3 <= turnover <= 10: score += 10
    elif turnover < 3: score += 5

    pe = quote.get("pe_ttm", 0)
    if 0 < pe <= 30: score += 10
    elif 0 < pe <= 60: score += 6
    elif pe > 60: score += 2

    return min(100, max(0, round(score, 1)))
    reason = data.get("reason", "手动移除")
    if not code:
        return jsonify({"error": "缺少股票代码"}), 400

    db.remove_from_pool(code, reason)
    return jsonify({"success": True})


@app.route("/api/analysis/main_force")
def api_main_force():
    """主力分析"""
    code = request.args.get("code", "")
    if not code:
        return jsonify({"error": "缺少股票代码"}), 400

    result = main_force_analyzer.analyze(code)
    return jsonify(result)


@app.route("/api/analysis/intent")
def api_intent_analysis():
    """主力操盘意图及手法分析 + 未来3日推演"""
    code = request.args.get("code", "")
    if not code:
        return jsonify({"error": "缺少股票代码"}), 400
    phase_result = main_force_analyzer.analyze(code)
    intent_result = main_force_analyzer.analyze_intent(code, phase_info=phase_result)
    return jsonify(intent_result)


@app.route("/api/analysis/breakout")
def api_breakout():
    """突破分析"""
    code = request.args.get("code", "")
    if not code:
        return jsonify({"error": "缺少股票代码"}), 400

    result = breakout_analyzer.analyze(code)
    return jsonify(result)


@app.route("/api/analysis/hot_spot")
def api_hot_spot():
    """热点分析"""
    result = hot_spot_engine.analyze()
    return jsonify(result)


@app.route("/api/analysis/risk")
def api_risk():
    """风险分析"""
    result = risk_controller.check_environment()
    return jsonify(result)


@app.route("/api/analysis/policy")
def api_policy():
    """政策分析"""
    sector = request.args.get("sector", "")
    if sector:
        result = policy_analyzer.analyze_sector_deep(sector)
    else:
        result = policy_analyzer.analyze_policy_environment()
    return jsonify(result)


@app.route("/api/analysis/sector_leaders")
def api_sector_leaders():
    """板块龙头"""
    sector = request.args.get("sector", "人工智能")
    leaders = policy_analyzer.find_sector_leaders(sector)
    return jsonify({"sector": sector, "leaders": leaders})


@app.route("/api/recommendations")
def api_recommendations():
    """获取推荐记录（含追踪数据）"""
    date_str = request.args.get("date", "")
    if date_str:
        recs = db.get_recommendations(trade_date=date_str)
    else:
        recs = db.get_recommendations(trade_date=None, limit=20)
    return jsonify({"date": date_str or "all", "recommendations": recs})


@app.route("/api/recommendations/generate", methods=["POST"])
def api_generate_recommendations():
    """生成每日推荐"""
    result = daily_recommender.generate_recommendations()
    return jsonify(result)


@app.route("/api/recommendations/track", methods=["POST"])
def api_track_recommendations():
    """更新所有活跃推荐的7日追踪数据"""
    from engine.data_fetcher import tencent_quote
    active_recs = db.get_recommendations_needing_tracking(7)

    updated = 0
    for rec in active_recs:
        rec_id = rec["id"]
        code = rec["code"]
        rec_price = rec.get("recommend_price", rec.get("buy_price", 0))
        rec_date = rec["date"]

        if not rec_price:
            continue

        quotes = tencent_quote([code])
        q = quotes.get(code, {})
        current_price = q.get("price", 0)
        high = q.get("high", 0)
        low = q.get("low", 0)
        last_close = q.get("last_close", 0)

        if not current_price:
            continue

        # 计算当日涨幅
        intraday_gain = round((current_price / rec_price - 1) * 100, 2) if rec_price else 0
        tracking = {
            "intraday_high": high,
            "intraday_low": low,
            "intraday_close": current_price,
            "intraday_gain_pct": intraday_gain,
        }

        # 计算从推荐日到现在的天数
        from datetime import datetime as dt
        try:
            rec_dt = dt.strptime(rec_date, "%Y-%m-%d")
            days_since = (dt.now() - rec_dt).days
        except:
            days_since = 0

        # 填充7天收益（day1_gain ~ day7_gain 对应第1-7天的累计收益）
        if days_since >= 1:
            tracking["day1_gain"] = intraday_gain
        if days_since >= 2:
            tracking["day2_gain"] = intraday_gain
        if days_since >= 3:
            tracking["day3_gain"] = intraday_gain

        # 最大收益/回撤
        if rec.get("intraday_high", 0) < high:
            tracking["max_gain_7d"] = round((high / rec_price - 1) * 100, 2)
        elif not rec.get("max_gain_7d"):
            tracking["max_gain_7d"] = max(intraday_gain, 0)

        if rec.get("intraday_low", 9999) > low:
            tracking["max_loss_7d"] = round((low / rec_price - 1) * 100, 2)
        elif not rec.get("max_loss_7d"):
            tracking["max_loss_7d"] = min(intraday_gain, 0)

        db.update_recommendation_tracking(rec_id, tracking)
        updated += 1

    return jsonify({"success": True, "updated": updated})


@app.route("/api/trades")
def api_trades():
    """获取交易记录"""
    limit = int(request.args.get("limit", 50))
    trades = db.get_trades(limit)
    stats = db.get_trade_stats()
    return jsonify({"trades": trades, "stats": stats})


@app.route("/api/trades/add", methods=["POST"])
def api_add_trade():
    """添加交易记录"""
    data = request.json or {}
    trade_id = db.add_trade(data)
    return jsonify({"success": True, "id": trade_id})


@app.route("/api/portfolio/report")
def api_portfolio_report():
    """组合报告"""
    report = portfolio_manager.generate_report()
    performance = portfolio_manager.get_portfolio_performance()
    return jsonify({"report": report, "performance": performance})


@app.route("/api/portfolio/monitor")
def api_portfolio_monitor():
    """组合监控"""
    result = portfolio_manager.monitor_holdings()
    return jsonify(result)


@app.route("/api/alerts")
def api_alerts():
    """获取预警"""
    alerts = db.get_active_alerts()
    return jsonify({"alerts": alerts})


@app.route("/api/news")
def api_news():
    """获取新闻"""
    code = request.args.get("code", "")
    limit = int(request.args.get("limit", 20))
    if code:
        news = get_stock_news(code, limit)
    else:
        news = get_global_news(limit)
    return jsonify({"news": news})


@app.route("/api/technical")
def api_technical():
    """获取技术指标"""
    code = request.args.get("code", "")
    if not code:
        return jsonify({"error": "缺少股票代码"}), 400

    indicators = get_technical_indicators(code)
    return jsonify({"code": code, "indicators": indicators})


@app.route("/api/fund_flow")
def api_fund_flow():
    """获取资金流向"""
    code = request.args.get("code", "")
    if not code:
        return jsonify({"error": "缺少股票代码"}), 400

    flow_type = request.args.get("type", "120d")
    if flow_type == "minute":
        data = get_fund_flow_minute(code)
    else:
        data = get_fund_flow_120d(code)

    return jsonify({"code": code, "flow_type": flow_type, "data": data})


@app.route("/api/screen")
def api_screen():
    """选股筛选"""
    candidates = stock_selector.get_hot_sector_candidates()
    results = stock_selector.screen_candidates(candidates)
    return jsonify({"candidates_count": len(candidates), "results": results[:30]})


@app.route("/api/build_pool", methods=["POST"])
def api_build_pool():
    """构建股票池 — 尝试TDX选股+腾讯行情验证"""
    try:
        candidates = stock_selector.get_hot_sector_candidates()
        if candidates:
            results = stock_selector.screen_candidates(candidates)
            pool = stock_selector.build_stock_pool(results)
            return jsonify(pool)
    except Exception as e:
        print(f"自动建池失败: {e}")

    # 降级：返回当前已有池的数据
    buy_pool = db.get_buy_pool()
    if buy_pool:
        early = [s for s in buy_pool if s.get('phase') == 'early']
        mid = [s for s in buy_pool if s.get('phase') == 'mid']
        return jsonify({
            "early_stage": early, "mid_stage": mid,
            "total": len(buy_pool),
            "message": "⚠️ 外部数据获取受限，显示当前股票池状态。可通过\"智能加入\"手动添加股票。",
        })

    return jsonify({"message": "暂无股票池数据，请通过TDX选股后手动添加"})


# ==================== VIP持仓池 API ====================

@app.route("/api/vip/holdings")
def api_vip_holdings():
    """获取VIP持仓列表（含实时行情和自动盈亏计算）"""
    status = request.args.get("status", "holding")
    holdings = db.get_vip_holdings(status=status)

    # 批量获取实时行情并更新盈亏
    if holdings and status == 'holding':
        codes = [h["code"] for h in holdings]
        quotes = tencent_quote(codes)

        for h in holdings:
            code = h["code"]
            q = quotes.get(code, {})
            current_price = q.get("price", 0)
            if current_price > 0:
                h["current_price"] = current_price
                h["current_value"] = round(current_price * h["shares"], 2)
                h["profit_loss"] = round(h["current_value"] - h["entry_amount"], 2)
                h["profit_loss_pct"] = round((current_price / h["entry_price"] - 1) * 100, 2) if h["entry_price"] else 0
                h["change_pct"] = q.get("change_pct", 0)

                # 更新数据库中价格
                db.update_vip_prices(code, current_price)

    summary = db.get_vip_summary() if status == 'holding' else {}
    return jsonify({"holdings": holdings, "summary": summary})


@app.route("/api/vip/holdings/add", methods=["POST"])
def api_vip_add_holding():
    """手动添加VIP持仓"""
    data = request.json or {}
    code = data.get("code", "")
    if not code:
        return jsonify({"error": "缺少股票代码"}), 400

    # 获取股票名称
    quotes = tencent_quote([code])
    q = quotes.get(code, {})
    name = q.get("name", data.get("name", ""))

    if not name:
        return jsonify({"error": "获取股票名称失败"}), 400

    holding = {
        "code": code,
        "name": name,
        "sector": data.get("sector", ""),
        "entry_date": data.get("entry_date", date.today().isoformat()),
        "entry_price": data.get("entry_price", 0),
        "shares": data.get("shares", 0),
        "stop_loss_price": data.get("stop_loss_price"),
        "take_profit_price": data.get("take_profit_price"),
        "notes": data.get("notes", ""),
    }

    if holding["entry_price"] <= 0 or holding["shares"] <= 0:
        return jsonify({"error": "建仓价格和数量必须大于0"}), 400

    # 检查是否已存在
    existing = db.get_vip_holding_by_code(code)
    if existing:
        return jsonify({"error": f"{name}({code})已在持仓中"}), 400

    holding_id = db.add_vip_holding(holding)

    # 立即更新当前价格
    current_price = q.get("price", holding["entry_price"])
    db.update_vip_prices(code, current_price)

    # 生成AI建议
    _generate_vip_suggestion(code, name, holding["entry_price"], current_price, holding["shares"])

    return jsonify({"success": True, "id": holding_id, "name": name})


@app.route("/api/vip/holdings/update", methods=["POST"])
def api_vip_update_holding():
    """更新VIP持仓"""
    data = request.json or {}
    code = data.get("code", "")
    if not code:
        return jsonify({"error": "缺少股票代码"}), 400

    updates = {}
    for field in ["shares", "entry_price", "entry_date", "stop_loss_price",
                   "take_profit_price", "notes", "sector"]:
        if field in data:
            updates[field] = data[field]

    if not updates:
        return jsonify({"error": "没有需要更新的字段"}), 400

    # 如果修改了价格或数量，重算建仓金额
    if 'entry_price' in updates or 'shares' in updates:
        holding = db.get_vip_holding_by_code(code)
        if holding:
            entry_price = updates.get('entry_price', holding['entry_price'])
            shares = updates.get('shares', holding['shares'])
            updates['entry_amount'] = entry_price * shares

    db.update_vip_holding(code, updates)
    return jsonify({"success": True})


@app.route("/api/vip/holdings/remove", methods=["POST"])
def api_vip_remove_holding():
    """删除VIP持仓"""
    data = request.json or {}
    code = data.get("code", "")
    if not code:
        return jsonify({"error": "缺少股票代码"}), 400

    db.update_vip_holding(code, {"status": "removed"})
    return jsonify({"success": True})


@app.route("/api/vip/holdings/sell", methods=["POST"])
def api_vip_sell_holding():
    """卖出VIP持仓"""
    data = request.json or {}
    code = data.get("code", "")
    sell_price = data.get("sell_price", 0)
    sell_date = data.get("sell_date", date.today().isoformat())

    if not code:
        return jsonify({"error": "缺少股票代码"}), 400

    if sell_price <= 0:
        # 自动使用当前价格
        quotes = tencent_quote([code])
        sell_price = quotes.get(code, {}).get("price", 0)

    if sell_price <= 0:
        return jsonify({"error": "无法获取卖出价格"}), 400

    db.sell_vip_holding(code, sell_price, sell_date)
    return jsonify({"success": True, "sell_price": sell_price})


@app.route("/api/vip/suggestion", methods=["POST"])
def api_vip_generate_suggestion():
    """为VIP持仓生成AI建议（单只或全部）"""
    data = request.json or {}
    code = data.get("code", "")

    if code:
        holding = db.get_vip_holding_by_code(code)
        if not holding:
            return jsonify({"error": "未找到该持仓"}), 400

        quotes = tencent_quote([code])
        current_price = quotes.get(code, {}).get("price", holding["entry_price"])

        suggestion = _generate_vip_suggestion(
            code, holding["name"], holding["entry_price"],
            current_price, holding["shares"]
        )
        return jsonify({"code": code, "suggestion": suggestion})
    else:
        # 分析全部持仓
        holdings = db.get_vip_holdings()
        results = []
        for h in holdings:
            code = h["code"]
            quotes = tencent_quote([code])
            current_price = quotes.get(code, {}).get("price", h["entry_price"])
            sug = _generate_vip_suggestion(
                code, h["name"], h["entry_price"], current_price, h["shares"]
            )
            results.append({"code": code, "name": h["name"], "suggestion": sug})

        return jsonify({"results": results})


@app.route("/api/vip/history")
def api_vip_history():
    """获取VIP历史交易"""
    limit = int(request.args.get("limit", 50))
    history = db.get_vip_history(limit)

    total_pl = sum(h.get("sell_profit_loss", 0) or 0 for h in history)
    wins = sum(1 for h in history if (h.get("sell_profit_loss", 0) or 0) > 0)
    total = len(history)

    return jsonify({
        "history": history,
        "stats": {
            "total": total,
            "wins": wins,
            "losses": total - wins,
            "win_rate": round(wins / total * 100, 1) if total > 0 else 0,
            "total_profit": round(total_pl, 2),
        }
    })


def _generate_vip_suggestion(code: str, name: str, entry_price: float,
                             current_price: float, shares: int) -> dict:
    """生成VIP持仓AI建议"""
    change_pct = (current_price / entry_price - 1) * 100 if entry_price > 0 else 0
    suggestion = ""
    score = 50
    swap_sug = ""
    swap_code = ""
    swap_name = ""
    swap_reason = ""

    # 分析主力阶段
    try:
        force = main_force_analyzer.analyze(code)
        phase = force.get("phase", 0)
        confidence = force.get("confidence", 0)
        phase_name = force.get("phase_name", "")
        signals = force.get("signals", [])
    except:
        phase = 0
        confidence = 0
        phase_name = "无法分析"
        signals = []

    # 分析突破
    try:
        breakout = breakout_analyzer.analyze(code)
        breakout_status = breakout.get("status", "")
        breakout_signals = breakout.get("signals", [])
    except:
        breakout_status = ""
        breakout_signals = []

    # === 生成持仓建议 ===
    if change_pct <= -7:
        suggestion = f"⚠️ 触发止损线！当前亏损{change_pct:.1f}%，建议立即止损离场"
        score = 80
    elif phase >= 5:
        suggestion = f"⚠️ 主力进入{phase_name}，建议减仓或清仓"
        score = 75
    elif phase == 3 and confidence >= 60 and change_pct < 10:
        suggestion = f"✅ 主升浪刚启动，建议坚定持有，可适当加仓"
        score = 80
    elif phase == 4 and change_pct > 5:
        suggestion = f"📈 主升浪运行中，浮盈{change_pct:.1f}%，建议持有观察"
        score = 65
    elif phase == 2 and change_pct > -3:
        suggestion = f"⏳ 处于洗盘阶段，浮盈{change_pct:.1f}%，建议耐心等待突破"
        score = 55
    elif phase == 1:
        suggestion = f"🔍 处于建仓阶段，浮盈{change_pct:.1f}%，关注量能变化"
        score = 50
    elif phase == 6:
        suggestion = f"🚨 主力出货阶段！浮盈{change_pct:.1f}%，建议立即清仓"
        score = 85
    elif change_pct >= 15:
        suggestion = f"💰 浮盈{change_pct:.1f}%已达止盈区域，建议分批止盈"
        score = 70
    elif change_pct <= -3:
        suggestion = f"📉 浮亏{change_pct:.1f}%，注意止损风险，关注支撑位"
        score = 45
    else:
        suggestion = f"📊 当前浮盈{change_pct:.1f}%，{phase_name}，建议持有观察"
        score = 55

    # === 生成换股建议 ===
    # 如果主力进入末期/出货，且买入池中有更优标的
    if phase >= 5:
        buy_pool = db.get_buy_pool()
        # 找同一板块或其他板块评分高的股票
        holding_sector = ""
        try:
            h = db.get_vip_holding_by_code(code)
            if h:
                holding_sector = h.get("sector", "")
        except:
            pass

        candidates = [s for s in buy_pool if s.get("code") != code]
        if candidates:
            best = max(candidates, key=lambda x: x.get("total_score", 0))
            if best.get("total_score", 0) >= 60:
                swap_sug = f"建议换入 {best['name']}({best['code']})"
                swap_code = best["code"]
                swap_name = best["name"]
                swap_reason = f"当前持仓主力进入{phase_name}，换入评分{best.get('total_score',0)}分的{best.get('name','')}，处于{best.get('phase','')}阶段"

    # 保存到数据库
    db.update_vip_suggestion(code, suggestion, score, swap_sug, swap_code, swap_name, swap_reason)

    return {
        "suggestion": suggestion,
        "score": score,
        "phase": phase,
        "phase_name": phase_name,
        "signals": signals[:3],
        "breakout_status": breakout_status,
        "breakout_signals": [s.get("description", "") for s in breakout_signals[:2]],
        "swap_suggestion": swap_sug,
        "swap_target_code": swap_code,
        "swap_target_name": swap_name,
        "swap_reason": swap_reason,
    }


# ==================== 双体系龙头选股 API ====================

@app.route("/api/leaders/screen")
def api_leader_screen():
    """龙头筛选 — 对当前买入池股票进行龙头分类"""
    pool = db.get_buy_pool()
    codes = [s["code"] for s in pool]

    hot_spots = db.get_hot_spots(1)

    value_leaders = leader_selector.screen_value_leaders(codes)
    sentiment_leaders = leader_selector.screen_sentiment_leaders(codes, hot_spots)

    # 更新数据库龙头标记
    for vl in value_leaders:
        db.update_vip_holding(vl["code"], {"leader_type": "value"})

    for sl in sentiment_leaders:
        db.update_vip_holding(sl["code"], {"leader_type": "sentiment"})

    return jsonify({
        "value_leaders": value_leaders,
        "sentiment_leaders": sentiment_leaders,
        "value_count": len(value_leaders),
        "sentiment_count": len(sentiment_leaders),
    })


@app.route("/api/leaders/analyze_pool")
def api_leader_analyze_pool():
    """对买入池所有股票进行龙头分析打分"""
    pool = db.get_buy_pool()
    codes = [s["code"] for s in pool]
    hot_spots = db.get_hot_spots(1)

    results = []
    for code in codes:
        quotes = tencent_quote([code])
        q = quotes.get(code, {})
        name = q.get("name", "")
        price = q.get("price", 0)
        change = q.get("change_pct", 0)
        turnover = q.get("turnover_pct", 0)
        amount = q.get("amount_wan", 0) / 10000
        vol_ratio = q.get("vol_ratio", 0)
        mcap = q.get("mcap_yi", 0)
        pe = q.get("pe_ttm", 0)

        # 判断龙头类型
        is_sentiment = (change >= 4 and 5 <= turnover <= 25 and amount > 1)
        is_value = (mcap > 100 and pe > 0 and pe < 80 and amount > 3)

        leader_type = "none"
        if is_sentiment and is_value:
            leader_type = "value" if mcap > 500 else "sentiment"
        elif is_sentiment:
            leader_type = "sentiment"
        elif is_value:
            leader_type = "value"

        # 避坑检查
        pitfall = leader_selector.is_pitfall_stock(code)

        results.append({
            "code": code,
            "name": name,
            "price": price,
            "change_pct": change,
            "turnover_pct": turnover,
            "amount_yi": round(amount, 1),
            "vol_ratio": vol_ratio,
            "mcap_yi": mcap,
            "pe_ttm": pe,
            "leader_type": leader_type,
            "leader_label": {"value": "中线价值龙头", "sentiment": "短线情绪龙头", "none": "待分类"}.get(leader_type, ""),
            "pitfall": pitfall,
        })

    # 按龙头类型排序
    results.sort(key=lambda x: ({"sentiment": 0, "value": 1, "none": 2}.get(x["leader_type"], 2),
                                 -(x.get("change_pct", 0) or 0)))

    return jsonify({
        "results": results,
        "value_count": sum(1 for r in results if r["leader_type"] == "value"),
        "sentiment_count": sum(1 for r in results if r["leader_type"] == "sentiment"),
        "strategy_note": {
            "allocation": "7成中线价值 + 3成短线情绪",
            "value_hold": "1-12个月，分批低吸",
            "sentiment_hold": "1-10天，严格止损",
        },
    })


@app.route("/api/leaders/daily_checklist")
def api_daily_checklist():
    """每日复盘执行清单"""
    checklist = leader_selector.daily_review_checklist()
    return jsonify(checklist)


@app.route("/api/leaders/pitfall_check")
def api_pitfall_check():
    """避坑检查"""
    code = request.args.get("code", "")
    if not code:
        return jsonify({"error": "缺少代码"}), 400
    result = leader_selector.is_pitfall_stock(code)
    return jsonify(result)


# ==================== TDX数据缓存 API ====================

@app.route("/api/tdx/cache", methods=["POST"])
def api_tdx_cache():
    """接收TDX实时数据并缓存"""
    data = request.json or {}
    code = data.get("code", "")
    tdx_data = data.get("data", {})
    if not code or not tdx_data:
        return jsonify({"error": "缺少code或data"}), 400
    success = db.save_tdx_quote(code, tdx_data)
    return jsonify({"success": success})


@app.route("/api/tdx/quote")
def api_tdx_quote():
    """获取TDX缓存行情（含5档盘口）"""
    code = request.args.get("code", "")
    if not code:
        return jsonify({"error": "缺少code"}), 400
    cached = db.get_tdx_quote(code)
    cache_age = db.get_tdx_cache_age(code)
    return jsonify({"code": code, "cached": cached, "cache_age_sec": cache_age})


# ==================== 突发事件 API ====================

@app.route("/api/events")
def api_breaking_events():
    """获取近期突发事件"""
    days = int(request.args.get("days", 7))
    events = breaking_events.get_recent_events(days=days, limit=30)
    severity_stats = breaking_events.get_events_by_severity()
    pool_impact = breaking_events.analyze_pool_impact()
    return jsonify({
        "events": events,
        "severity_stats": severity_stats,
        "pool_impact": pool_impact,
        "total": len(events),
    })


@app.route("/api/events/add", methods=["POST"])
def api_add_event():
    """手动添加突发事件"""
    data = request.json or {}
    if not data.get("title"):
        return jsonify({"error": "缺少标题"}), 400
    event_id = breaking_events.add_event(data)
    return jsonify({"success": True, "id": event_id})


# ==================== 同花顺同步 API ====================

@app.route("/api/ths/sync")
def api_ths_sync():
    """同步同花顺自选股到平台"""
    result = sync_ths_to_pool(db)
    return jsonify(result)


@app.route("/api/ths/pool")
def api_ths_pool():
    """获取同花顺同步池"""
    pool = db.get_pool_by_type("ths_sync")
    return jsonify({"pool": pool, "count": len(pool)})


@app.route("/api/pool/quick_add", methods=["POST"])
def api_quick_add():
    """从同花顺池快速加入买入池"""
    data = request.json or {}
    code = data.get("code", "")
    if not code:
        return jsonify({"error": "缺少code"}), 400

    # 从同花顺池找到该股
    ths_pool = db.get_pool_by_type("ths_sync")
    stock = next((s for s in ths_pool if s.get("code") == code), None)
    if not stock:
        quotes = tencent_quote([code])
        q = quotes.get(code, {})
        stock = {"code": code, "name": q.get("name", code), "entry_price": q.get("price", 0)}

    conn = get_connection()
    try:
        conn.execute("""INSERT OR REPLACE INTO stock_pool
            (code, name, sector, entry_price, entry_date, pool_type, phase,
             total_score, main_force_phase, risk_score, updated_at)
            VALUES (?,?,?,?,date('now','localtime'),'buy','early',50,3,30,datetime('now','localtime'))""",
            (code, stock.get("name", code), stock.get("sector", "自选"), stock.get("entry_price", 0)))
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        conn.close()


# ==================== 模拟交易 API ====================

@app.route("/api/sim/pick")
def api_sim_pick():
    """今日自动选股模拟买入（1 early + 1 mid）"""
    result = sim_trader.daily_pick_and_buy()
    return jsonify(result)


@app.route("/api/sim/check")
def api_sim_check():
    """检查持仓止盈止损"""
    result = sim_trader.check_holding_trades()
    return jsonify(result)


@app.route("/api/sim/trades")
def api_sim_trades():
    """获取模拟交易记录"""
    days = int(request.args.get("days", 90))
    data = sim_trader.get_sim_trades(days)
    return jsonify(data)


@app.route("/api/sim/manual_sell", methods=["POST"])
def api_sim_manual_sell():
    """手动卖出模拟持仓"""
    data = request.json or {}
    code = data.get("code", "")
    if not code:
        return jsonify({"error": "缺少code"}), 400

    quotes = tencent_quote([code])
    price = quotes.get(code, {}).get("price", 0)
    if not price:
        return jsonify({"error": "获取价格失败"}), 400

    conn = get_connection()
    try:
        h = conn.execute(
            "SELECT * FROM sim_trades WHERE code=? AND status='holding'", (code,)
        ).fetchone()
        if not h:
            return jsonify({"error": "未找到该持仓"}), 400

        hd = dict(h)
        pl = round(price * hd['shares'] - hd['amount'], 2)
        pl_pct = round((price / hd['buy_price'] - 1) * 100, 2)
        hold_days = (date.today() - datetime.strptime(hd['trade_date'], '%Y-%m-%d').date()).days

        conn.execute("""
            UPDATE sim_trades SET status='sold', sell_price=?, sell_date=?,
            sell_time=?, profit_loss=?, profit_loss_pct=?, sell_reason='manual',
            hold_days=?, updated_at=datetime('now','localtime')
            WHERE id=?
        """, (price, date.today().isoformat(), datetime.now().strftime('%H:%M'),
             pl, pl_pct, hd['id']))
        conn.commit()
        return jsonify({"success": True, "sell_price": price, "profit_pct": pl_pct})
    finally:
        conn.close()


# ==================== 启动 ====================

if __name__ == "__main__":
    print("=" * 60)
    print("  A股操盘平台 v1.0")
    print("  热点波段操作 + 主力分析 + 风控系统")
    print("  访问地址: http://127.0.0.1:5000")
    print("=" * 60)
    app.run(host="0.0.0.0", port=5000, debug=True)
