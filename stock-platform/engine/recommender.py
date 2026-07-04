"""
操盘平台 - 每日推荐引擎（含集合竞价抢筹分析）
盘前9:30快速选出TOP 2
"""
from datetime import date
from config import DAILY_RECOMMEND_COUNT
from engine.data_fetcher import tencent_quote

class DailyRecommender:
    """每日推荐引擎"""

    def __init__(self, db_manager):
        self.db = db_manager

    def generate_recommendations(self) -> dict:
        """快速生成每日推荐（含竞价抢筹分析）"""
        today = date.today().isoformat()
        pool = self.db.get_buy_pool()

        if not pool:
            return {"date": today, "recommendations": [], "message": "股票池为空"}

        # 批量获取行情
        codes = [s["code"] for s in pool]
        quotes = tencent_quote(codes)

        # 获取TDX竞价位数据缓存
        auction_data = self._load_auction_cache(codes)

        # 评分排序
        scored = []
        auction_summary = {"抢筹": 0, "高开": 0, "低开": 0, "平盘": 0}

        for stock in pool:
            code = stock.get("code", "")
            q = quotes.get(code, {})
            price = q.get("price") or stock.get("entry_price") or 0

            change_pct = q.get("change_pct", 0)
            vol_ratio = q.get("vol_ratio", 0)
            turnover = q.get("turnover_pct", 0)
            last_close = q.get("last_close", 0)

            # === 集合竞价抢筹分析 ===
            auc = auction_data.get(code, {})
            auc_score, auc_signal = self._analyze_auction_bid(price, last_close, vol_ratio, change_pct, auc)

            # 竞价统计
            if "抢筹" in auc_signal:
                auction_summary["抢筹"] += 1
            elif change_pct > 0.5:
                auction_summary["高开"] += 1
            elif change_pct < -0.5:
                auction_summary["低开"] += 1
            else:
                auction_summary["平盘"] += 1

            # 综合评分
            base_score = (stock.get("total_score") or 50)
            phase_bonus = 10 if stock.get("phase") == "early" else 5
            vol_bonus = min(10, (vol_ratio or 0) * 2)
            change_bonus = min(10, abs(change_pct or 0) * 2)
            score = base_score + phase_bonus + vol_bonus + change_bonus + auc_score

            scored.append({
                "code": code,
                "name": stock.get("name", ""),
                "price": price,
                "change_pct": change_pct,
                "vol_ratio": vol_ratio,
                "phase": stock.get("phase", ""),
                "total_score": round(score, 1),
                "main_force_phase": stock.get("main_force_phase", 0),
                "fund_flow_20d": stock.get("fund_flow_20d", 0),
                "auction_signal": auc_signal,
                "confidence": "high" if score >= 65 else ("medium" if score >= 55 else "low"),
            })

        scored.sort(key=lambda x: x["total_score"], reverse=True)
        recommendations = scored[:DAILY_RECOMMEND_COUNT]

        # 计算买卖点
        for rec in recommendations:
            price = rec.get("price") or 0
            if not price:
                rec["buy_sell_points"] = {"error": "无有效价格数据"}
                rec["reason"] = "价格数据缺失"
                rec["technical_signals"] = "数据异常"
                rec["fund_flow_signal"] = "数据异常"
                rec["hot_topic_support"] = ""
                continue
            rec["buy_sell_points"] = {
                "suggested_buy_price": round(price * 0.995, 2),
                "stop_loss_price": round(price * 0.93, 2),
                "take_profit_price": round(price * 1.20, 2),
                "buy_zone": f"{round(price * 0.98, 2)} - {round(price * 1.01, 2)}",
            }
            # 构建详细原因
            parts = []
            if rec["phase"] == "early":
                parts.append("主升浪启动阶段")
            else:
                parts.append("主升浪运行中")
            parts.append(f"评分{rec['total_score']:.0f}分")
            if (rec.get("fund_flow_20d") or 0) > 0:
                parts.append(f"近20日主力净流入{(rec.get('fund_flow_20d') or 0):.1f}亿")
            rec["reason"] = "；".join(parts)
            # 保持评分阶段的竞价信号（不覆盖）
            rec["technical_signals"] = "多头排列" if (rec.get("main_force_phase") or 0) >= 3 else "蓄势中"
            rec["fund_flow_signal"] = "净流入" if (rec.get("fund_flow_20d") or 0) > 0 else "持平"
            rec["hot_topic_support"] = rec.get("phase", "")

        # 保存
        from datetime import datetime as dt
        now_time = dt.now().strftime('%H:%M')
        saved = []
        for rec in recommendations:
            bsp = rec.get("buy_sell_points", {})
            rec_id = self.db.add_recommendation({
                "date": today,
                "code": rec["code"],
                "name": rec["name"],
                "reason": rec.get("reason", ""),
                "buy_price": bsp.get("suggested_buy_price"),
                "recommend_price": rec.get("price", 0),
                "stop_loss_price": bsp.get("stop_loss_price"),
                "take_profit_price": bsp.get("take_profit_price"),
                "confidence": rec.get("confidence", "medium"),
                "auction_analysis": rec.get("auction_signal", ""),
                "technical_signals": rec.get("technical_signals", ""),
                "fund_flow_signal": rec.get("fund_flow_signal", ""),
                "hot_topic_support": rec.get("hot_topic_support", ""),
            })
            rec["recommendation_id"] = rec_id
            saved.append(rec)

        return {
            "date": today,
            "time": now_time,
            "recommendations": saved,
            "auction_summary": self._format_auction_summary(auction_summary),
            "disclaimer": "以上为AI系统分析建议，不构成投资建议。",
        }

    def _load_auction_cache(self, codes: list) -> dict:
        """从TDX缓存加载竞价位数据"""
        try:
            from database.models import get_connection
            conn = get_connection()
            result = {}
            for code in codes:
                row = conn.execute(
                    "SELECT bsp_data, price, change_pct FROM tdx_cache WHERE code=? ORDER BY fetch_time DESC LIMIT 1",
                    (code,)
                ).fetchone()
                if row:
                    import json
                    bsp = json.loads(row[0]) if row[0] else []
                    result[code] = {"bsp": bsp, "price": row[1], "change_pct": row[2]}
            conn.close()
            return result
        except Exception:
            return {}

    def _analyze_auction_bid(self, price, last_close, vol_ratio, change_pct, tdx_cache) -> tuple:
        """分析集合竞价抢筹信号
        
        抢筹条件:
        1. 竞价量比 > 2 (集合竞价成交量显著放大)
        2. 竞价涨幅 > 0.5% (小幅高开，不是跳空透支)  
        3. 买盘深度 > 卖盘深度 (BspInfo中买量之和 > 卖量之和)
        4. 竞价形态: 9:20-9:25价格上翘 (近似用高开+日内高位判断)
        
        返回: (加分值, 信号文字)
        """
        signal_parts = []

        # 1. 量比检查
        if (vol_ratio or 0) >= 3:
            signal_parts.append("竞价量比" + str(round(vol_ratio, 1)) + "倍放量")
        elif (vol_ratio or 0) >= 2:
            signal_parts.append("竞价放量(" + str(round(vol_ratio, 1)) + "倍)")

        # 2. 涨幅检查
        if price and last_close:
            gap = round((price / last_close - 1) * 100, 2)
            if 0.3 <= gap <= 3:
                signal_parts.append("小幅高开" + ("+" if gap > 0 else "") + str(gap) + "%")
            elif gap > 3:
                signal_parts.append("大幅高开" + str(gap) + "%")
            elif gap < -1:
                signal_parts.append("低开" + str(gap) + "%")

        # 3. 盘口买卖力量对比
        bsp = tdx_cache.get("bsp", [])
        if bsp:
            total_buy = sum(int(b.get("BuyV", 0) or 0) for b in bsp)
            total_sell = sum(int(b.get("SellV", 0) or 0) for b in bsp)
            if total_buy > total_sell * 2:
                signal_parts.append("买盘深度碾压卖盘(买" + str(total_buy) + "vs卖" + str(total_sell) + ")")

        # 判定抢筹等级
        score = 0
        has_vol = (vol_ratio or 0) >= 2
        has_gap = price and last_close and 0.3 <= (price / last_close - 1) * 100 <= 3
        has_bid = bsp and total_buy > total_sell * 1.5

        if has_vol and has_gap and has_bid:
            score = 15
            signal_parts.insert(0, "🔥 集合竞价抢筹")
        elif has_vol and has_gap:
            score = 8
            signal_parts.insert(0, "📈 竞价积极")
        elif has_vol:
            score = 3
            signal_parts.insert(0, "竞价放量")

        signal = "；".join(signal_parts) if signal_parts else "竞价平盘"
        return score, signal

    def _format_auction_summary(self, stats: dict) -> str:
        """格式化竞价汇总"""
        parts = []
        if stats.get("抢筹", 0) > 0:
            parts.append(f"{stats['抢筹']}只抢筹")
        parts.append(f"{stats.get('高开',0)}高开")
        parts.append(f"{stats.get('低开',0)}低开")
        parts.append(f"{stats.get('平盘',0)}平盘")
        return "集合竞价: " + " | ".join(parts)
