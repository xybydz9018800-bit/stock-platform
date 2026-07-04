/**
 * A股操盘平台 - 前端交互逻辑
 */

// ==================== 初始化 ====================
document.addEventListener('DOMContentLoaded', function() {
    initNavigation();
    initPoolTabs();
    updateTime();
    setInterval(updateTime, 10000);
    loadOverview();
    setInterval(loadOverview, 30000);
});

function updateTime() {
    const now = new Date();
    document.getElementById('current-time').textContent =
        now.toLocaleString('zh-CN', {hour:'2-digit',minute:'2-digit',second:'2-digit'});
}

// ==================== 导航 ====================
function initNavigation() {
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
            item.classList.add('active');
            const tab = item.dataset.tab;
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.getElementById('tab-' + tab).classList.add('active');
            switch(tab) {
                case 'overview': loadOverview(); break;
                case 'pool': loadPool(); break;
                case 'vip': loadVipHoldings(); break;
                case 'recommend': loadRecommendations(); break;
                case 'sim': loadSimTrades(); break;
                case 'ths': loadThsPool(); break;
                case 'events': loadEvents(); break;
                case 'risk': checkRisk(); loadHoldingsMonitor(); break;
                case 'trades': loadTrades(); break;
                case 'report': loadPerformanceReport(); break;
                case 'settings': loadSettings(); break;
            }
        });
    });
}

async function refreshAll() {
    loadOverview();
    const activeTab = document.querySelector('.tab-content.active');
    if (activeTab) {
        const tabId = activeTab.id.replace('tab-', '');
        switch(tabId) {
            case 'pool': loadPool(); break;
            case 'vip': loadVipHoldings(); break;
            case 'recommend': loadRecommendations(); break;
            case 'risk': checkRisk(); break;
            case 'trades': loadTrades(); break;
            case 'report': loadPerformanceReport(); break;
        }
    }
}

// ==================== 总览 ====================
async function loadOverview() {
    try {
        const resp = await fetch('/api/overview');
        const data = await resp.json();

        // 指数
        document.getElementById('idx-sh').textContent = (data.indices.sh * 100).toFixed(2) + '%';
        document.getElementById('idx-sz').textContent = (data.indices.sz * 100).toFixed(2) + '%';
        document.getElementById('idx-cyb').textContent = (data.indices.cyb * 100).toFixed(2) + '%';

        // 统计
        document.getElementById('stat-pool-total').textContent = data.pool_stats.total;
        document.getElementById('stat-early').textContent = data.pool_stats.early_count;
        document.getElementById('stat-mid').textContent = data.pool_stats.mid_count;
        document.getElementById('stat-trades').textContent = data.trade_stats.total_trades;
        document.getElementById('stat-winrate').textContent = '胜率 ' + data.trade_stats.win_rate + '%';
        document.getElementById('stat-profit').textContent = '¥' + data.trade_stats.total_profit;
        document.getElementById('stat-risk').textContent = data.risk_env.score;

        // 风险徽章
        const badge = document.getElementById('risk-badge');
        badge.textContent = '风险: ' + data.risk_env.level;
        badge.className = 'risk-badge ' + data.risk_env.level;

        // 预警条
        const alertBar = document.getElementById('alert-bar');
        if (data.risk_env.alerts && data.risk_env.alerts.length > 0) {
            alertBar.style.display = 'flex';
            document.getElementById('alert-message').textContent = data.risk_env.alerts[0].message;
        } else {
            alertBar.style.display = 'none';
        }

        // 加载热点
        loadHotSpots();
        // 加载预警
        loadAlerts();
        // 加载图表
        loadOverviewCharts();

    } catch(e) {
        console.error('加载概览失败:', e);
    }
}

async function loadHotSpots() {
    try {
        const resp = await fetch('/api/analysis/hot_spot');
        const data = await resp.json();
        const container = document.getElementById('hot-sectors-list');
        container.innerHTML = (data.hot_sectors || []).slice(0, 12).map(function(s) {
            var name = s.topic || s.name || '--';
            var chg = s.sector_index_change || s.change_pct || s.heat_score || 0;
            var chgNum = parseFloat(chg) || 0;
            var chgStr = chgNum >= 0 ? '+' + chgNum.toFixed(2) : chgNum.toFixed(2);
            return '<span class="hot-tag">' +
                name +
                '<span class="' + (chgNum >= 0 ? 'change-up' : 'change-down') + '">' +
                chgStr + '%</span></span>';
        }).join('');
    } catch(e) {
        console.error('加载热点失败:', e);
    }
}

async function loadAlerts() {
    try {
        const resp = await fetch('/api/alerts');
        const data = await resp.json();
        const container = document.getElementById('alerts-list');
        container.innerHTML = (data.alerts || []).slice(0, 5).map(a => `
            <div style="padding:6px 0;border-bottom:1px solid var(--border);font-size:13px;">
                <span style="color:${a.level==='critical'?'var(--danger)':'var(--warning)'}">●</span>
                ${a.title}
                <span style="color:var(--text-muted);float:right">${a.alert_time}</span>
            </div>
        `).join('');
    } catch(e) {
        console.error('加载预警失败:', e);
    }
}

function loadOverviewCharts() {
    // 盈亏分布图
    fetch('/api/trades?limit=50').then(r => r.json()).then(data => {
        const profits = (data.trades || []).filter(t => t.profit_loss_pct != null).map(t => t.profit_loss_pct);
        const ranges = { '-10%以下':0, '-10%~-5%':0, '-5%~0':0, '0~5%':0, '5%~10%':0, '10%~20%':0, '20%以上':0 };
        profits.forEach(p => {
            if(p < -10) ranges['-10%以下']++;
            else if(p < -5) ranges['-10%~-5%']++;
            else if(p < 0) ranges['-5%~0']++;
            else if(p < 5) ranges['0~5%']++;
            else if(p < 10) ranges['5%~10%']++;
            else if(p < 20) ranges['10%~20%']++;
            else ranges['20%以上']++;
        });

        const chartDom = document.getElementById('chart-pl-distribution');
        if (chartDom) {
            const chart = echarts.init(chartDom, 'dark');
            chart.setOption({
                tooltip: {trigger:'axis'},
                xAxis: {type:'category', data: Object.keys(ranges), axisLabel:{fontSize:10}},
                yAxis: {type:'value'},
                series: [{
                    type:'bar', data: Object.values(ranges),
                    itemStyle: {color: params => params.value > 0 ? '#ff0000' : '#00aa00'},
                }],
                backgroundColor:'transparent'
            });
        }
    });

    // 板块分布饼图
    fetch('/api/stock_pool').then(r => r.json()).then(data => {
        const sectors = {};
        (data.pool || []).forEach(s => {
            const sec = s.sector || '其他';
            sectors[sec] = (sectors[sec] || 0) + 1;
        });

        const chartDom = document.getElementById('chart-sector-pie');
        if (chartDom) {
            const chart = echarts.init(chartDom, 'dark');
            chart.setOption({
                tooltip: {trigger:'item'},
                series: [{
                    type:'pie',
                    radius:['45%','75%'],
                    data: Object.entries(sectors).map(([k,v]) => ({name:k, value:v})),
                    label: {fontSize:11},
                }],
                backgroundColor:'transparent'
            });
        }
    });

    // 月度收益图
    fetch('/api/portfolio/report').then(r => r.json()).then(data => {
        const monthly = (data.performance?.monthly_performance || []).reverse();
        const chartDom = document.getElementById('chart-monthly-profit');
        if (chartDom) {
            const chart = echarts.init(chartDom, 'dark');
            chart.setOption({
                tooltip: {trigger:'axis'},
                xAxis: {type:'category', data: monthly.map(m => m.month)},
                yAxis: {type:'value', name:'收益(元)'},
                series: [{
                    type:'line',
                    data: monthly.map(m => m.profit),
                    areaStyle: {opacity:0.2},
                    itemStyle: {color:'#8b5cf6'},
                    smooth: true,
                }],
                backgroundColor:'transparent'
            });
        }
    });
}

// ==================== 股票池（三层体系：买入/清仓/淘汰） ====================
async function loadPool() {
    try {
        const resp = await fetch('/api/stock_pool');
        const data = await resp.json();

        const earlyPool = (data.pool || []).filter(function(s) { return s.phase === 'early'; });
        const midPool = (data.pool || []).filter(function(s) { return s.phase === 'mid'; });

        var ec = document.getElementById('early-count');
        var mc = document.getElementById('mid-count');
        if (ec) ec.textContent = earlyPool.length;
        if (mc) mc.textContent = midPool.length;
        var eb = document.getElementById('early-stage-pool');
        var mb = document.getElementById('mid-stage-pool');
        if (eb) eb.innerHTML = earlyPool.map(renderBuyStockCard).join('');
        if (mb) mb.innerHTML = midPool.map(renderBuyStockCard).join('');
    } catch(e) {
        console.error('加载股票池失败:', e);
    }
}

function renderBuyStockCard(stock) {
    var change = stock.change_pct || 0;
    var changeColor = change >= 0 ? 'var(--up)' : 'var(--down)';
    var phaseClass = 'phase-' + stock.phase;
    var phaseName = {early: '启动', mid: '主升', watch: '观察'}[stock.phase] || '';
    var score = stock.total_score || 0;
    var scoreColor = score >= 70 ? 'var(--up)' : (score >= 50 ? 'var(--warning)' : 'var(--text-muted)');

    // 龙头类型标签
    var leaderType = stock.leader_type || '';
    var leaderBadge = '';
    if (leaderType === 'value') {
        leaderBadge = '<span class="leader-badge leader-value">中线价值龙头</span>';
    } else if (leaderType === 'sentiment') {
        leaderBadge = '<span class="leader-badge leader-sentiment">短线情绪龙头</span>';
    }

    return '<div class="stock-card" onclick="analyzeStock(\'' + stock.code + '\')">' +
        '<div class="code-name"><span class="name">' + stock.name + '</span><span class="code">' + stock.code + '</span></div>' +
        '<div><span class="price">' + ((stock.price || 0)).toFixed(2) + '</span>' +
        '<span class="change" style="color:' + changeColor + '">' + (change > 0 ? '+' : '') + change.toFixed(2) + '%</span>' +
        '<span style="float:right;font-size:12px;color:' + scoreColor + ';font-weight:bold;">★' + score.toFixed(0) + '分</span></div>' +
        (leaderBadge ? '<div style="margin:4px 0;">' + leaderBadge + '</div>' : '') +
        '<div class="info-row"><span>市值: ' + ((stock.market_cap || 0)).toFixed(0) + '亿</span>' +
        '<span>PE: ' + ((stock.pe_ttm_current || stock.pe_ttm || 0)).toFixed(1) + '</span>' +
        '<span class="phase-tag ' + phaseClass + '">' + phaseName + '</span></div>' +
        '<div class="info-row"><span>板块: ' + (stock.sector || '--') + '</span><span>资金: ' + ((stock.fund_flow_20d || 0)).toFixed(1) + '亿</span></div>' +
        '<div style="font-size:11px;color:var(--text-muted);">入选: ' + (stock.entry_date || '--') + '</div>' +
        '<div class="actions">' +
        '<button class="btn btn-sm" onclick="event.stopPropagation();quickQuote(\'' + stock.code + '\',\'' + stock.name + '\')">行情</button>' +
        '<button class="btn btn-sm" onclick="event.stopPropagation();analyzeStock(\'' + stock.code + '\')">分析</button>' +
        '<button class="btn btn-sm" onclick="event.stopPropagation();moveToLiquidate(\'' + stock.code + '\',\'' + stock.name + '\')">清仓</button>' +
        '<button class="btn btn-sm btn-danger" onclick="event.stopPropagation();removeFromPool(\'' + stock.code + '\')">淘汰</button>' +
        '</div></div>';
}

async function quickQuote(code, name) {
    var resp = await fetch('/api/quotes?codes=' + code);
    var data = await resp.json();
    var q = data.quotes[code] || {};
    alert(name + '(' + code + ') 实时行情\n' +
        '现价: ¥' + (q.price || 0).toFixed(2) + '\n' +
        '涨跌: ' + (q.change_pct > 0 ? '+' : '') + (q.change_pct || 0).toFixed(2) + '%\n' +
        '今开: ¥' + (q.open || 0).toFixed(2) + '  昨收: ¥' + (q.last_close || 0).toFixed(2) + '\n' +
        '最高: ¥' + (q.high || 0).toFixed(2) + '  最低: ¥' + (q.low || 0).toFixed(2) + '\n' +
        '振幅: ' + (q.amplitude_pct || 0).toFixed(2) + '%  换手: ' + (q.turnover_pct || 0).toFixed(2) + '%\n' +
        '量比: ' + (q.vol_ratio || 0).toFixed(2) + '  成交: ' + ((q.amount_wan || 0)/10000).toFixed(2) + '亿\n' +
        'PE(TTM): ' + (q.pe_ttm || 0).toFixed(1) + '  PB: ' + (q.pb || 0).toFixed(1) + '\n' +
        '总市值: ' + (q.mcap_yi || 0).toFixed(1) + '亿  流通市值: ' + (q.float_mcap_yi || 0).toFixed(1) + '亿');
}

async function addToPool() {
    var code = document.getElementById('add-code').value.trim();
    var sector = document.getElementById('add-sector').value.trim();
    if (!code) return alert('请输入股票代码');
    try {
        var resp = await fetch('/api/stock_pool/add', {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({code: code, sector: sector})
        });
        var data = await resp.json();
        if (data.success) {
            var elimDiv = document.getElementById('elimination-result');
            if (data.elimination && data.elimination.eliminated && data.elimination.eliminated.length > 0) {
                var html = '';
                data.elimination.eliminated.forEach(function(e) {
                    html += '<div class="elimination-result-card">⚠️ 自动淘汰: <strong>' + e.name + '(' + e.code + ')</strong> | 评分' + e.eliminated_score + '分 | 淘汰价 ' + (e.eliminated_price || 0).toFixed(2) + '<br><span style="color:var(--text-muted);font-size:11px;">' + e.reason + '</span></div>';
                });
                elimDiv.innerHTML = html;
                setTimeout(function() { elimDiv.innerHTML = ''; }, 8000);
            } else {
                elimDiv.innerHTML = '<div style="color:var(--success);padding:8px;">✅ 已加入买入池 | ' + (data.elimination && data.elimination.added && data.elimination.added.status === 'already_in_pool' ? '该股已在池中' : '新增成功') + '</div>';
            }
            loadPool();
            document.getElementById('add-code').value = '';
            document.getElementById('add-sector').value = '';
        } else {
            alert(data.error || '添加失败');
        }
    } catch(e) {
        alert('添加失败: ' + e.message);
    }
}

async function estimateScore() {
    var code = document.getElementById('add-code').value.trim();
    if (!code) return alert('请输入股票代码');
    try {
        var resp = await fetch('/api/stock_pool/estimate_score', {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({code: code})
        });
        var data = await resp.json();
        if (data.error) { alert(data.error); return; }
        document.getElementById('elimination-result').innerHTML =
            '<div class="elimination-result-card">📊 ' + data.name + '(' + data.code + ') 预估评分: <strong style="font-size:18px;">' + data.estimated_score + '分</strong><br>阶段: ' + data.phase_name + ' | 主升浪: ' + (data.main_wave_stage || 'none') + ' | 资金流: ' + data.fund_flow_20d + '亿 | PE: ' + data.pe_ttm + '</div>';
    } catch(e) {
        alert('评分失败: ' + e.message);
    }
}

async function removeFromPool(code) {
    if (!confirm('确定淘汰 ' + code + ' 吗？将移入淘汰池并记录淘汰时间和价格。')) return;
    try {
        await fetch('/api/stock_pool/remove', {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({code: code, reason: '手动淘汰'})
        });
        loadPool();
    } catch(e) {
        alert('淘汰失败');
    }
}

async function moveToLiquidate(code, name) {
    var reason = prompt('输入将 ' + name + '(' + code + ') 移入清仓池的原因:', '触发卖出信号');
    if (!reason) return;
    try {
        var resp = await fetch('/api/stock_pool/move_to_liquidate', {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({code: code, reason: reason})
        });
        var data = await resp.json();
        if (data.success) {
            alert(name + ' 已移入清仓池');
            loadPool();
        }
    } catch(e) {
        alert('操作失败');
    }
}

