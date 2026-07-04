#!/usr/bin/env python3
"""每日盘前刷新股票池 - 2026-07-04"""
import sqlite3
import json
from datetime import datetime

DB_PATH = "D:/workbud工作空间/2026-06-21-17-55-14/stock-platform/data/trading_platform.db"

# ========== 数据源 ==========

# Q1: "放量上攻 均线多头排列 主力净流入 非ST" → 19只 (已验证主力净额)
q1_stocks = [
    {"code":"688017","name":"绿的谐波","price":488.00,"chg":18.15,"flow":1011119872,"signals":"放量上攻,10日内创新高,10日内放量,120日内放量,20日内放量,20日内强势股"},
    {"code":"301379","name":"天山电子","price":32.16,"chg":20.00,"flow":365081792,"signals":"放量上攻,10日内创新高,10日内放量,涨停收盘,120日内放量,20日内放量"},
    {"code":"603662","name":"柯力传感","price":80.00,"chg":8.37,"flow":355100960,"signals":"放量上攻,10日内放量,涨停收盘,20日内放量,20日内强势股,20天内涨停"},
    {"code":"600360","name":"华微电子","price":14.96,"chg":6.10,"flow":320450272,"signals":"放量上攻,10日内创新高,10日内放量,涨停收盘,20日内放量,20天内涨停"},
    {"code":"300503","name":"昊志机电","price":111.00,"chg":16.99,"flow":233873200,"signals":"放量上攻,10日内创新高,10日内放量,涨停收盘,120日内放量,20日内放量"},
    {"code":"688400","name":"凌云光","price":71.41,"chg":9.02,"flow":188986880,"signals":"放量上攻,10日内创新高,10日内放量,20日内放量,CCI超买,CCI上穿100"},
    {"code":"300607","name":"拓斯达","price":52.96,"chg":13.55,"flow":145464528,"signals":"放量上攻,10日内创新高,10日内放量,涨停收盘,120日内放量,20日内放量"},
    {"code":"301603","name":"乔锋智能","price":159.99,"chg":10.54,"flow":135358288,"signals":"放量上攻,10日内创新高,10日内放量,120日内放量,20日内放量,20日内强势股,MACD金叉"},
    {"code":"301232","name":"飞沃科技","price":182.00,"chg":11.69,"flow":102211456,"signals":"放量上攻,10日内创新高,10日内放量,120日内放量,20日内放量,20日内强势股"},
    {"code":"603087","name":"甘李药业","price":60.99,"chg":6.53,"flow":99233080,"signals":"放量上攻,CCI超买,EXPMA金叉,KDJ多头排列,KDJ拐头向上,MACD多头排列"},
    {"code":"603638","name":"艾迪精密","price":27.90,"chg":7.85,"flow":82814120,"signals":"放量上攻,10日内创新高,10日内放量,涨停收盘,20日内强势股,20天内涨停"},
    {"code":"603903","name":"中持股份","price":14.15,"chg":8.10,"flow":55168320,"signals":"放量上攻,10日内放量,涨停收盘,20日内强势股,20天内涨停,60日内阴多阳少"},
    {"code":"002860","name":"星帅尔","price":15.96,"chg":7.84,"flow":42932816,"signals":"放量上攻,10日内放量,20日内放量,20天内涨停,60日内阳多阴少,CCI超买"},
    {"code":"300508","name":"维宏股份","price":60.81,"chg":6.27,"flow":33823876,"signals":"放量上攻,10日内创新高,10日内放量,120日内放量,20日内放量,20日内强势股,MACD金叉"},
    {"code":"301067","name":"显盈科技","price":37.97,"chg":6.93,"flow":31366536,"signals":"放量上攻,10日内放量,120日内放量,20日内放量,60日内放量,BIAS金叉"},
    {"code":"002901","name":"大博医疗","price":45.37,"chg":4.16,"flow":19862162,"signals":"放量上攻,10日内平台整理,60日内平台整理,CCI超买,KDJ多头排列,MACD多头排列"},
    {"code":"301210","name":"金杨精密","price":32.67,"chg":6.76,"flow":11627564,"signals":"放量上攻,10日内放量,120日内放量,20日内放量,20日内强势股,5日线上穿20日线"},
    {"code":"300878","name":"维康药业","price":39.45,"chg":10.66,"flow":10576613,"signals":"放量上攻,10日内创新高,10日内放量,20日内强势股,BIAS2>12,CCI超买"},
    {"code":"688098","name":"申联生物","price":9.88,"chg":13.30,"flow":8463951,"signals":"放量上攻,BIAS金叉,CCI超买,CCI上穿100,KDJ多头排列,KDJ拐头向上"},
]

# Q3补充: MACD金叉 均线多头 非ST (不在Q1中的)
q3_supplement = [
    {"code":"002520","name":"日发精机","price":7.72,"chg":9.97,"signals":"MACD金叉,10日内放量,涨停收盘,120日内放量,20日内放量,20天内涨停"},
    {"code":"300998","name":"宁波方正","price":29.61,"chg":3.71,"signals":"MACD金叉,10日内放量,20日内放量,BOLL缩口,KDJ多头排列,MACD多头排列"},
    {"code":"300964","name":"本川智能","price":83.40,"chg":0.48,"signals":"MACD金叉,10日内创新高,10日内放量,120日内放量,20日内放量,60日内放量"},
]

