"""
操盘平台 - 数据库模型定义
"""
import sqlite3
import os
from datetime import datetime
from config import DATABASE_PATH

SCHEMA = """
-- ============================================================
-- 三层股票池体系
-- pool_type: buy(买入池) / liquidate(清仓池) / eliminated(淘汰池)
-- ============================================================
CREATE TABLE IF NOT EXISTS stock_pool (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    sector TEXT,
    sub_sector TEXT,
    leader_type TEXT,          -- 龙头类型: value(中线价值)/sentiment(短线情绪)/none
    leader_subtype TEXT,       -- 短线子类型: trend_mid/limit_emotion/reverse
    leader_score REAL,         -- 龙头评分(0-100)
    moat_type TEXT,            -- 护城河类型: 品牌/技术/规模
    market_cap REAL,          -- 市值(亿)
    pe_ttm REAL,              -- 市盈率
    pb REAL,                  -- 市净率
    pool_type TEXT DEFAULT 'buy',  -- 池类型: buy(买入) / liquidate(清仓) / eliminated(淘汰) / ths_sync(同花顺同步)
    phase TEXT,               -- 阶段: early(刚启动) / mid(主升浪中) / watch(观察)
    main_wave_start_date TEXT, -- 主升浪启动日期
    main_wave_gain REAL,      -- 主升浪累计涨幅
    main_force_phase INTEGER, -- 主力操盘阶段(1-6)
    entry_price REAL,         -- 入选买入池价格
    entry_date TEXT,          -- 入选买入池日期
    hot_topics TEXT,          -- 关联热点(JSON数组)
    institution_rating TEXT,  -- 机构评级
    risk_score REAL,          -- 风险评分(0-100, 越低越安全)
    total_score REAL,         -- 综合评分(0-100, 越高越好)
    volume_trend TEXT,        -- 成交量趋势
    fund_flow_20d REAL,       -- 近20日主力资金净流入(亿)
    -- 淘汰追踪字段
    eliminated_date TEXT,     -- 被淘汰日期
    eliminated_price REAL,    -- 被淘汰时价格
    eliminated_reason TEXT,   -- 淘汰原因
    replaced_by_code TEXT,    -- 被哪只股票替换
    replaced_by_name TEXT,    -- 替换股票名称
    eliminated_total_score REAL, -- 淘汰时的综合评分
    -- 清仓追踪字段
    liquidate_date TEXT,      -- 移入清仓池日期
    liquidate_price REAL,     -- 移入清仓池时价格
    liquidate_reason TEXT,    -- 清仓原因
    -- 复盘评分(淘汰/清仓后可填)
    review_evaluation TEXT,   -- 复盘评价: correct(正确)/wrong(错误)/uncertain(不确定)
    review_notes TEXT,        -- 复盘笔记
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT DEFAULT (datetime('now', 'localtime'))
);

-- 每日推荐记录（增强版：含实时追踪+7天表现）
CREATE TABLE IF NOT EXISTS daily_recommendation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,           -- 推荐日期
    recommend_time TEXT,          -- 推荐时间 HH:MM
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    reason TEXT,                  -- 推荐理由（详细）
    buy_price REAL,               -- 建议买入价
    recommend_price REAL,         -- 推荐时实时价格
    stop_loss_price REAL,         -- 止损价
    take_profit_price REAL,       -- 止盈价
    confidence TEXT,              -- 信心等级: high/medium/low
    auction_analysis TEXT,        -- 集合竞价分析
    technical_signals TEXT,       -- 技术信号
    fund_flow_signal TEXT,        -- 资金流向信号
    hot_topic_support TEXT,       -- 热点支撑
    status TEXT DEFAULT 'pending', -- pending/bought/sold/expired
    -- 当日表现追踪
    intraday_high REAL,           -- 当日最高价
    intraday_low REAL,            -- 当日最低价
    intraday_close REAL,          -- 当日收盘价
    intraday_gain_pct REAL,       -- 推荐后当天涨幅%
    -- 7日表现追踪（逐日记录JSON）
    day1_gain REAL,               -- 第1天收益%
    day2_gain REAL,               -- 第2天收益%  ...  day7_gain
    day3_gain REAL,
    day4_gain REAL,
    day5_gain REAL,
    day6_gain REAL,
    day7_gain REAL,
    max_gain_7d REAL,             -- 7日内最大收益%
    max_loss_7d REAL,             -- 7日内最大回撤%
    tracking_updated TEXT,        -- 追踪数据最后更新时间
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);

-- 交易记录
CREATE TABLE IF NOT EXISTS trade_record (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recommendation_id INTEGER,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    buy_date TEXT,
    buy_price REAL,
    shares INTEGER,
    sell_date TEXT,
    sell_price REAL,
    profit_loss REAL,         -- 盈亏金额
    profit_loss_pct REAL,     -- 盈亏百分比
    hold_days INTEGER,        -- 持仓天数
    max_profit_pct REAL,      -- 最大浮盈
    max_loss_pct REAL,        -- 最大浮亏
    exit_reason TEXT,         -- 卖出原因
    strategy_tag TEXT,        -- 策略标签
    review_notes TEXT,        -- 复盘笔记
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);

-- ============================================================
-- 模拟交易记录表
-- ============================================================
CREATE TABLE IF NOT EXISTS sim_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date TEXT NOT NULL,       -- 交易日期
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    pool_phase TEXT,                -- 池类型: early/mid
    buy_price REAL NOT NULL,        -- 买入价（开盘价）
    buy_time TEXT,                  -- 买入时间
    shares INTEGER DEFAULT 1000,    -- 模拟买入股数
    amount REAL,                    -- 买入金额
    sell_price REAL,                -- 卖出价
    sell_time TEXT,                 -- 卖出时间
    sell_date TEXT,                 -- 卖出日期
    profit_loss REAL,               -- 盈亏金额
    profit_loss_pct REAL,           -- 盈亏百分比
    max_gain_pct REAL,              -- 持仓期间最大涨幅
    max_loss_pct REAL,              -- 持仓期间最大跌幅
    hold_days INTEGER,              -- 持仓天数
    sell_reason TEXT,               -- 卖出原因: stop_loss/trailing_stop/manual/expired
    status TEXT DEFAULT 'holding',  -- holding/sold
    score_at_buy REAL,              -- 买入时评分
    score_at_sell REAL,             -- 卖出时评分
    notes TEXT,                     -- 备注
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_sim_trades_date ON sim_trades(trade_date);
CREATE INDEX IF NOT EXISTS idx_sim_trades_status ON sim_trades(status);

-- ============================================================
-- 突发事件追踪表
-- ============================================================
CREATE TABLE IF NOT EXISTS breaking_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_date TEXT NOT NULL,        -- 事件日期
    event_time TEXT,                 -- 事件时间
    title TEXT NOT NULL,             -- 事件标题
    event_type TEXT,                 -- 类型: policy/company/industry/macro/intl/breaking
    severity TEXT DEFAULT 'medium',  -- 严重程度: critical/high/medium/low
    impact_direction TEXT,           -- 影响方向: positive/negative/neutral
    summary TEXT,                    -- 事件摘要
    affected_sectors TEXT,           -- 影响板块(JSON数组)
    affected_stocks TEXT,            -- 影响个股(JSON数组)
    impact_analysis TEXT,            -- 影响分析
    action_suggestion TEXT,          -- 操作建议
    source TEXT,                     -- 来源
    source_url TEXT,                 -- 来源链接
    status TEXT DEFAULT 'active',    -- active/expired
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_breaking_events_date ON breaking_events(event_date);
CREATE INDEX IF NOT EXISTS idx_breaking_events_severity ON breaking_events(severity);

-- 热点追踪
CREATE TABLE IF NOT EXISTS hot_spot_tracker (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    topic TEXT NOT NULL,
    heat_score REAL,          -- 热度评分(0-100)
    stock_count INTEGER,      -- 关联股票数
    leading_stocks TEXT,      -- 领涨股票(JSON)
    sector_index_change REAL, -- 板块指数涨跌幅
    fund_flow REAL,           -- 板块资金净流入(亿)
    news_count INTEGER,       -- 相关新闻数
    sustainability TEXT,      -- 持续性评估: strong/medium/weak
    policy_support TEXT,      -- 政策支撑
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);

-- 市场环境记录
CREATE TABLE IF NOT EXISTS market_environment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    sh_index REAL,            -- 上证指数
    sz_index REAL,            -- 深证成指
    cyb_index REAL,           -- 创业板指
    market_sentiment TEXT,    -- 市场情绪: bullish/neutral/bearish
    northbound_flow REAL,     -- 北向资金净流入(亿)
    total_volume REAL,        -- 全市场成交额(亿)
    up_count INTEGER,         -- 上涨家数
    down_count INTEGER,       -- 下跌家数
    limit_up_count INTEGER,   -- 涨停家数
    limit_down_count INTEGER, -- 跌停家数
    vix_level REAL,           -- 恐慌指数
    risk_warning TEXT,        -- 风险预警(JSON)
    event_impact TEXT,        -- 突发事件影响
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);

-- 策略优化记录
CREATE TABLE IF NOT EXISTS strategy_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    strategy_name TEXT,
    total_trades INTEGER,
    win_rate REAL,
    avg_profit REAL,
    max_profit REAL,
    max_loss REAL,
    sharpe_ratio REAL,
    max_drawdown REAL,
    improvement_notes TEXT,
    params_snapshot TEXT,     -- 参数快照(JSON)
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);

-- 卖出信号记录
CREATE TABLE IF NOT EXISTS sell_signal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    signal_date TEXT NOT NULL,
    signal_type TEXT,         -- stop_loss/take_profit/technical/risk_event
    signal_strength TEXT,     -- strong/medium/weak
    price_at_signal REAL,
    reason TEXT,
    action_taken TEXT DEFAULT 'pending',
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);

-- 预警记录
CREATE TABLE IF NOT EXISTS alert_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_time TEXT DEFAULT (datetime('now', 'localtime')),
    alert_type TEXT,          -- risk/external_event/policy/technical
    level TEXT,               -- critical/warning/info
    title TEXT,
    description TEXT,
    affected_stocks TEXT,     -- 受影响股票(JSON)
    resolved INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);

-- ============================================================
-- VIP持仓池：手动添加的个人持仓
-- ============================================================
CREATE TABLE IF NOT EXISTS vip_holdings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    sector TEXT,
    entry_date TEXT NOT NULL,     -- 建仓日期
    entry_price REAL NOT NULL,    -- 建仓价格
    shares INTEGER NOT NULL,      -- 持股数量
    entry_amount REAL,            -- 建仓金额(entry_price * shares)
    current_price REAL,           -- 当前价格(自动更新)
    current_value REAL,           -- 当前市值(自动更新)
    profit_loss REAL,             -- 浮动盈亏金额(自动更新)
    profit_loss_pct REAL,         -- 浮动盈亏百分比(自动更新)
    max_price REAL,               -- 持仓期间最高价
    max_profit_pct REAL,          -- 最大浮盈百分比
    max_loss_pct REAL,            -- 最大浮亏百分比
    hold_days INTEGER,            -- 持仓天数(自动计算)
    stop_loss_price REAL,         -- 止损价(手动设置)
    take_profit_price REAL,       -- 止盈价(手动设置)
    ai_suggestion TEXT,            -- AI持仓建议
    ai_suggestion_score REAL,      -- AI建议信心评分(0-100)
    ai_suggestion_time TEXT,       -- AI建议生成时间
    swap_suggestion TEXT,          -- 换股建议
    swap_target_code TEXT,         -- 换股目标代码
    swap_target_name TEXT,         -- 换股目标名称
    swap_reason TEXT,              -- 换股理由
    notes TEXT,                    -- 备注
    status TEXT DEFAULT 'holding', -- holding/sold/transferred
    sell_date TEXT,                -- 卖出日期
    sell_price REAL,               -- 卖出价格
    sell_profit_loss REAL,         -- 卖出盈亏
    sell_profit_loss_pct REAL,     -- 卖出盈亏百分比
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT DEFAULT (datetime('now', 'localtime'))
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_stock_pool_code ON stock_pool(code);
CREATE INDEX IF NOT EXISTS idx_stock_pool_pool_type ON stock_pool(pool_type);
CREATE INDEX IF NOT EXISTS idx_stock_pool_phase ON stock_pool(phase);
CREATE INDEX IF NOT EXISTS idx_stock_pool_entry_date ON stock_pool(entry_date);
CREATE INDEX IF NOT EXISTS idx_stock_pool_eliminated_date ON stock_pool(eliminated_date);
CREATE INDEX IF NOT EXISTS idx_recommendation_date ON daily_recommendation(date);
CREATE INDEX IF NOT EXISTS idx_trade_code ON trade_record(code);
CREATE INDEX IF NOT EXISTS idx_trade_date ON trade_record(buy_date);
CREATE INDEX IF NOT EXISTS idx_hot_spot_date ON hot_spot_tracker(date);
CREATE INDEX IF NOT EXISTS idx_market_date ON market_environment(date);
CREATE INDEX IF NOT EXISTS idx_alert_time ON alert_log(alert_time);
CREATE INDEX IF NOT EXISTS idx_sell_signal_code ON sell_signal(code);
CREATE INDEX IF NOT EXISTS idx_vip_holdings_code ON vip_holdings(code);
CREATE INDEX IF NOT EXISTS idx_vip_holdings_status ON vip_holdings(status);

-- ============================================================
-- TDX实时数据缓存表
-- ============================================================
CREATE TABLE IF NOT EXISTS tdx_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    name TEXT,
    fetch_time TEXT DEFAULT (datetime('now','localtime')),
    price REAL,
    change_pct REAL,
    open REAL,
    high REAL,
    low REAL,
    last_close REAL,
    volume INTEGER,
    amount REAL,
    turnover_pct REAL,
    vol_ratio REAL,
    amplitude_pct REAL,
    pe_ttm REAL,
    pb REAL,
    mcap_yi REAL,
    limit_up REAL,
    limit_down REAL,
    -- 盘口数据(JSON: 5档买卖)
    bsp_data TEXT,
    -- 资金流
    fund_inout REAL,
    fund_inout_hb REAL,
    -- 主力阶段缓存
    main_force_phase INTEGER,
    main_force_signals TEXT,
    -- 元数据
    market_status INTEGER,
    source TEXT DEFAULT 'tdx',
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_tdx_cache_code ON tdx_cache(code);
CREATE INDEX IF NOT EXISTS idx_tdx_cache_time ON tdx_cache(fetch_time);
"""

def init_database():
    """初始化数据库"""
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    print(f"数据库已初始化: {DATABASE_PATH}")

def get_connection():
    """获取数据库连接"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.text_factory = str  # 强制UTF-8
    return conn