// ============ 清仓池 ============
async function loadLiquidatePool() {
    try {
        var resp = await fetch('/api/pools/liquidate');
        var data = await resp.json();
        var pool = data.pool || [];
        var container = document.getElementById('liquidate-pool-list');
        if (!container) return;
        if (pool.length === 0) {
            container.innerHTML = '<p style="color:var(--text-muted);text-align:center;padding:40px;">清仓池为空，没有待清仓的股票</p>';
            return;
        }
        container.innerHTML = pool.map(function(s) {
            return '<div class="liquidate-card"><div class="code-name"><span class="name">' + s.name + '</span><span class="code">' + s.code + '</span></div>' +
                '<div style="margin:8px 0;font-size:13px;">入选价: <strong>' + ((s.entry_price || 0)).toFixed(2) + '</strong> | 清仓触发价: <strong>' + ((s.liquidate_price || 0)).toFixed(2) + '</strong> | 当前价: <strong style="color:' + ((s.change_from_entry || 0) >= 0 ? 'var(--up)' : 'var(--down)') + '">' + ((s.current_price || 0)).toFixed(2) + '</strong></div>' +
                '<div style="font-size:12px;color:var(--warning);margin:6px 0;">⚠ 清仓原因: ' + (s.liquidate_reason || '--') + ' | 触发时间: ' + (s.liquidate_date || '--') + '</div>' +
                '<div class="actions"><button class="btn btn-danger" onclick="confirmLiquidate(\'' + s.code + '\')">✅ 确认清仓</button><button class="btn btn-sm" onclick="analyzeStock(\'' + s.code + '\')">分析</button></div></div>';
        }).join('');
    } catch(e) {
        console.error('加载清仓池失败:', e);
    }
}

async function confirmLiquidate(code) {
    if (!confirm('确认清仓？清仓后该股票将移入淘汰池记录。')) return;
    try {
        await fetch('/api/stock_pool/confirm_liquidate', {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({code: code, reason: '已清仓'})
        });
        loadLiquidatePool();
    } catch(e) {
        alert('确认失败');
    }
}

// ============ 淘汰池 ============
async function loadEliminatedPool() {
    try {
        var resp = await fetch('/api/pools/eliminated');
        var data = await resp.json();
        var pool = data.pool || [];
        var stats = data.stats || {};

        var statsDiv = document.getElementById('eliminated-stats');
        if (statsDiv) {
            statsDiv.innerHTML =
                '<div class="elim-stat-card"><div class="es-label">累计淘汰</div><div class="es-value">' + (stats.total_eliminated || 0) + '只</div></div>' +
                '<div class="elim-stat-card"><div class="es-label">平均存活天数</div><div class="es-value">' + (stats.avg_days_in_pool || 0) + '天</div></div>' +
                '<div class="elim-stat-card"><div class="es-label">淘汰时平均评分</div><div class="es-value">' + (stats.avg_eliminated_score || 0) + '分</div></div>' +
                '<div class="elim-stat-card"><div class="es-label">淘汰原因分布</div><div class="es-value" style="font-size:11px;">' + ((stats.eliminate_reasons || []).map(function(r) { return r.reason + '×' + r.count; }).join(', ') || '--') + '</div></div>';
        }

        var tbody = document.getElementById('eliminated-table-body');
        if (!tbody) return;
        tbody.innerHTML = pool.map(function(s) {
            var badge = '';
            if (s.review_evaluation === 'correct') {
                badge = '<span class="review-badge review-correct" onclick="setReview(\'' + s.code + '\',\'correct\')">✓ 正确</span>';
            } else if (s.review_evaluation === 'wrong') {
                badge = '<span class="review-badge review-wrong" onclick="setReview(\'' + s.code + '\',\'wrong\')">✗ 错误</span>';
            } else if (s.review_evaluation === 'uncertain') {
                badge = '<span class="review-badge review-uncertain" onclick="setReview(\'' + s.code + '\',\'uncertain\')">? 不确定</span>';
            } else {
                badge = '<span class="review-badge review-none" onclick="setReview(\'' + s.code + '\',\'correct\')">待评价</span>';
            }
            return '<tr class="eliminated-row"><td>' + s.code + '</td><td>' + s.name + '</td><td>' + (s.entry_date || '--') + '</td><td>' + ((s.entry_price || 0)).toFixed(2) + '</td><td>' + (s.eliminated_date || '--') + '</td><td>' + ((s.eliminated_price || 0)).toFixed(2) + '</td><td>' + ((s.eliminated_total_score || 0)).toFixed(0) + '</td><td style="max-width:200px;font-size:12px;">' + (s.eliminated_reason || '--') + '</td><td style="font-size:12px;">' + (s.replaced_by_name || '--') + '</td><td>' + badge + '</td></tr>';
        }).join('') || '<tr><td colspan="10" style="text-align:center;padding:40px;color:var(--text-muted);">暂无淘汰记录</td></tr>';
    } catch(e) {
        console.error('加载淘汰池失败:', e);
    }
}

async function setReview(code, evaluation) {
    var notes = prompt('添加复盘笔记（可选）:', '');
    try {
        await fetch('/api/stock_pool/review_eliminated', {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({code: code, evaluation: evaluation, notes: notes || ''})
        });
        loadEliminatedPool();
    } catch(e) {
        alert('评价失败');
    }
}

async function buildPool() {
    if (!confirm('将根据市场热点和主升浪条件重新筛选构建股票池，继续？')) return;
    try {
        var resp = await fetch('/api/build_pool', {method:'POST'});
        var data = await resp.json();
        alert('股票池构建完成！\n启动阶段: ' + (data.early_stage ? data.early_stage.length : 0) + '只\n主升浪中: ' + (data.mid_stage ? data.mid_stage.length : 0) + '只');
        loadPool();
    } catch(e) {
        alert('构建失败: ' + e.message);
    }
}

async function optimizePool() {
    try {
        var resp = await fetch('/api/portfolio/monitor');
        var data = await resp.json();
        alert('池优化扫描完成！\n监控股票: ' + (data.holdings ? data.holdings.length : 0) + '只\n预警: ' + (data.alert_count || 0) + '条');
        loadPool();
    } catch(e) {
        alert('优化失败');
    }
}

// ==================== 龙头分类分析 ====================
async function analyzeLeaders() {
    var panel = document.getElementById('leader-panel');
    panel.style.display = 'block';
    panel.innerHTML = '<p style="text-align:center;padding:20px;color:var(--text-muted);">🐉 正在进行双体系龙头分类分析...</p>';

    try {
        var resp = await fetch('/api/leaders/analyze_pool');
        var data = await resp.json();
        var results = data.results || [];

        var summaryHtml =
            '<div class="leader-summary-card value">' +
            '<div class="lsc-title">🏛️ 中线价值龙头</div>' +
            '<div class="lsc-count" style="color:#34d399;">' + (data.value_count || 0) + '只</div>' +
            '<div class="lsc-note">持有1-12个月 | 7成仓位</div></div>' +
            '<div class="leader-summary-card sentiment">' +
            '<div class="lsc-title">⚡ 短线情绪龙头</div>' +
            '<div class="lsc-count" style="color:#c084fc;">' + (data.sentiment_count || 0) + '只</div>' +
            '<div class="lsc-note">持有1-10天 | 3成仓位 | 严格止损</div></div>' +
            '<div class="leader-summary-card strategy">' +
            '<div class="lsc-title">📐 策略配置</div>' +
            '<div class="lsc-count" style="font-size:16px;line-height:1.6;">' +
            '<span style="color:#34d399;">70%中线</span> + <span style="color:#c084fc;">30%短线</span></div>' +
            '<div class="lsc-note">分批低吸不追涨 | 强势市场可加大短线</div></div>';

        var tableHtml = '<div class="table-container" style="margin-top:16px;"><table class="data-table leader-table"><thead><tr>' +
            '<th>代码</th><th>名称</th><th>现价</th><th>涨跌%</th><th>换手%</th><th>成交(亿)</th><th>量比</th>' +
            '<th>PE</th><th>市值(亿)</th><th>龙头类型</th><th>风险</th>' +
            '</tr></thead><tbody>' +
            results.map(function(r) {
                var typeBadge = '';
                if (r.leader_type === 'value') {
                    typeBadge = '<span class="leader-badge leader-value">中线价值龙头</span>';
                } else if (r.leader_type === 'sentiment') {
                    typeBadge = '<span class="leader-badge leader-sentiment">短线情绪龙头</span>';
                } else {
                    typeBadge = '<span class="leader-badge leader-none">待分类</span>';
                }
                var pitfallHtml = '';
                if (r.pitfall && r.pitfall.is_pitfall) {
                    pitfallHtml = '<span class="pitfall-warn">⚠ ' + (r.pitfall.warnings || []).join(',') + '</span>';
                } else {
                    pitfallHtml = '<span style="color:var(--success);">✅</span>';
                }
                return '<tr><td>' + r.code + '</td><td><strong>' + r.name + '</strong></td>' +
                    '<td>' + (r.price || 0).toFixed(2) + '</td>' +
                    '<td style="color:' + ((r.change_pct||0) >= 0 ? 'var(--up)' : 'var(--down)') + '">' + ((r.change_pct||0) > 0 ? '+' : '') + (r.change_pct||0).toFixed(2) + '%</td>' +
                    '<td>' + (r.turnover_pct||0).toFixed(2) + '%</td>' +
                    '<td>' + (r.amount_yi||0).toFixed(1) + '</td>' +
                    '<td>' + (r.vol_ratio||0).toFixed(1) + '</td>' +
                    '<td>' + (r.pe_ttm||0).toFixed(1) + '</td>' +
                    '<td>' + (r.mcap_yi||0).toFixed(0) + '</td>' +
                    '<td>' + typeBadge + '</td>' +
                    '<td>' + pitfallHtml + '</td></tr>';
            }).join('') + '</tbody></table></div>';

        panel.innerHTML = '<div class="leader-summary" id="leader-summary">' + summaryHtml + '</div>' +
            '<div class="leader-results" id="leader-results">' + tableHtml + '</div>';

        // 刷新股票池卡片以显示龙头标签
        loadPool();
    } catch(e) {
        panel.innerHTML = '<p style="color:var(--danger);text-align:center;padding:20px;">分析失败: ' + e.message + '</p>';
    }
}

// ==================== 实时行情弹窗（双击打开） ====================
var quoteTimer = null;
var quoteCode = '';
var quoteAutoRefresh = true;

// 全局双击监听 — 股票代码或卡片双击打开行情弹窗
document.addEventListener('dblclick', function(e) {
    var target = e.target;

    // 找到最近的包含code的元素
    var card = target.closest('.stock-card');
    var row = target.closest('tr');
    var codeEl = target.closest('.code');

    var code = '';
    if (card) {
        var codeSpan = card.querySelector('.code');
        if (codeSpan) code = codeSpan.textContent.trim();
    }
    if (!code && row) {
        var firstTd = row.querySelector('td');
        if (firstTd && /^\d{6}$/.test(firstTd.textContent.trim())) {
            code = firstTd.textContent.trim();
        }
    }
    if (!code && codeEl) {
        code = codeEl.textContent.trim();
    }

    if (code && /^\d{6}$/.test(code)) {
        e.preventDefault();
        e.stopPropagation();
        openQuoteModal(code);
    }
});

async function openQuoteModal(code) {
    quoteCode = code;
    quoteAutoRefresh = true;
    document.getElementById('quote-modal').style.display = 'flex';
    document.getElementById('qm-name').textContent = code + ' 加载中...';
    document.getElementById('qm-price').textContent = '--';

    await refreshQuoteData();
    loadKlineChart(code);

    // 自动刷新
    if (quoteTimer) clearInterval(quoteTimer);
    quoteTimer = setInterval(function() {
        if (quoteAutoRefresh) refreshQuoteData();
    }, 3000);
}

function closeQuoteModal() {
    document.getElementById('quote-modal').style.display = 'none';
    quoteCode = '';
    if (quoteTimer) { clearInterval(quoteTimer); quoteTimer = null; }
}

function toggleQuoteRefresh() {
    quoteAutoRefresh = !quoteAutoRefresh;
    var btn = document.getElementById('qm-refresh-btn');
    btn.textContent = quoteAutoRefresh ? '⏸ 暂停刷新' : '▶ 继续刷新';
    btn.style.background = quoteAutoRefresh ? '' : 'var(--warning)';
}

async function refreshQuoteData() {
    if (!quoteCode) return;
    try {
        var resp = await fetch('/api/quotes?codes=' + quoteCode);
        var data = await resp.json();
        var q = data.quotes[quoteCode] || {};
        if (!q.price) return;

        document.getElementById('qm-name').textContent = q.name + ' (' + quoteCode + ')';
        document.getElementById('qm-price').textContent = '¥' + (q.price || 0).toFixed(2);
        var chg = q.change_pct || 0;
        var chgColor = chg >= 0 ? 'var(--up)' : 'var(--down)';
        document.getElementById('qm-change').textContent = (chg >= 0 ? '+' : '') + (q.change_amt || 0).toFixed(2);
        document.getElementById('qm-change').style.color = chgColor;
        document.getElementById('qm-change-pct').textContent = (chg >= 0 ? '+' : '') + chg.toFixed(2) + '%';
        document.getElementById('qm-change-pct').style.color = chgColor;
        document.getElementById('qm-price').style.color = chgColor;

        document.getElementById('qm-open').textContent = '¥' + (q.open || 0).toFixed(2);
        document.getElementById('qm-close').textContent = '¥' + (q.last_close || 0).toFixed(2);
        document.getElementById('qm-high').textContent = '¥' + (q.high || 0).toFixed(2);
        document.getElementById('qm-low').textContent = '¥' + (q.low || 0).toFixed(2);
        document.getElementById('qm-volume').textContent = ((q.amount_wan || 0)/10000).toFixed(2) + '亿';
        document.getElementById('qm-amount').textContent = ((q.amount_wan || 0)/10000).toFixed(2) + '亿';
        document.getElementById('qm-turnover').textContent = (q.turnover_pct || 0).toFixed(2) + '%';
        document.getElementById('qm-vol-ratio').textContent = (q.vol_ratio || 0).toFixed(2);
        document.getElementById('qm-amplitude').textContent = (q.amplitude_pct || 0).toFixed(2) + '%';
        document.getElementById('qm-pe').textContent = (q.pe_ttm || 0).toFixed(1);
        document.getElementById('qm-mcap').textContent = (q.mcap_yi || 0).toFixed(1) + '亿';
        document.getElementById('qm-float-mcap').textContent = (q.float_mcap_yi || 0).toFixed(1) + '亿';
        document.getElementById('qm-pb').textContent = (q.pb || 0).toFixed(2);
        document.getElementById('qm-limit-up').textContent = '¥' + (q.limit_up || 0).toFixed(2);
        document.getElementById('qm-limit-down').textContent = '¥' + (q.limit_down || 0).toFixed(2);
    } catch(e) {
        console.error('刷新行情失败:', e);
    }
}

