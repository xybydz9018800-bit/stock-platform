"""
操盘平台 - 市场热点检测引擎（从数据库读取已缓存的热点数据）
"""
from datetime import date, timedelta
from config import SECTOR_KEYWORDS, SECTOR_ROTATION_DAYS

class HotSpotEngine:
    """市场热点检测引擎"""

    def __init__(self, db_manager):
        self.db = db_manager

    def analyze(self) -> dict:
        """全面热点分析（从DB读取预设数据）"""
        today = date.today().isoformat()

        # 从数据库读取今日热点
        hot_spots = self.db.get_hot_spots(1)

        # 分析题材热度
        topic_heat = self._analyze_topics_from_spots(hot_spots)

        # 分析板块轮动
        rotation = self._analyze_rotation()

        # 生成热点摘要
        summary = self._generate_summary_from_spots(hot_spots)

        return {
            "date": today,
            "hot_sectors": hot_spots[:10],
            "topic_heat": topic_heat[:10],
            "rotation": rotation,
            "summary": summary,
            "top_news": [],
        }

    def _analyze_topics_from_spots(self, hot_spots: list) -> list:
        """从热点数据中分析题材热度"""
        result = []
        for spot in hot_spots:
            topic = spot.get("topic", "")
            heat = spot.get("heat_score", 50)
            result.append({
                "topic": topic,
                "heat_score": heat,
                "mention_count": spot.get("stock_count", 0),
                "policy_support": spot.get("policy_support", ""),
            })
        result.sort(key=lambda x: x["heat_score"], reverse=True)
        return result

    def _analyze_rotation(self) -> dict:
        """分析板块轮动"""
        past_spots = self.db.get_hot_spots(SECTOR_ROTATION_DAYS)
        sector_changes = {}
        for spot in past_spots:
            topic = spot.get("topic", "")
            change = spot.get("sector_index_change", 0)
            if topic not in sector_changes:
                sector_changes[topic] = []
            sector_changes[topic].append(change)

        rotation_direction = "轮动中"
        if sector_changes:
            recent = list(sector_changes.keys())[:3]
            if len(recent) >= 2:
                rotation_direction = f"资金从{recent[-1]}流向{recent[0]}"

        return {
            "sector_changes": sector_changes,
            "direction": rotation_direction,
            "active_sectors_count": len(sector_changes),
        }

    def _generate_summary_from_spots(self, hot_spots: list) -> dict:
        """生成热点摘要"""
        top5 = [s["topic"] for s in hot_spots[:5]]
        top3 = top5[:3]
        return {
            "top_sectors": top5,
            "top_topics": top3,
            "rotation_direction": "",
            "total_hot_sectors": len(hot_spots),
            "market_focus": top3[0] if top3 else "分散",
        }
