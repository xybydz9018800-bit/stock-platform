"""
操盘平台 - 真假突破判别引擎
识别真实突破 vs 假突破（诱多/诱空）
"""
from engine.data_fetcher import get_kline
from config import (
    BREAKOUT_VOLUME_RATIO, BREAKOUT_CONFIRM_DAYS,
    BREAKOUT_RETRACEMENT_MAX
)

class BreakoutAnalyzer:
    """真假突破判别器"""

    def analyze(self, code: str, klines: list = None) -> dict:
        """分析突破性质"""
        if klines is None:
            klines = get_kline(code, "day", 120)

        if len(klines) < 30:
            return {"code": code, "status": "insufficient_data", "signals": []}

        closes = [k["close"] for k in klines]
        highs = [k["high"] for k in klines]
        lows = [k["low"] for k in klines]
        opens = [k["open"] for k in klines]
        volumes = [k["volume"] for k in klines]
        dates = [k.get("date", "") for k in klines]

        signals = []

        # 1. 识别关键压力位和支撑位
        resistance = self._find_resistance(highs[-60:-5])
        support = self._find_support(lows[-60:-5])

        # 2. 检测最近突破
        breakout_signals = self._detect_breakout(
            closes, highs, lows, opens, volumes, dates, resistance, support
        )

        # 3. 判别真假突破
        for bs in breakout_signals:
            is_true = self._validate_breakout(
                bs, closes, volumes, resistance, support
            )
            bs["is_true_breakout"] = is_true["is_true"]
            bs["confidence"] = is_true["confidence"]
            bs["risk_flags"] = is_true["risk_flags"]
            signals.append(bs)

        # 4. 检测诱多诱空
        traps = self._detect_traps(closes, highs, lows, volumes, dates)
        for trap in traps:
            signals.append(trap)

        # 5. 综合判断
        status = self._overall_status(signals, closes)

        return {
            "code": code,
            "status": status,
            "resistance_levels": resistance,
            "support_levels": support,
            "signals": signals[:8],
            "current_price": closes[-1] if closes else 0,
            "recent_trend": self._trend_direction(closes[-10:]),
        }

    def _find_resistance(self, highs: list) -> list:
        """找关键压力位"""
        if len(highs) < 20:
            return []
        sorted_highs = sorted(set(round(h, 2) for h in highs), reverse=True)
        # 找出局部高点
        levels = []
        for i in range(1, len(sorted_highs) - 1):
            # 聚类相近的高点
            if not levels or abs(sorted_highs[i] - levels[-1]) / levels[-1] > 0.02:
                levels.append(sorted_highs[i])
                if len(levels) >= 3:
                    break
        return levels

    def _find_support(self, lows: list) -> list:
        """找关键支撑位"""
        if len(lows) < 20:
            return []
        sorted_lows = sorted(set(round(l, 2) for l in lows))
        levels = []
        for i in range(len(sorted_lows) - 1, 0, -1):
            if not levels or abs(sorted_lows[i] - levels[-1]) / levels[-1] > 0.02:
                levels.append(sorted_lows[i])
                if len(levels) >= 3:
                    break
        return levels

    def _detect_breakout(self, closes, highs, lows, opens, volumes, dates,
                         resistance, support) -> list:
        """检测突破信号"""
        signals = []
        avg_vol_20 = sum(volumes[-25:-5]) / 20 if len(volumes) >= 25 else volumes[-1]

        # 向上突破检测
        for r in resistance[:3]:
            for i in range(len(closes) - 5, len(closes)):
                if closes[i] > r and closes[i-1] <= r:
                    vol_ratio = volumes[i] / avg_vol_20 if avg_vol_20 > 0 else 1
                    signal_date = dates[i] if i < len(dates) else ""
                    signals.append({
                        "type": "up_breakout",
                        "level": r,
                        "date_index": i,
                        "date": signal_date,
                        "volume_ratio": round(vol_ratio, 2),
                        "price": closes[i],
                        "description": f"{signal_date} 突破压力位{r}元",
                    })

        # 向下突破检测
        for s in support[-3:]:
            for i in range(len(closes) - 5, len(closes)):
                if closes[i] < s and closes[i-1] >= s:
                    vol_ratio = volumes[i] / avg_vol_20 if avg_vol_20 > 0 else 1
                    signal_date = dates[i] if i < len(dates) else ""
                    signals.append({
                        "type": "down_breakout",
                        "level": s,
                        "date_index": i,
                        "date": signal_date,
                        "volume_ratio": round(vol_ratio, 2),
                        "price": closes[i],
                        "description": f"{signal_date} 跌破支撑位{s}元",
                    })

        return signals[:5]

    def _validate_breakout(self, signal: dict, closes, volumes,
                          resistance, support) -> dict:
        """验证突破真假"""
        is_true = True
        risk_flags = []
        confidence = 50
        idx = signal.get("date_index", 0)

        if signal["type"] == "up_breakout":
            # 向上突破验证逻辑
            vol_ratio = signal.get("volume_ratio", 1)

            # 1. 放量验证
            if vol_ratio >= BREAKOUT_VOLUME_RATIO:
                confidence += 20
            elif vol_ratio >= 1.5:
                confidence += 10
            else:
                confidence -= 15
                risk_flags.append("突破量能不足，疑似诱多")

            # 2. 回踩验证（突破后是否回踩确认）
            if idx + BREAKOUT_CONFIRM_DAYS < len(closes):
                post_breakout = closes[idx:idx + BREAKOUT_CONFIRM_DAYS + 1]
                breakout_price = closes[idx]
                min_retrace = min(post_breakout)

                # 回踩不超过突破价的50%斐波那契回撤
                retrace_ratio = (breakout_price - min_retrace) / (breakout_price - closes[idx-1]) if closes[idx-1] != breakout_price else 0

                if min_retrace > breakout_price * 0.98:  # 没有明显回踩
                    confidence += 15
                elif retrace_ratio < BREAKOUT_RETRACEMENT_MAX:
                    confidence += 5
                    risk_flags.append(f"回踩幅度{round(retrace_ratio*100)}%，尚在合理范围")
                else:
                    confidence -= 15
                    risk_flags.append(f"回踩过深({round(retrace_ratio*100)}%)，警惕假突破")

            # 3. 后续走势验证
            if idx + 3 < len(closes):
                if closes[idx + 1] > closes[idx] and closes[idx + 2] > closes[idx]:
                    confidence += 10
                elif closes[idx + 1] < closes[idx] * 0.97:
                    confidence -= 20
                    risk_flags.append("突破后快速回落，高度疑似假突破")

            # 4. 分时图验证：收盘价 > 开盘价（阳线）
            # (K线数据中有open/close可以用)
            if idx < len(closes):
                if closes[idx] >= closes[max(0, idx-1)]:
                    confidence += 5

        elif signal["type"] == "down_breakout":
            # 向下突破验证逻辑
            vol_ratio = signal.get("volume_ratio", 1)

            # 1. 缩量下跌可能是洗盘诱空
            if vol_ratio < 0.8:
                confidence -= 10
                risk_flags.append("缩量下跌，可能是诱空洗盘")
            elif vol_ratio > 2.0:
                confidence += 15
                risk_flags.append("放量破位，真实向下突破概率高")

            # 2. 快速收回验证
            if idx + 3 < len(closes):
                if closes[idx + 1] > closes[idx] and closes[idx + 2] > signal["level"]:
                    confidence -= 25
                    risk_flags.append("快速收回支撑位，疑似诱空")
                    is_true = False

            # 3. 均线支撑验证
            if idx + 3 < len(closes) and all(c < signal["level"] for c in closes[idx:idx+3]):
                confidence += 10

        confidence = min(100, max(0, confidence))
        if confidence < 45:
            is_true = False

        return {"is_true": is_true, "confidence": confidence, "risk_flags": risk_flags}

    def _detect_traps(self, closes, highs, lows, volumes, dates) -> list:
        """检测诱多诱空陷阱"""
        traps = []

        if len(closes) < 10:
            return traps

        # 诱多检测：快速拉高后放量回落
        for i in range(5, len(closes) - 3):
            # 前3天涨幅>8%
            if closes[i-1] / closes[i-4] > 1.08:
                # 之后2天回落>3%
                if closes[i+2] < closes[i] * 0.97:
                    vol_surge = volumes[i] > sum(volumes[i-5:i]) / 5 * 1.5
                    if vol_surge:
                        signal_date = dates[i] if i < len(dates) else ""
                        traps.append({
                            "type": "lure_long",
                            "date_index": i,
                            "date": signal_date,
                            "price": closes[i],
                            "volume_ratio": round(volumes[i] / (sum(volumes[i-5:i])/5), 2),
                            "description": f"{signal_date} 拉高后放量回落，疑似主力诱多出货",
                            "is_true_breakout": False,
                            "confidence": 30,
                            "risk_flags": ["诱多陷阱", "高位放量回落"],
                        })

        # 诱空检测：快速下跌后缩量反弹
        for i in range(5, len(closes) - 3):
            if closes[i-1] / closes[i-4] < 0.92:
                if closes[i+2] > closes[i] * 1.03:
                    vol_shrink = volumes[i] < sum(volumes[i-5:i]) / 5 * 0.7
                    if vol_shrink:
                        signal_date = dates[i] if i < len(dates) else ""
                        traps.append({
                            "type": "lure_short",
                            "date_index": i,
                            "date": signal_date,
                            "price": closes[i],
                            "description": f"{signal_date} 急跌后缩量反弹，疑似主力诱空吸筹",
                            "is_true_breakout": False,
                            "confidence": 35,
                            "risk_flags": ["诱空陷阱", "缩量急跌反弹"],
                        })

        # 近期诱骗信号
        return traps[-3:]

    def _trend_direction(self, prices: list) -> str:
        """判断短期趋势方向"""
        if len(prices) < 5:
            return "不明"
        if all(prices[i] > prices[i-1] for i in range(1, min(5, len(prices)))):
            return "强势上涨"
        if prices[-1] > prices[0] * 1.02:
            return "震荡上行"
        if prices[-1] < prices[0] * 0.98:
            return "震荡下行"
        if all(prices[i] < prices[i-1] for i in range(1, min(5, len(prices)))):
            return "弱势下跌"
        return "横盘整理"

    def _overall_status(self, signals: list, closes: list) -> str:
        """综合判断突破状态"""
        true_breakouts = [s for s in signals if s.get("is_true_breakout")]
        traps = [s for s in signals if "trap" in s.get("type", "") or "诱" in s.get("description", "")]

        if traps:
            return "warning_trap"  # 有诱骗信号
        if true_breakouts:
            if any(s["type"] == "up_breakout" for s in true_breakouts):
                return "true_breakout_up"
            return "true_breakout_down"
        return "no_breakout"