function loadKlineChart(code) {
    var chartDom = document.getElementById('qm-kline-chart');
    if (!chartDom) return;
    chartDom.innerHTML = '<p style="text-align:center;padding:40px;color:var(--text-muted);">⏳ 加载K线...</p>';

    fetch('/api/kline?code=' + code + '&period=day&count=60').then(function(r) { return r.json(); }).then(function(data) {
        var klines = data.klines || [];
        if (klines.length === 0) {
            chartDom.innerHTML = '<p style="text-align:center;padding:40px;color:var(--text-muted);">暂无K线数据</p>';
            return;
        }

        var dates = klines.map(function(k) { return k.date; });
        var values = klines.map(function(k) { return [k.open, k.close, k.low, k.high]; });
        var volumes = klines.map(function(k) { return k.volume; });

        var chart = echarts.init(chartDom, 'dark');
        chart.setOption({
            tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
            grid: [{ left: '8%', right: '3%', top: '5%', height: '70%' },
                   { left: '8%', right: '3%', top: '80%', height: '15%' }],
            xAxis: [
                { type: 'category', data: dates, gridIndex: 0, axisLabel: { fontSize: 10 } },
                { type: 'category', data: dates, gridIndex: 1, axisLabel: { show: false } }
            ],
            yAxis: [
                { type: 'value', gridIndex: 0, scale: true, splitNumber: 4 },
                { type: 'value', gridIndex: 1, splitNumber: 2, axisLabel: { fontSize: 9 } }
            ],
            series: [
                {
                    type: 'candlestick', data: values,
                    itemStyle: { color: '#ff0000', color0: '#00aa00', borderColor: '#ff0000', borderColor0: '#00aa00' },
                    xAxisIndex: 0, yAxisIndex: 0
                },
                {
                    type: 'bar', data: volumes,
                    itemStyle: { color: function(p) { return p.dataIndex > 0 && values[p.dataIndex][1] >= values[p.dataIndex][0] ? '#ff0000' : '#00aa00'; } },
                    xAxisIndex: 1, yAxisIndex: 1
                }
            ],
            backgroundColor: 'transparent'
        });

        chartDom._echart_instance = chart;
    }).catch(function() {
        chartDom.innerHTML = '<p style="text-align:center;padding:40px;color:var(--text-muted);">K线加载失败</p>';
    });

    // 加载TDX盘口数据
    loadTdxBsp(code);
}

function loadTdxBsp(code) {
    fetch('/api/tdx/quote?code=' + code).then(function(r) { return r.json(); }).then(function(data) {
        var cached = data.cached || {};
        var bsp = cached.bsp || [];
        var content = document.getElementById('qm-bsp-content');
        if (!content) return;

        if (bsp.length === 0) {
            content.innerHTML = '<p style="color:var(--text-muted);">暂无TDX盘口数据（需盘前9:25自动刷新）</p>';
            return;
        }

        var html = '<table style="width:100%;font-size:12px;border-collapse:collapse;">' +
            '<tr style="color:var(--text-muted);"><th style="width:8%;">档位</th><th style="width:20%;color:var(--down);">买价</th><th style="width:18%;">买量(手)</th><th style="width:8%;"></th><th style="width:20%;color:var(--up);">卖价</th><th style="width:18%;">卖量(手)</th></tr>';

        bsp.forEach(function(row, i) {
            html += '<tr style="text-align:center;border-bottom:1px solid var(--border);">' +
                '<td style="padding:4px 0;">' + (i+1) + '</td>' +
                '<td style="color:var(--down);font-weight:600;">' + (row.BuyP||0).toFixed(2) + '</td>' +
                '<td>' + (row.BuyV||0) + '</td>' +
                '<td style="font-size:18px;color:var(--text-muted);">│</td>' +
                '<td style="color:var(--up);font-weight:600;">' + (row.SellP||0).toFixed(2) + '</td>' +
                '<td>' + (row.SellV||0) + '</td></tr>';
        });

        html += '</table>';
        html += '<div style="text-align:center;margin-top:4px;font-size:11px;color:var(--text-muted);">数据源: 通达信TDX | 缓存' + (data.cache_age_sec || 0) + '秒前</div>';
        content.innerHTML = html;
    }).catch(function() {
        var content = document.getElementById('qm-bsp-content');
        if (content) content.innerHTML = '<p style="color:var(--text-muted);">盘口加载失败</p>';
    });
}
function initPoolTabs() {
    var tabs = document.querySelectorAll('.pool-tab');
    tabs.forEach(function(tab) {
        tab.addEventListener('click', function() {
            tabs.forEach(function(t) { t.classList.remove('active'); });
            document.querySelectorAll('.pool-tab-content').forEach(function(c) { c.classList.remove('active'); });
            tab.classList.add('active');
            var poolTab = tab.getAttribute('data-pool-tab');
            var content = document.getElementById('pool-tab-' + poolTab);
            if (content) content.classList.add('active');
            if (poolTab === 'buy') loadPool();
            else if (poolTab === 'liquidate') loadLiquidatePool();
            else if (poolTab === 'eliminated') loadEliminatedPool();
        });
    });
}

// ==================== 推荐 ====================
async function loadRecommendations() {
    try {
        // 先刷新追踪数据
        fetch('/api/recommendations/track', {method: 'POST'}).catch(function(){});

        var resp = await fetch('/api/recommendations?date=');
        var data = await resp.json();

        if (!data.recommendations || data.recommendations.length === 0) {
            document.getElementById('daily-recs').innerHTML =
                '<p style="color:var(--text-muted);text-align:center;padding:40px;">暂未生成今日推荐，点击按钮生成</p>';
            document.getElementById('rec-history').innerHTML = '';
        } else {
            document.getElementById('daily-recs').innerHTML = data.recommendations.map(renderRecCard).join('');
            document.getElementById('rec-history').innerHTML = data.recommendations.map(renderRecTracking).join('');
        }
    } catch(e) {
        console.error('加载推荐失败:', e);
    }
}

function renderRecCard(rec) {
    var intradayGain = rec.intraday_gain_pct || 0;
    var gainColor = intradayGain >= 0 ? 'var(--up)' : 'var(--down)';
    var gainBg = intradayGain >= 0 ? 'rgba(255,0,0,0.08)' : 'rgba(0,170,0,0.08)';

    // 7天表现条
    var days7 = '';
    for (var d = 1; d <= 7; d++) {
        var gain = rec['day' + d + '_gain'];
        if (gain !== null && gain !== undefined) {
            var dColor = gain >= 0 ? 'var(--up)' : 'var(--down)';
            days7 += '<span style="display:inline-block;width:30px;text-align:center;font-size:11px;color:' + dColor + ';">D' + d + '<br>' + (gain > 0 ? '+' : '') + gain.toFixed(1) + '%</span>';
        }
    }

    var maxGain = rec.max_gain_7d || intradayGain;
    var maxLoss = rec.max_loss_7d || intradayGain;

    return '<div class="rec-card">' +
        '<div class="rec-header">' +
        '<div><span class="rec-name">' + rec.name + '</span><span style="color:var(--text-muted);margin-left:8px;">' + rec.code + '</span></div>' +
        '<span class="rec-confidence conf-' + rec.confidence + '">' + (rec.confidence === 'high' ? '高信心' : rec.confidence === 'medium' ? '中信心' : '低信心') + '</span>' +
        '</div>' +
        '<div class="rec-detail-grid">' +
        '<div class="rec-detail-item"><div class="label">推荐时间</div><div class="value" style="font-size:14px;">' + (rec.date || '') + ' ' + (rec.recommend_time || '') + '</div></div>' +
        '<div class="rec-detail-item"><div class="label">推荐价格</div><div class="value">' + (rec.recommend_price || rec.buy_price || 0).toFixed(2) + '</div></div>' +
        '<div class="rec-detail-item"><div class="label">建议买入价</div><div class="value" style="color:var(--up);">' + (rec.buy_price || 0).toFixed(2) + '</div></div>' +
        '<div class="rec-detail-item"><div class="label">止损价</div><div class="value" style="color:var(--down);">' + (rec.stop_loss_price || 0).toFixed(2) + '</div></div>' +
        '<div class="rec-detail-item"><div class="label">止盈价</div><div class="value" style="color:var(--up);">' + (rec.take_profit_price || 0).toFixed(2) + '</div></div>' +
        '<div class="rec-detail-item"><div class="label">当天涨幅</div><div class="value" style="background:' + gainBg + ';padding:2px 8px;border-radius:4px;color:' + gainColor + ';">' + (intradayGain > 0 ? '+' : '') + intradayGain.toFixed(2) + '%</div></div>' +
        '</div>' +
        '<div class="rec-reason">📊 ' + (rec.reason || '综合多维度分析') + '</div>' +
        (days7 ? '<div style="margin-top:8px;padding:6px 8px;background:var(--bg-hover);border-radius:4px;"><strong style="font-size:12px;">📈 7日追踪:</strong><br>' + days7 + '<br><span style="font-size:11px;color:var(--text-muted);">最大收益: <span style="color:var(--up);">+' + maxGain.toFixed(1) + '%</span> | 最大回撤: <span style="color:var(--down);">' + (maxLoss > 0 ? '+' : '') + maxLoss.toFixed(1) + '%</span></span></div>' : '<div style="font-size:11px;color:var(--text-muted);margin-top:4px;">追踪数据将在首个交易日后更新</div>') +
        '<div style="font-size:12px;color:var(--text-muted);margin-top:6px;">竞价: ' + (rec.auction_analysis || '--') + ' | 技术: ' + (rec.technical_signals || '--') + ' | 资金: ' + (rec.fund_flow_signal || '--') + ' | 热点: ' + (rec.hot_topic_support || '--') + '</div>' +
        '</div>';
}

function renderRecTracking(rec) {
    var intradayGain = rec.intraday_gain_pct || 0;
    var gColor = intradayGain >= 0 ? 'var(--up)' : 'var(--down)';
    var maxGain = rec.max_gain_7d || intradayGain;
    var maxLoss = rec.max_loss_7d || intradayGain;
    return '<div style="display:grid;grid-template-columns:80px 60px 1fr 60px 60px 70px;gap:8px;align-items:center;padding:6px 0;border-bottom:1px solid var(--border);font-size:12px;">' +
        '<span>' + (rec.date || '') + '</span>' +
        '<span style="font-weight:600;">' + rec.name + '</span>' +
        '<span style="color:var(--text-muted);">推荐价: ' + ((rec.recommend_price || rec.buy_price || 0)).toFixed(2) + ' | ' + (rec.reason || '').substring(0,30) + '</span>' +
        '<span style="color:' + gColor + ';font-weight:600;">当天 ' + (intradayGain > 0 ? '+' : '') + intradayGain.toFixed(1) + '%</span>' +
        '<span style="color:var(--up);">最高 +' + maxGain.toFixed(1) + '%</span>' +
        '<span style="color:var(--down);">最低 ' + (maxLoss > 0 ? '+' : '') + maxLoss.toFixed(1) + '%</span>' +
        '</div>';
}

async function generateRecommendations() {
    try {
        const resp = await fetch('/api/recommendations/generate', {method:'POST'});
        const data = await resp.json();
        loadRecommendations();

        const count = data.recommendations?.length || 0;
        if (count > 0) {
            alert(`今日推荐生成成功！共推荐${count}只股票`);
        } else {
            alert('当前无符合条件的推荐股票');
        }
    } catch(e) {
        alert('生成推荐失败: ' + e.message);
    }
}

// ==================== 深度分析（增强版） ====================
async function analyzeStock(code) {
    document.querySelectorAll('.nav-item').forEach(function(i) { i.classList.remove('active'); });
    var tab = document.querySelector('[data-tab="analysis"]');
    if (tab) tab.classList.add('active');
    document.querySelectorAll('.tab-content').forEach(function(t) { t.classList.remove('active'); });
    var atab = document.getElementById('tab-analysis');
    if (atab) atab.classList.add('active');
    document.getElementById('analysis-code').value = code;
    await runDeepAnalysis();
}

async function runDeepAnalysis() {
    var code = document.getElementById('analysis-code').value.trim();
    if (!code) return;

    var container = document.getElementById('analysis-result');
    container.innerHTML = '<p style="text-align:center;padding:40px;">⏳ AI正在深度分析...</p>';

    try {
        // 每个API独立容错
        var force = {}, breakout = {}, quotesData = {}, hotData = {}, intentData = {};
        try { force = await fetch('/api/analysis/main_force?code=' + code).then(function(r) { return r.json(); }); } catch(e) {}
        try { breakout = await fetch('/api/analysis/breakout?code=' + code).then(function(r) { return r.json(); }); } catch(e) {}
        try { quotesData = await fetch('/api/quotes?codes=' + code).then(function(r) { return r.json(); }); } catch(e) {}
        try { hotData = await fetch('/api/analysis/hot_spot').then(function(r) { return r.json(); }); } catch(e) {}
        try { intentData = await fetch('/api/analysis/intent?code=' + code).then(function(r) { return r.json(); }); } catch(e) {}

        var q = quotesData.quotes && quotesData.quotes[code] ? quotesData.quotes[code] : {};

        var phase = force.phase || 0;
        var phaseName = force.phase_name || '暂无数据';
        var confidence = force.confidence || 0;
        var signals = force.signals || [];
        var maPos = force.ma_position || {};
        var volInfo = force.volume_analysis || {};
        var pricePos = force.price_position || {};

        // 主力操盘细节
        var mainForceDetail = _buildMainForceDetail(force);
        // 后期走势预判
        var futureTrend = _buildFutureTrend(force, breakout);
        // 风险评估
        var riskAssessment = _buildRiskAssessment(force, breakout, q);

        container.innerHTML =
        '<div class="analysis-panel">' +
        '<h4>📊 ' + code + ' ' + (q.name || '') + ' 深度分析报告</h4>' +
        '<div style="font-size:13px;color:var(--text-muted);">现价 ¥' + ((q.price || 0)).toFixed(2) + ' | 涨跌 ' + ((q.change_pct > 0 ? '+' : '') + (q.change_pct || 0).toFixed(2) + '%') + ' | PE ' + ((q.pe_ttm || 0)).toFixed(1) + ' | 市值 ' + ((q.mcap_yi || 0)).toFixed(1) + '亿</div>' +
        '</div>' +

        // 1. 主力操盘阶段
        '<div class="analysis-panel">' +
        '<h4>🔍 主力操盘阶段分析</h4>' +
        '<p style="font-size:16px;font-weight:700;color:var(--accent);">阶段' + phase + ': ' + phaseName + ' (置信度: ' + confidence + '%)</p>' +
        '<ul class="signal-list">' + signals.map(function(s) { return '<li>' + s + '</li>'; }).join('') + '</ul>' +
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:8px;font-size:12px;color:var(--text-muted);">' +
        '<span>MA5>MA10: ' + (maPos.ma5_above_ma10 ? '✅' : '❌') + '</span>' +
        '<span>MA10>MA20: ' + (maPos.ma10_above_ma20 ? '✅' : '❌') + '</span>' +
        '<span>MA20>MA60: ' + (maPos.ma20_above_ma60 ? '✅' : '❌') + '</span>' +
        '<span>价>MA20: ' + (maPos.price_above_ma20 ? '✅' : '❌') + '</span>' +
        '<span>量比(20/60): ' + (volInfo.vol_ratio_20_60 || 0).toFixed(1) + 'x</span>' +
        '<span>量趋势: ' + (volInfo.recent_volume_trend || '--') + '</span>' +
        '</div>' +
        mainForceDetail +
        '</div>' +

        // 2. 突破与陷阱分析
        '<div class="analysis-panel">' +
        '<h4>⚡ 真假突破判别</h4>' +
        '<p>当前状态: <strong>' + (breakout.status || '--') + '</strong> | 趋势: ' + (breakout.recent_trend || '--') + '</p>' +
        (breakout.signals || []).map(function(s) {
            return '<div style="padding:6px 0;border-bottom:1px solid var(--border);font-size:13px;">' + s.description + ' ' + (s.is_true_breakout ? '✅ 真突破(置信' + s.confidence + '%)' : '⚠️ 疑似假突破') + ((s.risk_flags || []).length ? s.risk_flags.map(function(f) { return '<br><span style="color:var(--warning)">→ ' + f + '</span>'; }).join('') : '') + '</div>';
        }).join('') +
        '<div style="margin-top:8px;font-size:12px;color:var(--text-muted);">压力位: ' + ((breakout.resistance_levels || []).join(', ') || '--') + ' | 支撑位: ' + ((breakout.support_levels || []).join(', ') || '--') + '</div>' +
        '</div>' +

        // 2.5. K线走势图
        '<div class="analysis-panel">' +
        '<h4>📈 动态K线走势</h4>' +
        '<div id="analysis-kline-chart" style="width:100%;height:320px;"><p style="text-align:center;padding:40px;color:var(--text-muted);">⏳ 加载K线...</p></div>' +
        '</div>' +

        // 3. 板块地位
        '<div class="analysis-panel">' +
        '<h4>🏆 板块地位及个股地位详细分析</h4>' +
        _buildPositionAnalysis(code, q, force, hotData, breakout) +
        '</div>' +

        // 3.5. 上涨逻辑与基本面深度分析
        '<div class="analysis-panel">' +
        '<h4>📊 上涨逻辑与基本面深度分析</h4>' +
        _buildFundamentalAnalysis(code, q, force, breakout) +
        '</div>' +

        // 4. 主力操盘意图及手法
        '<div class="analysis-panel">' +
        '<h4>🧠 主力操盘意图及手法</h4>' +
        _renderIntentTable(intentData) +
        '</div>' +

        // 5. 未来三天推演
        '<div class="analysis-panel" style="border-color:var(--warning);">' +
        '<h4>🔮 未来三天主力操盘推演</h4>' +
        _renderForecast3Days(intentData) +
        '</div>' +

        // 6. 操作建议
        '<div class="analysis-panel" style="border-color:var(--accent);">' +
        '<h4>🎯 AI操作建议</h4>' +
        _buildActionSuggestion(phase, confidence, breakout.status || '', q) +
        '</div>';

        // 延迟加载K线（等DOM渲染完毕）
        setTimeout(function() { _loadAnalysisKline(code); }, 500);
    } catch(e) {
        container.innerHTML = '<p style="color:var(--danger);text-align:center;padding:40px;">分析失败: ' + e.message + '</p>';
    }
}

