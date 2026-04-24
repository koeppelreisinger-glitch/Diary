/**
 * Echo 前端 — 寻迹页逻辑 (trace.js)
 */

// ── 状态 ─────────────────────────────────────────────
const XJ = { range: 'month', expData: null };

const EMOTION_COLORS = {
    '开心': { bg: '#FEF3E2', color: '#F5A623' },
    '快乐': { bg: '#FEF3E2', color: '#F5A623' },
    '高兴': { bg: '#FEF3E2', color: '#F5A623' },
    '愉快': { bg: '#FEF3E2', color: '#D4870D' },
    '平静': { bg: '#E8F7EE', color: '#4CAF7D' },
    '放松': { bg: '#E8F7EE', color: '#4CAF7D' },
    '安宁': { bg: '#E8F7EE', color: '#4CAF7D' },
    '焦虑': { bg: '#FDECEA', color: '#E05555' },
    '紧张': { bg: '#FDECEA', color: '#E05555' },
    '压力': { bg: '#FDECEA', color: '#E05555' },
    '悲伤': { bg: '#EEF4FD', color: '#5A76D8' },
    '失落': { bg: '#EEF4FD', color: '#5A76D8' },
    '沮丧': { bg: '#EEF4FD', color: '#5A76D8' },
    '愤怒': { bg: '#FDEAF3', color: '#E05FA8' },
    '烦躁': { bg: '#FDEAF3', color: '#E05FA8' },
};
function getEmotionStyle(label) {
    for (const key of Object.keys(EMOTION_COLORS)) {
        if (label.includes(key)) return EMOTION_COLORS[key];
    }
    return { bg: '#EDEBFC', color: '#9D8FE0' };
}

// ── 入口 ─────────────────────────────────────────────
function initTrace() {
    updateRangeLabel();
    loadAll();
}

// ── 时间范围 ──────────────────────────────────────────
function setRange(r) {
    XJ.range = r;
    document.querySelectorAll('.xj-range-tab').forEach(t =>
        t.classList.toggle('active', t.dataset.range === r)
    );
    updateRangeLabel();
    loadAll();
}

function updateRangeLabel() {
    const now = new Date();
    const m = now.getMonth() + 1;
    const labels = { week: '本周', month: `本月 · ${m}月`, quarter: '近三月', all: '全部记录' };
    const el = document.getElementById('xjRangeLabel');
    if (el) el.textContent = labels[XJ.range] || '';
}

