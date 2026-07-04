"""
操盘平台 - 风险控制系统
仓位管理、止损止盈、外部环境预警、突发事件应对
"""
from datetime import date, datetime
from config import (
    MAX_SINGLE_POSITION, MAX_TOTAL_POSITION,
    STOP_LOSS_RATIO, TAKE_PROFIT_RATIO, TRAILING_STOP_RATIO,
    VIX_WARNING, NORTHBOUND_OUTFLOW_WARN, INDEX_DROP_WARN
)
from engine.data_fetcher import get_index_data, get_global_news

class RiskController:
    """风险控制器"""

    def __init__(self, db_manager):
        self.db = db_manager

    def check_environment(self) -> dict:
        """检查外部环境风险"""
        alerts = []
        risk_level = "low"

        # 1. 大盘指数风险
        indices = get_index_data()
        sh = indices.get("sh", {})
        sz = indices.get("sz", {})
        cyb = indices.get("cyb", {})

        sh_change = sh.get("change_pct", 0)
        sz_change = sz.get("change_pct", 0)
        cyb_change = cyb.get("change_pct", 0)

        if sh_change < INDEX_DROP_WARN or sz_change < INDEX_DROP_WARN:
            risk_level = "high"
            alerts.append({
                "type": "index_drop",
                "level": "critical",
                "message": f"大盘指数大幅下跌! 上证{sh_change:.2%} 深证{sz_change:.2%}",
            })
        elif sh_change < -0.01 or sz_change < -0.01:
            risk_level = "medium"
            alerts.append({
                "type": "index_drop",
                "level": "warning",
                "message": f"大盘指数下跌，注意风险控制",
            })

        # 2. 市场情绪分析
        sentiment = self._analyze_sentiment(indices)

        # 3. 突发事件检测
        events = self._detect_events()

        # 4. 整体仓位风险
        position_risk = self._check_position_risk()

        # 综合风险评分
        risk_score = self._calc_risk_score(alerts, sentiment, position_risk)

        result = {
            "date": date.today().isoformat(),
            "risk_level": risk_level,
            "risk_score": risk_score,
            "alerts": alerts,
            "sentiment": sentiment,
            "events": events,
            "position_risk": position_risk,
            "indices": {
                "sh": {"price": sh.get("price"), "change": sh_change},
                "sz": {"price": sz.get("price"), "change": sz_change},
                "cyb": {"price": cyb.get("price"), "change": cyb_change},
            },
        }

        # 保存市场环境
        self.db.add_market_env({
            "date": date.today().isoformat(),
            "sh_index": sh.get("price", 0),
            "sz_index": sz.get("price", 0),
            "cyb_index": cyb.get("price", 0),
            "market_sentiment": sentiment["status"],
            "northbound_flow": 0,
            "total_volume": 0,
            "up_count": 0,
            "down_count": 0,
            "limit_up_count": 0,
            "limit_down_count": 0,
            "vix_level": 0,
            "risk_warning": alerts,
            "event_impact": str(events[:3]) if events else "",
        })

        # 记录预警
        for alert in alerts:
            if alert["level"] == "critical":
                self.db.add_alert({
                    "alert_type": "risk",
                    "level": alert["level"],
                    "title": alert["message"][:50],
                    "description": alert["message"],
                    "affected_stocks": [],
                })

        return result

    def calc_position_size(self, total_capital: float, risk_per_trade: float = 0.02,
                          entry_price: float = 0, stop_loss_price: float = 0) -> dict:
        """计算仓位大小"""
        if entry_price <= 0:
            return {"shares": 0, "amount": 0, "position_pct": 0}

        # 基于风险百分比计算
        risk_amount = total_capital * risk_per_trade
        risk_per_share = abs(entry_price - stop_loss_price)
        position_by_risk = risk_amount / risk_per_share if risk_per_share > 0 else 0

        # 基于最大仓位限制
        max_position_amount = total_capital * MAX_SINGLE_POSITION
        position_by_limit = max_position_amount / entry_price

        # 取较小值
        shares = int(min(position_by_risk, position_by_limit))
        amount = shares * entry_price
        position_pct = amount / total_capital if total_capital > 0 else 0

        return {
            "shares": shares,
            "amount": round(amount, 2),
            "position_pct": round(position_pct, 4),
            "risk_amount": round(risk_amount, 2),
        }

    def check_stop_loss(self, code: str, entry_price: float, current_price: float,
                       highest_price: float = None) -> dict:
        """检查止损止盈条件"""
        change_pct = (current_price / entry_price - 1)

        signals = []

        # 固定止损
        if change_pct <= -STOP_LOSS_RATIO:
            signals.append({
                "type": "stop_loss",
                "strength": "strong",
                "reason": f"触发固定止损线(-{STOP_LOSS_RATIO*100}%)，当前亏损{change_pct*100:.1f}%"
            })

        # 固定止盈
        if change_pct >= TAKE_PROFIT_RATIO:
            signals.append({
                "type": "take_profit",
                "strength": "strong",
                "reason": f"触发固定止盈线(+{TAKE_PROFIT_RATIO*100}%)，当前盈利{change_pct*100:.1f}%"
            })

        # 移动止损
        if highest_price and highest_price > entry_price:
            trailing_stop = highest_price * (1 - TRAILING_STOP_RATIO)
            if current_price <= trailing_stop:
                max_profit = (highest_price / entry_price - 1)
                signals.append({
                    "type": "trailing_stop",
                    "strength": "medium",
                    "reason": f"触发移动止损(最高回撤{TRAILING_STOP_RATIO*100}%)，最大浮盈{max_profit*100:.1f}%"
                })

        return {
            "code": code,
            "current_price": current_price,
            "entry_price": entry_price,
            "change_pct": round(change_pct * 100, 2),
            "signals": signals,
            "has_signal": len(signals) > 0,
        }

    def check_position_risk_overall(self, holdings: list, total_capital: float) -> dict:
        """检查整体仓位风险"""
        total_position = sum(
            h.get("buy_price", 0) * h.get("shares", 0)
            for h in holdings if h.get("buy_price")
        )
        position_ratio = total_position / total_capital if total_capital > 0 else 0

        warnings = []
        if position_ratio > MAX_TOTAL_POSITION:
            warnings.append(f"总仓位{position_ratio*100:.0f}%超过上限{MAX_TOTAL_POSITION*100:.0f}%")
        if position_ratio > 0.7:
            warnings.append("仓位较重，建议控制风险")

        # 单只股票仓位检查
        for h in holdings:
            single_ratio = (h.get("buy_price", 0) * h.get("shares", 0)) / total_capital
            if single_ratio > MAX_SINGLE_POSITION:
                warnings.append(f"{h.get('name')}仓位{single_ratio*100:.0f}%超过单只上限")

        return {
            "total_position_ratio": round(position_ratio, 4),
            "total_position_amount": round(total_position, 2),
            "available_capital": round(total_capital - total_position, 2),
            "warnings": warnings,
            "status": "warning" if warnings else "normal",
        }

    def _analyze_sentiment(self, indices: dict) -> dict:
        """分析市场情绪"""
        sh_change = indices.get("sh", {}).get("change_pct", 0)
        sz_change = indices.get("sz", {}).get("change_pct", 0)

        avg_change = (sh_change + sz_change) / 2 if sh_change and sz_change else 0

        if avg_change > 0.02:
            status = "bullish"
        elif avg_change > 0:
            status = "slightly_bullish"
        elif avg_change > -0.01:
            status = "neutral"
        elif avg_change > -0.02:
            status = "slightly_bearish"
        else:
            status = "bearish"

        return {
            "status": status,
            "avg_change": round(avg_change, 4),
            "description": {
                "bullish": "市场情绪乐观，适合积极操作",
                "slightly_bullish": "市场偏暖，可适当参与",
                "neutral": "市场中性，精选个股",
                "slightly_bearish": "市场偏弱，控制仓位",
                "bearish": "市场恐慌，建议减仓观望",
            }.get(status, ""),
        }

    def _detect_events(self) -> list:
        """检测突发事件"""
        news = get_global_news(20)
        events = []
        risk_keywords = [
            "黑天鹅", "暴跌", "崩盘", "危机", "战争", "制裁", "加息",
            "降息", "贸易战", "脱钩", "疫情", "地震", "台海",
            "熔断", "退市", "暴雷", "违约"
        ]

        for n in news:
            title = n.get("title", "")
            for kw in risk_keywords:
                if kw in title:
                    events.append({
                        "type": "external_event",
                        "keyword": kw,
                        "title": title,
                        "time": n.get("time", ""),
                    })
                    break
            if len(events) >= 5:
                break

        return events

    def _calc_risk_score(self, alerts: list, sentiment: dict,
                        position_risk: dict) -> float:
        """计算综合风险评分(0-100, 越高越危险)"""
        score = 30  # 基础分

        # 预警贡献
        for alert in alerts:
            if alert["level"] == "critical":
                score += 25
            elif alert["level"] == "warning":
                score += 10

        # 情绪贡献
        sentiment_score = {
            "bullish": -10, "slightly_bullish": -5,
            "neutral": 0, "slightly_bearish": 10, "bearish": 25
        }
        score += sentiment_score.get(sentiment.get("status", ""), 0)

        # 仓位贡献
        if position_risk.get("warnings"):
            score += 15

        return min(100, max(0, score))

    def _check_position_risk(self) -> dict:
        """检查仓位风险"""
        holdings = self.db.get_active_holdings()
        warnings = []
        position_count = len(holdings)

        if position_count > 8:
            warnings.append("持仓数量过多，分散过度")
        if position_count == 0:
            warnings.append("空仓状态")

        return {"position_count": position_count, "warnings": warnings}