function _buildPositionAnalysis(code, q, force, hotData, breakout) {
    var mcap = q.mcap_yi || 0;
    var pe = q.pe_ttm || 0;
    var pb = q.pb || 0;
    var turnover = q.turnover_pct || 0;
    var volRatio = q.vol_ratio || 0;
    var amount = (q.amount_wan || 0) / 10000;
    var changePct = q.change_pct || 0;
    var name = q.name || '';

    // === 板块地位 ===
    var sectorName = '';
    var positionLevel = '';
    var positionDesc = '';

    // 通过盘中表现推断板块地位
    if (changePct >= 9.5 && turnover > 10 && amount > 5) {
        positionLevel = '板块情绪总龙头';
        positionDesc = '涨停封板，换手充分，资金高度聚焦。它的一举一动直接决定板块当日走势，是板块内所有资金的风向标。';
    } else if (changePct >= 5 && amount > 3) {
        positionLevel = '板块领涨先锋';
        positionDesc = '涨幅居板块前列，成交活跃。它率先突破关键压力位，带动板块内其他个股跟涨。';
    } else if (mcap > 200 && turnover > 3) {
        positionLevel = '板块趋势中军';
        positionDesc = '大市值+稳健换手，是机构资金和北向资金配置该板块的首选标的。走势稳定，代表板块中期方向。';
    } else if (Math.abs(changePct) < 2 && mcap > 100) {
        positionLevel = '板块跟随者';
        positionDesc = '走势基本跟随板块指数波动，缺乏独立行情。需要板块龙头带动才能有所表现。';
    } else if (changePct < -5) {
        positionLevel = '板块拖累者';
        positionDesc = '跌幅远超板块均值，可能存在利空因素。对板块形成负面拖累，需排查是否有基本面问题。';
    } else {
        positionLevel = '板块普通成员';
        positionDesc = '与板块走势同步，缺乏超额收益。在板块上涨时涨幅中等，板块下跌时跟随回调。';
    }

    // === 个股核心竞争力 ===
    var coreStrength = '';
    if (mcap > 500) {
        coreStrength = '【规模壁垒】大市值蓝筹，行业地位稳固，抗风险能力强，机构持仓比例高。';
        if (pe > 0 && pe < 40) coreStrength += ' 估值合理，具备长期配置价值。';
        else if (pe > 60) coreStrength += ' 但估值偏高，需警惕回调风险。';
    } else if (mcap > 100) {
        coreStrength = '【成长弹性】中盘成长股，市占率有提升空间，业绩弹性大。';
        if (turnover > 5 && volRatio > 1.5) coreStrength += ' 当前资金活跃度高，市场关注度上升。';
        if (changePct > 3) coreStrength += ' 短期动能强劲，正处于市场风口。';
    } else {
        coreStrength = '【小而灵活】小盘股，可能处于细分赛道，具备高弹性高波动的特征。适合短线博弈，但需注意流动性风险。';
    }

    // === 资金博弈分析 ===
    // === 判断盘前/盘中/收盘状态 ===
    var isPreMarket = (amount <= 0 && turnover <= 0);
    var marketStatus = isPreMarket ? '盘前/休市中（无实时成交数据）' : '交易中';

    var capitalAnalysis = '';
    if (isPreMarket) {
        capitalAnalysis = '⏳ 当前处于盘前或休市状态，尚未产生今日成交数据。以下为上一交易日收盘数据。';
        if (amount <= 0) {
            capitalAnalysis += ' 流动性数据将在开盘后实时更新。';
        }
    } else if (amount > 10) {
        capitalAnalysis = '今日成交' + amount.toFixed(1) + '亿，属于全市场前5%的高流动性标的。巨量换手说明多空分歧剧烈。';
        if (changePct > 5) capitalAnalysis += ' 多方占优，资金抢筹意愿强。';
        else if (changePct < -3) capitalAnalysis += ' 空方主导，资金出逃明显。';
        else capitalAnalysis += ' 多空势均力敌，方向待选。';
    } else if (amount > 3) {
        capitalAnalysis = '今日成交' + amount.toFixed(1) + '亿，交投活跃。量价关系显示' + (changePct > 0 ? '买方略占优势。' : '卖方略占优势。');
    } else if (amount > 0) {
        capitalAnalysis = '今日成交' + amount.toFixed(1) + '亿，流动性一般。大资金进出需要拆单，短线操作需注意滑点。';
    } else {
        capitalAnalysis = '⏳ 成交数据暂未更新，请开盘后刷新查看。';
    }

    // === 同板块对标 ===
    var benchmarkHtml = '';
    if (mcap > 100) {
        benchmarkHtml = '<div style="margin-top:8px;padding:8px;background:rgba(59,130,246,0.1);border-radius:4px;font-size:12px;">' +
            '<strong>📊 同板块对标评估:</strong><br>该股' + name + '(' + code + ')当前';
        if (changePct >= 5) benchmarkHtml += '领涨板块，处于强势地位。';
        else if (changePct > 0) benchmarkHtml += '略微跑赢板块均值。';
        else benchmarkHtml += '表现弱于板块均值。';
        benchmarkHtml += ' 换手率' + turnover.toFixed(1) + '%';
        if (turnover > 10) benchmarkHtml += '远超板块均值，资金关注度极高。';
        else if (turnover > 5) benchmarkHtml += '处于板块活跃水平。';
        else benchmarkHtml += '低于板块活跃水平。';
        benchmarkHtml += ' 量比' + volRatio.toFixed(2) + (volRatio > 1.5 ? '，放量明显，有增量资金入场。' : '，量能平稳。') + '</div>';
    }
    // === 热点匹配 ===
    var hotTopics = ((hotData && hotData.hot_sectors) || []).slice(0, 8);
    var matchedTopics = [];
    hotTopics.forEach(function(h) {
        var topic = h.topic || h.name || '';
        if (topic && name.indexOf(topic.charAt(0)) >= 0) {
            matchedTopics.push(topic);
        }
    });

    var html = '<div style="font-size:13px;line-height:1.8;">';

    // 板块地位卡片
    html += '<div style="padding:10px;margin-bottom:10px;background:rgba(139,92,246,0.08);border-left:3px solid var(--accent);border-radius:4px;">' +
        '<div style="font-weight:700;font-size:15px;color:var(--accent);">' + positionLevel + '</div>' +
        '<div style="color:var(--text-secondary);margin-top:4px;font-size:12px;">' + positionDesc + '</div>' +
        '</div>';

    // 详细指标网格
    html += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">';

    // 核心竞争
    html += '<div style="padding:8px;background:rgba(16,185,129,0.06);border-radius:6px;">' +
        '<div style="font-weight:600;color:var(--success);margin-bottom:4px;">💎 核心竞争力</div>' +
        '<div style="font-size:12px;color:var(--text-secondary);">' + coreStrength + '</div></div>';

    // 资金博弈
    html += '<div style="padding:8px;background:rgba(245,158,11,0.06);border-radius:6px;">' +
        '<div style="font-weight:600;color:var(--warning);margin-bottom:4px;">💰 资金博弈</div>' +
        '<div style="font-size:12px;color:var(--text-secondary);">' + capitalAnalysis + '</div></div>';

    // 关键指标
    var amountStr = amount > 0 ? amount.toFixed(1) + '亿' : (isPreMarket ? '盘前暂无' : '--');
    var turnoverStr = turnover > 0 ? turnover.toFixed(2) + '%' : (isPreMarket ? '盘前暂无' : '--');
    var volRatioStr = volRatio > 0 ? volRatio.toFixed(2) : (isPreMarket ? '盘前暂无' : '--');
    var changeStr = changePct !== 0 ? (changePct > 0 ? '+' : '') + changePct.toFixed(2) + '%' : '平盘';
    var ampStr = (q.amplitude_pct || 0) > 0 ? (q.amplitude_pct || 0).toFixed(2) + '%' : (isPreMarket ? '--' : '0%');

    html += '<div style="padding:8px;background:rgba(59,130,246,0.06);border-radius:6px;">' +
        '<div style="font-weight:600;color:var(--info);margin-bottom:4px;">📐 关键指标' + (isPreMarket ? ' <span style="font-size:11px;color:var(--text-muted);">(上一交易日数据)</span>' : '') + '</div>' +
        '<div style="font-size:12px;color:var(--text-secondary);">' +
        '市值: ' + mcap.toFixed(0) + '亿 | PE: ' + pe.toFixed(1) + ' | PB: ' + pb.toFixed(2) + '<br>' +
        '换手: ' + turnoverStr + ' | 量比: ' + volRatioStr + ' | 成交: ' + amountStr + '<br>' +
        '涨跌: ' + changeStr + ' | 振幅: ' + ampStr +
        '</div></div>';

    // 热点关联
    html += '<div style="padding:8px;background:rgba(168,85,247,0.06);border-radius:6px;">' +
        '<div style="font-weight:600;color:#c084fc;margin-bottom:4px;">🔥 热点关联</div>' +
        '<div style="font-size:12px;color:var(--text-secondary);">' +
        '今日市场TOP热点:<br>' +
        hotTopics.map(function(h) {
            var chg = h.sector_index_change || h.change_pct || 0;
            var chgColor = chg >= 0 ? 'var(--up)' : 'var(--down)';
            return '<span style="display:inline-block;margin:2px;padding:2px 6px;background:var(--bg-hover);border-radius:4px;font-size:11px;">' +
                (h.topic || h.name || '?') + ' <span style="color:' + chgColor + ';">' + (chg > 0 ? '+' : '') + chg.toFixed(1) + '%</span></span>';
        }).join('') +
        '</div></div>';

    html += '</div>';

    // 同板块对标
    html += benchmarkHtml;

    // 地位总结
    html += '<div style="margin-top:10px;padding:10px;background:rgba(245,158,11,0.08);border-radius:6px;font-size:13px;color:var(--text-secondary);">' +
        '<strong>📋 地位总结:</strong> ' + name + '在板块中定位为<strong style="color:var(--accent);">' + positionLevel + '</strong>。';
    if (positionLevel.indexOf('龙头') >= 0 || positionLevel.indexOf('领涨') >= 0) {
        html += ' 其走势对板块有显著带动效应，适合作为中线价值龙头（70%仓位）或短线情绪龙头（30%仓位）配置。操作上应在回踩支撑位时加仓，在放量滞涨时减仓。';
    } else if (positionLevel.indexOf('中军') >= 0) {
        html += ' 走势稳健适合中线配置，可作为组合的压舱石。建议7成仓位中线持有。';
    } else if (positionLevel.indexOf('拖累') >= 0) {
        html += ' 当前表现弱于板块，建议排查是否有基本面恶化或重大利空。若板块逻辑未破坏可继续观察，否则应移入清仓池。';
    } else {
        html += ' 随板块波动，超额收益有限。若板块持续活跃可持有，板块退潮时应优先减仓。';
    }
    html += '</div>';

    return html;
}

// 以下旧函数保留兼容
function _estimateSectorCycle(q, hotData) {
    return '';
}
function _buildIndustryStatus(q, code) {
    return '';
}

function _buildMainForceDetail(force) {
    var phase = force.phase || 0;
    var detail = '';
    if (phase === 1) {
        detail = '主力处于底部区域缓慢收集筹码阶段。量能在逐步放大，但股价波动不大，适合耐心潜伏。';
    } else if (phase === 2) {
        detail = '主力通过缩量下跌清洗不坚定的浮筹。回调不破关键均线，是主力控盘能力强的体现。关注何时放量突破。';
    } else if (phase === 3) {
        detail = '主力完成建仓洗盘后开始拉升。标志性信号：放量突破前期平台+均线多头发散。这是最佳的介入时机。';
    } else if (phase === 4) {
        detail = '主力推动股价进入主升段。量价配合良好，均线多头排列。此阶段应以持有为主，享受趋势带来的利润。';
    } else if (phase === 5) {
        detail = '高位出现放量滞涨或量价背离。主力开始边拉边出。应逐步减仓锁定利润。';
    } else if (phase === 6) {
        detail = '主力已完成出货，股价跌破关键均线。此时应坚决清仓，不要抱有任何幻想。';
    }
    return detail ? '<div style="margin-top:8px;padding:8px;background:rgba(139,92,246,0.1);border-radius:4px;font-size:13px;">' + detail + '</div>' : '';
}

function _buildIndustryStatus(q, code) {
    var mcap = q.mcap_yi || 0;
    var html = '<div style="font-size:13px;">';
    html += '<p><strong>市值规模:</strong> ' + mcap.toFixed(1) + '亿';
    if (mcap >= 500) html += ' <span style="color:var(--accent);">(大市值蓝筹)</span>';
    else if (mcap >= 100) html += ' <span style="color:var(--info);">(中盘成长股)</span>';
    else html += ' <span style="color:var(--text-muted);">(小盘股)</span></p>';

    html += '<p><strong>估值水平:</strong> PE=' + ((q.pe_ttm || 0)).toFixed(1) + ' PB=' + ((q.pb || 0)).toFixed(2);
    if (q.pe_ttm > 100) html += ' <span style="color:var(--warning);">(高估值)</span>';
    else if (q.pe_ttm > 50) html += ' <span style="color:var(--info);">(中等估值)</span>';
    else if (q.pe_ttm > 0) html += ' <span style="color:var(--success);">(估值合理)</span></p>';

    html += '<p><strong>流动性:</strong> 换手率=' + ((q.turnover_pct || 0)).toFixed(2) + '% 量比=' + ((q.vol_ratio || 0)).toFixed(2);
    if ((q.turnover_pct || 0) > 10) html += ' <span style="color:var(--warning);">(高换手)</span></p>';
    else html += '</p>';

    html += '</div>';
    return html;
}

function _buildFutureTrend(force, breakout) {
    var phase = force.phase || 0;
    var html = '<div style="font-size:13px;line-height:1.8;">';
    
    if (phase === 3 || phase === 4) {
        html += '✅ <strong>短期看涨</strong> — 主升浪运行中，均线多头排列支撑股价上行。关注量能是否持续放大，若缩量则警惕回调。<br>';
        html += '✅ <strong>中期看好</strong> — 趋势一旦形成不会轻易改变，只要不破MA20，上升趋势延续。<br>';
        html += '⚠ <strong>风险点:</strong> ' + ((breakout.support_levels || []).length > 0 ? '关键支撑位 ' + breakout.support_levels.join('/') + '，跌破需止损' : '关注大盘系统性风险');
    } else if (phase === 1 || phase === 2) {
        html += '⏳ <strong>短期震荡</strong> — 底部或洗盘阶段，短期方向不明，适合逢低分批布局。<br>';
        html += '📈 <strong>中期偏多</strong> — 一旦完成洗盘放量突破，将进入主升浪。<br>';
        html += '⚠ <strong>风险点:</strong> 建仓/洗盘时间不确定，需要耐心等待，切忌追高。';
    } else if (phase === 5 || phase === 6) {
        html += '🔴 <strong>短期看跌</strong> — 主力出货阶段，卖压增大，反弹都是减仓机会。<br>';
        html += '🔴 <strong>中期偏空</strong> — 趋势已经走坏，不建议继续持有。<br>';
        html += '⚠ <strong>风险点:</strong> 主力出货后可能持续阴跌，不应抱有任何反弹幻想。';
    } else {
        html += '📊 数据不足，无法给出明确预判。建议参考基本面和技术面综合判断。';
    }
    
    html += '</div>';
    return html;
}

