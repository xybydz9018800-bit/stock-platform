#!/usr/bin/env python3
"""每日盘前刷新股票池 - 通过TDX筛选结果合并去重，选出20只优质标的写入数据库"""
import sqlite3
import json
from datetime import datetime
from collections import defaultdict

DB_PATH = r"D:\workbud工作空间\2026-06-21-17-55-14\stock-platform\data\trading_platform.db"

# ============================================================
# 原始筛选数据（从TDX Screener收集）
# ============================================================

# MACD金叉 全部190只（已去重，含名称）
MACD_GOLDEN = {
    # Page 1
    "300563": "神宇股份", "300503": "昊志机电", "300812": "易天股份", "300201": "海伦哲",
    "301018": "申菱环境", "301016": "雷尔伟", "300863": "卡倍亿", "301479": "弘景光电",
    "002310": "东方新能", "603577": "汇金通",
    # Page 2
    "300694": "蠡湖股份", "300415": "伊之密", "002841": "视源股份", "920108": "宏海科技",
    "603200": "上海洗霸", "300190": "维尔利", "002456": "欧菲光", "000045": "深纺织A",
    "002993": "奥海科技", "600482": "中国动力", "002865": "钧达股份", "300923": "研奥股份",
    "301275": "汉朔科技", "600100": "同方股份", "300722": "新余国科", "688510": "航亚科技",
    "300730": "科创信息", "600469": "风神股份", "301449": "天溯计量", "300513": "恒实科技",
    "300884": "狄耐克", "603583": "捷昌驱动", "002139": "拓邦股份", "301168": "通灵股份",
    "300855": "图南股份",
    # Page 3
    "300183": "东软载波", "301117": "佳缘科技", "600233": "圆通速递", "605123": "派克新材",
    "002361": "神剑股份", "688775": "影石创新", "688631": "莱斯信息", "301355": "南王科技",
    "688309": "恒誉环保", "601698": "中国卫通", "300455": "航天智装", "605222": "起帆电缆",
    "688290": "景业智能", "601908": "京运通", "300215": "电科院", "300369": "绿盟科技",
    "603076": "乐惠国际", "603197": "保隆科技", "002985": "北摩高科", "300479": "神思电子",
    "603063": "禾望电气", "600509": "天富能源", "600501": "航天晨光", "300133": "华策影视",
    "688070": "纵横股份", "300032": "金龙机电", "300228": "富瑞特装", "301327": "华宝新能",
    "300095": "华伍股份", "300766": "每日互动",
    # Page 4
    "000561": "烽火电子", "300207": "欣旺达", "600586": "金晶科技", "601615": "明阳智能",
    "002298": "中电鑫龙", "600435": "北方导航", "600654": "中安科", "300355": "蒙草生态",
    "002063": "远光软件", "300539": "横河精密", "600860": "京城股份", "002439": "启明星辰",
    "000006": "深振业A", "002663": "普邦股份", "603421": "鼎信通讯", "688819": "天能股份",
    "605117": "德业股份", "002395": "双象股份", "301556": "托普云农", "002315": "焦点科技",
    "300962": "中金辐照", "002218": "拓日新能", "688169": "石头科技", "603628": "清源股份",
    "605333": "沪光股份", "601016": "节能风电", "002554": "惠博普", "000020": "深华发A",
    "001388": "信通电子",
    # Page 5
    "000596": "古井贡酒", "603887": "城地香江", "300778": "新城市", "688660": "电气风电",
    "002045": "国光电器", "300509": "新美星", "601311": "骆驼股份", "300315": "掌趣科技",
    "688712": "北芯生命", "603352": "至信股份", "600438": "通威股份", "603300": "海南华铁",
    "600283": "钱江水利", "002724": "海洋王", "601106": "中国一重", "300359": "全通教育",
    "002749": "国光股份", "600325": "华发股份", "301048": "金鹰重工", "301036": "双乐股份",
    "603613": "国联股份", "000650": "仁和药业", "300960": "通业科技", "300750": "宁德时代",
    "603092": "德力佳", "002163": "海南发展", "600809": "山西汾酒", "002385": "大北农",
    "300111": "向日葵", "002103": "广博股份",
    # Page 6
    "300844": "山水比德", "600662": "外服控股", "603137": "恒尚节能", "603363": "傲农生物",
    "603279": "景津装备", "600576": "祥源文旅", "601595": "上海电影", "605099": "共创草坪",
    "688626": "翔宇医疗", "600066": "宇通客车", "300253": "卫宁健康", "605299": "舒华体育",
    "002035": "华帝股份", "603136": "天目湖", "603836": "海程邦达", "600519": "贵州茅台",
    "600748": "上实发展", "603016": "新宏泰", "601000": "唐山港", "600821": "金开新能",
    "300937": "药易购", "300413": "芒果超媒", "603258": "电魂网络", "001222": "源飞宠物",
    "301009": "可靠股份", "000912": "泸天化", "600085": "同仁堂", "688016": "心脉医疗",
    # Page 7
    "600329": "达仁堂", "605077": "华康股份", "301239": "普瑞眼科", "002629": "仁智股份",
    "600679": "上海凤凰", "300761": "立华股份", "002572": "索菲亚", "600422": "昆药集团",
    "300705": "九典制药", "003006": "百亚股份",
}

