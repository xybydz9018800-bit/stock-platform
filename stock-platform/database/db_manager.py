"""
操盘平台 - 数据库管理器
"""
import json
import sqlite3
from datetime import datetime, date
from database.models import get_connection, init_database
from typing import Optional

class DatabaseManager:
    def __init__(self):
        init_database()

    # ============================================================
    # 三层股票池操作: 买入池(buy) / 清仓池(liquidate) / 淘汰池(eliminated)
    # ============================================================
    
    def add_to_buy_pool(self, stock: dict) -> bool:
        """添加股票到买入池"""
        conn = get_connection()
        try:
            conn.execute("""
                INSERT OR REPLACE INTO stock_pool 
                (code, name, sector, sub_sector, market_cap, pe_ttm, pb,
                 pool_type, phase, main_wave_start_date, main_wave_gain, main_force_phase,
                 entry_price, entry_date, hot_topics, institution_rating, 
                 risk_score, total_score, volume_trend, fund_flow_20d, notes, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?, datetime('now','localtime'))
            """, (
                stock['code'], stock['name'], stock.get('sector'), stock.get('sub_sector'),
                stock.get('market_cap'), stock.get('pe_ttm'), stock.get('pb'),
                'buy', stock.get('phase', 'watch'), stock.get('main_wave_start_date'),
                stock.get('main_wave_gain', 0), stock.get('main_force_phase'),
                stock.get('entry_price'), stock.get('entry_date', date.today().isoformat()),
                json.dumps(stock.get('hot_topics', []), ensure_ascii=False),
                stock.get('institution_rating'), stock.get('risk_score'),
                stock.get('total_score', 0), stock.get('volume_trend'),
                stock.get('fund_flow_20d'), stock.get('notes')
            ))
            conn.commit()
            return True
        except Exception as e:
            print(f"添加股票到买入池失败: {e}")
            return False
        finally:
            conn.close()

    def get_buy_pool(self, phase: str = None) -> list:
        """获取买入池"""
        conn = get_connection()
        try:
            if phase:
                rows = conn.execute(
                    "SELECT * FROM stock_pool WHERE pool_type='buy' AND phase=? ORDER BY total_score DESC",
                    (phase,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM stock_pool WHERE pool_type='buy' ORDER BY phase, total_score DESC"
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_pool_by_type(self, pool_type: str) -> list:
        """按池类型获取股票"""
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM stock_pool WHERE pool_type=? ORDER BY total_score DESC",
                (pool_type,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_buy_pool_bottom(self, count: int = 3) -> list:
        """获取买入池中评分最低的几只股票（用于淘汰候选）"""
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM stock_pool WHERE pool_type='buy' ORDER BY total_score ASC LIMIT ?",
                (count,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_buy_pool_stats(self) -> dict:
        """获取买入池统计"""
        conn = get_connection()
        try:
            early = conn.execute(
                "SELECT COUNT(*) FROM stock_pool WHERE pool_type='buy' AND phase='early'"
            ).fetchone()[0]
            mid = conn.execute(
                "SELECT COUNT(*) FROM stock_pool WHERE pool_type='buy' AND phase='mid'"
            ).fetchone()[0]
            watch = conn.execute(
                "SELECT COUNT(*) FROM stock_pool WHERE pool_type='buy' AND phase='watch'"
            ).fetchone()[0]

            sectors = conn.execute("""
                SELECT sector, COUNT(*) as cnt FROM stock_pool 
                WHERE pool_type='buy' GROUP BY sector ORDER BY cnt DESC
            """).fetchall()

            avg_score = conn.execute(
                "SELECT AVG(total_score) FROM stock_pool WHERE pool_type='buy'"
            ).fetchone()[0]

            return {
                "early_count": early, "mid_count": mid, "watch_count": watch,
                "total": early + mid + watch,
                "avg_score": round(avg_score, 1) if avg_score else 0,
                "sectors": [{"name": s[0], "count": s[1]} for s in sectors]
            }
        finally:
            conn.close()

    def check_sector_limit_in_buy(self, sector: str) -> bool:
        """检查买入池中板块股票数量是否超限（同一板块≤3只）"""
        conn = get_connection()
        try:
            cnt = conn.execute(
                "SELECT COUNT(*) FROM stock_pool WHERE pool_type='buy' AND sector=?",
                (sector,)
            ).fetchone()[0]
            return cnt < 3
        finally:
            conn.close()

    def eliminate_from_buy_pool(self, code: str, reason: str, eliminated_price: float,
                                replaced_by_code: str = "", replaced_by_name: str = "") -> bool:
        """从买入池淘汰股票到淘汰池（记录完整追踪信息）"""
        conn = get_connection()
        try:
            today = date.today().isoformat()
            # 先获取当前评分
            row = conn.execute(
                "SELECT total_score FROM stock_pool WHERE code=? AND pool_type='buy'", (code,)
            ).fetchone()
            current_score = row[0] if row else 0

            conn.execute("""
                UPDATE stock_pool SET 
                    pool_type='eliminated',
                    eliminated_date=?,
                    eliminated_price=?,
                    eliminated_reason=?,
                    replaced_by_code=?,
                    replaced_by_name=?,
                    eliminated_total_score=?,
                    updated_at=datetime('now','localtime')
                WHERE code=? AND pool_type='buy'
            """, (today, eliminated_price, reason, replaced_by_code, replaced_by_name,
                 current_score, code))
            conn.commit()
            return True
        except Exception as e:
            print(f"淘汰股票失败: {e}")
            return False
        finally:
            conn.close()

    def move_to_liquidate_pool(self, code: str, reason: str, liquidate_price: float) -> bool:
        """从买入池移入清仓池"""
        conn = get_connection()
        try:
            today = date.today().isoformat()
            conn.execute("""
                UPDATE stock_pool SET 
                    pool_type='liquidate',
                    liquidate_date=?,
                    liquidate_price=?,
                    liquidate_reason=?,
                    updated_at=datetime('now','localtime')
                WHERE code=? AND pool_type='buy'
            """, (today, liquidate_price, reason, code))
            conn.commit()
            return True
        except Exception as e:
            print(f"移入清仓池失败: {e}")
            return False
        finally:
            conn.close()

    def liquidate_to_eliminated(self, code: str, reason: str = "") -> bool:
        """清仓池股票确认清仓后移入淘汰池"""
        conn = get_connection()
        try:
            today = date.today().isoformat()
            conn.execute("""
                UPDATE stock_pool SET 
                    pool_type='eliminated',
                    eliminated_date=?,
                    eliminated_reason=?,
                    updated_at=datetime('now','localtime')
                WHERE code=? AND pool_type='liquidate'
            """, (today, reason, code))
            conn.commit()
            return True
        except Exception as e:
            print(f"清仓确认失败: {e}")
            return False
        finally:
            conn.close()

    def get_liquidate_pool(self) -> list:
        """获取清仓池"""
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM stock_pool WHERE pool_type='liquidate' ORDER BY liquidate_date DESC"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_eliminated_pool(self, limit: int = 50) -> list:
        """获取淘汰池（含时间和价格标记，供策略优化参考）"""
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM stock_pool WHERE pool_type='eliminated' ORDER BY eliminated_date DESC LIMIT ?",
                (limit,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_eliminated_stats(self) -> dict:
        """获取淘汰池统计分析（用于策略优化）"""
        conn = get_connection()
        try:
            total = conn.execute(
                "SELECT COUNT(*) FROM stock_pool WHERE pool_type='eliminated'"
            ).fetchone()[0]
            
            # 淘汰原因分布
            reasons = conn.execute("""
                SELECT eliminated_reason, COUNT(*) as cnt 
                FROM stock_pool WHERE pool_type='eliminated' 
                GROUP BY eliminated_reason ORDER BY cnt DESC
            """).fetchall()

            # 复盘评价分布
            evals = conn.execute("""
                SELECT review_evaluation, COUNT(*) as cnt 
                FROM stock_pool WHERE pool_type='eliminated' AND review_evaluation IS NOT NULL
                GROUP BY review_evaluation
            """).fetchall()

            # 平均存活时间（淘汰日期-入选日期）
            avg_life = conn.execute("""
                SELECT AVG(julianday(eliminated_date) - julianday(entry_date))
                FROM stock_pool WHERE pool_type='eliminated' AND eliminated_date IS NOT NULL
            """).fetchone()[0] or 0

            # 淘汰时的平均评分
            avg_score = conn.execute("""
                SELECT AVG(eliminated_total_score) 
                FROM stock_pool WHERE pool_type='eliminated' AND eliminated_total_score IS NOT NULL
            """).fetchone()[0] or 0

            return {
                "total_eliminated": total,
                "avg_days_in_pool": round(avg_life, 1),
                "avg_eliminated_score": round(avg_score, 1),
                "eliminate_reasons": [{"reason": r[0], "count": r[1]} for r in reasons],
                "review_evaluations": [{"evaluation": r[0], "count": r[1]} for r in evals],
            }
        finally:
            conn.close()

    def update_eliminated_review(self, code: str, evaluation: str, notes: str = "") -> bool:
        """对淘汰股票进行复盘评价"""
        conn = get_connection()
        try:
            conn.execute("""
                UPDATE stock_pool SET 
                    review_evaluation=?,
                    review_notes=?,
                    updated_at=datetime('now','localtime')
                WHERE code=? AND pool_type='eliminated'
            """, (evaluation, notes, code))
            conn.commit()
            return True
        except Exception as e:
            print(f"复盘评价失败: {e}")
            return False
        finally:
            conn.close()

    def smart_eliminate_and_add(self, new_stock: dict, eliminate_bottom_n: int = 1) -> dict:
        """
        智能淘汰机制：新股票入池时，自动淘汰买入池中评分最低的N只股票
        返回淘汰和新增的详细信息
        """
        today = date.today().isoformat()
        result = {"added": None, "eliminated": []}

        # 1. 先添加新股票到买入池
        stock_code = new_stock['code']
        stock_price = new_stock.get('entry_price', 0)

        # 检查是否已在池中
        buy_pool = self.get_buy_pool()
        in_pool = any(s['code'] == stock_code for s in buy_pool)
        if in_pool:
            result["added"] = {"code": stock_code, "status": "already_in_pool"}
            return result

        # 2. 检查买入池是否已满（20只）
        total_in_buy = len(buy_pool)
        need_eliminate = total_in_buy >= 20

        if need_eliminate:
            # 3. 找出评分最低的N只
            bottom_stocks = self.get_buy_pool_bottom(eliminate_bottom_n)
            for bs in bottom_stocks:
                bs_code = bs['code']
                bs_name = bs['name']
                
                # 获取最新价格
                from engine.data_fetcher import tencent_quote
                quotes = tencent_quote([bs_code])
                elim_price = quotes.get(bs_code, {}).get('price', bs.get('entry_price', 0))
                
                reason = f"评分最低({bs.get('total_score',0)}分)，被{new_stock.get('name','')}({stock_code})替换"
                
                self.eliminate_from_buy_pool(
                    bs_code, reason, elim_price,
                    replaced_by_code=stock_code,
                    replaced_by_name=new_stock.get('name', '')
                )
                result["eliminated"].append({
                    "code": bs_code,
                    "name": bs_name,
                    "eliminated_price": elim_price,
                    "eliminated_score": bs.get('total_score', 0),
                    "reason": reason,
                })

        # 4. 添加新股票
        new_stock['entry_date'] = today
        new_stock['entry_price'] = stock_price
        self.add_to_buy_pool(new_stock)
        result["added"] = {
            "code": stock_code,
            "name": new_stock.get('name', ''),
            "score": new_stock.get('total_score', 0),
            "status": "added",
            "triggered_elimination": need_eliminate,
        }

        return result

    def get_all_pools_summary(self) -> dict:
        """获取三层池总览"""
        buy = self.get_buy_pool()
        liquidate = self.get_liquidate_pool()
        eliminated_stats = self.get_eliminated_stats()

        # 按阶段分组
        early = [s for s in buy if s.get('phase') == 'early']
        mid = [s for s in buy if s.get('phase') == 'mid']
        watch = [s for s in buy if s.get('phase') == 'watch']

        return {
            "buy_pool": {
                "total": len(buy),
                "early_count": len(early),
                "mid_count": len(mid),
                "watch_count": len(watch),
                "stocks": buy,
                "stats": self.get_buy_pool_stats(),
            },
            "liquidate_pool": {
                "total": len(liquidate),
                "stocks": liquidate,
            },
            "eliminated_pool": {
                "total": eliminated_stats["total_eliminated"],
                "stats": eliminated_stats,
            },
        }

    # 兼容旧接口
    def get_pool(self, phase: str = None) -> list:
        """获取买入池（兼容旧接口）"""
        return self.get_buy_pool(phase)

    def get_pool_stats(self) -> dict:
        """获取买入池统计（兼容旧接口）"""
        return self.get_buy_pool_stats()

    def check_sector_limit(self, sector: str) -> bool:
        """检查板块限制（兼容旧接口）"""
        return self.check_sector_limit_in_buy(sector)

    def add_to_pool(self, stock: dict) -> bool:
        """添加股票到买入池（兼容旧接口）"""
        return self.add_to_buy_pool(stock)

    def remove_from_pool(self, code: str, reason: str = ""):
        """从买入池淘汰（兼容旧接口）"""
        from engine.data_fetcher import tencent_quote
        quotes = tencent_quote([code])
        price = quotes.get(code, {}).get('price', 0)
        self.eliminate_from_buy_pool(code, reason, price)

    # ============================================================
    # 每日推荐操作（增强版：含追踪数据）
    # ============================================================
    def add_recommendation(self, rec: dict):
        """添加每日推荐（含推荐时间+推荐价格+原因+7天追踪字段）"""
        conn = get_connection()
        try:
            now_time = datetime.now().strftime('%H:%M')
            conn.execute("""
                INSERT INTO daily_recommendation 
                (date, recommend_time, code, name, reason, buy_price, recommend_price,
                 stop_loss_price, take_profit_price, confidence,
                 auction_analysis, technical_signals, fund_flow_signal, hot_topic_support)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                rec['date'], now_time, rec['code'], rec['name'], rec.get('reason'),
                rec.get('buy_price'), rec.get('recommend_price', rec.get('buy_price')),
                rec.get('stop_loss_price'), rec.get('take_profit_price'),
                rec.get('confidence', 'medium'), rec.get('auction_analysis'),
                rec.get('technical_signals'), rec.get('fund_flow_signal'),
                rec.get('hot_topic_support')
            ))
            conn.commit()
            return conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        finally:
            conn.close()

    def get_recommendations(self, trade_date: str = None, limit: int = 20) -> list:
        """获取推荐记录"""
        if trade_date is None:
            trade_date = date.today().isoformat()
        conn = get_connection()
        try:
            if trade_date:
                rows = conn.execute(
                    "SELECT * FROM daily_recommendation WHERE date=? ORDER BY created_at DESC",
                    (trade_date,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM daily_recommendation ORDER BY date DESC, created_at DESC LIMIT ?",
                    (limit,)
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_recommendation_tracking(self, rec_id: int, tracking_data: dict) -> bool:
        """更新推荐追踪数据（当日表现+7天收益）"""
        conn = get_connection()
        try:
            fields = []
            values = []
            field_map = {
                'intraday_high', 'intraday_low', 'intraday_close', 'intraday_gain_pct',
                'day1_gain', 'day2_gain', 'day3_gain', 'day4_gain', 'day5_gain',
                'day6_gain', 'day7_gain', 'max_gain_7d', 'max_loss_7d',
            }
            for k, v in tracking_data.items():
                if k in field_map:
                    fields.append(f"{k}=?")
                    values.append(v)
            fields.append("tracking_updated=datetime('now','localtime')")
            values.append(rec_id)
            sql = f"UPDATE daily_recommendation SET {', '.join(fields)} WHERE id=?"
            conn.execute(sql, values)
            conn.commit()
            return True
        finally:
            conn.close()

    def get_recommendations_needing_tracking(self, days: int = 7) -> list:
        """获取需要追踪的推荐（最近N天内、未被标记结束的）"""
        conn = get_connection()
        try:
            rows = conn.execute("""
                SELECT * FROM daily_recommendation 
                WHERE date >= date('now', ? || ' days')
                AND status != 'expired'
                ORDER BY date DESC
            """, (f'-{days}',)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_recommendation_status(self, rec_id: int, status: str):
        """更新推荐状态"""
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE daily_recommendation SET status=? WHERE id=?",
                (status, rec_id)
            )
            conn.commit()
        finally:
            conn.close()

    # ============================================================
    # 交易记录操作
    # ============================================================
    def add_trade(self, trade: dict) -> int:
        """添加交易记录"""
        conn = get_connection()
        try:
            conn.execute("""
                INSERT INTO trade_record 
                (recommendation_id, code, name, buy_date, buy_price, shares, 
                 sell_date, sell_price, profit_loss, profit_loss_pct, hold_days,
                 max_profit_pct, max_loss_pct, exit_reason, strategy_tag, review_notes)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                trade.get('recommendation_id'), trade['code'], trade['name'],
                trade.get('buy_date'), trade.get('buy_price'), trade.get('shares'),
                trade.get('sell_date'), trade.get('sell_price'),
                trade.get('profit_loss'), trade.get('profit_loss_pct'),
                trade.get('hold_days'), trade.get('max_profit_pct'),
                trade.get('max_loss_pct'), trade.get('exit_reason'),
                trade.get('strategy_tag'), trade.get('review_notes')
            ))
            conn.commit()
            return conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        finally:
            conn.close()

    def get_trades(self, limit: int = 50) -> list:
        """获取交易记录"""
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM trade_record ORDER BY buy_date DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_trade_stats(self) -> dict:
        """获取交易统计"""
        conn = get_connection()
        try:
            total = conn.execute("SELECT COUNT(*) FROM trade_record WHERE sell_date IS NOT NULL").fetchone()[0]
            wins = conn.execute(
                "SELECT COUNT(*) FROM trade_record WHERE sell_date IS NOT NULL AND profit_loss > 0"
            ).fetchone()[0]
            stats = conn.execute("""
                SELECT 
                    AVG(profit_loss_pct) as avg_pct,
                    MAX(profit_loss_pct) as max_pct,
                    MIN(profit_loss_pct) as min_pct,
                    AVG(hold_days) as avg_days,
                    SUM(profit_loss) as total_profit
                FROM trade_record WHERE sell_date IS NOT NULL
            """).fetchone()

            return {
                "total_trades": total,
                "wins": wins,
                "losses": total - wins,
                "win_rate": round(wins / total * 100, 1) if total > 0 else 0,
                "avg_profit_pct": round(stats[0], 2) if stats[0] else 0,
                "max_profit_pct": round(stats[1], 2) if stats[1] else 0,
                "max_loss_pct": round(stats[2], 2) if stats[2] else 0,
                "avg_hold_days": round(stats[3], 1) if stats[3] else 0,
                "total_profit": round(stats[4], 2) if stats[4] else 0,
            }
        finally:
            conn.close()

    def get_active_holdings(self) -> list:
        """获取当前持仓（已买未卖）"""
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM trade_record WHERE buy_date IS NOT NULL AND sell_date IS NULL ORDER BY buy_date"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ============================================================
    # 热点追踪操作
    # ============================================================
    def add_hot_spot(self, spot: dict):
        """添加热点记录"""
        conn = get_connection()
        try:
            conn.execute("""
                INSERT INTO hot_spot_tracker 
                (date, topic, heat_score, stock_count, leading_stocks, 
                 sector_index_change, fund_flow, news_count, sustainability, policy_support)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (
                spot['date'], spot['topic'], spot.get('heat_score'),
                spot.get('stock_count', 0), json.dumps(spot.get('leading_stocks', []), ensure_ascii=False),
                spot.get('sector_index_change'), spot.get('fund_flow'),
                spot.get('news_count', 0), spot.get('sustainability'),
                spot.get('policy_support')
            ))
            conn.commit()
        finally:
            conn.close()

    def get_hot_spots(self, days: int = 5) -> list:
        """获取近期热点"""
        conn = get_connection()
        try:
            rows = conn.execute("""
                SELECT * FROM hot_spot_tracker 
                WHERE date >= date('now', ? || ' days')
                ORDER BY date DESC, heat_score DESC
            """, (f'-{days}',)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ============================================================
    # 市场环境操作
    # ============================================================
    def add_market_env(self, env: dict):
        """添加市场环境记录"""
        conn = get_connection()
        try:
            conn.execute("""
                INSERT OR REPLACE INTO market_environment 
                (date, sh_index, sz_index, cyb_index, market_sentiment,
                 northbound_flow, total_volume, up_count, down_count,
                 limit_up_count, limit_down_count, vix_level, risk_warning, event_impact)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                env['date'], env.get('sh_index'), env.get('sz_index'),
                env.get('cyb_index'), env.get('market_sentiment'),
                env.get('northbound_flow'), env.get('total_volume'),
                env.get('up_count'), env.get('down_count'),
                env.get('limit_up_count'), env.get('limit_down_count'),
                env.get('vix_level'), json.dumps(env.get('risk_warning', []), ensure_ascii=False),
                env.get('event_impact')
            ))
            conn.commit()
        finally:
            conn.close()

    def get_latest_market_env(self) -> dict:
        """获取最新市场环境"""
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM market_environment ORDER BY date DESC LIMIT 1"
            ).fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()

    # ============================================================
    # 预警操作
    # ============================================================
    def add_alert(self, alert: dict):
        """添加预警"""
        conn = get_connection()
        try:
            conn.execute("""
                INSERT INTO alert_log (alert_type, level, title, description, affected_stocks)
                VALUES (?,?,?,?,?)
            """, (
                alert['alert_type'], alert['level'], alert['title'],
                alert['description'],
                json.dumps(alert.get('affected_stocks', []), ensure_ascii=False)
            ))
            conn.commit()
        finally:
            conn.close()

    def get_active_alerts(self) -> list:
        """获取活跃预警"""
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM alert_log WHERE resolved=0 ORDER BY alert_time DESC"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def resolve_alert(self, alert_id: int):
        """解决预警"""
        conn = get_connection()
        try:
            conn.execute("UPDATE alert_log SET resolved=1 WHERE id=?", (alert_id,))
            conn.commit()
        finally:
            conn.close()

    # ============================================================
    # 策略优化操作
    # ============================================================
    def add_strategy_log(self, log: dict):
        """添加策略优化记录"""
        conn = get_connection()
        try:
            conn.execute("""
                INSERT INTO strategy_log 
                (date, strategy_name, total_trades, win_rate, avg_profit, 
                 max_profit, max_loss, sharpe_ratio, max_drawdown, 
                 improvement_notes, params_snapshot)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (
                log['date'], log.get('strategy_name'), log.get('total_trades'),
                log.get('win_rate'), log.get('avg_profit'),
                log.get('max_profit'), log.get('max_loss'),
                log.get('sharpe_ratio'), log.get('max_drawdown'),
                log.get('improvement_notes'),
                json.dumps(log.get('params_snapshot', {}), ensure_ascii=False)
            ))
            conn.commit()
        finally:
            conn.close()

    # ============================================================
    # 卖出信号操作
    # ============================================================
    def add_sell_signal(self, signal: dict):
        """添加卖出信号"""
        conn = get_connection()
        try:
            conn.execute("""
                INSERT INTO sell_signal (code, name, signal_date, signal_type, 
                    signal_strength, price_at_signal, reason)
                VALUES (?,?,?,?,?,?,?)
            """, (
                signal['code'], signal['name'], signal['signal_date'],
                signal['signal_type'], signal.get('signal_strength'),
                signal.get('price_at_signal'), signal.get('reason')
            ))
            conn.commit()
        finally:
            conn.close()

    def get_pending_sell_signals(self) -> list:
        """获取待处理卖出信号"""
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM sell_signal WHERE action_taken='pending' ORDER BY signal_date DESC"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def mark_signal_action(self, signal_id: int, action: str):
        """标记信号已处理"""
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE sell_signal SET action_taken=? WHERE id=?", (action, signal_id)
            )
            conn.commit()
        finally:
            conn.close()

    # ============================================================
    # VIP持仓池操作
    # ============================================================
    def add_vip_holding(self, holding: dict) -> int:
        """添加VIP持仓"""
        conn = get_connection()
        try:
            entry_amount = holding['entry_price'] * holding['shares']
            today = date.today().isoformat()
            if 'entry_date' not in holding:
                holding['entry_date'] = today

            conn.execute("""
                INSERT INTO vip_holdings 
                (code, name, sector, entry_date, entry_price, shares, entry_amount,
                 stop_loss_price, take_profit_price, notes, status)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (
                holding['code'], holding['name'], holding.get('sector'),
                holding['entry_date'], holding['entry_price'], holding['shares'],
                entry_amount, holding.get('stop_loss_price'), holding.get('take_profit_price'),
                holding.get('notes'), 'holding'
            ))
            conn.commit()
            return conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        finally:
            conn.close()

    def get_vip_holdings(self, status: str = 'holding') -> list:
        """获取VIP持仓"""
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM vip_holdings WHERE status=? ORDER BY entry_date DESC",
                (status,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_vip_holding_by_code(self, code: str) -> dict:
        """获取单只VIP持仓"""
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM vip_holdings WHERE code=? AND status='holding'",
                (code,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_vip_prices(self, code: str, current_price: float) -> bool:
        """更新VIP持仓当前价格和盈亏"""
        conn = get_connection()
        try:
            holding = conn.execute(
                "SELECT * FROM vip_holdings WHERE code=? AND status='holding'", (code,)
            ).fetchone()
            if not holding:
                return False

            h = dict(holding)
            entry_price = h['entry_price']
            shares = h['shares']
            current_value = current_price * shares
            profit_loss = current_value - h['entry_amount']
            profit_loss_pct = (current_price / entry_price - 1) * 100 if entry_price > 0 else 0

            # 更新最高价
            max_price = h.get('max_price') or 0
            if current_price > max_price:
                max_price = current_price

            max_profit_pct = round((max_price / entry_price - 1) * 100, 2) if entry_price > 0 else 0

            # 计算持仓天数
            from datetime import datetime
            try:
                entry_dt = datetime.strptime(h['entry_date'], '%Y-%m-%d')
                hold_days = (datetime.now() - entry_dt).days
            except:
                hold_days = 0

            conn.execute("""
                UPDATE vip_holdings SET 
                    current_price=?, current_value=?, profit_loss=?, profit_loss_pct=?,
                    max_price=?, max_profit_pct=?, hold_days=?,
                    updated_at=datetime('now','localtime')
                WHERE code=? AND status='holding'
            """, (current_price, current_value, profit_loss, profit_loss_pct,
                 max_price, max_profit_pct, hold_days, code))
            conn.commit()
            return True
        except Exception as e:
            print(f"更新VIP价格失败: {e}")
            return False
        finally:
            conn.close()

    def update_vip_suggestion(self, code: str, suggestion: str, score: float,
                              swap_suggestion: str = "", swap_code: str = "",
                              swap_name: str = "", swap_reason: str = "") -> bool:
        """更新AI持仓建议和换股建议"""
        conn = get_connection()
        try:
            today = date.today().isoformat()
            conn.execute("""
                UPDATE vip_holdings SET 
                    ai_suggestion=?, ai_suggestion_score=?, ai_suggestion_time=?,
                    swap_suggestion=?, swap_target_code=?, swap_target_name=?, swap_reason=?,
                    updated_at=datetime('now','localtime')
                WHERE code=? AND status='holding'
            """, (suggestion, score, today, swap_suggestion, swap_code, swap_name,
                 swap_reason, code))
            conn.commit()
            return True
        finally:
            conn.close()

    def sell_vip_holding(self, code: str, sell_price: float, sell_date: str = None) -> bool:
        """卖出VIP持仓"""
        if sell_date is None:
            sell_date = date.today().isoformat()
        conn = get_connection()
        try:
            holding = conn.execute(
                "SELECT * FROM vip_holdings WHERE code=? AND status='holding'", (code,)
            ).fetchone()
            if not holding:
                return False

            h = dict(holding)
            sell_amount = sell_price * h['shares']
            sell_pl = sell_amount - h['entry_amount']
            sell_pl_pct = round((sell_price / h['entry_price'] - 1) * 100, 2) if h['entry_price'] > 0 else 0

            conn.execute("""
                UPDATE vip_holdings SET 
                    status='sold', sell_date=?, sell_price=?,
                    sell_profit_loss=?, sell_profit_loss_pct=?,
                    current_price=?, current_value=?,
                    updated_at=datetime('now','localtime')
                WHERE code=? AND status='holding'
            """, (sell_date, sell_price, sell_pl, sell_pl_pct, sell_price, sell_amount, code))
            conn.commit()
            return True
        finally:
            conn.close()

    def update_vip_holding(self, code: str, updates: dict) -> bool:
        """更新VIP持仓信息"""
        conn = get_connection()
        try:
            fields = []
            values = []
            for k, v in updates.items():
                fields.append(f"{k}=?")
                values.append(v)
            values.append(code)
            sql = f"UPDATE vip_holdings SET {', '.join(fields)}, updated_at=datetime('now','localtime') WHERE code=? AND status='holding'"
            conn.execute(sql, values)
            conn.commit()
            return True
        finally:
            conn.close()

    def get_vip_summary(self) -> dict:
        """VIP持仓总览统计"""
        conn = get_connection()
        try:
            holdings = conn.execute(
                "SELECT * FROM vip_holdings WHERE status='holding'"
            ).fetchall()

            total_cost = 0
            total_value = 0
            total_pl = 0
            count = len(holdings)

            for row in holdings:
                h = dict(row)
                total_cost += h.get('entry_amount', 0) or 0
                total_value += h.get('current_value', 0) or 0
                total_pl += h.get('profit_loss', 0) or 0

            total_pl_pct = round((total_value / total_cost - 1) * 100, 2) if total_cost > 0 else 0

            need_action = 0
            for row in holdings:
                h = dict(row)
                sug = h.get('ai_suggestion', '') or ''
                if any(w in sug for w in ['减仓', '清仓', '止盈', '止损', '换股']):
                    need_action += 1

            return {
                "total_holdings": count,
                "total_cost": round(total_cost, 2),
                "total_value": round(total_value, 2),
                "total_profit_loss": round(total_pl, 2),
                "total_profit_loss_pct": total_pl_pct,
                "need_action_count": need_action,
                "profit_count": sum(1 for row in holdings if (dict(row).get('profit_loss_pct', 0) or 0) > 0),
                "loss_count": sum(1 for row in holdings if (dict(row).get('profit_loss_pct', 0) or 0) < 0),
            }
        finally:
            conn.close()

    def get_vip_history(self, limit: int = 50) -> list:
        """获取VIP历史交易（已卖出）"""
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM vip_holdings WHERE status='sold' ORDER BY sell_date DESC LIMIT ?",
                (limit,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ============================================================
    # TDX缓存操作
    # ============================================================
    def save_tdx_quote(self, code: str, quote_data: dict) -> bool:
        """保存TDX实时行情到缓存"""
        conn = get_connection()
        try:
            bsp = quote_data.get("BspInfo", [])
            bsp_json = json.dumps(bsp, ensure_ascii=False) if bsp else "[]"

            hq = quote_data.get("HQInfo", {})
            ext = quote_data.get("ExtInfo", {})
            pro = quote_data.get("ProInfo", {})
            calc = quote_data.get("CalcInfo", {})
            base = quote_data.get("BaseInfo", {})

            conn.execute("""
                INSERT OR REPLACE INTO tdx_cache 
                (code, name, fetch_time, price, change_pct, open, high, low, last_close,
                 volume, amount, turnover_pct, vol_ratio, amplitude_pct,
                 pe_ttm, pb, mcap_yi, limit_up, limit_down, bsp_data,
                 fund_inout, fund_inout_hb, market_status, source)
                VALUES (?,?,datetime('now','localtime'),?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                code,
                base.get("Name", ""),
                hq.get("Now", 0),
                calc.get("CAZAF", 0),
                hq.get("Open", 0),
                hq.get("MaxP", 0),
                hq.get("MinP", 0),
                hq.get("Close", 0),
                hq.get("Volume", 0),
                hq.get("Amount", 0),
                hq.get("HSL", 0),
                hq.get("LB", 0),
                calc.get("CAZAF", 0) if abs(calc.get("CAZAF", 0) or 0) > abs(hq.get("HSL", 0) or 0) else 0,
                ext.get("SYL", 0),
                ext.get("MGSY", 0),
                ext.get("ZSZ", 0) / 1e8 if ext.get("ZSZ") else None,
                ext.get("ZTPrice", 0),
                ext.get("DTPrice", 0),
                bsp_json,
                pro.get("InOut", 0),
                pro.get("InOutHB", 0),
                base.get("OpenStatus", 0),
                "tdx",
            ))
            conn.commit()
            return True
        except Exception as e:
            print(f"保存TDX缓存失败: {e}")
            return False
        finally:
            conn.close()

    def get_tdx_quote(self, code: str) -> dict:
        """获取TDX缓存的行情数据"""
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM tdx_cache WHERE code=? ORDER BY fetch_time DESC LIMIT 1",
                (code,)
            ).fetchone()
            if not row:
                return {}
            d = dict(row)
            bsp = d.get("bsp_data", "[]")
            try:
                d["bsp"] = json.loads(bsp) if isinstance(bsp, str) else bsp
            except:
                d["bsp"] = []
            return d
        finally:
            conn.close()

    def get_tdx_quotes_batch(self, codes: list) -> dict:
        """批量获取TDX缓存行情"""
        conn = get_connection()
        try:
            result = {}
            for code in codes:
                row = conn.execute(
                    "SELECT * FROM tdx_cache WHERE code=? ORDER BY fetch_time DESC LIMIT 1",
                    (code,)
                ).fetchone()
                if row:
                    result[code] = dict(row)
                    bsp = result[code].get("bsp_data", "[]")
                    try:
                        result[code]["bsp"] = json.loads(bsp) if isinstance(bsp, str) else bsp
                    except:
                        result[code]["bsp"] = []
            return result
        finally:
            conn.close()

    def get_tdx_cache_age(self, code: str) -> int:
        """获取TDX缓存年龄（秒）"""
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT (julianday('now','localtime') - julianday(fetch_time)) * 86400 FROM tdx_cache WHERE code=? ORDER BY fetch_time DESC LIMIT 1",
                (code,)
            ).fetchone()
            return int(row[0]) if row and row[0] else 99999
        finally:
            conn.close()