function _buildRiskAssessment(force, breakout, q) {
    var riskScore = 0;
    var items = [];
    var phase = force.phase || 0;

    if (phase >= 5) { riskScore += 30; items.push('主力进入末期/出货阶段'); }
    else if (phase >= 3) { riskScore += 5; }
    else { riskScore += 15; items.push('尚未进入主升浪'); }

    if (breakout.status === 'warning_trap') { riskScore += 20; items.push('检测到诱多/诱空陷阱信号'); }
    if ((q.pe_ttm || 0) > 100) { riskScore += 10; items.push('PE过高，估值风险'); }
    if ((q.turnover_pct || 0) > 15) { riskScore += 10; items.push('换手率过高'); }

    var level = riskScore >= 40 ? '高' : riskScore >= 20 ? '中' : '低';
    var color = riskScore >= 40 ? 'var(--danger)' : riskScore >= 20 ? 'var(--warning)' : 'var(--success)';

    return '<div style="text-align:center;padding:10px;">' +
        '<div style="font-size:36px;font-weight:700;color:' + color + ';">' + riskScore + '/100</div>' +
        '<div style="color:' + color + ';">风险等级: ' + level + '</div>' +
        '<div style="margin-top:8px;font-size:13px;">' + items.map(function(i) { return '<div>• ' + i + '</div>'; }).join('') + '</div>' +
        '</div>';
}

function _buildActionSuggestion(phase, confidence, breakoutStatus, q) {
    var sug = '';
    if (phase >= 5) {
        sug = '🚨 <strong style="color:var(--danger);">建议减仓/清仓</strong> — 主力进入出货阶段，风险大于收益。可考虑卖出后换入买入池中评分更高的标的。';
    } else if (phase === 4) {
        sug = '✅ <strong style="color:var(--success);">坚定持有</strong> — 处于主升浪中期，趋势良好。可根据移动止损策略（回撤5%止盈）锁定利润。';
    } else if (phase === 3) {
        sug = '📈 <strong style="color:var(--up);">加仓或持有</strong> — 主升浪刚启动，是最佳介入时机。止损设在买入价的-7%。';
    } else if (phase === 2) {
        sug = '⏳ <strong style="color:var(--warning);">等待突破</strong> — 洗盘阶段适合小仓位试探，等待放量突破确认后再加仓。';
    } else if (phase === 1) {
        sug = '🔍 <strong style="color:var(--info);">观察建仓</strong> — 底部建仓期，可分批小额买入。注意仓位控制。';
    } else {
        sug = '📊 数据不足，建议观望。';
    }
    return '<div style="padding:10px;font-size:14px;">' + sug + '</div>';
}

// ===== 上涨逻辑与基本面分析 =====
function _buildFundamentalAnalysis(code, q, force, breakout) {
    var pe = q.pe_ttm || 0;
    var peStatic = q.pe_static || 0;
    var pb = q.pb || 0;
    var mcap = q.mcap_yi || 0;
    var changePct = q.change_pct || 0;
    var turnover = q.turnover_pct || 0;
    var name = q.name || '';
    var phase = force.phase || 0;
    var volRatio = q.vol_ratio || 0;
    var amount = (q.amount_wan || 0) / 10000;

    // 上涨逻辑推断（基于阶段+技术面）
    var logicParts = [];
    if (phase === 3) {
        logicParts.push('处于主力主升浪启动阶段，前期已完成建仓+洗盘，目前放量突破平台');
    } else if (phase === 4) {
        logicParts.push('处于主升浪中期，均线多头发散，趋势强劲，市场共识形成');
    } else if (phase === 1 || phase === 2) {
        logicParts.push('处于底部蓄势阶段，主力正在收集筹码，上涨逻辑在积累中');
    }
    if (volRatio > 1.5) logicParts.push('量比' + volRatio.toFixed(1) + '放量明显，增量资金入场');
    if (changePct > 3) logicParts.push('近期涨幅' + changePct.toFixed(0) + '%领涨板块，情绪共振');
    if (pe > 0 && pe < 50) logicParts.push('PE仅' + pe.toFixed(0) + '倍，估值合理偏低，安全边际充足');
    else if (pe > 50 && pe < 100) logicParts.push('PE' + pe.toFixed(0) + '倍处于行业中等水平');
    else if (pe > 100) logicParts.push('PE偏高(' + pe.toFixed(0) + ')，市场给予成长溢价');

    var risingLogic = logicParts.length > 0 ? logicParts.join('；') + '。' : '基于板块轮动+资金流向+技术形态的综合判断。';

    // 明线暗线外部因素分析
    var catalysts = _findExternalCatalysts(code, name, q);

    // 中长线价值判断
    var ltValue = '';
    if (mcap > 200) {
        ltValue = '大市值(' + mcap.toFixed(0) + '亿)蓝筹，行业地位稳固，适合作为中线配置标的。持仓周期3-12个月。';
    } else if (mcap > 50) {
        ltValue = '中盘成长股，市值' + mcap.toFixed(0) + '亿，具有较好的成长弹性。适合波段操作，持仓1-3个月。';
    } else {
        ltValue = '小市值弹性标的，市值' + mcap.toFixed(0) + '亿，波动较大，适合短线博弈。';
    }
    if (pe > 0 && pe < 40) ltValue += ' 当前估值偏低，中长线安全边际较高。';
    else if (pe > 100) ltValue += ' 注意估值偏高，中长线需防范估值回归风险。';

    // 盈利能力（基于PE/PB/行业推断）
    var profitAbility = '';
    if (pe > 0 && pe < 30 && pb < 3) {
        profitAbility = '低PE+低PB组合，盈利稳定，属于价值型标的。ROE大概率在10%以上。';
    } else if (pe > 30 && pe < 80) {
        profitAbility = '中等估值区间，市场给予合理的成长溢价。盈利能力稳健，适合价值成长策略。';
    } else if (pe > 80 && pe < 200) {
        profitAbility = '市场给予较高成长溢价，当前盈利可能处于快速增长期。需关注后续季报验证。';
    } else if (pe > 200) {
        profitAbility = '高PE说明当前盈利较小，市场在博未来成长。盈利波动较大，需谨慎。';
    } else {
        profitAbility = 'PE为负，当前处于亏损状态。关注扭亏拐点。';
    }

    // 盈利预测（基于当前增长趋势推断）
    var forecast = '';
    if (changePct > 0 && phase >= 3) {
        forecast = '当前处于上升趋势，若维持量价配合，短期目标看涨5-10%。中期（1-3月）有望延续上升趋势。长期需关注行业景气度和公司基本面变化。';
    } else if (phase >= 5) {
        forecast = '主力进入末期/出货阶段，短期有回调风险。不宜期待过高收益，以保住利润为主。';
    } else {
        forecast = '处于蓄势阶段，短期方向待明确。中期若突破关键压力位，有望打开上行空间。';
    }

    return '<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;font-size:13px;">' +

        // 上涨逻辑
        '<div style="padding:10px;background:rgba(16,185,129,0.06);border-radius:6px;grid-column:1/-1;">' +
        '<div style="font-weight:700;color:var(--success);margin-bottom:6px;">📈 上涨逻辑</div>' +
        '<div style="color:var(--text-secondary);line-height:1.7;">' + risingLogic + '</div></div>' +

        // 上涨原因（明线+暗线）
        '<div style="padding:10px;background:rgba(245,158,11,0.06);border-radius:6px;">' +
        '<div style="font-weight:700;color:var(--warning);margin-bottom:6px;">🔥 明线驱动（市场可见）</div>' +
        '<div style="color:var(--text-secondary);font-size:12px;line-height:1.7;">' + catalysts.surface + '</div></div>' +

        '<div style="padding:10px;background:rgba(139,92,246,0.08);border-radius:6px;">' +
        '<div style="font-weight:700;color:#c084fc;margin-bottom:6px;">🕵️ 暗线驱动（底层逻辑）</div>' +
        '<div style="color:var(--text-secondary);font-size:12px;line-height:1.7;">' + catalysts.hidden + '</div></div>' +

        // 中长线价值  
        '<div style="padding:10px;background:rgba(59,130,246,0.06);border-radius:6px;">' +
        '<div style="font-weight:700;color:var(--info);margin-bottom:6px;">💎 中长线投资价值</div>' +
        '<div style="color:var(--text-secondary);">' + ltValue + '</div></div>' +

        // 核心竞争力
        '<div style="padding:10px;background:rgba(168,85,247,0.06);border-radius:6px;">' +
        '<div style="font-weight:700;color:#c084fc;margin-bottom:6px;">🛡️ 核心竞争力</div>' +
        '<div style="color:var(--text-secondary);">' +
        (mcap > 200 ? '规模壁垒：大市值行业龙头' : '成长弹性：细分赛道优势') + '<br>' +
        'PE: ' + pe.toFixed(1) + ' | PB: ' + pb.toFixed(2) + '<br>' +
        '市值: ' + mcap.toFixed(0) + '亿' +
        (pe > 0 && pe < 40 ? ' (低估区间)' : '') +
        '</div></div>' +

        // 行业地位
        '<div style="padding:10px;background:rgba(16,185,129,0.06);border-radius:6px;">' +
        '<div style="font-weight:700;color:var(--success);margin-bottom:6px;">🏭 行业地位</div>' +
        '<div style="color:var(--text-secondary);">' +
        (mcap > 500 ? '行业龙头，市场份额领先' : mcap > 100 ? '行业中腰部，具有追赶潜力' : '细分市场参与者') + '<br>' +
        '板块内排名: ' + (mcap > 200 ? '前20%' : '中游') +
        '</div></div>' +

        // 盈利能力
        '<div style="padding:10px;background:rgba(245,158,11,0.06);border-radius:6px;">' +
        '<div style="font-weight:700;color:var(--warning);margin-bottom:6px;">💰 盈利能力</div>' +
        '<div style="color:var(--text-secondary);">' + profitAbility + '</div></div>' +

        // 盈利预测
        '<div style="padding:10px;background:rgba(59,130,246,0.08);border-radius:6px;grid-column:1/-1;">' +
        '<div style="font-weight:700;color:var(--info);margin-bottom:6px;">🔮 盈利预测与展望</div>' +
        '<div style="color:var(--text-secondary);line-height:1.7;">' + forecast + '</div></div>' +

        '</div>';
}

// ===== 外部催化剂知识库 =====
var EXTERNAL_CATALYSTS = {
    '半导体': {
        surface: ['国产替代政策加速推进', 'AI算力需求爆发带动芯片需求', 'DeepSeek等大模型推动推理芯片需求'],
        hidden: ['台积电/三星先进制程产能紧张，国产替代窗口打开', '美国芯片出口管制倒逼国内供应链自主化', '存储芯片/HBM全球短缺，价格持续上涨', '汽车电子/物联网芯片需求结构性增长']
    },
    '芯片': {
        surface: ['AI大模型训练推理拉动GPU/NPU需求', '国产芯片在端侧AI加速渗透'],
        hidden: ['英伟达B200配套液冷/PCB/先进封装供应链溢出', 'HBM3e产能被SK海力士垄断，国产替代紧迫', 'Chiplet先进封装技术突破，降低对先进制程依赖']
    },
    '电子元器件': {
        surface: ['消费电子复苏周期开启', 'AI服务器/数据中心建设加速'],
        hidden: ['MLCC/电感等被动元器件涨价周期启动', '英伟达GB200配套的PCB/连接器/散热模组订单外溢', '华为/苹果新品备货拉动上游元器件需求']
    },
    '券商': {
        surface: ['市场成交量放大，经纪业务弹性显现', 'IPO/再融资政策松绑预期'],
        hidden: ['央国企市值管理考核推进，并购重组预期升温', '社保/险资等长线资金入市预期', '券商自营业务在牛市中弹性最大']
    },
    '通信光纤': {
        surface: ['5G-A/6G建设持续推进', '数据中心光纤互联需求增长'],
        hidden: ['英伟达NVLink/InfiniBand高速互联带动光模块/光纤需求', '海底光缆项目进入密集交付期', 'AI集群对超低延迟光纤的刚性需求']
    },
    '稀土永磁': {
        surface: ['国家石墨烯创新中心获批', '新能源车/风电对永磁材料需求增长'],
        hidden: ['缅甸稀土矿进口受限，供给收缩', '人形机器人电机对高性能钕铁硼需求爆发', '稀土价格底部回升，龙头矿企利润弹性显现']
    },
    '新材料': {
        surface: ['国产替代在高性能材料领域加速', '新能源/半导体对特种材料需求增长'],
        hidden: ['AI算力芯片配套的TIM导热材料/EMI屏蔽材料供不应求', '碳纤维/芳纶等军工复合材料订单饱满', '光伏/锂电上游材料技术迭代带来新需求']
    },
    '机器人': {
        surface: ['CMG世界机器人技能大赛即将开幕', '特斯拉Optimus V3三季度小批量生产'],
        hidden: ['人形机器人丝杠/减速器/电机国产供应链从0到1突破', 'Figure AI/Boston Dynamics等融资扩张产业链', '机器人大脑(具身智能大模型)技术进步加速']
    },
    '军工': {
        surface: ['国防预算持续增长', '军民融合政策推进'],
        hidden: ['十四五规划末期军工订单集中释放', '无人装备/电子对抗等新质战斗力建设加速', '军品定价机制改革提升主机厂利润率']
    },
    '医药': {
        surface: ['创新药密集获批上市', '医保谈判边际改善'],
        hidden: ['GLP-1等多肽药物全球爆火，CDMO产业链受益', 'ADC/双抗等新技术平台License-out加速', '老龄化+消费升级推动医疗需求持续增长']
    },
    '锂电材料': {
        surface: ['新能源车销量超预期', '储能市场爆发增长'],
        hidden: ['碳酸锂价格触底反弹，产业链补库存周期开启', '固态电池技术突破在即，电解质材料先行', '海外电池厂扩产带动中国设备/材料出海']
    },
    'AI算力': {
        surface: ['DeepSeek-V4等开源大模型发布', '各地智算中心建设加速'],
        hidden: ['英伟达GB300/GB200供应链中液冷/HBM/PCB/铜缆连接器价值量提升', '国产AI芯片(华为昇腾/寒武纪)在推理市场快速放量', 'AI应用爆发带动边缘计算芯片需求']
    },
    '面板': {
        surface: ['大尺寸面板价格回升', 'TV/显示器需求回暖'],
        hidden: ['韩国产能退出LCD市场，中国面板厂份额提升至70%+', 'OLED在IT/车载市场渗透加速', 'MicroLED技术突破打开新增长空间']
    },
    '家电': {
        surface: ['以旧换新政策刺激消费', '出口数据超预期'],
        hidden: ['智能家居AI化升级带来换机需求', '海外产能布局规避关税风险', '白电龙头高股息+回购提升股东回报']
    },
    '消费电子': {
        surface: ['苹果VisionPro/MR产品线扩张', 'AI手机/AI PC换机周期启动'],
        hidden: ['端侧AI推理芯片/存储/散热模组价值量翻倍', '华为Mate系列回归带动国产供应链', '折叠屏/钛合金中框等结构件升级']
    },
    '房地产': {
        surface: ['限购限贷政策全面松绑', '央行降准降息'],
        hidden: ['政府收储去库存政策推进，行业出清加速', '城中村改造/保障房建设拉动开工', '优质房企并购重组整合行业格局']
    },
    '智能制造': {
        surface: ['新质生产力政策密集出台', '工业自动化需求增长'],
        hidden: ['人形机器人量产带动核心零部件(丝杠/减速器/传感器)需求', 'AI+工业质检/预测性维护降本增效', '高端数控机床国产替代加速']
    }
};