# Q5补充: 10日内创新高 + 10日放量 + 非ST (不在Q1中, 排除北交所)
q5_supplement = [
    {"code":"605178","name":"时空科技","price":120.06,"chg":6.93,"signals":"10日内创新高,10日内放量,涨停收盘,20日内放量,20日内强势股"},
    {"code":"300966","name":"共同药业","price":31.07,"chg":8.03,"signals":"10日内创新高,10日内放量,20日内放量,60日内放量,CCI超买"},
    {"code":"603580","name":"艾艾精工","price":30.13,"chg":10.00,"signals":"10日内创新高,涨停收盘,20日内强势股,20天内涨停"},
    {"code":"002167","name":"东方锆业","price":25.04,"chg":-3.88,"signals":"10日内创新高,10日内放量,涨停收盘,120日内放量,100天常涨停"},
    {"code":"301051","name":"信濠光电","price":22.77,"chg":17.07,"signals":"10日内创新高,10日内放量,涨停收盘,20日内放量,20日内强势股"},
    {"code":"603588","name":"高能环境","price":19.80,"chg":5.04,"signals":"10日内创新高,10日内放量,涨停收盘,20日内放量,20日内强势股"},
    {"code":"300932","name":"三友联众","price":11.97,"chg":4.72,"signals":"10日内创新高,10日内放量,120日内放量,20日内放量,BIAS2>12"},
    {"code":"002458","name":"益生股份","price":9.06,"chg":-3.72,"signals":"10日内创新高,10日内放量,涨停收盘,20天内涨停,BOLL张开"},
    {"code":"300163","name":"先锋新材","price":7.50,"chg":15.92,"signals":"10日内创新高,10日内放量,涨停收盘,120日内放量,20日内放量"},
]

# ========== 主力净额排名分位数 (用于补充股票估算) ==========
q1_min_flow = min(s["flow"] for s in q1_stocks)  # ~846万
q1_max_flow = max(s["flow"] for s in q1_stocks)  # ~10.1亿

# ========== 评分系统 ==========
def score_stock(s):
    """综合评分 0-100"""
    score = 0
    sigs = s.get("signals", "")
    flow = s.get("flow", 0)
    chg = s.get("chg", 0)

    # 1. 放量上攻 (最核心信号) +均线多头+主力净流入 → +30
    if "放量上攻" in sigs:
        score += 30

    # 2. 主力净额 (归一化, 最大+15)
    if flow > 0:
        log_flow = __import__("math").log10(max(flow, 1e6))
        log_min = __import__("math").log10(1e6)
        log_max = __import__("math").log10(1e10)
        flow_score = min(15, max(0, (log_flow - log_min) / (log_max - log_min) * 15))
        score += flow_score

    # 3. 10日内创新高 +10
    if "10日内创新高" in sigs:
        score += 10

    # 4. MACD金叉 +8
    if "MACD金叉" in sigs:
        score += 8

    # 5. 当天涨停/接近涨停 +5
    if chg >= 19.9:
        score += 5
    elif chg >= 10:
        score += 3
    elif chg >= 5:
        score += 2

    # 6. 20日内强势股 +5
    if "20日内强势股" in sigs:
        score += 5

    # 7. KDJ多头 +3
    if "KDJ多头排列" in sigs:
        score += 3

    # 8. MACD多头 +3
    if "MACD多头排列" in sigs:
        score += 3

    # 9. 均线金叉类 (EXPMA金叉, 5穿20等) +3
    if "EXPMA金叉" in sigs or "5日线上穿20日线" in sigs:
        score += 3

    # 10. 信号丰富度 (信号数量) +5
    signal_count = len(sigs.split(",")) if sigs else 1
    score += min(5, signal_count)

    # 11. 当日跌幅惩罚
    if chg < -2:
        score -= 5
    elif chg < 0:
        score -= 2

    return round(score, 1)


def classify_phase(s):
    """分类 early/mid"""
    sigs = s.get("signals", "")
    chg = s.get("chg", 0)
    flow = s.get("flow", 0)

    # mid标准: 放量上攻 + (创新高 或 20日内强势股) + 主力净额>3000万
    mid_signals = 0
    if "放量上攻" in sigs:
        mid_signals += 1
    if "10日内创新高" in sigs or "20日内强势股" in sigs:
        mid_signals += 1
    if flow > 30_000_000:
        mid_signals += 1
    if chg > 5:
        mid_signals += 1

    if mid_signals >= 3:
        return "mid"
    return "early"


# ========== 合并所有候选 ==========
all_candidates = {}
seen_codes = set()

for s in q1_stocks:
    all_candidates[s["code"]] = s
    seen_codes.add(s["code"])

