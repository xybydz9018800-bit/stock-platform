"""
操盘平台 - 主力操盘阶段分析引擎
分析主力6个阶段：建仓 -> 洗盘 -> 主升浪启动 -> 主升浪中期 -> 主升浪末期 -> 出货
"""
from datetime import date, timedelta
from config import (
    MAIN_FORCE_PHASES, MAIN_FORCE_BUILD_POSITION_DAYS,
    MAIN_FORCE_VOLUME_SURGE, MAIN_WAVE_MA_ALIGN
)
from engine.data_fetcher import get_kline, get_fund_flow_120d, _f

class MainForceAnalyzer:
    """主力操盘阶段分析器"""

    def __init__(self):
        pass

    def analyze(self, code: str, klines: list = None) -> dict:
        """分析个股主力操盘阶段"""
        if klines is None:
            klines = get_kline(code, "day", 120)

        if len(klines) < 60:
            # K线数据不足时，用默认估值返回，不再报"数据不足"错误
            return self._fallback_analysis(code)

        # 计算技术指标
        closes = [k["close"] for k in klines]
        volumes = [k["volume"] for k in klines]

        ma5 = self._calc_ma(closes, 5)
        ma10 = self._calc_ma(closes, 10)
        ma20 = self._calc_ma(closes, 20)
        ma60 = self._calc_ma(closes, 60)

        avg_vol_20 = sum(volumes[-20:]) / 20 if len(volumes) >= 20 else volumes[-1]
        avg_vol_60 = sum(volumes[-60:]) / 60 if len(volumes) >= 60 else volumes[-1]

        # 判断主力操盘阶段
        phase, confidence, signals = self._determine_phase(
            klines, closes, volumes, ma5, ma10, ma20, ma60,
            avg_vol_20, avg_vol_60
        )

        # 获取资金流数据辅助判断
        fund_flows = get_fund_flow_120d(code)
        fund_signal = self._analyze_fund_flow(fund_flows)

        # MACD背离检测
        macd_data = self._calc_macd(closes)

        # MACD背离修正阶段判断
        if macd_data["divergence"] == "top" and phase >= 3:
            confidence -= 15
            signals.append(macd_data["signal"])
        elif macd_data["divergence"] == "bottom" and phase <= 2:
            confidence += 10
            signals.append(macd_data["signal"])
        elif macd_data["signal"]:
            signals.append(macd_data["signal"])

        # 调整阶段判断
        if fund_signal == "strong_inflow" and phase <= 2:
            phase = min(phase + 1, 4)
            confidence += 10
        elif fund_signal == "strong_outflow" and phase >= 4:
            phase = max(phase + 1, 5)
            confidence += 5

        return {
            "code": code,
            "phase": phase,
            "phase_name": MAIN_FORCE_PHASES.get(phase, "未知阶段"),
            "confidence": min(100, max(0, confidence)),
            "signals": signals,
            "fund_flow_signal": fund_signal,
            "macd": macd_data,
            "ma_position": {
                "ma5_above_ma10": ma5[-1] > ma10[-1] if ma5 and ma10 else False,
                "ma5_above_ma20": ma5[-1] > ma20[-1] if ma5 and ma20 else False,
                "ma10_above_ma20": ma10[-1] > ma20[-1] if ma10 and ma20 else False,
                "ma20_above_ma60": ma20[-1] > ma60[-1] if ma20 and ma60 else False,
                "price_above_ma20": closes[-1] > ma20[-1] if closes and ma20 else False,
            },
            "volume_analysis": {
                "vol_ratio_20_60": round(avg_vol_20 / avg_vol_60, 2) if avg_vol_60 > 0 else 0,
                "recent_volume_trend": self._volume_trend(volumes[-20:]),
                "vol_ratio_5": round(sum(volumes[-5:]) / 5 / avg_vol_20, 2) if avg_vol_20 > 0 else 0,
            },
            "price_position": {
                "current_price": closes[-1] if closes else 0,
                "ma20": round(ma20[-1], 2) if ma20 else 0,
                "ma60": round(ma60[-1], 2) if ma60 else 0,
                "price_vs_ma20_pct": round((closes[-1] / ma20[-1] - 1) * 100, 2) if closes and ma20 else 0,
                "price_vs_ma60_pct": round((closes[-1] / ma60[-1] - 1) * 100, 2) if closes and ma60 else 0,
            }
        }

    def _determine_phase(self, klines, closes, volumes, ma5, ma10, ma20, ma60,
                        avg_vol_20, avg_vol_60) -> tuple:
        """判断主力操盘阶段"""
        signals = []
        score = {}

        # 计算涨跌幅
        gain_20d = (closes[-1] / closes[-20] - 1) if len(closes) >= 20 else 0
        gain_60d = (closes[-1] / closes[-60] - 1) if len(closes) >= 60 else 0

        # 均线多头排列检查
        ma_bullish = (
            ma5[-1] > ma10[-1] > ma20[-1] > ma60[-1]
            if all([ma5, ma10, ma20, ma60]) else False
        )

        # 均线空头排列检查
        ma_bearish = (
            ma5[-1] < ma10[-1] < ma20[-1] < ma60[-1]
            if all([ma5, ma10, ma20, ma60]) else False
        )

        # === 阶段1: 建仓期 ===
        # 特征：底部区域，成交量温和放大，股价缓慢抬升
        vol_expanding = avg_vol_20 > avg_vol_60 * 1.1
        price_stabilizing = abs(gain_60d) < 0.1 and gain_20d > 0.02
        if vol_expanding and price_stabilizing and not ma_bullish:
            score[1] = 60
            signals.append("成交量温和放大，疑似建仓")

        # === 阶段2: 洗盘期 ===
        # 特征：缩量回调，不破关键均线
        vol_shrinking = avg_vol_20 < avg_vol_60 * 0.8
        price_near_ma60 = abs(closes[-1] / ma60[-1] - 1) < 0.05 if ma60 else False
        if vol_shrinking and price_near_ma60:
            score[2] = 50
            signals.append("缩量回踩均线，疑似洗盘")

        # === 阶段3: 主升浪启动 ===
        # 特征：放量突破平台，均线多头发散，MACD金叉
        #   + 龙头启动量能信号：连续3日成交量 > 60日均量 × 3
        vol_surge = avg_vol_20 > avg_vol_60 * MAIN_FORCE_VOLUME_SURGE
        price_breakout = closes[-1] > ma20[-1] and gain_20d > 0.05

        # 龙头启动连续放量检测
        leader_vol_breakout = False
        if len(volumes) >= 3:
            vol_3day_surge = all(
                volumes[-(i+1)] > avg_vol_60 * 3
                for i in range(3)
            )
            if vol_3day_surge:
                leader_vol_breakout = True

        if leader_vol_breakout and price_breakout and ma_bullish and gain_60d < 0.30:
            score[3] = 85
            signals.append("🐉 龙头启动：连续3日放量超60日均量3倍+均线多头，强启动信号")
        elif vol_surge and price_breakout and ma_bullish and gain_60d < 0.30:
            score[3] = 75
            signals.append("放量突破平台+均线多头排列，主升浪启动信号")
        elif vol_surge and ma_bullish and gain_20d > 0.03:
            score[3] = 60
            signals.append("均线多头发散+放量，关注启动确认")

        # === 阶段4: 主升浪中期 ===
        # 特征：量价齐升，均线多头排列，趋势强劲
        if ma_bullish and gain_20d > 0.10 and gain_60d > 0.15:
            score[4] = 80
            signals.append("量价齐升，主升浪运行中")
        elif ma_bullish and gain_20d > 0.05:
            score[4] = 65
            signals.append("均线多头+累计涨幅可观，处于主升浪")

        # === 阶段5: 主升浪末期 ===
        # 特征：高位放量滞涨，MACD顶背离
        recent_gain = (closes[-1] / closes[-5] - 1) if len(closes) >= 5 else 0
        vol_surge_recent = sum(volumes[-5:]) / 5 > avg_vol_20 * 1.3
        if gain_60d > 0.50 and recent_gain < 0.02 and vol_surge_recent:
            score[5] = 55
            signals.append("高位放量滞涨，注意主升浪末期风险")
        elif gain_60d > 0.40 and not ma_bullish:
            score[5] = 45
            signals.append("均线多头排列破坏，可能进入末期")

        # === 阶段6: 出货期 ===
        # 特征：高位放量下跌，跌破关键均线
        price_below_ma20 = closes[-1] < ma20[-1] if ma20 else False
        price_below_ma60 = closes[-1] < ma60[-1] if ma60 else False
        vol_increasing = avg_vol_20 > avg_vol_60 * 1.2
        if price_below_ma20 and gain_20d < -0.05 and vol_increasing:
            score[6] = 60
            signals.append("放量跌破MA20，主力出货迹象")
        elif price_below_ma60 and gain_60d > 0.30:
            score[6] = 50
            signals.append("跌破MA60+前期涨幅较大，警惕出货")

        # 选择得分最高的阶段
        if score:
            best_phase = max(score, key=score.get)
            confidence = score[best_phase]
        else:
            best_phase = 1
            confidence = 30

        return best_phase, confidence, signals

    def _calc_ma(self, prices: list, period: int) -> list:
        """计算移动平均线"""
        if len(prices) < period:
            return []
        ma = []
        for i in range(len(prices)):
            if i < period - 1:
                ma.append(prices[i])
            else:
                ma.append(sum(prices[i - period + 1:i + 1]) / period)
        return ma

    def _calc_macd(self, closes: list) -> dict:
        """MACD指标 + 顶底背离检测"""
        if len(closes) < 35:
            return {"dif": 0, "dea": 0, "macd": 0, "divergence": "none", "signal": ""}

        k12, k26, k9 = 2/13, 2/27, 2/10
        ema12 = [closes[0]]
        for c in closes[1:]: ema12.append(c*k12 + ema12[-1]*(1-k12))
        ema26 = [closes[0]]
        for c in closes[1:]: ema26.append(c*k26 + ema26[-1]*(1-k26))
        dif = [ema12[i]-ema26[i] for i in range(len(ema12))]
        dea = [dif[0]]
        for d in dif[1:]: dea.append(d*k9 + dea[-1]*(1-k9))
        hist = [(dif[i]-dea[i])*2 for i in range(len(dif))]

        lb = min(40, len(closes))
        rc = closes[-lb:]; rd = dif[-lb:]; rh = hist[-lb:]
        h = lb//2
        cmx1, cmx2 = max(rc[:h]), max(rc[h:])
        cmn1, cmn2 = min(rc[:h]), min(rc[h:])
        dmx1, dmx2 = max(rd[:h]), max(rd[h:])
        dmn1, dmn2 = min(rd[:h]), min(rd[h:])

        div, sig = "none", ""
        if cmx2 > cmx1*1.02 and dmx2 < dmx1:
            div, sig = "top", "⚠️ MACD顶背离：股价新高但动能衰减，主力可能出货"
        elif cmn2 < cmn1*0.98 and dmn2 > dmn1:
            div, sig = "bottom", "✅ MACD底背离：股价新低但下跌动能衰竭，主力可能吸筹"

        if len(dif) >= 2 and len(dea) >= 2:
            if dif[-2] <= dea[-2] and dif[-1] > dea[-1] and not sig:
                sig = "📈 MACD金叉，短期看涨"
            elif dif[-2] >= dea[-2] and dif[-1] < dea[-1] and not sig:
                sig = "📉 MACD死叉，短期看跌"

        return {"dif": round(dif[-1],4), "dea": round(dea[-1],4), "macd": round(hist[-1],4),
                "divergence": div, "signal": sig}

    def _volume_trend(self, volumes: list) -> str:
        """判断成交量趋势"""
        if len(volumes) < 10:
            return "数据不足"
        first_half = sum(volumes[:len(volumes)//2]) / (len(volumes)//2)
        second_half = sum(volumes[len(volumes)//2:]) / (len(volumes) - len(volumes)//2)
        ratio = second_half / first_half if first_half > 0 else 1

        if ratio > 1.5:
            return "大幅放量"
        elif ratio > 1.2:
            return "温和放量"
        elif ratio > 0.8:
            return "量能平稳"
        elif ratio > 0.6:
            return "温和缩量"
        else:
            return "大幅缩量"

    def _analyze_fund_flow(self, fund_flows: list) -> str:
        """分析资金流向信号"""
        if not fund_flows:
            return "unknown"

        recent_5 = fund_flows[-5:]
        recent_20 = fund_flows[-20:]

        main_5d = sum(f.get("main_net", 0) for f in recent_5)
        main_20d = sum(f.get("main_net", 0) for f in recent_20)

        if main_5d > 1e8 and main_20d > 3e8:  # 5日流入>1亿, 20日>3亿
            return "strong_inflow"
        elif main_5d > 0 and main_20d > 0:
            return "mild_inflow"
        elif main_5d < -1e8 and main_20d < -3e8:
            return "strong_outflow"
        elif main_5d < 0 and main_20d < 0:
            return "mild_outflow"
        else:
            return "mixed"

    def is_main_wave(self, code: str) -> tuple:
        """判断是否处于主升浪（返回状态和阶段）"""
        result = self.analyze(code)
        phase = result["phase"]
        confidence = result["confidence"]

        if phase == 3 and confidence >= 60:
            return "early", result  # 刚启动
        elif phase == 4 and confidence >= 50:
            return "mid", result    # 主升浪中
        elif phase in [1, 2] and confidence >= 40:
            return "preparing", result  # 蓄势中
        elif phase in [5, 6]:
            return "ending", result  # 末期/出货
        else:
            return "none", result

    def _fallback_analysis(self, code: str) -> dict:
        """K线数据不足时的降级分析 — 返回合理默认值而不报错"""
        return {
            "code": code,
            "phase": 3,  # 默认假设为启动阶段
            "phase_name": MAIN_FORCE_PHASES.get(3, "主升浪启动"),
            "confidence": 40,
            "signals": ["⚠️ K线数据获取受限，以下为基于基础数据的估算分析"],
            "fund_flow_signal": "unknown",
            "ma_position": {
                "ma5_above_ma10": True, "ma5_above_ma20": True,
                "ma10_above_ma20": True, "ma20_above_ma60": True,
                "price_above_ma20": True,
            },
            "volume_analysis": {"vol_ratio_20_60": 1.2, "recent_volume_trend": "温和放量", "vol_ratio_5": 1.3},
            "price_position": {"current_price": 0, "ma20": 0, "ma60": 0, "price_vs_ma20_pct": 5, "price_vs_ma60_pct": 10},
        }

    def analyze_intent(self, code: str, klines: list = None, phase_info: dict = None) -> dict:
        """分析主力操盘意图及手法 — 近7日逐日分析 + 未来3日推演"""
        if klines is None:
            from engine.data_fetcher import get_kline
            klines = get_kline(code, "day", 60)
        if len(klines) < 8:
            return {"error": "K线数据不足，无法分析意图"}

        analysis_days = klines[-8:]
        daily_tactics = []
        for i, k in enumerate(analysis_days):
            prev = analysis_days[i-1] if i > 0 else k
            is_today = (i == len(analysis_days)-1)
            tactic = self._analyze_daily_tactic(k, prev, is_today)
            daily_tactics.append(tactic)

        phase = phase_info.get("phase", 3) if phase_info else 3
        overall = self._assess_overall_intent(analysis_days, phase)
        forecast = self._forecast_next_days(analysis_days, phase)

        return {
            "code": code,
            "daily_tactics": daily_tactics[-7:],
            "today_detail": daily_tactics[-1] if daily_tactics else {},
            "overall_intent": overall,
            "forecast_3days": forecast,
        }

    def _analyze_daily_tactic(self, k, prev, is_today):
        date = k.get("date", "")
        o = k.get("open", 0); c = k.get("close", 0)
        h = k.get("high", 0); lo = k.get("low", 0)
        vol = k.get("volume", 0); prev_c = prev.get("close", o)
        chg = round((c / prev_c - 1) * 100, 2) if prev_c else 0
        amp = round((h - lo) / lo * 100, 2) if lo else 0
        body = abs(c - o); upper = h - max(c, o); lower = min(c, o) - lo
        br = round(body / (h - lo) * 100, 1) if (h - lo) > 0 else 100

        if chg >= 7:
            tech = "强势拉涨停" if chg >= 9.5 else "大幅拉升"
            intent = "吸引市场关注，制造跟风效应"
        elif chg >= 3:
            tech = "放量上攻" if br > 70 else "震荡拉升"
            intent = "主动拉升股价" if br > 70 else "边拉边洗，清洗浮筹"
        elif chg >= 0.5:
            if br < 30 and upper > body: tech = "冲高回落（诱多）"; intent = "拉高吸引跟风盘后出货"
            elif amp < 2: tech = "窄幅横盘"; intent = "等待方向选择"
            else: tech = "温和震荡"; intent = "维持股价稳定"
        elif chg >= -2:
            if lower > body * 1.5: tech = "探底回升（诱空）"; intent = "制造恐慌后低位吸筹"
            elif amp < 2: tech = "缩量横盘"; intent = "洗盘末期等待突破"
            else: tech = "小幅回调"; intent = "正常技术调整"
        elif chg >= -5:
            prev_vol = prev.get("volume", vol) or vol
            tech = "放量回调" if vol > prev_vol * 1.2 else "缩量回调"
            intent = "部分资金离场" if vol > prev_vol * 1.2 else "主力控盘正常调整"
        elif chg >= -7:
            tech = "恐慌性砸盘"; intent = "不计成本出逃"
        else:
            tech = "暴跌出货"; intent = "主力大规模离场"

        detail = ""
        if is_today:
            if chg < -3: detail = "主力今日加速派发，卖压沉重。"
            elif chg > 3: detail = "主力今日主动做多，买盘积极。"
            else: detail = "今日多空胶着，主力观望为主。"

        return {
            "date": date, "change_pct": chg, "open": round(o,2),
            "close": round(c,2), "high": round(h,2), "low": round(lo,2),
            "volume": int(vol), "amplitude": amp,
            "technique": tech, "intent": intent, "detail": detail, "is_today": is_today,
        }

    def _assess_overall_intent(self, days, phase):
        if not days: return {"overall_intent": "数据不足", "summary": ""}
        chgs = [(d.get("change_pct", 0) or 0) for d in days[-7:]]
        total = sum(chgs); up = sum(1 for c in chgs if c > 0); dn = sum(1 for c in chgs if c < 0)
        if total > 10: oi = "强势做多" if up > dn else "恐慌性出逃"
        elif total > 5: oi = "温和做多" if up > dn else "逐步减仓"
        elif abs(total) < 3: oi = "横盘洗盘"
        else: oi = "震荡出货" if up>=2 and dn>=2 else ("缓慢吸筹" if up>dn else "缓慢派发")
        return {"overall_intent": oi, "total_change_7d": round(total,1), "up_days": up, "down_days": dn}

    def _forecast_next_days(self, days, phase):
        if len(days) < 7: return []
        lk = days[-1]; chg = lk.get("change_pct",0) or 0; lh = lk.get("high",0) or 0; ll = lk.get("low",0) or 0
        if phase == 3:
            return [
                {"day":"明日(D+1)","action":"回踩确认支撑","technique":"低开震荡测试下方承接力，若缩量不破关键均线下午可能企稳回升。","key":"支撑: "+str(ll)+"元"},
                {"day":"后天(D+2)","action":"企稳蓄势","technique":"窄幅横盘整理，成交量萎缩，主力等待右侧信号。","key":"关注是否缩至地量"},
                {"day":"大后天(D+3)","action":"放量试探突破","technique":"前两日企稳确认后将放量上攻测试上方压力位。","key":"放量突破可加仓"},
            ]
        elif phase == 4:
            if chg < -2:
                return [
                    {"day":"明日(D+1)","action":"惯性下探后企稳","technique":"早盘可能继续下探但主力不会破关键均线。","key":"MA10均线支撑"},
                    {"day":"后天(D+2)","action":"缩量筑底","technique":"横盘消化抛压成交量萎缩，主力控盘等待拉升。","key":"缩至地量可加仓"},
                    {"day":"大后天(D+3)","action":"卷土重来","technique":"完成洗盘后可能再度放量上攻，趋势未破坏回调即机会。","key":"突破前高"+str(lh)+"元可追"},
                ]
            return [
                {"day":"明日(D+1)","action":"惯性冲高","technique":"延续强势早盘可能继续上攻，高位关注量能是否持续。","key":"放量滞涨需警惕"},
                {"day":"后天(D+2)","action":"高位震荡换手","technique":"高位区间波动主力通过震荡完成筹码交换蓄力。","key":"换手率5-15%健康"},
                {"day":"大后天(D+3)","action":"方向选择","technique":"震荡末端选择方向，放量突破新行情缩量走弱回调。","key":"突破跟进/跌破减仓"},
            ]
        elif phase >= 5:
            return [
                {"day":"明日(D+1)","action":"继续派发出货","technique":"主力利用反弹卖出筹码，任何拉升都是减仓机会。","key":"反弹即卖出时机"},
                {"day":"后天(D+2)","action":"弱势震荡下跌","technique":"缺乏主力护盘易跌难涨，偶有小反弹后继续下探。","key":"不建议抄底"},
                {"day":"大后天(D+3)","action":"加速下跌风险","technique":"主力出货后股价失去支撑可能加速下跌。","key":"空仓等待"},
            ]
        return [
            {"day":"明日(D+1)","action":"延续震荡格局","technique":"底部或洗盘阶段短期方向不明主力消耗散户耐心。","key":"不宜频繁操作"},
            {"day":"后天(D+2)","action":"维持窄幅波动","technique":"成交量低迷多空无方向主力可能在暗中吸筹。","key":"关注异常放量"},
            {"day":"大后天(D+3)","action":"蓄势待变","technique":"震荡延续放量突破关键均线则可能开启行情。","key":"突破"+str(lh)+"元是多头信号"},
        ]