function _findExternalCatalysts(code, name, q) {
    var sector = '';
    var mcap = q.mcap_yi || 0;
    var changePct = q.change_pct || 0;

    // 智能匹配板块
    var sectorMap = {
        '300623': '半导体', '300319': '电子元器件', '000636': '电子元器件', '688662': '半导体',
        '300285': '电子元器件', '688300': '新材料', '301217': '新材料', '300554': '新材料',
        '000859': '新材料', '601869': '通信光纤', '600909': '券商', '601066': '券商',
        '300835': '稀土永磁', '002141': '锂电材料', '000050': '面板', '603669': '医药',
        '603011': '智能制造', '300031': '机器人', '002577': '消费电子',
        '600162': '房地产', '002668': '家电', '688146': '军工'
    };
    sector = sectorMap[code] || '';

    // 未匹配则通过名称推断
    if (!sector) {
        var nameSectors = {'证券': '券商', '药': '医药', '光电': '面板', '智': '智能制造', '磁': '稀土永磁', '芯': '芯片', '电': '电子元器件', '材': '新材料'};
        for (var kw in nameSectors) {
            if (name.indexOf(kw) >= 0) { sector = nameSectors[kw]; break; }
        }
    }
    if (!sector) sector = '新材料';

    var cat = EXTERNAL_CATALYSTS[sector] || EXTERNAL_CATALYSTS['新材料'];
    var surfaceItems = cat.surface || [];
    var hiddenItems = cat.hidden || [];

    // 根据阶段添加上下文
    if (changePct > 5) {
        surfaceItems.push('今日涨幅领跑板块，短线资金高度聚焦');
        hiddenItems.push('主力借势拉升吸引跟风盘，关注后续量能变化');
    } else if (changePct < -3) {
        hiddenItems.push('回调清洗获利盘，为下一波拉升蓄力');
    }

    if (mcap > 300) {
        hiddenItems.push('大市值标的，机构重仓，走势稳健但弹性较小');
    } else if (mcap < 50) {
        hiddenItems.push('小盘高弹性，游资偏好，波动较大需注意风险');
    }

    return {
        surface: surfaceItems.map(function(s, i) { return (i+1) + '. ' + s; }).join('<br>'),
        hidden: hiddenItems.map(function(h, i) { return (i+1) + '. ' + h; }).join('<br>')
    };
}

// ===== K线图表加载（深度分析内嵌） =====
function _loadAnalysisKline(code) {
    var chartDom = document.getElementById('analysis-kline-chart');
    if (!chartDom) return;
    chartDom.innerHTML = '<p style="text-align:center;padding:40px;color:var(--text-muted);">⏳ 加载K线...</p>';

    fetch('/api/kline?code=' + code + '&period=day&count=80').then(function(r) { return r.json(); }).then(function(data) {
        var klines = data.klines || [];
        if (klines.length === 0) {
            chartDom.innerHTML = '<p style="text-align:center;padding:40px;color:var(--text-muted);">暂无K线数据</p>';
            return;
        }
        var dates = klines.map(function(k) { return k.date; });
        var values = klines.map(function(k) { return [k.open, k.close, k.low, k.high]; });
        var volumes = klines.map(function(k) { return k.volume; });

        var chart = echarts.init(chartDom, 'dark');
        chart.setOption({
            tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
            grid: [{ left: '8%', right: '3%', top: '5%', height: '68%' }, { left: '8%', right: '3%', top: '78%', height: '16%' }],
            xAxis: [{ type: 'category', data: dates, gridIndex: 0, axisLabel: { fontSize: 10 } }, { type: 'category', data: dates, gridIndex: 1, axisLabel: { show: false } }],
            yAxis: [{ type: 'value', gridIndex: 0, scale: true, splitNumber: 4 }, { type: 'value', gridIndex: 1, splitNumber: 2 }],
            series: [
                { type: 'candlestick', data: values, itemStyle: { color: '#ff0000', color0: '#00aa00', borderColor: '#ff0000', borderColor0: '#00aa00' }, xAxisIndex: 0, yAxisIndex: 0 },
                { type: 'bar', data: volumes, itemStyle: { color: function(p) { return p.dataIndex > 0 && values[p.dataIndex][1] >= values[p.dataIndex][0] ? '#ff0000' : '#00aa00'; } }, xAxisIndex: 1, yAxisIndex: 1 }
            ],
            backgroundColor: 'transparent'
        });
    }).catch(function() {
        chartDom.innerHTML = '<p style="text-align:center;padding:40px;color:var(--text-muted);">K线加载失败（请确认网络连接）</p>';
    });
}

// ===== 意图分析渲染 =====
function _renderIntentTable(intentData) {
    if (!intentData || intentData.error) {
        return '<p style="color:var(--text-muted);">' + (intentData ? intentData.error : '暂无数据') + '</p>';
    }

    var overall = intentData.overall_intent || {};
    var headerHtml = '<div style="margin-bottom:12px;padding:10px;background:rgba(139,92,246,0.1);border-radius:6px;">' +
        '<strong>整体意图:</strong> ' + overall.overall_intent +
        ' | 近7日: <span style="color:' + ((overall.total_change_7d||0) >= 0 ? 'var(--up)' : 'var(--down)') + '">' + (overall.total_change_7d > 0 ? '+' : '') + (overall.total_change_7d || 0).toFixed(1) + '%</span>' +
        ' | ' + (overall.up_days||0) + '涨' + (overall.down_days||0) + '跌</div>';

    var tactics = intentData.daily_tactics || [];
    var tableHtml = '<div class="table-container"><table class="data-table" style="font-size:12px;"><thead><tr>' +
        '<th>日期</th><th>涨跌幅</th><th>开盘</th><th>收盘</th><th>最高</th><th>最低</th><th>成交量</th><th>操盘手法</th><th>核心意图</th></tr></thead><tbody>';

    tactics.forEach(function(t) {
        var chgColor = (t.change_pct || 0) >= 0 ? 'var(--up)' : 'var(--down)';
        var rowStyle = t.is_today ? ' style="background:rgba(139,92,246,0.15);font-weight:bold;"' : '';
        tableHtml += '<tr' + rowStyle + '><td>' + t.date + (t.is_today ? ' 【今日】' : '') + '</td>' +
            '<td style="color:' + chgColor + '">' + ((t.change_pct||0) > 0 ? '+' : '') + (t.change_pct||0).toFixed(2) + '%</td>' +
            '<td>' + (t.open||0).toFixed(2) + '</td><td>' + (t.close||0).toFixed(2) + '</td>' +
            '<td>' + (t.high||0).toFixed(2) + '</td><td>' + (t.low||0).toFixed(2) + '</td>' +
            '<td>' + ((t.volume||0)/10000).toFixed(0) + '万手</td>' +
            '<td>' + (t.technique||'') + '</td><td>' + (t.intent||'') + '</td></tr>';
    });

    tableHtml += '</tbody></table></div>';

    // 今日详情
    var today = intentData.today_detail || {};
    var todayHtml = '';
    if (today.is_today) {
        todayHtml = '<div style="margin-top:12px;padding:10px;background:rgba(168,85,247,0.1);border-radius:6px;font-size:13px;">' +
            '<strong>📌 今日总结:</strong> 开盘 ' + (today.open||0).toFixed(2) + '元 | 收盘 ' + (today.close||0).toFixed(2) + '元' +
            ' | 振幅 ' + (today.amplitude||0).toFixed(2) + '%<br>' +
            '<strong>手法:</strong> ' + (today.technique||'') + ' | <strong>意图:</strong> ' + (today.intent||'') +
            (today.detail ? '<br>' + today.detail : '') + '</div>';
    }

    return headerHtml + tableHtml + todayHtml;
}

function _renderForecast3Days(intentData) {
    if (!intentData || !intentData.forecast_3days) {
        return '<p style="color:var(--text-muted);">暂无推演数据</p>';
    }

    var forecast = intentData.forecast_3days || [];
    var html = '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;">';

    var colors = ['rgba(59,130,246,0.15)', 'rgba(139,92,246,0.15)', 'rgba(168,85,247,0.15)'];
    forecast.forEach(function(f, i) {
        html += '<div style="padding:12px;background:' + colors[i] + ';border-radius:8px;font-size:13px;">' +
            '<div style="font-weight:700;color:var(--accent);margin-bottom:6px;">' + f.day + '</div>' +
            '<div style="font-weight:600;margin-bottom:4px;">' + (f.action||'') + '</div>' +
            '<div style="color:var(--text-secondary);font-size:12px;line-height:1.6;">' + (f.technique||'') + '</div>' +
            '<div style="margin-top:6px;padding:4px 8px;background:rgba(245,158,11,0.15);border-radius:4px;font-size:11px;color:var(--warning);">⚡ ' + (f.key||'') + '</div>' +
            '</div>';
    });

    html += '</div>';
    return html;
}

// ==================== 风险控制 ====================
async function checkRisk() {
    try {
        const resp = await fetch('/api/analysis/risk');
        const data = await resp.json();

        document.getElementById('risk-overview').innerHTML = `
            <h4>📊 风险评分</h4>
            <div class="risk-gauge">
                <div class="gauge-value" style="color:${data.risk_score > 70 ? 'var(--danger)' : data.risk_score > 40 ? 'var(--warning)' : 'var(--success)'}">
                    ${data.risk_score}</div>
                <div class="gauge-label">${data.risk_level === 'high' ? '⚠️ 高风险' : data.risk_level === 'medium' ? '⚡ 中风险' : '✅ 低风险'}</div>
            </div>
            <p>市场情绪: ${data.sentiment?.description || '--'}</p>
            <p>上证: ${(data.indices?.sh?.change * 100).toFixed(2)}%</p>
            <p>深证: ${(data.indices?.sz?.change * 100).toFixed(2)}%</p>
        `;

        document.getElementById('risk-events').innerHTML = `
            <h4>🚨 突发事件</h4>
            ${(data.events || []).length === 0 ? '<p style="color:var(--text-muted);">未检测到重大突发事件</p>' :
                data.events.map(e => `<p style="color:var(--warning);font-size:13px;">⚠ ${e.title}</p>`).join('')}
            <h4 style="margin-top:16px;">预警列表</h4>
            ${(data.alerts || []).map(a => `
                <p style="font-size:13px;color:${a.level==='critical'?'var(--danger)':'var(--warning)'};">● ${a.message}</p>
            `).join('')}
        `;

        document.getElementById('position-risk').innerHTML = `
            <h4>📋 仓位状态</h4>
            <p>持仓数量: ${data.position_risk?.position_count || 0}只</p>
            ${(data.position_risk?.warnings || []).map(w => `<p style="color:var(--warning);">⚠ ${w}</p>`).join('')}
        `;
    } catch(e) {
        console.error('加载风险数据失败:', e);
    }
}

async function loadHoldingsMonitor() {
    try {
        const resp = await fetch('/api/portfolio/monitor');
        const data = await resp.json();

        const container = document.getElementById('holdings-monitor');
        if (!data.holdings || data.holdings.length === 0) {
            container.innerHTML = '<p style="color:var(--text-muted);">暂无持仓数据</p>';
            return;
        }

        container.innerHTML = data.holdings.map(h => `
            <div class="stock-card" style="margin-bottom:8px;">
                <div class="code-name">
                    <span class="name">${h.name}</span>
                    <span class="code">${h.code}</span>
                </div>
                <div>成本: ${h.entry_price} | 现价: <span style="color:${h.change_pct >= 0 ? 'var(--up)' : 'var(--down)'}">${h.current_price}</span></div>
                <div>盈亏: <span style="color:${h.change_pct >= 0 ? 'var(--up)' : 'var(--down)'}">${h.change_pct > 0 ? '+' : ''}${h.change_pct}%</span></div>
                <div style="font-size:12px;color:var(--text-muted);">阶段: ${h.phase_name} | 风险: ${h.risk_level}</div>
            </div>
        `).join('');

        // 预警
        if (data.alerts && data.alerts.length > 0) {
            container.innerHTML += '<div style="margin-top:12px;">' +
                data.alerts.map(a => `
                    <div style="padding:8px;background:rgba(239,68,68,0.1);border-radius:4px;margin:4px 0;font-size:13px;">
                        ⚠️ ${a.name}: ${a.reason}
                    </div>
                `).join('') + '</div>';
        }
    } catch(e) {
        console.error('加载持仓监控失败:', e);
    }
}

// ==================== 模拟交易 ====================
async function simPickAndBuy() {
    try {
        var resp = await fetch('/api/sim/pick');
        var data = await resp.json();
        if (data.picks && data.picks.length > 0) {
            alert('模拟买入成功！\n' + data.picks.map(function(p) { return p.name + '(' + p.code + ') 买入价: ' + p.buy_price.toFixed(2) + ' | ' + p.phase; }).join('\n'));
            loadSimTrades();
        } else {
            alert('股票池为空或无符合条件标的');
        }
    } catch(e) {
        alert('选股失败: ' + e.message);
    }
}

async function simCheckHoldings() {
    try {
        var resp = await fetch('/api/sim/check');
        var data = await resp.json();
        if (data.sold > 0) {
            alert('触发卖出信号！\n' + data.details.map(function(d) {
                return d.name + '(' + d.code + ') ' + d.reason + ' | 盈亏: ' + (d.profit_pct > 0 ? '+' : '') + d.profit_pct.toFixed(1) + '% | 持仓' + d.hold_days + '天';
            }).join('\n'));
        } else {
            alert('已检查' + data.checked + '只持仓，未触发卖出信号');
        }
        loadSimTrades();
    } catch(e) {
        alert('检查失败: ' + e.message);
    }
}