# 10日内创新高 + 10日内放量 (11)
NEW_HIGH_VOL = {
    "688286": "敏芯股份", "605178": "时空科技", "002653": "海思科", "688689": "银河微电",
    "688729": "屹唐股份", "688671": "碧兴物联", "688179": "阿拉丁", "300873": "海晨股份",
    "000551": "创元科技", "002972": "科安达", "300506": "名家汇",
}

# KDJ多头排列 + 10日内放量 (67)
KDJ_BULL_VOL = {
    # Page 1
    "920367": "新赣江", "002367": "康力电梯", "688338": "赛科希德", "920662": "方盛股份",
    "000756": "新华制药", "300434": "金石亚药", "300485": "赛升药业", "301520": "万邦医药",
    "600962": "国投中鲁", "603335": "迪生力", "603607": "京华激光", "688105": "诺唯赞",
    "920017": "星昊医药", "920478": "峆一药业", "000541": "佛山照明", "000566": "海南海药",
    "000751": "锌业股份", "000777": "中核科技", "002687": "乔治白", "002728": "特一药业",
    "301051": "信濠光电", "301257": "普蕊斯", "301393": "昊帆生物", "301633": "港迪技术",
    "600129": "太极集团", "600379": "宝光股份", "600405": "动力源", "600468": "百利电气",
    "601108": "财通证券", "603010": "万盛股份",
    # Page 2
    "603407": "长裕集团", "603567": "珍宝岛", "603766": "隆鑫通用", "603983": "丸美生物",
    "605118": "力鼎光电", "688117": "圣诺生物", "688136": "科兴制药", "688286": "敏芯股份",
    "688505": "复旦张江", "688592": "司南导航", "688729": "屹唐股份", "688765": "禾元生物-U",
    "920344": "三元基因", "000017": "深中华A", "000603": "盛达资源", "000776": "广发证券",
    "000818": "航锦科技", "001390": "古麒绒材", "002038": "双鹭药业", "002058": "威尔泰",
    "002212": "天融信", "002370": "亚太药业", "002452": "长高电气", "002521": "齐峰新材",
    "002653": "海思科", "002921": "联诚精密", "002972": "科安达", "300046": "台基股份",
    "300077": "国民技术",
    # Page 3
    "300200": "高盟新材", "300255": "常山药业", "300343": "联创股份",
}


def is_st_stock(name):
    """判断是否为ST股票"""
    return 'ST' in name.upper() or '*ST' in name


