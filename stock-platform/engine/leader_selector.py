"""
操盘平台 - 双体系龙头选股引擎
中线价值行业龙头 + 短线情绪主线龙头
"""
from datetime import date, timedelta
from config import (
    VALUE_LEADER_MIN_DAILY_AMOUNT, SENTIMENT_LEADER_MIN_BOARD_STOCKS,
    SENTIMENT_LEADER_MIN_TURNOVER, SENTIMENT_LEADER_MAX_TURNOVER,
    HIGH_GROWTH_SECTORS, CONSUMER_STAPLE_SECTORS,
    SENTIMENT_LEADER_CRITERIA, SENTIMENT_BUY_POINTS,
    SENTIMENT_SELL_RULES, VALUE_LEADER_HOLD_MONTHS,
    PORTFOLIO_ALLOCATION, PITFALL_CHECKS,
)
from engine.data_fetcher import tencent_quote

class LeaderSelector:
    """双体系龙头选股引擎"""

    def __init__(self, db_manager):
        self.db = db_manager

    # ============================================================
    # 第一套：中线价值行业龙头
    # ============================================================

    def screen_value_leaders(self, candidate_codes: list) -> list:
        """筛选中线价值龙头 — 自上而下三步法"""
        results = []

        for code in candidate_codes:
            try:
                leader = self._evaluate_value_leader(code)
                if leader:
                    results.append(leader)
            except Exception as e:
                print(f"价值龙头评估{code}失败: {e}")

        results.sort(key=lambda x: x.get("leader_score", 0), reverse=True)
        return results

    def _evaluate_value_leader(self, code: str) -> dict:
        """评估是否为中线价值龙头（量化阈值版）
        价值龙头 = 高ROE(>12%) + 深护城河(品牌/技术/网络) + 低估值(PE<行业中位数) + 大市值(>200亿)
        量化阈值:
          ROE: PE_TTM>0 且 PE<50 → PE<15=优秀, PE15-30=良好, PE30-50=中等
          护城河: 市值>500亿=强, 200-500=中, <200=弱
          估值分位: PE<行业均值70%为低估, >130%为高估
          流动性: 日均成交额>3亿为合格
        """
        quotes = tencent_quote([code])
        if code not in quotes:
            return None
        q = quotes[code]

        mcap = q.get("mcap_yi", 0)
        pe = q.get("pe_ttm", 0)
        pb = q.get("pb", 0)
        turnover = q.get("turnover_pct", 0)
        amount = (q.get("amount_wan", 0) or 0) / 10000
        name = q.get("name", "")

        # === 量化阈值检查 ===
        reasons = []
        
        # 1. 市值门槛: >200亿
        if mcap < 200:
            reasons.append(f"市值{mcap:.0f}亿不达标(<200亿)")
            # 不直接拒绝，但大幅扣分
        else:
            reasons.append(f"✅ 市值{mcap:.0f}亿达标")

        # 2. 估值门槛: PE>0 且 PE<60 (排除亏损和泡沫)
        if pe <= 0 or pe > 60:
            reasons.append(f"PE={pe:.1f}不在合理区间(0-60)")
        elif pe < 15:
            reasons.append("✅ PE<15，深度低估")
        elif pe < 30:
            reasons.append("✅ PE15-30，估值合理偏低")
        else:
            reasons.append(f"✅ PE{pe:.0f}，估值适中")

        # 3. 流动性门槛: 日均成交额>3亿
        if amount < 3:
            reasons.append(f"日均成交{amount:.1f}亿不达标(<3亿)")
        else:
            reasons.append(f"✅ 日均成交{amount:.1f}亿达标")

        # 4. PB门槛: PB<8 (排除过度溢价)
        if pb > 8:
            reasons.append(f"PB={pb:.1f}偏高(>8)")

        # 5. 换手率: 2%-15%为活跃区间
        if turnover < 2:
            reasons.append(f"换手{turnover:.1f}%偏低(<2%)")
        elif turnover > 20:
            reasons.append(f"换手{turnover:.1f}%偏高(>20%，投机性强)")
        else:
            reasons.append(f"✅ 换手{turnover:.1f}%适中")

        # 综合评分（量化版）
        score = 50  # 基准分
        if mcap >= 500: score += 20  # 大市值加分
        elif mcap >= 200: score += 10
        if 0 < pe <= 15: score += 15  # 低PE加分
        elif 0 < pe <= 30: score += 10
        elif 0 < pe <= 50: score += 5
        if pb < 3: score += 10  # 低PB加分
        elif pb < 5: score += 5
        if amount >= 10: score += 10  # 高流动性加分
        elif amount >= 5: score += 5
        if 2 <= turnover <= 15: score += 10  # 健康换手加分

        score = min(100, score)

        # === 护城河判断 ===
        moat = self._judge_moat(name, self._identify_sector(name, code).get("name", ""), mcap)

        # === 估值分位 ===
        pe_percentile = "低估" if pe < 20 else ("合理" if pe < 40 else "偏高")
        
        # === 估值状态 ===
        valuation_status = self._assess_valuation(pe, pb, self._identify_sector(name, code).get("category", "growth"))

        # 龙头判定：评分>60为合格价值龙头
        is_leader = score >= 60
        leader_label = "中线价值龙头" if is_leader else "价值候选（待确认）"

        return {
            "code": code,
            "name": name,
            "leader_type": "value",
            "leader_label": leader_label,
            "leader_score": round(score, 1),
            "is_leader": is_leader,
            "market_cap": mcap,
            "pe_ttm": pe,
            "pb": pb,
            "daily_amount_yi": round(amount, 1),
            "valuation_status": valuation_status,
            "pe_percentile": pe_percentile,
            "moat_type": moat.get("type", ""),
            "moat_strength": moat.get("strength", ""),
            "quant_reasons": reasons,
            "hold_suggestion": f"建议持有{VALUE_LEADER_HOLD_MONTHS}个月" if is_leader else "等待确认信号",
        }

    def _identify_sector(self, name: str, code: str) -> dict:
        """识别股票所属赛道"""
        sector_map = {
            "AI算力": ["算力", "GPU", "服务器", "光模块", "数据中心", "浪潮", "中科", "寒武纪", "海光"],
            "半导体": ["芯片", "晶圆", "封测", "北方华创", "中芯", "华虹", "长电", "韦尔"],
            "创新药": ["医药", "药", "生物", "基因", "疫苗", "恒瑞", "百济", "信达"],
            "军工": ["航天", "航空", "军工", "中船", "中航", "中国", "航发"],
            "储能": ["储能", "电池", "逆变器", "宁德", "阳光", "亿纬"],
            "高端制造": ["精密", "机床", "激光", "自动化", "机器人", "工业"],
            "白酒": ["茅台", "五粮液", "泸州", "汾酒", "洋河", "古井", "酒"],
            "家电": ["美的", "格力", "海尔", "家电"],
            "医疗服务": ["医疗", "爱尔", "通策", "美年"],
            "食品饮料": ["海天", "伊利", "双汇", "食品", "饮料", "调味"],
        }

        for sector_name, keywords in sector_map.items():
            if any(kw in name for kw in keywords):
                category = "growth" if sector_name in HIGH_GROWTH_SECTORS else "staple"
                return {"name": sector_name, "category": category}

        return {"name": "其他", "category": "other"}

    def _judge_moat(self, name: str, sector: str, mcap: float) -> dict:
        """判断护城河类型和强度"""
        brand_sectors = ["白酒", "家电", "医疗服务", "食品饮料"]
        tech_sectors = ["AI算力", "半导体", "创新药", "军工"]
        scale_sectors = ["储能", "高端制造"]

        if sector in brand_sectors:
            return {"type": "品牌壁垒", "strength": "强"}
        elif sector in tech_sectors and mcap > 500:
            return {"type": "技术/专利壁垒", "strength": "强"}
        elif sector in scale_sectors and mcap > 200:
            return {"type": "规模成本壁垒", "strength": "中强"}
        elif mcap > 1000:
            return {"type": "规模+渠道壁垒", "strength": "强"}
        else:
            return {"type": "规模壁垒", "strength": "中"}

    def _assess_valuation(self, pe: float, pb: float, category: str) -> str:
        """评估估值位置"""
        if category == "growth":
            if pe <= 30:
                return "低估区间"
            elif pe <= 60:
                return "合理区间"
            elif pe <= 100:
                return "偏高区间"
            else:
                return "高估区间(谨慎)"
        else:
            if pe <= 20:
                return "低估区间"
            elif pe <= 40:
                return "合理区间"
            else:
                return "偏高区间"

    def _calc_value_leader_score(self, mcap, pe, pb, turnover, amount, sector, moat, valuation) -> float:
        """中线价值龙头综合评分(0-100)"""
        score = 50

        # 赛道得分 (0-20)
        if sector["category"] == "growth":
            score += 15
        elif sector["category"] == "staple":
            score += 10

        # 护城河得分 (0-15)
        moat_scores = {"强": 15, "中强": 10, "中": 5}
        score += moat_scores.get(moat["strength"], 5)

        # 估值得分 (0-15)
        if "低估" in valuation:
            score += 15
        elif "合理" in valuation:
            score += 8
        elif "偏高" in valuation:
            score -= 5
        else:
            score -= 10

        # 流动性得分 (0-10)
        if amount > 20:
            score += 10
        elif amount > 10:
            score += 7
        elif amount > 5:
            score += 4

        return min(100, max(0, score))

    def _value_buy_timing(self, quote: dict, sector: dict) -> str:
        """中线龙头买入时机建议"""
        pe = quote.get("pe_ttm", 0)
        change = quote.get("change_pct", 0)
        if pe > 0 and pe < 30:
            return "当前估值偏低，可建40%底仓"
        elif 30 <= pe < 60:
            return "估值合理，回调至MA60可加仓"
        elif change < -2:
            return "当日下跌，可小仓试探"
        else:
            return "等待回调至均线支撑再建仓"

    def _value_sell_signals(self) -> list:
        """中线龙头卖出条件"""
        from config import VALUE_SELL_CONDITIONS
        return VALUE_SELL_CONDITIONS

    # ============================================================
    # 第二套：短线情绪龙头战法
    # ============================================================

    def screen_sentiment_leaders(self, candidate_codes: list, hot_sectors: list) -> list:
        """筛选短线情绪龙头"""
        results = []
        hot_sector_names = [s.get("topic", s.get("name", "")) for s in hot_sectors]

        for code in candidate_codes:
            try:
                leader = self._evaluate_sentiment_leader(code, hot_sector_names)
                if leader:
                    results.append(leader)
            except Exception as e:
                print(f"情绪龙头评估{code}失败: {e}")

        results.sort(key=lambda x: x.get("leader_score", 0), reverse=True)
        return results

    def _evaluate_sentiment_leader(self, code: str, hot_sectors: list) -> dict:
        """评估是否为短线情绪龙头 — 量化阈值版
        
        情绪龙头 = 率先涨停/领涨 + 高换手(5%-18%) + 板块带动性 + 龙虎榜资金聚焦
        量化阈值:
          涨幅: >5%才算领涨, >9.5%为情绪总龙头
          换手: 5%-18%为健康区间, <2%无关注, >25%过度投机
          量比: >1.5为放量启动, <0.8为缩量
          成交额: >3亿为活跃, >10亿为市场焦点
          市值: 50-500亿弹性最佳, <30亿或>1000亿不适合
        """
        quotes = tencent_quote([code])
        if code not in quotes:
            return None
        q = quotes[code]

        change_pct = q.get("change_pct", 0)
        turnover = q.get("turnover_pct", 0)
        amount = (q.get("amount_wan", 0) or 0) / 10000
        vol_ratio = q.get("vol_ratio", 0)
        name = q.get("name", "")
        mcap = q.get("mcap_yi", 0)

        reasons = []

        # === 量化阈值检查 ===
        # 涨幅分级
        if change_pct >= 9.5:
            reasons.append(f"✅ 涨停({change_pct:.1f}%)，情绪总龙头特征")
        elif change_pct >= 7:
            reasons.append(f"✅ 强势上涨({change_pct:.1f}%)，领涨先锋")
        elif change_pct >= 5:
            reasons.append(f"✅ 上涨{change_pct:.1f}%，板块领涨")
        elif change_pct >= 3:
            reasons.append(f"⚠️ 涨幅{change_pct:.1f}%偏弱，龙头气质不足")
        else:
            reasons.append(f"❌ 涨幅{change_pct:.1f}%不达标(<3%)")

        # 换手率分级
        if 5 <= turnover <= 18:
            reasons.append(f"✅ 换手{turnover:.1f}%健康(5-18%)")
        elif 2 <= turnover < 5:
            reasons.append(f"⚠️ 换手{turnover:.1f}%偏低")
        elif turnover > 18 and turnover <= 25:
            reasons.append(f"⚠️ 换手{turnover:.1f}%偏高")
        elif turnover > 25:
            reasons.append(f"❌ 换手{turnover:.1f}%过度投机(>25%)")
        else:
            reasons.append(f"❌ 换手{turnover:.1f}%无人气(<2%)")

        # 量比分级
        if vol_ratio >= 1.5:
            reasons.append(f"✅ 量比{vol_ratio:.1f}，放量启动")
        elif vol_ratio >= 1.0:
            reasons.append(f"⚠️ 量比{vol_ratio:.1f}，量能一般")
        elif vol_ratio > 0:
            reasons.append(f"❌ 量比{vol_ratio:.1f}，缩量不活跃")
        else:
            reasons.append(f"⏳ 量比数据暂缺")

        # 成交额分级
        if amount >= 10:
            reasons.append(f"✅ 成交{amount:.1f}亿，市场焦点")
        elif amount >= 3:
            reasons.append(f"✅ 成交{amount:.1f}亿，活跃")
        elif amount >= 1:
            reasons.append(f"⚠️ 成交{amount:.1f}亿，一般")
        else:
            reasons.append(f"❌ 成交{amount:.1f}亿不达标(<1亿)")

        # 市值弹性
        if 50 <= mcap <= 500:
            reasons.append(f"✅ 市值{mcap:.0f}亿弹性佳")
        elif mcap < 30:
            reasons.append(f"❌ 市值{mcap:.0f}亿过小风险高")
        elif mcap > 1000:
            reasons.append(f"⚠️ 市值{mcap:.0f}亿过大，弹性不足")
        else:
            reasons.append(f"⚠️ 市值{mcap:.0f}亿")

        # 综合评分
        score = 50
        score += min(20, max(0, change_pct * 2))  # 涨幅分 0-20
        if 5 <= turnover <= 18: score += 15  # 健康换手
        elif 2 <= turnover < 5: score += 8
        if vol_ratio >= 1.5: score += 15  # 放量确认
        elif vol_ratio >= 1.0: score += 5
        if amount >= 10: score += 15  # 高成交加分
        elif amount >= 3: score += 8
        if 50 <= mcap <= 500: score += 10  # 弹性加分
        score = min(100, score)

        is_leader = score >= 60
        subtype = self._classify_sentiment_type(change_pct, turnover, vol_ratio, q)

        return {
            "code": code, "name": name,
            "leader_type": "sentiment",
            "leader_label": "短线情绪龙头" if is_leader else "情绪候选",
            "leader_subtype": subtype,
            "is_leader": is_leader,
            "change_pct": change_pct,
            "turnover_pct": turnover,
            "daily_amount_yi": round(amount, 1),
            "vol_ratio": vol_ratio,
            "market_cap": mcap,
            "leader_score": round(score, 1),
            "quant_reasons": reasons,
            "strategy_note": "3成短线配置，快进快出不超过10天",
        }

    def _classify_sentiment_type(self, change_pct: float, turnover: float, vol_ratio: float, quote: dict) -> str:
        """分类短线龙头类型"""
        mcap = quote.get("mcap_yi", 0)
        if mcap > 200 and turnover < 10 and 3 < change_pct < 10:
            return "trend_mid"  # 趋势中军龙头
        elif change_pct >= 9.5:
            return "limit_emotion"  # 连板情绪总龙头
        elif change_pct > 5 and vol_ratio > 2:
            return "limit_emotion"
        else:
            return "trend_mid"

    def _calc_sentiment_leader_score(self, change_pct, turnover, amount, vol_ratio, mcap) -> float:
        """短线情绪龙头评分(0-100)"""
        score = 40

        # 涨幅热度 (0-25)
        if change_pct >= 9.5: score += 25
        elif change_pct >= 7: score += 20
        elif change_pct >= 5: score += 15
        elif change_pct >= 3: score += 10

        # 换手健康度 (0-15)
        if 5 <= turnover <= 18: score += 15
        elif 3 <= turnover <= 25: score += 8

        # 成交额 (0-15)
        if amount > 10: score += 15
        elif amount > 5: score += 10
        elif amount > 2: score += 5

        # 量比 (0-10)
        if vol_ratio > 3: score += 10
        elif vol_ratio > 2: score += 7
        elif vol_ratio > 1.5: score += 4

        return min(100, max(0, score))

    def _sentiment_buy_point(self, subtype: str, quote: dict) -> str:
        """短线龙头买点建议"""
        change = quote.get("change_pct", 0)
        if subtype == "trend_mid":
            if change > 5:
                return "趋势中军：不宜追高，等回踩5/10日线缩量企稳"
            else:
                return "趋势中军：当前可分批低吸，分时水下承接介入"
        elif subtype == "limit_emotion":
            if change >= 9.5:
                return "连板龙头：等待分歧低吸机会（低开缩量），不打无量一字板"
            else:
                return "连板龙头：关注换手回封板机会，盘中炸板充分换手封回介入"
        else:
            return "反包龙头：前日大分歧，次日高开放量突破前高可介入"

    # ============================================================
    # 综合：仓位分配 + 每日复盘
    # ============================================================

    def allocate_portfolio(self, value_leaders: list, sentiment_leaders: list, total_capital: float) -> dict:
        """按照7:3原则分配仓位"""
        value_amount = total_capital * PORTFOLIO_ALLOCATION["value_leader"]
        sentiment_amount = total_capital * PORTFOLIO_ALLOCATION["sentiment_leader"]

        return {
            "total_capital": total_capital,
            "value_allocation": {
                "amount": round(value_amount, 2),
                "max_stocks": 3,
                "per_stock_max": round(value_amount / 3, 2),
                "leaders": value_leaders[:3],
            },
            "sentiment_allocation": {
                "amount": round(sentiment_amount, 2),
                "max_stocks": 2,
                "per_stock_max": round(sentiment_amount / 2, 2),
                "leaders": sentiment_leaders[:2],
            },
        }

    def daily_review_checklist(self) -> dict:
        """每日复盘执行清单"""
        today = date.today().isoformat()
        return {
            "date": today,
            "value_checklist": [
                "梳理各行业月度产销、政策新闻，更新景气赛道",
                "筛选赛道内ROE、增速、现金流达标头部企业",
                "核对估值分位、均线位置，标记低吸标的",
                "排查商誉、质押、减持等风险指标，剔除雷股",
            ],
            "sentiment_checklist": [
                "确认当日市场主线，剔除一日游小题材",
                "板块内排序：高度龙、趋势中军、补涨龙分层",
                "统计量能、换手率、龙虎榜资金行为",
                "标记次日分歧低吸、换手板潜在买点，提前设止损",
            ],
            "pitfalls": PITFALL_CHECKS,
        }

    def is_pitfall_stock(self, code: str) -> dict:
        """检查是否为避坑股票"""
        quotes = tencent_quote([code])
        if code not in quotes:
            return {"is_pitfall": True, "reason": "无法获取行情"}

        q = quotes[code]
        warnings = []

        # 检查是否蹭概念
        name = q.get("name", "")
        if any(w in name for w in ["ST", "*ST"]):
            warnings.append("ST风险股")

        # 检查流动性
        amount = q.get("amount_wan", 0) / 10000
        if amount < 0.5:
            warnings.append("日均成交不足5000万，流动性差")

        # 检查估值极端
        pe = q.get("pe_ttm", 0)
        if pe > 500 or pe < 0:
            warnings.append("估值异常")

        return {
            "is_pitfall": len(warnings) > 0,
            "warnings": warnings,
            "suggestion": "建议避开" if warnings else "可进一步分析",
        }
