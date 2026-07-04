"""
操盘平台 - 同花顺自选股同步引擎
从同花顺 SelfStockCache.json 读取自选股，同步到平台
"""
import json, os, glob
from datetime import date
from database.models import get_connection
from engine.data_fetcher import tencent_quote

THS_USER_PATH = "D:/同花顺远航版/bin/users"

def find_ths_cache() -> str:
    """查找同花顺自选股缓存文件"""
    if not os.path.exists(THS_USER_PATH):
        return ""
    for d in os.listdir(THS_USER_PATH):
        fpath = os.path.join(THS_USER_PATH, d, "SelfStockCache.json")
        if os.path.exists(fpath):
            return fpath
    return ""

def parse_ths_stocks(filepath: str = None) -> list:
    """解析同花顺自选股JSON → 股票代码列表"""
    if not filepath:
        filepath = find_ths_cache()
    if not filepath or not os.path.exists(filepath):
        return []

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    raw = data.get("Data", {}).get("Selfstock", "")
    if not raw:
        return []

    comma_idx = raw.index(',')
    codes_raw = raw[:comma_idx]
    markets_raw = raw[comma_idx+1:]

    codes = [c for c in codes_raw.split('|') if c.strip()]
    markets = [m for m in markets_raw.split('|') if m.strip()]

    # A股市场代码
    a_markets = {'17', '33', '36', '48', '151'}
    a_stocks = []
    for i, c in enumerate(codes):
        m = markets[i] if i < len(markets) else '?'
        if m in a_markets:
            a_stocks.append(c)

    return a_stocks

def sync_ths_to_pool(db) -> dict:
    """同步同花顺自选股到平台数据库"""
    codes = parse_ths_stocks()
    if not codes:
        return {"success": False, "message": "未找到同花顺自选股数据，请确认同花顺已安装且登录"}

    today = date.today().isoformat()
    conn = get_connection()

    try:
        # 清除旧的ths_sync池
        conn.execute("DELETE FROM stock_pool WHERE pool_type='ths_sync'")

        # 批量获取行情+名称
        batch_size = 50
        total_added = 0
        for i in range(0, len(codes), batch_size):
            batch = codes[i:i+batch_size]
            quotes = tencent_quote(batch)

            for code in batch:
                q = quotes.get(code, {})
                name = q.get("name", code)
                price = q.get("price", 0)
                mcap = q.get("mcap_yi", 0)
                pe = q.get("pe_ttm", 0)
                pb = q.get("pb", 0)
                change_pct = q.get("change_pct", 0)
                turnover = q.get("turnover_pct", 0)

                conn.execute("""
                    INSERT INTO stock_pool 
                    (code, name, sector, entry_price, entry_date, pool_type, phase,
                     total_score, market_cap, pe_ttm, pb, main_wave_gain, risk_score,
                     updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now','localtime'))
                """, (code, name or code, "自选", price or 0, today, "ths_sync",
                     "watch", 50, mcap, pe, pb, change_pct or 0, 30))
                total_added += 1

        conn.commit()
        return {
            "success": True,
            "total": total_added,
            "message": f"已同步{total_added}只同花顺自选股",
            "date": today,
        }
    except Exception as e:
        return {"success": False, "message": f"同步失败: {e}"}
    finally:
        conn.close()

def get_ths_pool(db) -> list:
    """获取同花顺同步池"""
    return db.get_pool_by_type("ths_sync")