def build_candidate_pool():
    """合并所有数据源，构建候选池"""
    all_stocks = {}  # code -> {name, macd_golden, new_high_vol, kdj_bull_vol}
    
    # MACD金叉 (最高权重)
    for code, name in MACD_GOLDEN.items():
        if is_st_stock(name):
            continue
        all_stocks[code] = {
            'name': name,
            'macd_golden': True,
            'new_high_vol': False,
            'kdj_bull_vol': False,
        }
    
    # 创新高+放量
    for code, name in NEW_HIGH_VOL.items():
        if is_st_stock(name):
            continue
        if code in all_stocks:
            all_stocks[code]['new_high_vol'] = True
            if not all_stocks[code]['name']:
                all_stocks[code]['name'] = name
        else:
            all_stocks[code] = {
                'name': name,
                'macd_golden': False,
                'new_high_vol': True,
                'kdj_bull_vol': False,
            }
    
    # KDJ多头+放量
    for code, name in KDJ_BULL_VOL.items():
        if is_st_stock(name):
            continue
        if code in all_stocks:
            all_stocks[code]['kdj_bull_vol'] = True
            if not all_stocks[code].get('name'):
                all_stocks[code]['name'] = name
        else:
            all_stocks[code] = {
                'name': name,
                'macd_golden': False,
                'new_high_vol': False,
                'kdj_bull_vol': True,
            }
    
    return all_stocks


def score_candidate(info):
    """综合评分：基于信号强度和叠加程度"""
    score = 0
    detail = []
    
    # 基础分：MACD金叉
    if info['macd_golden']:
        score += 15
        detail.append("MACD金叉")
    
    # 叠加分：创新高+放量（主升浪特征）
    if info['new_high_vol']:
        score += 20
        detail.append("创新高+放量")
    
    # 叠加分：KDJ多头+放量
    if info['kdj_bull_vol']:
        score += 10
        detail.append("KDJ多头+放量")
    
    # 综合叠加加分（完美共振）
    combo = info['macd_golden'] + info['new_high_vol'] + info['kdj_bull_vol']
    if combo >= 3:
        score += 20  # 三信号完美共振
        detail.append("三信号共振+20")
    elif combo >= 2:
        score += 8   # 双信号叠加
        detail.append("双信号叠加+8")
    
    return score, '; '.join(detail)


def select_top_20(candidates):
    """从候选池选出前20只，分early/mid"""
    scored = []
    for code, info in candidates.items():
        sc, det = score_candidate(info)
        scored.append((code, info['name'], sc, det, info))
    
    # 按得分降序排列
    scored.sort(key=lambda x: -x[2])
    
    # 候选池去重后还需进一步筛选：优先选高分+有热点逻辑的
    selected = []
    
    priority_tags = ['三信号共振', '创新高+放量', '双信号叠加']
    
    for tag in priority_tags:
        for s in scored:
            if len(selected) >= 20:
                break
            if tag in s[3] and s[0] not in [x[0] for x in selected]:
                selected.append(s)
    
    # 如果还不足20，补充剩余高分
    for s in scored:
        if len(selected) >= 20:
            break
        if s[0] not in [x[0] for x in selected]:
            selected.append(s)
    
    # 前10只标记为mid（主升浪中期/强势），后10只为early（早期/刚启动）
    # 实际逻辑：分数>=30为mid，否则early
    mid_pool = []
    early_pool = []
    
    for s in selected:
        if s[2] >= 30:
            mid_pool.append(s)
        else:
            early_pool.append(s)
    
    # 保证mid不超过10只，early补足10只
    mid_pool = mid_pool[:10]
    while len(mid_pool) < 10 and early_pool:
        mid_pool.append(early_pool.pop(0))
    
    early_pool = early_pool[:10]
    
    return mid_pool, early_pool