for s in q3_supplement:
    if s["code"] not in seen_codes:
        s["flow"] = 0
        all_candidates[s["code"]] = s
        seen_codes.add(s["code"])

for s in q5_supplement:
    if s["code"] not in seen_codes:
        s["flow"] = 0
        all_candidates[s["code"]] = s
        seen_codes.add(s["code"])

# ========== 评分 & 分类 ==========
for code, s in all_candidates.items():
    s["total_score"] = score_stock(s)
    s["phase"] = classify_phase(s)

# 按phase分组排序
mid_candidates = sorted(
    [s for s in all_candidates.values() if s["phase"] == "mid"],
    key=lambda x: x["total_score"], reverse=True
)
early_candidates = sorted(
    [s for s in all_candidates.values() if s["phase"] == "early"],
    key=lambda x: x["total_score"], reverse=True
)

# 选出10mid + 10early
mid_selected = mid_candidates[:10]
early_selected = early_candidates[:10]

# 如果mid不够10只, 从early补充
if len(mid_selected) < 10:
    shortage = 10 - len(mid_selected)
    for s in early_candidates[len(early_selected):]:
        if shortage <= 0:
            break
        s["phase"] = "mid"
        mid_selected.append(s)
        shortage -= 1

# 如果early不够10只, 从剩余mid补充
if len(early_selected) < 10:
    shortage = 10 - len(early_selected)
    for s in mid_candidates[len(mid_selected):]:
        if shortage <= 0:
            break
        s["phase"] = "early"
        early_selected.append(s)
        shortage -= 1

final_pool = mid_selected[:10] + early_selected[:10]

print(f"=== 候选汇总 ===")
print(f"Q1(放量上攻): {len(q1_stocks)}只")
print(f"Q3(MACD金叉补充): {len(q3_supplement)}只")
print(f"Q5(创新高补充): {len(q5_supplement)}只")
print(f"合并去重后: {len(all_candidates)}只")
print(f"mid候选: {len(mid_candidates)}只, early候选: {len(early_candidates)}只")
print()

print("=== MID池(主升浪) 10只 ===")
total_flow = 0
for i, s in enumerate(mid_selected[:10], 1):
    flow_str = f"{s['flow']/1e8:.2f}亿" if s['flow'] > 0 else "N/A"
    total_flow += s['flow']
    print(f"{i:2d}. {s['code']} {s['name']:<6s} ¥{s['price']:<10.2f} +{s['chg']:.2f}% flow={flow_str} score={s['total_score']}")

print()
print("=== EARLY池(刚启动) 10只 ===")
for i, s in enumerate(early_selected[:10], 1):
    flow_str = f"{s['flow']/1e8:.2f}亿" if s['flow'] > 0 else "N/A"
    total_flow += s['flow']
    print(f"{i:2d}. {s['code']} {s['name']:<6s} ¥{s['price']:<10.2f} +{s['chg']:.2f}% flow={flow_str} score={s['total_score']}")

print(f"\n累计主力净流入: {total_flow/1e8:.2f}亿")

# ========== 与当前池对比 ==========
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute("SELECT code, name, phase, total_score FROM stock_pool WHERE pool_type='buy'")
old_pool = {r[0]: {"name": r[1], "phase": r[2], "score": r[3]} for r in cur.fetchall()}

new_codes = {s["code"] for s in final_pool}
old_codes = set(old_pool.keys())

kept = new_codes & old_codes
added = new_codes - old_codes
removed = old_codes - new_codes

print(f"\n=== 池变更 ===")
print(f"保留: {len(kept)}只 → {' '.join(kept)}")
print(f"新增: {len(added)}只 → {' '.join(added)}")
print(f"淘汰: {len(removed)}只 → {' '.join(removed)}")

# ========== 写入数据库 ==========
today = datetime.now().strftime("%Y-%m-%d")

# 1. 将旧的buy池股票移到淘汰池
cur.execute("""
    UPDATE stock_pool SET pool_type='eliminated',
        eliminated_date=?, eliminated_reason='2026-07-04定期刷新替换'
    WHERE pool_type='buy'
""", (today,))
print(f"\n淘汰旧池: {cur.rowcount}只")

# 2. 插入新股池
inserted = 0
for s in final_pool:
    total_flow_billion = s.get("flow", 0) / 1e8 if s.get("flow", 0) > 0 else 0
    cur.execute("""
        INSERT INTO stock_pool (code, name, pool_type, phase, total_score, 
            entry_price, entry_date, fund_flow_20d, created_at, updated_at)
        VALUES (?, ?, 'buy', ?, ?, ?, ?, ?, datetime('now','localtime'), datetime('now','localtime'))
    """, (
        s["code"], s["name"], s["phase"], s["total_score"],
        s["price"], today, round(total_flow_billion, 4)
    ))
    inserted += 1

conn.commit()
conn.close()
print(f"写入新股池: {inserted}只")

print("\n=== DONE ===")
print(f"数据库: {DB_PATH}")
print(f"MID: {len(mid_selected[:10])}只 | EARLY: {len(early_selected[:10])}只")
