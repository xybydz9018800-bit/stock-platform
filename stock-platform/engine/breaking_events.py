"""
操盘平台 - 突发事件分析引擎
追踪政策/行业/公司/宏观/国际突发事件，分析对持仓影响
"""
from datetime import date
from database.models import get_connection

class BreakingEventEngine:
    """突发事件引擎"""

    def __init__(self, db_manager):
        self.db = db_manager

    def add_event(self, event: dict) -> int:
        """添加突发事件"""
        conn = get_connection()
        try:
            conn.execute("""
                INSERT INTO breaking_events 
                (event_date, event_time, title, event_type, severity, impact_direction,
                 summary, affected_sectors, affected_stocks, impact_analysis,
                 action_suggestion, source, source_url)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                event.get('event_date', date.today().isoformat()),
                event.get('event_time', ''),
                event.get('title', ''),
                event.get('event_type', 'breaking'),
                event.get('severity', 'medium'),
                event.get('impact_direction', 'neutral'),
                event.get('summary', ''),
                event.get('affected_sectors', '[]'),
                event.get('affected_stocks', '[]'),
                event.get('impact_analysis', ''),
                event.get('action_suggestion', ''),
                event.get('source', ''),
                event.get('source_url', ''),
            ))
            conn.commit()
            return conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        finally:
            conn.close()

    def get_recent_events(self, days: int = 7, limit: int = 30) -> list:
        """获取近期突发事件"""
        conn = get_connection()
        try:
            rows = conn.execute("""
                SELECT * FROM breaking_events 
                WHERE event_date >= date('now', ? || ' days')
                ORDER BY severity DESC, event_date DESC, id DESC
                LIMIT ?
            """, (f'-{days}', limit)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_events_by_severity(self) -> dict:
        """按严重程度分组统计"""
        conn = get_connection()
        try:
            result = {}
            for level in ['critical', 'high', 'medium', 'low']:
                cnt = conn.execute(
                    "SELECT COUNT(*) FROM breaking_events WHERE severity=? AND event_date >= date('now','-3 days')",
                    (level,)
                ).fetchone()
                result[level] = cnt[0] if cnt else 0
            return result
        finally:
            conn.close()

    def analyze_pool_impact(self) -> list:
        """分析突发事件对股票池的影响"""
        pool = self.db.get_buy_pool()
        events = self.get_recent_events(3, 20)
        impacts = []

        for s in pool:
            code = s.get('code', '')
            name = s.get('name', '')
            related_events = []
            for e in events:
                stocks = e.get('affected_stocks', '[]')
                if code in stocks or name in stocks:
                    related_events.append({
                        'title': e.get('title', ''),
                        'type': e.get('event_type', ''),
                        'severity': e.get('severity', ''),
                        'direction': e.get('impact_direction', '')
                    })
            if related_events:
                impacts.append({'code': code, 'name': name, 'events': related_events})

        return impacts