async function loadSimTrades() {
    try {
        var resp = await fetch('/api/sim/trades');
        var data = await resp.json();
        var trades = data.trades || [];
        var holding = data.holding || [];
        var stats = data.stats || {};

        var pnlColor = (stats.total_pnl || 0) >= 0 ? 'var(--up)' : 'var(--down)';
        document.getElementById('sim-stats').innerHTML =
            '<div style="display:grid;grid-template-columns:repeat(6,1fr);gap:10px;">' +
            '<div class="vip-summary-card"><div class="vs-label">总交易</div><div class="vs-value">' + (stats.total_trades || 0) + '</div></div>' +
            '<div class="vip-summary-card"><div class="vs-label">胜率</div><div class="vs-value" style="color:' + ((stats.win_rate||0) >= 50 ? 'var(--up)' : 'var(--down)') + '">' + (stats.win_rate || 0) + '%</div></div>' +
            '<div class="vip-summary-card"><div class="vs-label">累计盈亏</div><div class="vs-value" style="color:' + pnlColor + '">' + (stats.total_pnl_pct > 0 ? '+' : '') + (stats.total_pnl_pct || 0).toFixed(1) + '%</div></div>' +
            '<div class="vip-summary-card"><div class="vs-label">平均盈亏</div><div class="vs-value" style="color:' + ((stats.avg_pl_pct||0) >= 0 ? 'var(--up)' : 'var(--down)') + '">' + (stats.avg_pl_pct > 0 ? '+' : '') + (stats.avg_pl_pct || 0).toFixed(1) + '%</div></div>' +
            '<div class="vip-summary-card"><div class="vs-label">平均持仓</div><div class="vs-value">' + (stats.avg_hold_days || 0) + '天</div></div>' +
            '<div class="vip-summary-card"><div class="vs-label">盈亏比</div><div class="vs-value">' + (stats.wins || 0) + ':' + (stats.losses || 0) + '</div></div>' +
            '</div>';

        var holdHtml = '';
        if (holding.length === 0) {
            holdHtml = '<p style="color:var(--text-muted);text-align:center;padding:20px;">暂无模拟持仓</p>';
        } else {
            holdHtml = holding.map(function(h) {
                var buyP = h.buy_price || 0;
                var plPct = h.profit_loss_pct || 0;
                var cl = plPct >= 0 ? 'var(--up)' : 'var(--down)';
                var bg = plPct >= 0 ? 'rgba(255,0,0,0.08)' : 'rgba(0,170,0,0.08)';
                var maxG = h.max_gain_pct || 0;
                var maxL = h.max_loss_pct || 0;
                var days = 0;
                try { days = Math.floor((new Date() - new Date(h.trade_date)) / 86400000); } catch(e) {}
                return '<div style="display:flex;justify-content:space-between;align-items:center;padding:10px;background:' + bg + ';border-radius:6px;margin-bottom:6px;">' +
                    '<div><strong>' + h.name + '</strong> <span style="color:var(--text-muted);">' + h.code + '</span> | ' + h.pool_phase + ' | 买入: ' + buyP.toFixed(2) + ' | ' + days + '天</div>' +
                    '<div style="text-align:right;"><span style="font-weight:700;color:' + cl + ';">' + (plPct > 0 ? '+' : '') + plPct.toFixed(1) + '%</span>' +
                    '<br><span style="font-size:11px;color:var(--text-muted);">最高 +' + maxG.toFixed(1) + '% | 最低 ' + maxL.toFixed(1) + '%</span></div>' +
                    '<button class="btn btn-sm btn-danger" onclick="simManualSell(\'' + h.code + '\',\'' + h.name + '\')">手动卖出</button></div>';
            }).join('');
        }
        document.getElementById('sim-holdings').innerHTML = holdHtml;

        var soldTrades = data.sold || [];
        var histHtml = '';
        if (soldTrades.length === 0) {
            histHtml = '<p style="color:var(--text-muted);text-align:center;padding:20px;">暂无已完结交易</p>';
        } else {
            histHtml = '<div class="table-container"><table class="data-table" style="font-size:12px;"><thead><tr>' +
                '<th>日期</th><th>代码</th><th>名称</th><th>池</th><th>买入价</th><th>卖出价</th><th>盈亏%</th><th>盈亏额</th><th>持仓天</th><th>原因</th></tr></thead><tbody>' +
                soldTrades.map(function(t) {
                    var plC = (t.profit_loss_pct || 0) >= 0 ? 'var(--up)' : 'var(--down)';
                    var reasonMap = {stop_loss: '止损-5%', trailing_stop: '移动止损', manual: '手动卖出', expired: '到期平仓'};
                    return '<tr><td>' + (t.trade_date || '') + '</td><td>' + t.code + '</td><td>' + t.name + '</td>' +
                        '<td>' + t.pool_phase + '</td><td>' + (t.buy_price || 0).toFixed(2) + '</td><td>' + (t.sell_price || 0).toFixed(2) + '</td>' +
                        '<td style="color:' + plC + ';font-weight:600;">' + (t.profit_loss_pct > 0 ? '+' : '') + (t.profit_loss_pct || 0).toFixed(1) + '%</td>' +
                        '<td style="color:' + plC + ';">' + (t.profit_loss > 0 ? '+' : '') + (t.profit_loss || 0).toFixed(2) + '</td>' +
                        '<td>' + (t.hold_days || 0) + '天</td><td>' + (reasonMap[t.sell_reason] || t.sell_reason) + '</td></tr>';
                }).join('') + '</tbody></table></div>';
        }
        document.getElementById('sim-history').innerHTML = histHtml;
    } catch(e) {
        console.error('加载模拟交易失败:', e);
    }
}

async function simManualSell(code, name) {
    if (!confirm('确认手动卖出 ' + name + '(' + code + ') ？将以当前价成交。')) return;
    try {
        var resp = await fetch('/api/sim/manual_sell', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({code: code})
        });
        var data = await resp.json();
        if (data.success) {
            alert('已卖出 ' + name + ' | 卖出价: ' + data.sell_price.toFixed(2) + ' | 盈亏: ' + (data.profit_pct > 0 ? '+' : '') + data.profit_pct.toFixed(1) + '%');
            loadSimTrades();
        }
    } catch(e) {
        alert('卖出失败');
    }
}

// ==================== 同花顺同步池 ====================
async function syncThsPool() {
    document.getElementById('ths-sync-status').innerHTML = '<span style=\"color:var(--warning);\">⏳ 同步中...</span>';
    try {
        var resp = await fetch('/api/ths/sync');
        var data = await resp.json();
        if (data.success) {
            document.getElementById('ths-sync-status').innerHTML = '<span style=\"color:var(--success);\">✅ ' + data.message + '</span>';
            loadThsPool();
        } else {
            document.getElementById('ths-sync-status').innerHTML = '<span style=\"color:var(--danger);\">❌ ' + data.message + '</span>';
        }
    } catch(e) {
        document.getElementById('ths-sync-status').innerHTML = '<span style=\"color:var(--danger);\">❌ 同步失败: ' + e.message + '</span>';
    }
}

async function loadThsPool() {
    try {
        var resp = await fetch('/api/ths/pool');
        var data = await resp.json();
        var pool = data.pool || [];

        document.getElementById('ths-stats-bar').innerHTML =
            '<div style=\"display:grid;grid-template-columns:repeat(4,1fr);gap:8px;\">' +
            '<div class=\"vip-summary-card\"><div class=\"vs-label\">同步总数</div><div class=\"vs-value\">' + (data.count || 0) + '</div></div>' +
            '<div class=\"vip-summary-card\"><div class=\"vs-label\">今涨</div><div class=\"vs-value\" style=\"color:var(--up);\">' + pool.filter(function(s) { return (s.main_wave_gain||0) > 0; }).length + '</div></div>' +
            '<div class=\"vip-summary-card\"><div class=\"vs-label\">今跌</div><div class=\"vs-value\" style=\"color:var(--down);\">' + pool.filter(function(s) { return (s.main_wave_gain||0) < 0; }).length + '</div></div>' +
            '<div class=\"vip-summary-card\"><div class=\"vs-label\">平均PE</div><div class=\"vs-value\">' + (pool.length > 0 ? (pool.reduce(function(a,s){return a+(s.pe_ttm||0);},0)/pool.length).toFixed(0) : '--') + '</div></div>' +
            '</div>';

        var listHtml = '';
        if (pool.length === 0) {
            listHtml = '<p style=\"color:var(--text-muted);text-align:center;padding:40px;\">尚未同步，点击「同步同花顺自选股」导入</p>';
        } else {
            listHtml = '<div class=\"table-container\"><table class=\"data-table\" style=\"font-size:12px;\">' +
                '<thead><tr><th>代码</th><th>名称</th><th>现价</th><th>涨跌%</th><th>PE</th><th>市值(亿)</th><th>操作</th></tr></thead><tbody>' +
                pool.map(function(s) {
                    var chg = s.main_wave_gain || 0;
                    var cl = chg >= 0 ? 'var(--up)' : 'var(--down)';
                    return '<tr><td>' + s.code + '</td><td><strong>' + (s.name || '--') + '</strong></td>' +
                        '<td>' + ((s.entry_price || 0)).toFixed(2) + '</td>' +
                        '<td style=\"color:' + cl + ';font-weight:600;\">' + (chg > 0 ? '+' : '') + chg.toFixed(2) + '%</td>' +
                        '<td>' + ((s.pe_ttm || 0)).toFixed(0) + '</td>' +
                        '<td>' + ((s.market_cap || 0)).toFixed(0) + '</td>' +
                        '<td><button class=\"btn btn-sm\" onclick=\"quickAddToBuyPool(\'' + s.code + '\')\">加入买入池</button></td></tr>';
                }).join('') + '</tbody></table></div>';
        }
        document.getElementById('ths-pool-list').innerHTML = listHtml;
    } catch(e) {
        console.error('加载同花顺池失败:', e);
    }
}

function quickAddToBuyPool(code) {
    if (!confirm('将 ' + code + ' 加入买入池？')) return;
    fetch('/api/pool/quick_add', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({code: code})
    }).then(function(r) { return r.json(); }).then(function(d) {
        alert(d.success ? '已加入买入池' : ('失败: ' + (d.error || '')));
    }).catch(function() { alert('添加失败'); });
}

// ==================== 突发事件 ====================
var eventFilter = 'all';

function filterEvents(type, btn) {
    eventFilter = type;
    document.querySelectorAll('.event-filter').forEach(function(b) { b.classList.remove('active'); });
    if (btn) btn.classList.add('active');
    loadEvents();
}

async function loadEvents() {
    try {
        var resp = await fetch('/api/events?days=7');
        var data = await resp.json();
        var events = data.events || [];
        var stats = data.severity_stats || {};
        var poolImpact = data.pool_impact || [];

        // 严重程度统计
        document.getElementById('event-severity-bar').innerHTML =
            '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;">' +
            '<div style="padding:10px;background:rgba(239,68,68,0.15);border-radius:6px;text-align:center;"><div style="font-size:11px;color:var(--text-muted);">🔴 极端</div><div style="font-size:22px;font-weight:700;color:#ef4444;">' + (stats.critical || 0) + '</div></div>' +
            '<div style="padding:10px;background:rgba(245,158,11,0.15);border-radius:6px;text-align:center;"><div style="font-size:11px;color:var(--text-muted);">🟠 重要</div><div style="font-size:22px;font-weight:700;color:#f59e0b;">' + (stats.high || 0) + '</div></div>' +
            '<div style="padding:10px;background:rgba(234,179,8,0.12);border-radius:6px;text-align:center;"><div style="font-size:11px;color:var(--text-muted);">🟡 一般</div><div style="font-size:22px;font-weight:700;color:#eab308;">' + (stats.medium || 0) + '</div></div>' +
            '<div style="padding:10px;background:rgba(59,130,246,0.12);border-radius:6px;text-align:center;"><div style="font-size:11px;color:var(--text-muted);">🔵 信息</div><div style="font-size:22px;font-weight:700;color:#3b82f6;">' + (stats.low || 0) + '</div></div></div>';

        // 持仓影响
        if (poolImpact.length > 0) {
            var impactPanel = document.getElementById('event-pool-impact');
            impactPanel.style.display = 'block';
            impactPanel.innerHTML = '<h4 style="margin-bottom:8px;">⚡ 对持仓影响（' + poolImpact.length + '只股票受影响）</h4>' +
                poolImpact.map(function(imp) {
                    return '<div style="padding:8px;margin-bottom:4px;background:rgba(239,68,68,0.08);border-radius:4px;font-size:12px;">' +
                        '<strong>' + imp.name + '</strong>(' + imp.code + ') ' +
                        imp.events.map(function(e) { return '<span style="color:var(--' + (e.direction === 'positive' ? 'up' : 'down') + ');">' + e.title.substring(0,15) + '</span>'; }).join(' | ') +
                        '</div>';
                }).join('') + '';
        }

        // 事件时间线
        var filtered = events;
        if (eventFilter !== 'all') {
            filtered = events.filter(function(e) {
                return e.severity === eventFilter || e.event_type === eventFilter;
            });
        }

        var sevMap = {critical: {color: '#ef4444', label: '极端', bg: 'rgba(239,68,68,0.1)'}, high: {color: '#f59e0b', label: '重要', bg: 'rgba(245,158,11,0.1)'}, medium: {color: '#eab308', label: '一般', bg: 'rgba(234,179,8,0.08)'}, low: {color: '#3b82f6', label: '信息', bg: 'rgba(59,130,246,0.08)'}};
        var dirMap = {positive: '🟢 利好', negative: '🔴 利空', neutral: '⚪ 中性'};
        var typeMap = {policy: '政策', company: '公司', industry: '行业', macro: '宏观', intl: '国际', breaking: '突发'};

        document.getElementById('event-timeline').innerHTML = filtered.map(function(e) {
            var sev = sevMap[e.severity] || sevMap.medium;
            return '<div style="padding:12px;margin-bottom:8px;background:' + sev.bg + ';border-left:3px solid ' + sev.color + ';border-radius:6px;">' +
                '<div style="display:flex;justify-content:space-between;align-items:center;">' +
                '<div style="font-weight:600;">' + e.title + '</div>' +
                '<div><span style="background:' + sev.color + ';color:#fff;padding:2px 8px;border-radius:4px;font-size:11px;">' + sev.label + '</span>' +
                ' <span style="color:var(--text-muted);font-size:11px;">' + (typeMap[e.event_type] || '') + '</span></div></div>' +
                '<div style="margin-top:6px;font-size:12px;">' +
                '<span style="color:var(--text-muted);">' + (e.event_date || '') + '</span>' +
                ' | ' + (dirMap[e.impact_direction] || '') +
                (e.summary ? ' | ' + e.summary.substring(0, 80) : '') + '</div>' +
                (e.impact_analysis ? '<div style="margin-top:6px;padding:6px;background:rgba(0,0,0,0.2);border-radius:4px;font-size:12px;color:var(--text-secondary);">📊 ' + e.impact_analysis + '</div>' : '') +
                (e.action_suggestion ? '<div style="margin-top:4px;font-size:12px;color:var(--warning);">⚡ ' + e.action_suggestion + '</div>' : '') +
                '</div>';
        }).join('') || '<p style="color:var(--text-muted);text-align:center;padding:40px;">暂无突发事件</p>';
    } catch(e) {
        console.error('加载事件失败:', e);
    }
}


// ==================== 交易记录 ====================
async function loadTrades() {
    try {
        const resp = await fetch('/api/trades?limit=50');
        const data = await resp.json();

        document.getElementById('trade-stats-bar').innerHTML = `
            <div class="trade-stat">
                <div class="ts-label">总交易</div>
                <div class="ts-value">${data.stats.total_trades}</div>
            </div>
            <div class="trade-stat">
                <div class="ts-label">胜率</div>
                <div class="ts-value">${data.stats.win_rate}%</div>
            </div>
            <div class="trade-stat">
                <div class="ts-label">平均收益</div>
                <div class="ts-value">${data.stats.avg_profit_pct}%</div>
            </div>
            <div class="trade-stat">
                <div class="ts-label">累计盈亏</div>
                <div class="ts-value" style="color:${data.stats.total_profit >= 0 ? 'var(--up)' : 'var(--down)'}">
                    ¥${data.stats.total_profit}
                </div>
            </div>
            <div class="trade-stat">
                <div class="ts-label">最大盈利</div>
                <div class="ts-value" style="color:var(--up)">${data.stats.max_profit_pct}%</div>
            </div>
            <div class="trade-stat">
                <div class="ts-label">最大亏损</div>
                <div class="ts-value" style="color:var(--down)">${data.stats.max_loss_pct}%</div>
            </div>
            <div class="trade-stat">
                <div class="ts-label">平均持仓</div>
                <div class="ts-value">${data.stats.avg_hold_days}天</div>
            </div>
        `;

        document.getElementById('trades-table-body').innerHTML = (data.trades || []).map(t => `
            <tr>
                <td>${t.code}</td>
                <td>${t.name}</td>
                <td>${t.buy_date || '--'}</td>
                <td>${t.buy_price || '--'}</td>
                <td>${t.sell_date || '持仓中'}</td>
                <td>${t.sell_price || '--'}</td>
                <td class="${(t.profit_loss_pct || 0) >= 0 ? 'profit-positive' : 'profit-negative'}">
                    ${t.profit_loss_pct != null ? ((t.profit_loss_pct >= 0 ? '+' : '') + t.profit_loss_pct + '%') : '--'}
                </td>
                <td>${t.hold_days || '--'}</td>
                <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;">${t.exit_reason || '--'}</td>
            </tr>
        `).join('');
    } catch(e) {
        console.error('加载交易记录失败:', e);
    }
}