function getDateRange() {
    const now = new Date();
    const end = now.toISOString().slice(0, 10);
    let start;
    if (XJ.range === 'week') {
        const d = new Date(now); d.setDate(d.getDate() - 6);
        start = d.toISOString().slice(0, 10);
    } else if (XJ.range === 'month') {
        start = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-01`;
    } else if (XJ.range === 'quarter') {
        const d = new Date(now); d.setMonth(d.getMonth() - 3);
        start = d.toISOString().slice(0, 10);
    } else {
        start = '2000-01-01';
    }
    return { start, end };
}

// ── 并行加载 ──────────────────────────────────────────
async function loadAll() {
    const { start, end } = getDateRange();
    const qs = `start_date=${start}&end_date=${end}&page_size=100`;
    const now = new Date();
    const calQs = `year=${now.getFullYear()}&month=${now.getMonth() + 1}`;

    // 各区域重置为 loading 态
    setLoading('xjExpLoading', true);
    setHtml('xjEmotionChips', '<div class="xj-card-loading">加载中…</div>');
    setHtml('xjStream', '<div class="xj-stream-loading">加载中…</div>');
    setHtml('xjPlaceChips', '<div class="xj-card-loading">加载中…</div>');
    setHtml('xjTagCloud', '<div class="xj-card-loading">加载中…</div>');

    const [expenses, emotions, events, locations, tags, calendar] =
        await Promise.allSettled([
            apiFetch(`/history/expenses?${qs}`),
            apiFetch(`/history/emotions?${qs}`),
            apiFetch(`/history/events?${qs}`),
            apiFetch(`/history/locations?${qs}`),
            apiFetch(`/history/tags?${qs}`),
            apiFetch(`/history/calendar?${calQs}`)
        ]);

    setLoading('xjExpLoading', false);
    renderExpenses(ok(expenses));
    renderEmotions(ok(emotions), ok(calendar));
    renderEventStream(ok(events)?.items);
    renderLocations(ok(locations));
    renderTags(ok(tags));
}

const ok = r => r.status === 'fulfilled' ? r.value : null;
const setHtml = (id, html) => { const el = document.getElementById(id); if (el) el.innerHTML = html; };
const setLoading = (id, show) => { const el = document.getElementById(id); if (el) el.style.display = show ? 'block' : 'none'; };

// ── countUp 动画 ──────────────────────────────────────
function countUp(el, target) {
    if (!el) return;
    const t0 = performance.now(), dur = 700;
    const step = now => {
        const p = Math.min((now - t0) / dur, 1);
        const ease = 1 - (1 - p) ** 3;
        el.textContent = '¥ ' + (target * ease).toFixed(2);
        if (p < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
}

// ── ① 收支渲染 ─────────────────────────────────────────
function renderExpenses(data) {
    const items = data?.items || [];
    XJ.expData = items;

    const emptyEl = document.getElementById('xjExpEmpty');
    if (items.length === 0) {
        ['xjExpOverview', 'xjExpCategory', 'xjExpLedger'].forEach(id => setHtml(id, ''));
        if (emptyEl) emptyEl.style.display = 'block';
        return;
    }
    if (emptyEl) emptyEl.style.display = 'none';

    // 聚合
    const catMap = {};
    let total = 0;
    items.forEach(e => {
        const cat = e.category || '其他';
        const amt = parseFloat(e.amount) || 0;
        catMap[cat] = (catMap[cat] || 0) + amt;
        total += amt;
    });
    const cats = Object.entries(catMap).sort((a, b) => b[1] - a[1]);

    // 概览
    const heroEl = document.getElementById('xjTotalAmt');
    countUp(heroEl, total);

    const topEl = document.getElementById('xjTopCat');
    if (topEl && cats.length) {
        topEl.innerHTML = `<span style="font-size:11px;color:var(--text-muted)">最多支出</span><br>
            <strong>${cats[0][0]}</strong> ¥${cats[0][1].toFixed(0)}`;
    }

    const miniBar = document.getElementById('xjMiniBar');
    if (miniBar) {
        const barColors = ['var(--accent)', 'var(--accent-2)'];
        miniBar.innerHTML = cats.slice(0, 2).map((c, i) => {
            const pct = total > 0 ? (c[1] / total * 100).toFixed(0) : 0;
            return `<div class="xj-mini-bar-row">
                <span class="xj-mini-bar-label">${c[0]}</span>
                <div class="xj-mini-bar-track">
                    <div class="xj-mini-bar-fill" style="width:${pct}%;background:${barColors[i]}"></div>
                </div>
                <span class="xj-mini-bar-pct">${pct}%</span>
            </div>`;
        }).join('');
    }

    // 分类 tab
    const catBars = document.getElementById('xjCatBars');
    if (catBars) {
        catBars.innerHTML = cats.slice(0, 6).map(c => {
            const pct = total > 0 ? (c[1] / total * 100).toFixed(0) : 0;
            return `<div class="xj-cat-bar-row">
                <div class="xj-cat-bar-meta">
                    <span class="xj-cat-bar-name">${c[0]}</span>
                    <span class="xj-cat-bar-amt">¥${c[1].toFixed(2)}</span>
                </div>
                <div class="xj-mini-bar-track" style="margin-top:4px">
                    <div class="xj-mini-bar-fill" style="width:${pct}%;background:var(--grad-warm)"></div>
                </div>
            </div>`;
        }).join('');
    }

    // 明细 tab
    const ledgerList = document.getElementById('xjLedgerList');
    if (ledgerList) {
        const sorted = [...items].sort((a, b) => (b.record_date || '').localeCompare(a.record_date || ''));
        ledgerList.innerHTML = sorted.slice(0, 8).map(e => {
            const dateChip = e.record_date ? e.record_date.slice(5) : '—';
            const desc = e.description || e.category || '消费';
            const amt = parseFloat(e.amount || 0).toFixed(2);
            return `<div class="xj-ledger-row" onclick="goDetail('${e.record_date}')">
                <span class="xj-ledger-date">${dateChip}</span>
                <span class="xj-ledger-desc">${escapeHtml(desc)}</span>
                <span class="xj-ledger-amt">-¥${amt}</span>
            </div>`;
        }).join('');
    }
}

// 切换收支 Tab
function switchExpTab(tab) {
    document.querySelectorAll('.xj-expense-tab').forEach(t =>
        t.classList.toggle('active', t.id === `etab-${tab}`)
    );
    ['overview', 'category', 'ledger'].forEach(t => {
        const el = document.getElementById(`xjExp${t.charAt(0).toUpperCase() + t.slice(1)}`);
        if (el) el.style.display = t === tab ? 'block' : 'none';
    });
}

// ── ② 情绪渲染 ─────────────────────────────────────────
function renderEmotions(emotionsData, calData) {
    // Sparkline from calendar
    const days = calData?.days || [];
    renderSparkline(days);

    // 情绪 chips
    const items = emotionsData?.items || [];
    const chips = document.getElementById('xjEmotionChips');
    if (!chips) return;

    if (items.length === 0) {
        chips.innerHTML = '<div class="xj-card-empty" style="padding:8px 0">🌫️ 还没有情绪记录</div>';
        return;
    }

    // 聚合
    const countMap = {};
    items.forEach(e => {
        const label = e.emotion_label || '未知';
        countMap[label] = (countMap[label] || 0) + 1;
    });
    const sorted = Object.entries(countMap).sort((a, b) => b[1] - a[1]);
    const maxCount = sorted[0]?.[1] || 1;

    chips.innerHTML = sorted.slice(0, 16).map(([label, count]) => {
        const style = getEmotionStyle(label);
        const fontSize = 12 + Math.round((count / maxCount) * 8);
        return `<span class="xj-emotion-chip" style="background:${style.bg};color:${style.color};font-size:${fontSize}px">
            ${escapeHtml(label)}<sup style="font-size:9px;margin-left:2px">${count}</sup>
        </span>`;
    }).join('');
}

function renderSparkline(days) {
    const svg = document.getElementById('xjSparkSvg');
    const wrap = document.getElementById('xjSparkWrap');
    if (!svg || !wrap) return;

    const validDays = days.filter(d => d.emotion_overall_score != null);
    if (validDays.length < 2) {
        wrap.style.display = 'none';
        return;
    }
    wrap.style.display = 'block';

    const W = 300, H = 60, PAD = 4;
    const scores = validDays.map(d => d.emotion_overall_score);
    const minS = Math.min(...scores), maxS = Math.max(...scores) || 10;
    const range = maxS - minS || 1;

    const pts = scores.map((s, i) => {
        const x = PAD + (i / (scores.length - 1)) * (W - PAD * 2);
        const y = H - PAD - ((s - minS) / range) * (H - PAD * 2);
        return [x, y];
    });

    const linePts = pts.map(p => p.join(',')).join(' ');
    const areaPath = `M${pts[0][0]},${H} ` +
        pts.map(p => `L${p[0]},${p[1]}`).join(' ') +
        ` L${pts[pts.length - 1][0]},${H} Z`;

    svg.innerHTML = `
        <defs>
            <linearGradient id="sparkFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="#9D8FE0" stop-opacity="0.3"/>
                <stop offset="100%" stop-color="#9D8FE0" stop-opacity="0"/>
            </linearGradient>
        </defs>
        <path d="${areaPath}" fill="url(#sparkFill)"/>
        <polyline points="${linePts}" fill="none" stroke="#9D8FE0" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
        ${pts.map((p, i) => `<circle cx="${p[0]}" cy="${p[1]}" r="3" fill="#9D8FE0"/>`).join('')}
    `;
}

// ── ③ 事件流水 ─────────────────────────────────────────
function renderEventStream(items) {
    const container = document.getElementById('xjStream');
    if (!container) return;
    container.innerHTML = '';

    if (!items || items.length === 0) {
        container.innerHTML = '<div class="xj-stream-empty">还没有事件记录<br><small>去今日和 Echo 聊聊吧</small></div>';
        return;
    }

    const words = items.slice(0, 18).map(e => {
        const t = e.content || '';
        return t.length > 20 ? t.slice(0, 20) + '…' : t;
    });

    words.forEach((text) => {
        const el = document.createElement('div');
        el.className = 'xj-float-word';
        el.textContent = text;

        const x = 5 + Math.random() * 72;
        const dur = 8 + Math.random() * 7;
        const delay = -(Math.random() * dur);
        const drift = (Math.random() - 0.5) * 28;

        el.style.cssText = `left:${x}%;--xj-dur:${dur}s;--xj-delay:${delay}s;--xj-drift:${drift}px;`;
        container.appendChild(el);
    });
}

// ── ④ 地点渲染 ─────────────────────────────────────────
function renderLocations(data) {
    const container = document.getElementById('xjPlaceChips');
    if (!container) return;
    const items = data?.items || [];
    if (items.length === 0) {
        container.innerHTML = '<div class="xj-card-empty">📍 还没有地点记录</div>';
        return;
    }
    // 去重 + 计数
    const countMap = {};
    items.forEach(l => { const n = l.name || '未知'; countMap[n] = (countMap[n] || 0) + 1; });
    const sorted = Object.entries(countMap).sort((a, b) => b[1] - a[1]);
    container.innerHTML = sorted.slice(0, 12).map(([name, count]) =>
        `<span class="xj-place-chip">📍 ${escapeHtml(name)}${count > 1 ? ` <sup>×${count}</sup>` : ''}</span>`
    ).join('');
}

// ── ⑤ 标签云渲染 ─────────────────────────────────────────
function renderTags(data) {
    const container = document.getElementById('xjTagCloud');
    if (!container) return;
    const items = data?.items || [];
    if (items.length === 0) {
        container.innerHTML = '<div class="xj-card-empty">🏷️ 还没有标签记录</div>';
        return;
    }
    const countMap = {};
    items.forEach(t => { const n = t.tag_name || ''; if (n) countMap[n] = (countMap[n] || 0) + 1; });
    const sorted = Object.entries(countMap).sort((a, b) => b[1] - a[1]);
    const maxC = sorted[0]?.[1] || 1;
    container.innerHTML = sorted.slice(0, 20).map(([name, count]) => {
        const size = 12 + Math.round((count / maxC) * 9);
        const opacity = 0.6 + (count / maxC) * 0.4;
        return `<a class="xj-tag-item" href="index.html?tag=${encodeURIComponent(name)}"
            style="font-size:${size}px;opacity:${opacity}">${escapeHtml(name)}</a>`;
    }).join('');
}

// ── 工具 ─────────────────────────────────────────────
function goDetail(date) {
    if (date) window.location.href = `detail.html?date=${date}`;
}

// escapeHtml 由 api.js 提供，此处不重复声明

