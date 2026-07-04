"""
每日盘前刷新股票池脚本 - 2026-06-28
从TDX screener结果中筛选20只（10early+10mid），写入数据库
"""
import sqlite3
import os
import sys
from datetime import datetime

DB_PATH = r'D:\workbud工作空间\2026-06-21-17-55-14\stock-platform\data\trading_platform.db'
TODAY = datetime.now().strftime('%Y-%m-%d')
ENTRY_TIME = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

# ============================================================
# 最终选股结果（基于TDX screener 3轮查询 + 人工评分）
# ============================================================

# MID池（主升浪中，资金强、信号多）
mid_pool = [
    {"code": "300088", "name": "长信科技",     "sector": "MiniLED",   "flow": 599059200,   "price": 11.67,  "chg": 13.41, "score": 96.7, "signals": "涨停;创新高;放量;强势"},
    {"code": "605358", "name": "立昂微",       "sector": "半导体硅片", "flow": 294300832,   "price": 75.37,  "chg": 6.91,  "score": 88.4, "signals": "创新高;放量;强势"},
    {"code": "001389", "name": "广合科技",     "sector": "PCB",       "flow": 266337360,   "price": 220.88, "chg": 10.00, "score": 95.0, "signals": "涨停;创新高;放量"},
    {"code": "300162", "name": "雷曼光电",     "sector": "MicroLED",  "flow": 263981648,   "price": 12.13,  "chg": 19.98, "score": 90.0, "signals": "涨停;放量"},
    {"code": "300776", "name": "帝尔激光",     "sector": "光伏设备",   "flow": 236676352,   "price": 194.50, "chg": 8.54,  "score": 82.8, "signals": "创新高;放量"},
    {"code": "300260", "name": "新莱应材",     "sector": "半导体设备", "flow": 183039504,   "price": 92.90,  "chg": 14.54, "score": 85.0, "signals": "创新高;放量;强势"},
    {"code": "688432", "name": "有研硅",       "sector": "半导体硅片", "flow": 180640992,   "price": 30.90,  "chg": 20.00, "score": 92.0, "signals": "涨停;创新高;强势"},
    {"code": "603989", "name": "艾华集团",     "sector": "元器件",    "flow": 101264448,   "price": 56.00,  "chg": 4.19,  "score": 66.3, "signals": "涨停;创新高"},
    {"code": "002579", "name": "中京电子",     "sector": "PCB",       "flow": 88020888,    "price": 22.78,  "chg": 6.95,  "score": 68.4, "signals": "涨停;创新高;放量"},
    {"code": "688605", "name": "先锋精科",     "sector": "半导体设备", "flow": 68095992,    "price": 99.00,  "chg": 7.06,  "score": 58.6, "signals": "创新高;放量;强势"},
]

# EARLY池（刚启动/底部放量，关注度上升）
early_pool = [
    {"code": "002225", "name": "濮耐股份",     "sector": "建材",      "flow": 69509960,    "price": 4.62,   "chg": 6.94,  "score": 52.4, "signals": "放量;涨停"},
    {"code": "301349", "name": "信德新材",     "sector": "化工",      "flow": 59089964,    "price": 75.60,  "chg": 20.00, "score": 71.0, "signals": "涨停;创新高;MACD金叉"},
    {"code": "002787", "name": "华源控股",     "sector": "化工",      "flow": 0,            "price": 32.47,  "chg": 7.02,  "score": 55.5, "signals": "MACD金叉;涨停;创新高"},
    {"code": "688359", "name": "三孚新科",     "sector": "新材料",    "flow": 58264760,     "price": 188.61, "chg": 9.42,  "score": 55.1, "signals": "创新高;BIAS"},
    {"code": "603678", "name": "火炬电子",     "sector": "军工电子",  "flow": 53029608,     "price": 79.49,  "chg": 5.80,  "score": 58.7, "signals": "涨停;创新高;强势"},
    {"code": "603800", "name": "洪田股份",     "sector": "设备制造",  "flow": 0,            "price": 88.46,  "chg": 4.13,  "score": 51.2, "signals": "MACD金叉;涨停;创新高;强势"},
    {"code": "300219", "name": "鸿利智汇",     "sector": "MiniLED",   "flow": 33482216,     "price": 10.05,  "chg": 5.24,  "score": 45.9, "signals": "创新高;放量"},
    {"code": "002668", "name": "TCL智家",      "sector": "家电",      "flow": 29163090,     "price": 11.00,  "chg": 7.00,  "score": 46.5, "signals": "放量;BIAS;CCI"},
    {"code": "688448", "name": "磁谷科技",     "sector": "通用设备",  "flow": 0,            "price": 58.90,  "chg": 9.09,  "score": 48.6, "signals": "MACD金叉;创新高;放量"},
    {"code": "603661", "name": "恒林股份",     "sector": "家具",      "flow": 22054390,     "price": 40.06,  "chg": 7.40,  "score": 58.1, "signals": "涨停;创新高;强势"},
]