// ==================== 绩效报告 ====================
async function loadPerformanceReport() {
    try {
        const resp = await fetch('/api/portfolio/report');
        const data = await resp.json();
        const stats = data.performance?.stats || {};
        const monthly = data.performance?.monthly_performance || [];

        document.getElementById('performance-report').innerHTML = `
            <div class="stats-grid" style="margin-bottom:16px;">
                <div class="stat-card">
                    <div class="stat-label">累计收益率</div>
                    <div class="stat-value" style="color:${stats.total_profit >= 0 ? 'var(--up)' : 'var(--down)'}">
                        ${stats.total_profit >= 0 ? '+' : ''}¥${stats.total_profit}
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">胜率</div>
                    <div class="stat-value">${stats.win_rate}%</div>
                    <div class="stat-sub">${stats.wins}胜 ${stats.losses}负</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">平均盈亏</div>
                    <div class="stat-value">${stats.avg_profit_pct}%</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">当前持仓浮盈</div>
                    <div class="stat-value" style="color:${data.performance.floating_pl >= 0 ? 'var(--up)' : 'var(--down)'}">
                        ${data.performance.floating_pl_pct.toFixed(2)}%
                    </div>
                    <div class="stat-sub">¥${data.performance.floating_pl.toFixed(2)}</div>
                </div>
            </div>

            <div class="panel">
                <h3>月度表现</h3>
                <table class="data-table">
                    <thead><tr><th>月份</th><th>收益</th><th>交易笔数</th><th>胜率</th></tr></thead>
                    <tbody>${monthly.map(m => `
                        <tr>
                            <td>${m.month}</td>
                            <td class="${m.profit >= 0 ? 'profit-positive' : 'profit-negative'}">¥${m.profit}</td>
                            <td>${m.trades}</td>
                            <td>${m.win_rate}%</td>
                        </tr>
                    `).join('')}</tbody>
                </table>
            </div>

            <div class="panel">
                <h3>持仓建议</h3>
                ${(data.report?.suggestions || []).map(s => `<p style="padding:4px 0;">📌 ${s}</p>`).join('')}
            </div>
        `;
    } catch(e) {
        console.error('加载绩效报告失败:', e);
    }
}

// ==================== VIP持仓池 ====================
async function loadVipHoldings() {
    try {
        var resp = await fetch('/api/vip/holdings');
        var data = await resp.json();
        var holdings = data.holdings || [];
        var summary = data.summary || {};

        // 总览统计
        var sumDiv = document.getElementById('vip-summary');
        sumDiv.innerHTML =
            '<div class="vip-summary-card"><div class="vs-label">持仓数</div><div class="vs-value">' + (summary.total_holdings || 0) + '只</div></div>' +
            '<div class="vip-summary-card"><div class="vs-label">持仓成本</div><div class="vs-value">¥' + ((summary.total_cost || 0)/10000).toFixed(1) + '万</div></div>' +
            '<div class="vip-summary-card"><div class="vs-label">浮动盈亏</div><div class="vs-value" style="color:' + ((summary.total_profit_loss_pct || 0) >= 0 ? 'var(--up)' : 'var(--down)') + '">' + (summary.total_profit_loss_pct || 0).toFixed(2) + '%</div></div>' +
            '<div class="vip-summary-card"><div class="vs-label">盈利/亏损</div><div class="vs-value"><span style="color:var(--up)">' + (summary.profit_count || 0) + '</span> / <span style="color:var(--down)">' + (summary.loss_count || 0) + '</span></div></div>' +
            '<div class="vip-summary-card"><div class="vs-label">需操作</div><div class="vs-value" style="color:' + ((summary.need_action_count || 0) > 0 ? 'var(--warning)' : 'var(--text-muted)') + '">' + (summary.need_action_count || 0) + '只</div></div>';

        // 持仓卡片
        var listDiv = document.getElementById('vip-holdings-list');
        if (holdings.length === 0) {
            listDiv.innerHTML = '<p style="color:var(--text-muted);text-align:center;padding:40px;">暂无VIP持仓，请手动添加</p>';
            return;
        }

        listDiv.innerHTML = holdings.map(function(h) {
            var pl = h.profit_loss || 0;
            var plPct = h.profit_loss_pct || 0;
            var plColor = pl >= 0 ? 'var(--up)' : 'var(--down)';
            var plBg = pl >= 0 ? 'rgba(255,0,0,0.1)' : 'rgba(0,170,0,0.1)';
            var changePct = h.change_pct || 0;

            var sug = h.ai_suggestion || '';
            var sugClass = 'vip-sug-medium';
            if (sug.indexOf('清仓') >= 0 || sug.indexOf('止损') >= 0) sugClass = 'vip-sug-danger';
            else if (sug.indexOf('减仓') >= 0 || sug.indexOf('止盈') >= 0) sugClass = 'vip-sug-warning';
            else if (sug.indexOf('持有') >= 0 || sug.indexOf('加仓') >= 0) sugClass = 'vip-sug-strong';

            var sugScore = h.ai_suggestion_score || 0;
            var sugTime = h.ai_suggestion_time || '';

            var swapHtml = '';
            if (h.swap_suggestion) {
                swapHtml = '<div class="vip-swap-box">🔄 ' + h.swap_suggestion + (h.swap_target_name ? ' → <strong>' + h.swap_target_name + '(' + h.swap_target_code + ')</strong>' : '') + '<br><span style="color:var(--text-muted);">' + (h.swap_reason || '') + '</span></div>';
            }

            return '<div class="vip-holding-card">' +
                '<div class="vip-card-header">' +
                '<div><span class="vip-card-name">' + h.name + '</span><span class="vip-card-code">' + h.code + '</span></div>' +
                '<div><span class="vip-pl-badge" style="background:' + plBg + ';color:' + plColor + '">' + (plPct >= 0 ? '+' : '') + plPct.toFixed(2) + '%</span>' +
                '<span style="color:' + (changePct >= 0 ? 'var(--up)' : 'var(--down)') + ';font-size:13px;margin-left:8px;">' + (changePct > 0 ? '+' : '') + changePct.toFixed(2) + '%</span></div>' +
                '</div>' +
                '<div class="vip-grid">' +
                '<div class="vip-grid-item"><div class="vgi-label">建仓日期</div><div class="vgi-value">' + (h.entry_date || '--') + '</div></div>' +
                '<div class="vip-grid-item"><div class="vgi-label">建仓价</div><div class="vgi-value">¥' + (h.entry_price || 0).toFixed(2) + '</div></div>' +
                '<div class="vip-grid-item"><div class="vgi-label">持仓天数</div><div class="vgi-value">' + (h.hold_days || 0) + '天</div></div>' +
                '<div class="vip-grid-item"><div class="vgi-label">数量</div><div class="vgi-value">' + (h.shares || 0) + '股</div></div>' +
                '<div class="vip-grid-item"><div class="vgi-label">当前价</div><div class="vgi-value" style="color:' + plColor + '">¥' + ((h.current_price || 0)).toFixed(2) + '</div></div>' +
                '<div class="vip-grid-item"><div class="vgi-label">持仓市值</div><div class="vgi-value">¥' + ((h.current_value || 0)/10000).toFixed(1) + '万</div></div>' +
                '<div class="vip-grid-item"><div class="vgi-label">浮动盈亏</div><div class="vgi-value" style="color:' + plColor + '">¥' + (pl/10000).toFixed(1) + '万</div></div>' +
                '<div class="vip-grid-item"><div class="vgi-label">盈亏比例</div><div class="vgi-value" style="color:' + plColor + '">' + (plPct >= 0 ? '+' : '') + plPct.toFixed(2) + '%</div></div>' +
                '</div>' +
                (sug ? '<div class="vip-suggestion-box ' + sugClass + '"><div class="vip-sug-header"><span class="sug-label">🤖 AI建议</span><span class="sug-score">信心: ' + sugScore.toFixed(0) + '%</span></div>' + sug + (sugTime ? ' <span style="color:var(--text-muted);font-size:11px;">(' + sugTime + ')</span>' : '') + '</div>' : '') +
                swapHtml +
                '<div class="vip-card-actions">' +
                '<button class="btn btn-sm" onclick="analyzeStock(\'' + h.code + '\')">深度分析</button>' +
                '<button class="btn btn-sm" onclick="sellVipHolding(\'' + h.code + '\',\'' + h.name + '\',' + (h.current_price || 0) + ')">卖出</button>' +
                '<button class="btn btn-sm" onclick="editVipHolding(\'' + h.code + '\',' + h.entry_price + ',' + h.shares + ',\'' + (h.entry_date || '') + '\',' + (h.stop_loss_price || 0) + ',' + (h.take_profit_price || 0) + ')">编辑</button>' +
                '<button class="btn btn-sm btn-danger" onclick="removeVipHolding(\'' + h.code + '\',\'' + h.name + '\')">删除</button>' +
                '</div></div>';
        }).join('');
    } catch(e) {
        console.error('加载VIP持仓失败:', e);
    }
}

async function addVipHolding() {
    var code = document.getElementById('vip-code').value.trim();
    var price = parseFloat(document.getElementById('vip-price').value);
    var shares = parseInt(document.getElementById('vip-shares').value);
    var entryDate = document.getElementById('vip-entry-date').value.trim();
    var stopLoss = parseFloat(document.getElementById('vip-stop-loss').value) || null;
    var takeProfit = parseFloat(document.getElementById('vip-take-profit').value) || null;

    if (!code) return alert('请输入股票代码');
    if (!price || price <= 0) return alert('请输入有效的建仓价格');
    if (!shares || shares <= 0) return alert('请输入有效的持股数量');
    if (!entryDate) entryDate = new Date().toISOString().split('T')[0];

    try {
        var body = {code: code, entry_price: price, shares: shares, entry_date: entryDate};
        if (stopLoss) body.stop_loss_price = stopLoss;
        if (takeProfit) body.take_profit_price = takeProfit;

        var resp = await fetch('/api/vip/holdings/add', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(body)
        });
        var data = await resp.json();
        if (data.success) {
            document.getElementById('vip-code').value = '';
            document.getElementById('vip-price').value = '';
            document.getElementById('vip-shares').value = '';
            document.getElementById('vip-entry-date').value = '';
            document.getElementById('vip-stop-loss').value = '';
            document.getElementById('vip-take-profit').value = '';
            loadVipHoldings();
        } else {
            alert(data.error || '添加失败');
        }
    } catch(e) {
        alert('添加失败: ' + e.message);
    }
}

async function sellVipHolding(code, name, currentPrice) {
    var sellPrice = prompt('当前价 ¥' + currentPrice.toFixed(2) + '\n输入卖出价格（留空使用当前价）:', currentPrice.toFixed(2));
    if (sellPrice === null) return;
    var price = parseFloat(sellPrice) || currentPrice;
    if (!confirm('确认卖出 ' + name + '(' + code + ') ？\n卖出价: ¥' + price.toFixed(2))) return;
    try {
        await fetch('/api/vip/holdings/sell', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({code: code, sell_price: price})
        });
        loadVipHoldings();
    } catch(e) {
        alert('操作失败');
    }
}

async function editVipHolding(code, entryPrice, shares, entryDate, stopLoss, takeProfit) {
    var newPrice = prompt('建仓价格:', entryPrice);
    if (newPrice === null) return;
    var newShares = prompt('持股数量:', shares);
    if (newShares === null) return;
    var newDate = prompt('建仓日期:', entryDate);
    if (newDate === null) return;
    var newSL = prompt('止损价(0=不设):', stopLoss || 0);
    if (newSL === null) return;
    var newTP = prompt('止盈价(0=不设):', takeProfit || 0);
    if (newTP === null) return;

    var updates = {
        code: code,
        entry_price: parseFloat(newPrice) || entryPrice,
        shares: parseInt(newShares) || shares,
        entry_date: newDate || entryDate
    };
    var sl = parseFloat(newSL);
    var tp = parseFloat(newTP);
    if (sl > 0) updates.stop_loss_price = sl;
    if (tp > 0) updates.take_profit_price = tp;

    try {
        await fetch('/api/vip/holdings/update', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(updates)
        });
        loadVipHoldings();
    } catch(e) {
        alert('更新失败');
    }
}

async function removeVipHolding(code, name) {
    if (!confirm('确定删除 ' + name + '(' + code + ') 的持仓记录？')) return;
    try {
        await fetch('/api/vip/holdings/remove', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({code: code})
        });
        loadVipHoldings();
    } catch(e) {
        alert('删除失败');
    }
}

async function generateVipSuggestions() {
    var btn = event.target;
    btn.textContent = '⏳ 分析中...';
    btn.disabled = true;
    try {
        var resp = await fetch('/api/vip/suggestion', {method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({})});
        await resp.json();
        loadVipHoldings();
    } catch(e) {
        alert('分析失败: ' + e.message);
    } finally {
        btn.textContent = '🤖 AI分析建议';
        btn.disabled = false;
    }
}

async function loadVipHistory() {
    try {
        var resp = await fetch('/api/vip/history');
        var data = await resp.json();
        var history = data.history || [];
        var stats = data.stats || {};

        document.getElementById('vip-history').innerHTML =
            '<div class="trade-stats-bar">' +
            '<div class="trade-stat"><div class="ts-label">历史交易</div><div class="ts-value">' + (stats.total || 0) + '</div></div>' +
            '<div class="trade-stat"><div class="ts-label">胜率</div><div class="ts-value">' + (stats.win_rate || 0) + '%</div></div>' +
            '<div class="trade-stat"><div class="ts-label">累计盈亏</div><div class="ts-value" style="color:' + ((stats.total_profit || 0) >= 0 ? 'var(--up)' : 'var(--down)') + '">¥' + ((stats.total_profit || 0)).toFixed(2) + '</div></div>' +
            '</div>' +
            '<div class="table-container"><table class="data-table"><thead><tr>' +
            '<th>代码</th><th>名称</th><th>建仓日期</th><th>建仓价</th><th>卖出日期</th><th>卖出价</th><th>盈亏%</th><th>盈亏金额</th>' +
            '</tr></thead><tbody>' +
            history.map(function(h) {
                var plPct = h.sell_profit_loss_pct || 0;
                return '<tr><td>' + h.code + '</td><td>' + h.name + '</td><td>' + (h.entry_date || '--') + '</td><td>¥' + ((h.entry_price || 0)).toFixed(2) + '</td><td>' + (h.sell_date || '--') + '</td><td>¥' + ((h.sell_price || 0)).toFixed(2) + '</td><td class="' + (plPct >= 0 ? 'profit-positive' : 'profit-negative') + '">' + (plPct >= 0 ? '+' : '') + plPct.toFixed(2) + '%</td><td class="' + (plPct >= 0 ? 'profit-positive' : 'profit-negative') + '">¥' + ((h.sell_profit_loss || 0)).toFixed(2) + '</td></tr>';
            }).join('') + '</tbody></table></div>';
    } catch(e) {
        console.error('加载历史失败:', e);
    }
}
function loadSettings() {
    document.getElementById('settings-form').innerHTML = `
        <div class="setting-group">
            <h4>风控参数</h4>
            <div class="setting-row"><label>单只最大仓位</label><span class="value">20%</span></div>
            <div class="setting-row"><label>总仓位上限</label><span class="value">80%</span></div>
            <div class="setting-row"><label>止损线</label><span class="value">-7%</span></div>
            <div class="setting-row"><label>止盈线</label><span class="value">+20%</span></div>
            <div class="setting-row"><label>移动止损</label><span class="value">-5%</span></div>
        </div>
        <div class="setting-group">
            <h4>股票池参数</h4>
            <div class="setting-row"><label>池总数量</label><span class="value">20只</span></div>
            <div class="setting-row"><label>刚启动</label><span class="value">10只</span></div>
            <div class="setting-row"><label>主升浪中</label><span class="value">10只</span></div>
            <div class="setting-row"><label>同板块上限</label><span class="value">3只</span></div>
            <div class="setting-row"><label>最小市值</label><span class="value">50亿</span></div>
        </div>
        <div class="setting-group">
            <h4>选股条件</h4>
            <div class="setting-row"><label>主升浪最低涨幅</label><span class="value">15%</span></div>
            <div class="setting-row"><label>放量倍率</label><span class="value">1.5倍</span></div>
            <div class="setting-row"><label>最大PE(TTM)</label><span class="value">200</span></div>
            <div class="setting-row"><label>突破确认天数</label><span class="value">3天</span></div>
        </div>
        <div class="setting-group">
            <h4>数据源状态</h4>
            <div class="setting-row"><label>腾讯财经行情</label><span class="value" style="color:var(--success)">✅ 可用</span></div>
            <div class="setting-row"><label>通达信K线</label><span class="value" style="color:var(--success)">✅ 可用</span></div>
            <div class="setting-row"><label>东财资金流</label><span class="value" style="color:var(--warning)">⚠ 限流1s/次</span></div>
            <div class="setting-row"><label>同花顺热点</label><span class="value" style="color:var(--success)">✅ 可用</span></div>
        </div>
    `;
}
