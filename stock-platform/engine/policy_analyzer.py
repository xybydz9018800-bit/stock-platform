"""
操盘平台 - 政策和板块趋势深度挖掘引擎
"""
from datetime import date, timedelta
from config import SECTOR_KEYWORDS
from engine.data_fetcher import get_global_news, get_hot_sectors, get_stock_news, tencent_quote

class PolicyAnalyzer:
    """政策与板块趋势分析器"""

    def __init__(self, db_manager):
        self.db = db_manager

    def analyze_policy_environment(self) -> dict:
        """分析政策环境"""
        news = get_global_news(50)

        # 政策关键词检测
        policy_signals = self._extract_policy_signals(news)

        # 产业政策分析
        industry_policy = self._analyze_industry_policy(news)

        # 监管动态
        regulatory = self._analyze_regulatory(news)

        # 宏观政策
        macro_policy = self._analyze_macro(news)

        return {
            "date": date.today().isoformat(),
            "policy_signals": policy_signals,
            "industry_policy": industry_policy,
            "regulatory": regulatory,
            "macro_policy": macro_policy,
            "overall_assessment": self._assess_overall(policy_signals),
        }

    def analyze_sector_deep(self, sector_name: str) -> dict:
        """深度分析板块"""
        # 获取板块对应的关键词
        keywords = SECTOR_KEYWORDS.get(sector_name, [sector_name])

        # 分析政策支撑
        news = get_global_news(50)
        policy_items = []
        for n in news:
            title = n.get("title", "")
            if any(kw in title for kw in keywords):
                policy_items.append(n)

        # 分析板块走势
        sectors_data = get_hot_sectors()
        sector_info = None
        for s in sectors_data:
            if sector_name in s.get("name", "") or any(
                kw in s.get("name", "") for kw in keywords
            ):
                sector_info = s
                break

        # 分析资金流向
        fund_flow_analysis = self._analyze_sector_fund_flow(sector_name, keywords)

        # 产业趋势
        industry_trend = self._analyze_industry_trend(sector_name, keywords)

        return {
            "sector_name": sector_name,
            "keywords": keywords,
            "policy_support": {
                "strength": self._evaluate_policy_strength(policy_items),
                "recent_policies": policy_items[:5],
            },
            "sector_performance": sector_info,
            "fund_flow": fund_flow_analysis,
            "industry_trend": industry_trend,
            "rating": self._rate_sector(sector_name, policy_items, sector_info, fund_flow_analysis),
        }

    def find_sector_leaders(self, sector_name: str) -> list:
        """寻找板块龙头 — 热度最高/最先启动/资金流入最多"""
        keywords = SECTOR_KEYWORDS.get(sector_name, [sector_name])

        # 使用热门板块数据
        sectors = get_hot_sectors()

        leaders = []
        for s in sectors:
            name = s.get("name", "")
            if any(kw in name for kw in keywords):
                leader_code = s.get("code", "")
                leader_name = s.get("leader", "")

                if leader_code:
                    quote = tencent_quote([leader_code])
                    if quote:
                        q = quote.get(leader_code, {})
                        # 龙头评分 = 涨幅热度 + 换手活跃度
                        leader_score = abs(q.get("change_pct", 0)) * 2 + (q.get("turnover_pct", 0) or 0)
                        leaders.append({
                            "code": leader_code,
                            "name": leader_name,
                            "sector": sector_name,
                            "price": q.get("price", 0),
                            "change_pct": q.get("change_pct", 0),
                            "mcap_yi": q.get("mcap_yi", 0),
                            "pe_ttm": q.get("pe_ttm", 0),
                            "turnover_pct": q.get("turnover_pct", 0),
                            "leader_score": round(leader_score, 1),
                        })

        # 龙头排序：热度+换手综合评分 → 而非市值
        leaders.sort(key=lambda x: x.get("leader_score", 0), reverse=True)
        return leaders[:10]

    def analyze_sector_rotation(self, days: int = 10) -> dict:
        """分析板块轮动规律"""
        past_hot_spots = self.db.get_hot_spots(days)

        # 统计各板块出现频率
        sector_freq = {}
        sector_performance = {}

        for spot in past_hot_spots:
            topic = spot.get("topic", "")
            if topic not in sector_freq:
                sector_freq[topic] = 0
                sector_performance[topic] = []
            sector_freq[topic] += 1
            sector_performance[topic].append(spot.get("sector_index_change", 0))

        # 找出轮动规律
        ranked = sorted(sector_freq.items(), key=lambda x: x[1], reverse=True)

        # 判断轮动方向
        if len(ranked) >= 2:
            rotation_note = f"近期热点从分散转向集中，{ranked[0][0]}持续活跃"
        else:
            rotation_note = "热点分散，无明显轮动主线"

        return {
            "period_days": days,
            "sector_frequency": dict(ranked[:15]),
            "top_3_sectors": [r[0] for r in ranked[:3]],
            "rotation_note": rotation_note,
            "emerging_sectors": self._find_emerging_sectors(sector_freq),
        }

    def _extract_policy_signals(self, news: list) -> dict:
        """提取政策信号"""
        signals = {"bullish": [], "bearish": [], "neutral": []}

        bullish_keywords = ["利好", "支持", "促进", "补贴", "减税", "降准", "降息", "放开", "鼓励"]
        bearish_keywords = ["监管", "收紧", "限制", "处罚", "调查", "约谈", "加税", "制裁"]

        for n in news:
            title = n.get("title", "")
            if any(kw in title for kw in bullish_keywords):
                signals["bullish"].append({"title": title, "time": n.get("time", "")})
            elif any(kw in title for kw in bearish_keywords):
                signals["bearish"].append({"title": title, "time": n.get("time", "")})

        return signals

    def _analyze_industry_policy(self, news: list) -> list:
        """分析产业政策"""
        industry_policy = []
        for sector, keywords in SECTOR_KEYWORDS.items():
            for n in news:
                title = n.get("title", "")
                if any(kw in title for kw in keywords):
                    if any(w in title for w in ["政策", "规划", "方案", "意见", "通知", "补贴"]):
                        industry_policy.append({
                            "sector": sector,
                            "title": title,
                            "time": n.get("time", ""),
                        })
                        break
        return industry_policy[:10]

    def _analyze_regulatory(self, news: list) -> list:
        """分析监管动态"""
        regulatory_keywords = ["证监会", "交易所", "监管", "立案", "问询", "处罚", "警示"]
        items = []
        for n in news:
            title = n.get("title", "")
            if any(kw in title for kw in regulatory_keywords):
                items.append({"title": title, "time": n.get("time", "")})
        return items[:10]

    def _analyze_macro(self, news: list) -> list:
        """分析宏观政策"""
        macro_keywords = ["GDP", "CPI", "PPI", "社融", "M2", "LPR", "降准", "降息",
                         "央行", "财政部", "国务院", "政治局"]
        items = []
        for n in news:
            title = n.get("title", "")
            if any(kw in title for kw in macro_keywords):
                items.append({"title": title, "time": n.get("time", "")})
        return items[:10]

    def _assess_overall(self, signals: dict) -> str:
        """综合政策评估"""
        bullish_count = len(signals.get("bullish", []))
        bearish_count = len(signals.get("bearish", []))

        if bullish_count > bearish_count * 2:
            return "政策面偏暖，利好股市"
        elif bullish_count > bearish_count:
            return "政策面中性偏暖"
        elif bearish_count > bullish_count * 2:
            return "政策面偏紧，注意风险"
        elif bearish_count > bullish_count:
            return "政策面中性偏紧"
        else:
            return "政策面平稳"

    def _evaluate_policy_strength(self, policy_items: list) -> str:
        """评估政策支撑力度"""
        if len(policy_items) >= 5:
            return "强政策支撑"
        elif len(policy_items) >= 2:
            return "中等政策支撑"
        elif len(policy_items) >= 1:
            return "弱政策支撑"
        else:
            return "暂无明确政策支撑"

    def _analyze_sector_fund_flow(self, sector_name: str, keywords: list) -> dict:
        """分析板块资金流向"""
        # 获取板块数据
        sectors = get_hot_sectors()
        target_sector = None
        for s in sectors:
            name = s.get("name", "")
            if sector_name in name or any(kw in name for kw in keywords):
                target_sector = s
                break

        if target_sector:
            return {
                "has_data": True,
                "sector_change": target_sector.get("change_pct", 0),
                "up_count": target_sector.get("up_count", 0),
                "down_count": target_sector.get("down_count", 0),
                "assessment": "资金流入" if target_sector.get("change_pct", 0) > 0 else "资金流出",
            }

        return {"has_data": False, "assessment": "数据不足"}

    def _analyze_industry_trend(self, sector_name: str, keywords: list) -> dict:
        """分析产业趋势"""
        # 从新闻中分析产业趋势
        news = get_global_news(50)
        related_news = []
        for n in news:
            title = n.get("title", "")
            if any(kw in title for kw in keywords):
                related_news.append(n)

        # 分析趋势
        growth_signals = ["增长", "突破", "扩产", "订单", "需求", "出货"]
        risk_signals = ["过剩", "降价", "竞争", "淘汰", "亏损"]

        positive_count = sum(1 for n in related_news
                           if any(w in n.get("title", "") for w in growth_signals))
        negative_count = sum(1 for n in related_news
                           if any(w in n.get("title", "") for w in risk_signals))

        if positive_count > negative_count:
            trend = "景气上行"
        elif negative_count > positive_count:
            trend = "景气下行"
        else:
            trend = "景气平稳"

        return {
            "trend": trend,
            "related_news_count": len(related_news),
            "positive_signals": positive_count,
            "negative_signals": negative_count,
        }

    def _rate_sector(self, sector_name, policy_items, sector_info, fund_flow) -> str:
        """评估板块综合评级"""
        score = 50

        # 政策支撑
        if len(policy_items) >= 3:
            score += 20
        elif len(policy_items) >= 1:
            score += 10

        # 板块表现
        if sector_info:
            change = sector_info.get("change_pct", 0)
            score += change * 3

        # 资金流向
        if fund_flow.get("has_data"):
            if fund_flow.get("assessment") == "资金流入":
                score += 10
            else:
                score -= 10

        if score >= 80:
            return "强烈推荐"
        elif score >= 65:
            return "推荐关注"
        elif score >= 50:
            return "中性"
        elif score >= 35:
            return "谨慎"
        else:
            return "回避"

    def _find_emerging_sectors(self, sector_freq: dict) -> list:
        """发现新兴板块"""
        # 出现频率低但最近有表现的板块
        emerging = []
        for sector, freq in sector_freq.items():
            if freq <= 2:
                emerging.append(sector)
        return emerging[:5]
