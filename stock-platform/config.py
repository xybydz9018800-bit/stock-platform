"""
操盘平台 - 全局配置
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 数据库配置
DATABASE_PATH = os.path.join(BASE_DIR, "data", "trading_platform.db")

# 股票池配置
STOCK_POOL_SIZE = 20
EARLY_STAGE_COUNT = 10   # 刚启动主升浪
MID_STAGE_COUNT = 10     # 正在主升浪中
MAX_SAME_SECTOR = 3      # 同一板块最多3只
# 龙头选择标准（优先级从高到低）: 热度最高 → 最先启动 → 资金流入最多
MAX_SAME_SECTOR = 3      # 同一板块最多3只

# 选股条件阈值
MIN_MARKET_CAP = 50      # 最小市值(亿)
MAX_MARKET_CAP = 2000    # 最大市值(亿)
MIN_AVG_VOLUME = 1       # 最小日均成交额(亿)
MAX_PE_TTM = 200         # 最大PE(TTM)

# 主升浪判断参数
MAIN_WAVE_MIN_DAYS = 10      # 最短运行天数
MAIN_WAVE_MIN_GAIN = 0.15    # 最低累计涨幅(15%)
MAIN_WAVE_VOLUME_RATIO = 1.5 # 放量倍数
MAIN_WAVE_MA_ALIGN = True    # 均线多头排列

# 主力分析参数
MAIN_FORCE_BUILD_POSITION_DAYS = 20   # 建仓期最少天数
MAIN_FORCE_VOLUME_SURGE = 2.0         # 放量倍率阈值

# 突破判别参数
BREAKOUT_VOLUME_RATIO = 1.8   # 突破日放量倍率
BREAKOUT_CONFIRM_DAYS = 3     # 突破确认天数
BREAKOUT_RETRACEMENT_MAX = 0.5 # 最大回撤(斐波那契0.5)

# 风险控制参数
MAX_SINGLE_POSITION = 0.20    # 单只股票最大仓位20%
MAX_TOTAL_POSITION = 0.80     # 总仓位上限80%
STOP_LOSS_RATIO = 0.07        # 止损线 -7%
TAKE_PROFIT_RATIO = 0.20      # 止盈线 +20%
TRAILING_STOP_RATIO = 0.05    # 移动止损 5%

# 外部环境预警阈值
VIX_WARNING = 25              # VIX预警线
NORTHBOUND_OUTFLOW_WARN = -50 # 北向资金流出预警(亿)
INDEX_DROP_WARN = -0.02       # 大盘跌幅预警
SECTOR_ROTATION_DAYS = 5      # 板块轮动监测天数

# 集合竞价分析参数
AUCTION_VOLUME_RATIO = 2.0    # 集合竞价量比
AUCTION_PRICE_CHANGE = 0.03   # 集合竞价涨幅阈值
AUCTION_TRUST_RATIO = 0.6     # 委比阈值

# 推荐配置
DAILY_RECOMMEND_COUNT = 2     # 每日推荐数量
PRE_MARKET_TIME = "09:28"     # 推荐时间

# ============================================================
# 双体系龙头选股策略参数
# ============================================================

# ------ 中线价值龙头参数 ------
VALUE_LEADER_MIN_ROE = 15          # 连续3年ROE≥15%
VALUE_LEADER_MAX_DEBT_RATIO = 0.60 # 资产负债率<60%
VALUE_LEADER_MIN_DAILY_AMOUNT = 5  # 日均成交额≥5亿(大盘龙头)
VALUE_LEADER_MAX_PEG = 1.0         # PEG<1
VALUE_LEADER_MAX_PE_PERCENTILE = 30 # PE处于历史30%分位以下
VALUE_LEADER_MAX_POSITION = 0.30   # 单只最大仓位30%
VALUE_LEADER_MAX_HOLDINGS = 3      # 最多持有3个赛道龙头
VALUE_LEADER_HOLD_MONTHS = 6       # 建议持有时间(月)
VALUE_LEADER_SELL_PE_PERCENTILE = 85 # 估值85%分位以上减仓

# 中线龙头卖出条件
VALUE_SELL_CONDITIONS = [
    "赛道景气度拐点向下，行业增速持续下滑",
    "公司基本面恶化：利润/毛利率/现金流连续下滑",
    "估值达历史85%以上高位",
    "跌破120日线且3日无法收回",
]

# ------ 短线情绪龙头参数 ------
SENTIMENT_LEADER_MIN_BOARD_STOCKS = 5  # 龙头拉升需带动板块≥5只涨停
SENTIMENT_LEADER_MIN_TURNOVER = 5      # 主升换手率下限5%
SENTIMENT_LEADER_MAX_TURNOVER = 18     # 主升换手率上限18%
SENTIMENT_LEADER_STOP_LOSS = -0.05     # 短线止损线-5%
SENTIMENT_LEADER_MAX_POSITION = 0.60   # 单只最高60%仓位(主线清晰时)
SENTIMENT_LEADER_NORMAL_POSITION = 0.20 # 震荡市单票≤20%
SENTIMENT_LEADER_MAX_STOCKS = 2        # 最多同时持有2只

# 短线龙头识别标准
SENTIMENT_LEADER_CRITERIA = [
    "板块带动性：率先涨停，拉升后批量跟风",
    "业务纯正：主营贴合主线热点",
    "量价健康：上涨放量回调缩量，换手5%-18%",
    "市场辨识度：板块高度龙/趋势中军",
]

# 短线龙头三类买点
SENTIMENT_BUY_POINTS = {
    "trend_mid": "趋势中军：回踩5/10日线缩量企稳，分时水下承接",
    "limit_emotion": "连板龙头：分歧低吸(低开缩量)/换手回封板",
    "reverse_leader": "反包龙头：前日大分歧，次日高开放量突破前高",
}

# 短线卖出铁律
SENTIMENT_SELL_RULES = [
    "高位放量滞涨：成交额创新高但涨幅不足3%",
    "板块退潮：批量个股大跌，跟风股跌停",
    "连续加速缩量涨停后开板无法回封",
    "低吸买入跌5%无条件止损",
    "打板买入次日低开不冲高/收盘破10日线离场",
]

# 仓位配置比例
PORTFOLIO_ALLOCATION = {
    "value_leader": 0.70,       # 7成中线价值龙头
    "sentiment_leader": 0.30,   # 3成短线情绪龙头
}

# 高景气赛道清单（持续更新）
HIGH_GROWTH_SECTORS = [
    "AI算力", "半导体", "创新药", "军工", "储能",
    "高端制造", "机器人", "自动驾驶", "低空经济",
]

# 消费刚需赛道
CONSUMER_STAPLE_SECTORS = [
    "白酒", "家电", "医疗服务", "食品饮料",
]

# 避坑清单
PITFALL_CHECKS = [
    "跟风杂毛当龙头：只涨不带动板块",
    "中线龙头短线炒：高位透支业绩",
    "脱离赛道只看K线：无行业逻辑支撑",
    "分散持仓过多：>5只无法跟踪",
    "短线死拿不止损：情绪退潮A杀",
    "周期顶部做龙头：景气见顶越持越亏",
]

# API限流配置（东财防封）
EM_MIN_INTERVAL = 1.0         # 东财请求最小间隔(秒)
EM_MAX_BATCH = 5              # 批量请求上限

# 数据缓存
CACHE_TTL_KLINE = 300         # K线缓存5分钟
CACHE_TTL_QUOTE = 60          # 行情缓存1分钟
CACHE_TTL_FUND = 300          # 资金流缓存5分钟

# 图表配色（中国股市：红涨绿跌）
COLOR_UP = "#FF0000"
COLOR_DOWN = "#00AA00"
COLOR_MA5 = "#FFFFFF"
COLOR_MA10 = "#FFFF00"
COLOR_MA20 = "#FF00FF"
COLOR_MA60 = "#00FFFF"

# 板块分类关键词
SECTOR_KEYWORDS = {
    "人工智能": ["AI", "算力", "大模型", "智能", "机器人", "自动驾驶"],
    "新能源": ["光伏", "锂电", "储能", "风电", "氢能", "钠离子"],
    "半导体": ["芯片", "晶圆", "光刻", "封测", "EDA", "存储"],
    "消费电子": ["手机", "可穿戴", "VR", "AR", "MR"],
    "医药生物": ["创新药", "CXO", "医疗器械", "疫苗", "基因"],
    "数字经济": ["数据要素", "信创", "云计算", "大数据", "区块链"],
    "高端制造": ["工业母机", "航空航天", "军工", "精密仪器"],
    "新能源车": ["整车", "零部件", "一体化压铸", "充电桩"],
    "金融": ["银行", "券商", "保险", "金融科技"],
    "消费": ["白酒", "食品", "家电", "免税", "医美"],
}

# 主力操盘阶段定义
MAIN_FORCE_PHASES = {
    1: "建仓期 - 底部区域，成交量温和放大，股价缓慢抬升",
    2: "洗盘期 - 缩量回调，不破关键均线，清洗浮筹",
    3: "主升浪启动 - 放量突破平台，均线多头发散，MACD金叉",
    4: "主升浪中期 - 量价齐升，均线多头排列，趋势强劲",
    5: "主升浪末期 - 高位放量滞涨，MACD顶背离，筹码松动",
    6: "出货期 - 高位放量下跌，跌破关键均线，主力资金流出",
}