def write_to_db(mid_pool, early_pool):
    """写入数据库stock_pool表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 清除buy池的已有记录
    cursor.execute("DELETE FROM stock_pool WHERE pool_type='buy'")
    deleted = cursor.rowcount
    print(f"清除了 {deleted} 条旧的buy池记录")
    
    # 插入mid池（主升浪中期）
    for rank, s in enumerate(mid_pool):
        code, name, score, detail, info = s
        cursor.execute("""
            INSERT INTO stock_pool 
            (code, name, pool_type, phase, total_score, volume_trend, 
             hot_topics, created_at, updated_at)
            VALUES (?, ?, 'buy', 'mid', ?, ?, ?, ?, ?)
        """, (
            code, name, score,
            detail,
            f"TDX筛选共振-{detail}",
            now, now
        ))
        print(f"  [mid #{rank+1}] {code} {name} score={score} - {detail}")
    
    # 插入early池（刚启动）
    for rank, s in enumerate(early_pool):
        code, name, score, detail, info = s
        cursor.execute("""
            INSERT INTO stock_pool 
            (code, name, pool_type, phase, total_score, volume_trend, 
             hot_topics, created_at, updated_at)
            VALUES (?, ?, 'buy', 'early', ?, ?, ?, ?, ?)
        """, (
            code, name, score,
            detail,
            f"TDX筛选共振-{detail}",
            now, now
        ))
        print(f"  [early #{rank+1}] {code} {name} score={score} - {detail}")
    
    conn.commit()
    
    # 验证
    cursor.execute("SELECT COUNT(*) FROM stock_pool WHERE pool_type='buy'")
    count = cursor.fetchone()[0]
    print(f"\n买入池共 {count} 只股票写入成功")
    
    # 输出板块分布
    cursor.execute("""
        SELECT phase, COUNT(*) as cnt FROM stock_pool 
        WHERE pool_type='buy' GROUP BY phase
    """)
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]}只")
    
    conn.close()
    return count


def main():
    print("=" * 60)
    print(f"  每日盘前股票池刷新 - {datetime.now().strftime('%Y-%m-%d')}")
    print("=" * 60)
    
    # Step 1: 构建候选池
    print("\n[1/4] 构建候选池...")
    candidates = build_candidate_pool()
    print(f"  候选池共 {len(candidates)} 只股票（已排除ST）")
    
    # Stats
    macd_count = sum(1 for v in candidates.values() if v['macd_golden'])
    nhv_count = sum(1 for v in candidates.values() if v['new_high_vol'])
    kdj_count = sum(1 for v in candidates.values() if v['kdj_bull_vol'])
    combo3 = sum(1 for v in candidates.values() if v['macd_golden'] and v['new_high_vol'] and v['kdj_bull_vol'])
    combo2 = sum(1 for v in candidates.values() if sum([v['macd_golden'], v['new_high_vol'], v['kdj_bull_vol']]) >= 2)
    print(f"  MACD金叉: {macd_count} | 创新高+放量: {nhv_count} | KDJ多头+放量: {kdj_count}")
    print(f"  三信号共振: {combo3} | 双信号叠加: {combo2}")
    
    # Step 2: 评分排序
    print("\n[2/4] 综合评分排序...")
    mid_pool, early_pool = select_top_20(candidates)
    
    # Step 3: 与当前池对比
    print("\n[3/4] 与当前股票池对比...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT code, name, phase, total_score FROM stock_pool WHERE pool_type='buy' ORDER BY phase, total_score DESC")
    old_pool = {row[0]: (row[1], row[2], row[3]) for row in cursor.fetchall()}
    conn.close()
    
    new_codes = set(s[0] for s in mid_pool + early_pool)
    old_codes = set(old_pool.keys())
    
    retained = old_codes & new_codes
    new_in = new_codes - old_codes
    removed = old_codes - new_codes
    
    print(f"  保留: {len(retained)}只 | 新增: {len(new_in)}只 | 淘汰: {len(removed)}只")
    if new_in:
        print(f"  新入选: {', '.join(sorted(new_in))}")
    if removed:
        print(f"  已淘汰: {', '.join(sorted(removed))}")
    
    # Step 4: 写入数据库
    print("\n[4/4] 写入数据库...")
    count = write_to_db(mid_pool, early_pool)
    
    # 汇总
    print("\n" + "=" * 60)
    print(f"  股票池刷新完成！共 {count} 只股票")
    print(f"  mid（主升浪中期）: {len(mid_pool)}只")
    print(f"  early（刚启动）: {len(early_pool)}只")
    
    mid_codes = [f"{s[0]}({s[1]})" for s in mid_pool]
    early_codes = [f"{s[0]}({s[1]})" for s in early_pool]
    print(f"\n  MID: {', '.join(mid_codes)}")
    print(f"  EARLY: {', '.join(early_codes)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