# 淘汰池（本次落选）
eliminated = [
    {"code": "603155", "name": "新亚强",  "reason": "主力资金为零，走弱", "old_phase": "early"},
    {"code": "300264", "name": "佳创视讯", "reason": "主力资金为零，走弱", "old_phase": "early"},
    {"code": "600962", "name": "国投中鲁", "reason": "主力资金为零，走弱", "old_phase": "early"},
    {"code": "300668", "name": "杰恩股份", "reason": "主力资金为零，走弱", "old_phase": "early"},
    {"code": "688061", "name": "灿瑞科技", "reason": "主力净流入仅1864万，评分偏低", "old_phase": "new"},
    {"code": "688665", "name": "四方光电", "reason": "主力净流入仅1186万，评分偏低", "old_phase": "early"},
]


def refresh_pool():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # ---- Step 1: 获取旧买池中将被淘汰的股票信息 ----
    old_codes = [e["code"] for e in eliminated]
    placeholders = ','.join(['?' for _ in old_codes])
    cur.execute(f"SELECT code, name, phase, total_score, entry_price FROM stock_pool WHERE pool_type='buy' AND code IN ({placeholders})", old_codes)
    old_info = {r['code']: dict(r) for r in cur.fetchall()}

    # ---- Step 2: 清空买入池(移到淘汰池) ----
    # 先处理淘汰的
    for e in eliminated:
        info = old_info.get(e['code'])
        repl_code = "002225" if e['code'] == "603155" else \
                    "002787" if e['code'] == "300264" else \
                    "603800" if e['code'] == "600962" else \
                    "300219" if e['code'] == "300668" else \
                    "688448" if e['code'] == "688061" else \
                    "603661" if e['code'] == "688665" else ""
        repl_name = "濮耐股份" if e['code'] == "603155" else \
                    "华源控股" if e['code'] == "300264" else \
                    "洪田股份" if e['code'] == "600962" else \
                    "鸿利智汇" if e['code'] == "300668" else \
                    "磁谷科技" if e['code'] == "688061" else \
                    "恒林股份" if e['code'] == "688665" else ""

        if info:
            # 股票已在买入池 → 移到淘汰池
            cur.execute("""
                UPDATE stock_pool SET
                    pool_type = 'eliminated',
                    eliminated_date = ?,
                    eliminated_reason = ?,
                    replaced_by_code = ?,
                    replaced_by_name = ?,
                    eliminated_total_score = ?,
                    updated_at = ?
                WHERE code = ? AND pool_type = 'buy'
            """, (TODAY, e['reason'], repl_code, repl_name,
                  info.get('total_score'), ENTRY_TIME, e['code']))
        else:
            # 新候选但未采用 → 不需要处理（没入库）
            pass

    # ---- Step 3: 其他保留的旧池股票先不处理，后续UPDATE ----
    keep_codes = [s['code'] for s in mid_pool + early_pool]

    # ---- Step 4: 插入/更新mid池 ----
    for s in mid_pool:
        cur.execute("SELECT id FROM stock_pool WHERE code=? AND pool_type='buy'", (s['code'],))
        exists = cur.fetchone()
        if exists:
            cur.execute("""
                UPDATE stock_pool SET
                    phase = 'mid',
                    entry_price = COALESCE(NULLIF(entry_price,0), ?),
                    fund_flow_20d = ?,
                    total_score = ?,
                    hot_topics = ?,
                    updated_at = ?
                WHERE code = ? AND pool_type = 'buy'
            """, (s['price'], s['flow'], s['score'], s['signals'], ENTRY_TIME, s['code']))
        else:
            cur.execute("""
                INSERT INTO stock_pool (code, name, sector, pool_type, phase,
                    entry_price, entry_date, fund_flow_20d, total_score,
                    hot_topics, risk_score, created_at, updated_at)
                VALUES (?, ?, ?, 'buy', 'mid', ?, ?, ?, ?, ?, 20, ?, ?)
            """, (s['code'], s['name'], s['sector'], s['price'], TODAY,
                  s['flow'], s['score'], s['signals'], ENTRY_TIME, ENTRY_TIME))

    # ---- Step 5: 插入/更新early池 ----
    for s in early_pool:
        cur.execute("SELECT id FROM stock_pool WHERE code=? AND pool_type='buy'", (s['code'],))
        exists = cur.fetchone()
        if exists:
            cur.execute("""
                UPDATE stock_pool SET
                    phase = 'early',
                    entry_price = COALESCE(NULLIF(entry_price,0), ?),
                    fund_flow_20d = ?,
                    total_score = ?,
                    hot_topics = ?,
                    updated_at = ?
                WHERE code = ? AND pool_type = 'buy'
            """, (s['price'], s['flow'], s['score'], s['signals'], ENTRY_TIME, s['code']))
        else:
            cur.execute("""
                INSERT INTO stock_pool (code, name, sector, pool_type, phase,
                    entry_price, entry_date, fund_flow_20d, total_score,
                    hot_topics, risk_score, created_at, updated_at)
                VALUES (?, ?, ?, 'buy', 'early', ?, ?, ?, ?, ?, 25, ?, ?)
            """, (s['code'], s['name'], s['sector'], s['price'], TODAY,
                  s['flow'], s['score'], s['signals'], ENTRY_TIME, ENTRY_TIME))

    conn.commit()

    # ---- Step 6: 验证 ----
    cur.execute("SELECT code, name, phase, total_score, fund_flow_20d FROM stock_pool WHERE pool_type='buy' ORDER BY phase, total_score DESC")
    results = cur.fetchall()
    print(f"===== 新股池确认 ({len(results)}只) =====")
    total_flow = 0
    mid_count = 0
    early_count = 0
    sectors = {}
    for r in results:
        phase_tag = "MID" if r['phase']=='mid' else "EARLY"
        print(f"[{phase_tag}] {r['code']} {r['name']:8s} 评分={r['total_score']:.2f} 资金={r['fund_flow_20d']/1e8:.2f}亿")
        total_flow += (r['fund_flow_20d'] or 0)
        if r['phase'] == 'mid':
            mid_count += 1
        else:
            early_count += 1
        # 板块统计
        cur.execute("SELECT sector FROM stock_pool WHERE code=? AND pool_type='buy'", (r['code'],))
        sec = cur.fetchone()
        if sec and sec['sector']:
            sectors[sec['sector']] = sectors.get(sec['sector'], 0) + 1

    print(f"\n----- 统计 -----")
    print(f"Mid池: {mid_count}只 | Early池: {early_count}只")
    print(f"累计主力净流入: {total_flow/1e8:.2f}亿")
    print(f"热门板块: {', '.join([f'{k}({v})' for k,v in sorted(sectors.items(), key=lambda x:-x[1])[:6]])}")

    # 淘汰统计
    cur.execute("SELECT COUNT(*) as cnt FROM stock_pool WHERE pool_type='eliminated' AND eliminated_date=?", (TODAY,))
    elim_count = cur.fetchone()['cnt']
    print(f"今日淘汰: {elim_count}只")

    conn.close()
    return results


if __name__ == '__main__':
    refresh_pool()
    print("\n✅ 股票池刷新完成!")
