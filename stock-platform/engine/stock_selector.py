"""
操盘平台 - 选股引擎
多维度选股：热点+主升浪+资金+龙头+板块分散
"""
from datetime import date, timedelta
from config import (
    STOCK_POOL_SIZE, EARLY_STAGE_COUNT, MID_STAGE_COUNT,
    MAX_SAME_SECTOR, MIN_MARKET_CAP, MAX_MARKET_CAP,
    MIN_AVG_VOLUME, MAX_PE_TTM
)
from engine.data_fetcher import (
    tencent_quote, get_kline, get_fund_flow_120d,
    get_hot_sectors, get_stock_news
)
from engine.main_force import MainForceAnalyzer
from engine.policy_analyzer import PolicyAnalyzer

class StockSelector:
    """选股引擎"""

    def __init__(self, db_manager):
        self.db = db_manager
        self.main_force = MainForceAnalyzer()

    def screen_candidates(self, candidate_codes: list) -> list:
        """从候选股票中筛选符合投资理念的股票"""
        results = []

        for code in candidate_codes:
            try:
                score = self._evaluate_stock(code)
                if score:
                    results.append(score)
            except Exception as e:
                print(f"评估{code}失败: {e}")
                continue

        # 按综合评分排序
        results.sort(key=lambda x: x["total_score"], reverse=True)
        return results

    def build_stock_pool(self, candidates: list) -> dict:
        """构建20只动态股票池"""
        # 分类
        early_stage = []
        mid_stage = []
        sector_count = {}

        for stock in candidates:
            sector = stock.get("sector", "其他")

            # 检查板块限制（同一板块不超过3只）
            if sector_count.get(sector, 0) >= MAX_SAME_SECTOR:
                continue

            stage = stock.get("main_wave_stage", "")

            if stage == "early" and len(early_stage) < EARLY_STAGE_COUNT:
                early_stage.append(stock)
                sector_count[sector] = sector_count.get(sector, 0) + 1

            elif stage == "mid" and len(mid_stage) < MID_STAGE_COUNT:
                mid_stage.append(stock)
                sector_count[sector] = sector_count.get(sector, 0) + 1

            # 两个池子都满了就停止
            if len(early_stage) >= EARLY_STAGE_COUNT and len(mid_stage) >= MID_STAGE_COUNT:
                break

        pool_stocks = early_stage + mid_stage

        # 保存到数据库
        for stock in pool_stocks:
            self.db.add_to_pool({
                "code": stock["code"],
                "name": stock["name"],
                "sector": stock.get("sector", ""),
                "sub_sector": stock.get("sub_sector", ""),
                "market_cap": stock.get("market_cap", 0),
                "pe_ttm": stock.get("pe_ttm", 0),
                "pb": stock.get("pb", 0),
                "phase": "early" if stock in early_stage else "mid",
                "main_wave_start_date": stock.get("main_wave_start_date"),
                "main_wave_gain": stock.get("main_wave_gain", 0),
                "main_force_phase": stock.get("main_force_phase", 1),
                "entry_price": stock.get("price", 0),
                "hot_topics": stock.get("hot_topics", []),
                "institution_rating": stock.get("institution_rating", ""),
                "risk_score": stock.get("risk_score", 50),
                "volume_trend": stock.get("volume_trend", ""),
                "fund_flow_20d": stock.get("fund_flow_20d", 0),
            })

        return {
            "early_stage": early_stage,
            "mid_stage": mid_stage,
            "total": len(pool_stocks),
            "sectors": sector_count,
        }

    def _evaluate_stock(self, code: str) -> dict:
        """评估单只股票的综合得分"""
        # 1. 获取基础数据
        quotes = tencent_quote([code])
        if code not in quotes:
            return None
        q = quotes[code]

        name = q.get("name", "")
        price = q.get("price", 0)
        mcap = q.get("mcap_yi", 0)
        pe = q.get("pe_ttm", 0)
        pb = q.get("pb", 0)
        turnover = q.get("turnover_pct", 0)

        # 2. 基本过滤
        if mcap < MIN_MARKET_CAP or mcap > MAX_MARKET_CAP:
            return None
        if pe > MAX_PE_TTM and pe > 0:
            return None

        # 3. 主力阶段分析
        force_result = self.main_force.analyze(code)
        phase = force_result["phase"]
        stage, stage_detail = self.main_force.is_main_wave(code)

        # 只保留主升浪启动或中期
        if stage not in ["early", "mid"]:
            return None

        # 4. 资金流分析
        fund_flows = get_fund_flow_120d(code)
        fund_20d = sum(f.get("main_net", 0) for f in fund_flows[-20:]) / 1e8 if fund_flows else 0

        # 5. 综合评分
        score = self._calc_score(code, name, price, mcap, pe, pb, turnover,
                                 force_result, fund_20d, stage)

        return {
            "code": code,
            "name": name,
            "price": price,
            "market_cap": mcap,
            "pe_ttm": pe,
            "pb": pb,
            "turnover_pct": turnover,
            "main_force_phase": phase,
            "main_force_phase_name": force_result["phase_name"],
            "main_wave_stage": stage,
            "main_wave_gain": force_result.get("price_position", {}).get("price_vs_ma60_pct", 0),
            "fund_flow_20d": round(fund_20d, 2),
            "volume_trend": force_result.get("volume_analysis", {}).get("recent_volume_trend", ""),
            "risk_score": 50 - (force_result["confidence"] * 0.3),
            "hot_topics": [],
            "total_score": score,
        }

    def _calc_score(self, code, name, price, mcap, pe, pb, turnover,
                   force_result, fund_20d, stage) -> float:
        """计算综合评分(0-100)"""
        score = 0

        # 1. 主力阶段得分 (0-30分)
        phase = force_result["phase"]
        phase_score = {3: 30, 4: 25, 1: 10, 2: 15, 5: 5, 6: 0}
        score += phase_score.get(phase, 0)

        # 2. 主力分析置信度 (0-15分)
        confidence = force_result["confidence"]
        score += confidence * 0.15

        # 3. 资金流得分 (0-20分)
        if fund_20d > 5:
            score += 20
        elif fund_20d > 2:
            score += 15
        elif fund_20d > 0.5:
            score += 10
        elif fund_20d > 0:
            score += 5
        elif fund_20d < -1:
            score -= 10

        # 4. 均线多头排列得分 (0-15分)
        ma_position = force_result.get("ma_position", {})
        if all(ma_position.values()):
            score += 15
        elif ma_position.get("price_above_ma20"):
            score += 8

        # 5. 换手率得分 (0-10分)
        if 3 <= turnover <= 10:
            score += 10
        elif turnover < 3:
            score += 5

        # 6. 估值得分 (0-10分)
        if 0 < pe <= 30:
            score += 10
        elif 0 < pe <= 60:
            score += 6
        elif pe > 60:
            score += 2

        return min(100, max(0, round(score, 1)))

    def get_hot_sector_candidates(self) -> list:
        """从热门板块中提取候选股票"""
        sectors = get_hot_sectors()
        candidates = []

        for sector in sectors[:15]:
            leader = sector.get("leader", "")
            code = sector.get("code", "")

            if leader and code:
                candidates.append(code)

            # 避免重复
            if len(candidates) >= 50:
                break

        return list(set(candidates))[:50]
