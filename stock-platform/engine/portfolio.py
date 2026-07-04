"""
操盘平台 - 投资组合管理引擎
"""
from datetime import date, datetime
from engine.data_fetcher import tencent_quote, get_fund_flow_120d
from engine.main_force import MainForceAnalyzer
from engine.risk_control import RiskController

class PortfolioManager:
    """投资组合管理器"""

    def __init__(self, db_manager):
        self.db = db_manager
        self.main_force = MainForceAnalyzer()
        self.risk = RiskController(db_manager)

    def monitor_holdings(self) -> dict:
        """监控持仓股票状态"""
        holdings = self.db.get_active_holdings()
        alerts = []
        updates = []

        for holding in holdings:
            code = holding.get("code", "")
            entry_price = holding.get("buy_price", 0)
            shares = holding.get("shares", 0)

            if not code or not entry_price:
                continue

            try:
                quote = tencent_quote([code])
                if code not in quote:
                    continue

                q = quote[code]
                current_price = q.get("price", 0)
                change_pct = q.get("change_pct", 0)

                # 止损止盈检查
                stop_check = self.risk.check_stop_loss(
                    code, entry_price, current_price,
                    highest_price=holding.get("max_price")
                )

                if stop_check["has_signal"]:
                    for signal in stop_check["signals"]:
                        alerts.append({
                            "code": code,
                            "name": q.get("name", ""),
                            "type": signal["type"],
                            "reason": signal["reason"],
                            "current_price": current_price,
                            "entry_price": entry_price,
                            "change_pct": stop_check["change_pct"],
                            "action": "卖出",
                        })

                        # 记录卖出信号
                        self.db.add_sell_signal({
                            "code": code,
                            "name": q.get("name", ""),
                            "signal_date": date.today().isoformat(),
                            "signal_type": signal["type"],
                            "signal_strength": signal["strength"],
                            "price_at_signal": current_price,
                            "reason": signal["reason"],
                        })

                # 主力阶段更新
                force_result = self.main_force.analyze(code)
                phase = force_result["phase"]

                update_info = {
                    "code": code,
                    "name": q.get("name", ""),
                    "current_price": current_price,
                    "entry_price": entry_price,
                    "change_pct": round((current_price / entry_price - 1) * 100, 2),
                    "main_force_phase": phase,
                    "phase_name": force_result["phase_name"],
                    "risk_level": "high" if phase >= 5 else "low" if phase <= 2 else "medium",
                }

                # 主力末期/出货预警
                if phase >= 5:
                    alerts.append({
                        "code": code,
                        "name": q.get("name", ""),
                        "type": "main_force_warning",
                        "reason": f"主力进入{force_result['phase_name']}，建议减仓",
                        "current_price": current_price,
                        "entry_price": entry_price,
                        "change_pct": update_info["change_pct"],
                        "action": "减仓/清仓",
                    })

                updates.append(update_info)

            except Exception as e:
                print(f"监控{code}失败: {e}")

        return {
            "holdings": updates,
            "alerts": alerts,
            "alert_count": len(alerts),
            "status": "warning" if alerts else "normal",
        }

    def optimize_pool(self) -> dict:
        """优化股票池"""
        pool = self.db.get_pool()
        changes = []

        for stock in pool:
            code = stock.get("code", "")
            try:
                force_result = self.main_force.analyze(code)
                phase = force_result["phase"]

                current_phase = stock.get("phase", "")
                new_phase = None

                # 阶段升级
                if current_phase == "early" and phase >= 4:
                    new_phase = "mid"
                    changes.append({
                        "code": code,
                        "name": stock.get("name", ""),
                        "change": f"阶段升级: early -> mid",
                        "reason": "主升浪确认进入中期",
                    })

                # 阶段降级（移除预警）
                elif phase >= 5:
                    changes.append({
                        "code": code,
                        "name": stock.get("name", ""),
                        "change": "移除预警",
                        "reason": f"主力进入{force_result['phase_name']}",
                    })
                    self.db.remove_from_pool(code, f"主力进入{force_result['phase_name']}")

                # 更新阶段
                if new_phase:
                    self.db.update_stock_phase(code, new_phase, phase)
                else:
                    self.db.update_stock_phase(code, current_phase, phase)

            except Exception as e:
                print(f"优化{code}失败: {e}")

        return {
            "changes": changes,
            "change_count": len(changes),
            "pool_stats": self.db.get_pool_stats(),
        }

    def get_portfolio_performance(self) -> dict:
        """获取组合表现"""
        trades = self.db.get_trades(100)
        stats = self.db.get_trade_stats()
        holdings = self.db.get_active_holdings()

        # 计算当前持仓浮盈
        current_holdings_value = 0
        current_cost = 0
        for h in holdings:
            try:
                quote = tencent_quote([h.get("code", "")])
                if h.get("code") in quote:
                    q = quote[h["code"]]
                    current_price = q.get("price", 0)
                    shares = h.get("shares", 0)
                    current_holdings_value += current_price * shares
                    current_cost += h.get("buy_price", 0) * shares
            except:
                pass

        floating_pl = current_holdings_value - current_cost
        floating_pl_pct = (floating_pl / current_cost * 100) if current_cost > 0 else 0

        # 计算月度表现
        monthly = self._calc_monthly_performance(trades)

        return {
            "stats": stats,
            "holdings_count": len(holdings),
            "current_holdings_value": round(current_holdings_value, 2),
            "floating_pl": round(floating_pl, 2),
            "floating_pl_pct": round(floating_pl_pct, 2),
            "monthly_performance": monthly,
        }

    def _calc_monthly_performance(self, trades: list) -> list:
        """计算月度表现"""
        monthly = {}
        for t in trades:
            if t.get("sell_date"):
                month = t["sell_date"][:7]
                if month not in monthly:
                    monthly[month] = {"profit": 0, "trades": 0, "wins": 0}
                monthly[month]["profit"] += t.get("profit_loss", 0)
                monthly[month]["trades"] += 1
                if t.get("profit_loss", 0) > 0:
                    monthly[month]["wins"] += 1

        result = []
        for month in sorted(monthly.keys(), reverse=True):
            m = monthly[month]
            result.append({
                "month": month,
                "profit": round(m["profit"], 2),
                "trades": m["trades"],
                "win_rate": round(m["wins"] / m["trades"] * 100, 1) if m["trades"] > 0 else 0,
            })

        return result

    def generate_report(self) -> dict:
        """生成持仓分析报告"""
        holdings = self.db.get_active_holdings()
        report = []

        for h in holdings:
            code = h.get("code", "")
            try:
                quote = tencent_quote([code])
                force = self.main_force.analyze(code)

                q = quote.get(code, {})
                current_price = q.get("price", 0)

                report.append({
                    "code": code,
                    "name": q.get("name", ""),
                    "entry_price": h.get("buy_price", 0),
                    "current_price": current_price,
                    "change_pct": round((current_price / h.get("buy_price", 0) - 1) * 100, 2) if h.get("buy_price") else 0,
                    "main_force_phase": force["phase"],
                    "phase_name": force["phase_name"],
                    "suggestion": self._get_suggestion(force["phase"]),
                })
            except:
                pass

        return {
            "date": date.today().isoformat(),
            "holdings": report,
            "suggestions": self._generate_suggestions(report),
        }

    def _get_suggestion(self, phase: int) -> str:
        """根据主力阶段给出建议"""
        suggestions = {
            1: "建仓期 → 可分批建仓",
            2: "洗盘期 → 等待突破确认后加仓",
            3: "主升浪启动 → 加仓或持有",
            4: "主升浪中期 → 坚定持有",
            5: "主升浪末期 → 逐步减仓",
            6: "出货期 → 清仓离场",
        }
        return suggestions.get(phase, "观望")

    def _generate_suggestions(self, report: list) -> list:
        """生成综合建议"""
        suggestions = []

        # 需加仓的
        add_position = [r for r in report if r.get("main_force_phase", 0) in [1, 3]]
        if add_position:
            suggestions.append(f"建议加仓标的: {', '.join(r['name'] for r in add_position[:3])}")

        # 需减仓的
        reduce = [r for r in report if r.get("main_force_phase", 0) in [5, 6]]
        if reduce:
            suggestions.append(f"建议减仓标的: {', '.join(r['name'] for r in reduce[:3])}")

        return suggestions
