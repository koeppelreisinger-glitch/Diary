/**
 * Echo 前端 — 记录主页逻辑 (records.js)
 * Phase 2 增强：正文编辑 + AI 补充对话
 */

// ── 全局状态 ──────────────────────────────
const pageState = {
    activeTab: 'events',
    startDate: null,
    endDate: null,
    tabs: {
        events:    { page: 1, pageSize: 20, data: null },
        emotions:  { page: 1, pageSize: 20, data: null, localFilters: {} },
        expenses:  { page: 1, pageSize: 20, data: null, localFilters: {} },
        locations: { page: 1, pageSize: 20, data: null, localFilters: {} },
        inspirations: { page: 1, pageSize: 20, data: null },
    }
};

// 今日总结区编辑状态
let todayRecord = null;          // 当前加载到的 daily_record 对象
let todayConversation = null;    // 当前今日会话对象（用于 Path B 补充）
let originalBodyText = '';       // body_text 原始值（用于重置）
let supplementMessages = [];     // 本轮补充消息列表（本地追踪）

const todayEditState = {
    pendingDeleteInspirationIds: new Set(),
    inspirationEditMode: false,
};

const TAB_ENDPOINTS = {
    events:    '/history/events',
    emotions:  '/history/emotions',
    expenses:  '/history/expenses',
    locations: '/history/locations',
    inspirations: '/history/inspirations',
};

// ── 初始化 ──────────────────────────────
async function init() {
    loadTodaySummary();
    loadTabData('events', 1);
}

function refreshAll() {
    for (const key in pageState.tabs) {
        pageState.tabs[key].data = null;
    }
    supplementMessages = [];
    loadTodaySummary();
    loadTabData(pageState.activeTab, 1);
}

// ── 今日总结 ──────────────────────────────
async function loadTodaySummary() {
    const card = document.getElementById('todayCard');
    card.innerHTML = '<div class="status-box"><div class="loading-spinner"></div><div class="text" style="margin-top:12px">加载今日总结...</div></div>';

    // 同时拉取日记和会话
    try {
        const [recordData, convData] = await Promise.all([
            apiFetch('/daily-records/today'),
            apiFetch('/conversations/today').catch(() => null),
        ]);
        todayConversation = convData?.conversation || null;
        renderTodaySummary(recordData);
    } catch (err) {
        card.innerHTML = `<div class="status-box"><div class="icon">❌</div><div class="text">${escapeHtml(err.message)}</div></div>`;
        hidePanel('bodyEditPanel');
        hidePanel('supplementPanel');
    }
}

function renderTodaySummary(data) {
    const card = document.getElementById('todayCard');

    // 状态 A: 生成中
    if (data.is_generating) {
        card.innerHTML = `
            <div class="status-box">
                <div class="icon">⏳</div>
                <div class="text">今日总结正在生成中，请稍后刷新...</div>
                <button class="btn btn-primary btn-sm" onclick="loadTodaySummary()" style="margin-top:8px">🔄 刷新</button>
            </div>`;
        hidePanel('bodyEditPanel');
        hidePanel('supplementPanel');
        hidePanel('todayEditPanel');
        return;
    }

    // 状态 B: 无记录
    if (!data.has_record || !data.record) {
        const actionText = todayConversation && todayConversation.status === 'recording'
            ? '今天的记录还在进行中，去今日记录页继续说吧'
            : '今天还没有生成日记，去今日记录页开始记录吧';
        card.innerHTML = `
            <div class="status-box">
                <div class="icon">📝</div>
                <div class="text">${escapeHtml(actionText)}</div>
                <button class="btn btn-primary btn-sm" onclick="location.href='today.html'" style="margin-top:8px">去今日记录页</button>
            </div>`;
        hidePanel('bodyEditPanel');
        hidePanel('supplementPanel');
        hidePanel('todayEditPanel');
        return;
    }

    // 状态 C: 正常展示
    const r = data.record;
    todayRecord = r;
    originalBodyText = r.body_text || r.summary_text || '';
    const overviewItems = [
        { label: '事件', value: (r.events || []).length },
        { label: '情绪', value: (r.emotions || []).length },
        { label: '消费', value: (r.expenses || []).length },
        { label: '地点', value: (r.locations || []).length },
        { label: '灵感', value: (r.inspirations || []).length },
    ];

    const keywordsHtml = (r.keywords || []).map(k => `<span class="keyword-tag">${escapeHtml(k)}</span>`).join('');
    const overviewHtml = overviewItems.map(item => `
        <div class="today-overview-item">
            <span class="today-overview-label">${item.label}</span>
            <span class="today-overview-value">${item.value}</span>
        </div>
    `).join('');

    // 备注区：可点击展开内联编辑
    const noteText = r.user_note
        ? `💬 ${escapeHtml(r.user_note)}`
        : `<span style="opacity:0.45">💬 点击添加备注…</span>`;
    const noteKwHtml = `
        <div class="today-note today-note--clickable" onclick="showNoteKwEdit()" id="noteDisplay">
            ${noteText} <span class="note-edit-icon">✏️</span>
        </div>
        <div id="noteKwForm" class="note-kw-form" style="display:none">
            <textarea id="note-inline" rows="2" placeholder="今日备注…">${r.user_note ? escapeHtml(r.user_note) : ''}</textarea>
            <div class="note-kw-label">关键词 <span class="hint">英文逗号分隔</span></div>
            <input type="text" id="kw-inline" placeholder="工作, 疲惫, 放松" value="${(r.keywords || []).join(', ')}">
            <div class="note-kw-actions">
                <button class="btn btn-primary btn-sm" onclick="saveNoteKw()">保存</button>
                <button class="btn btn-ghost btn-sm" onclick="hideNoteKwEdit()">取消</button>
                <span id="noteKwStatus" class="edit-status"></span>
            </div>
        </div>
    `;

    card.innerHTML = `
        <div class="today-card-head">
            <div>
                <div class="today-card-label">今天的日记</div>
                <div class="today-date">${formatDateCN(r.record_date)}</div>
            </div>
            <div class="today-score-badge">情绪 ${r.emotion_overall_score}/10</div>
        </div>
        <div class="today-block-title">今日总结</div>
        <div class="today-summary">${escapeHtml(r.summary_text)}</div>
        <div class="today-overview-grid">${overviewHtml}</div>
        <div class="keywords-row">${keywordsHtml}</div>
        ${noteKwHtml}
        ${renderTodaySubSections(r)}
    `;

    // 初始化正文编辑区
    renderBodyEditPanel(r);

    // 初始化补充对话区
    renderSupplementPanel();
}

// ── 辅助：显隐面板 ──────────────────────────────
function hidePanel(id) {
    const el = document.getElementById(id);
    if (el) el.style.display = 'none';
}

function showPanel(id) {
    const el = document.getElementById(id);
    if (el) el.style.display = 'block';
}

// ════════════════════════════════════════════════════════
// ── 正文编辑区（Path A）────────────────────────────────
// ════════════════════════════════════════════════════════

function renderBodyEditPanel(record) {
    const panel = document.getElementById('bodyEditPanel');
    if (!panel) return;
    showPanel('bodyEditPanel');

    const textarea = document.getElementById('bodyTextarea');
    textarea.value = record.body_text || record.summary_text || '';
    originalBodyText = textarea.value;

    const statusEl = document.getElementById('bodyEditStatus');
    if (statusEl) { statusEl.textContent = ''; statusEl.className = 'edit-status'; }
}

/** 保存正文（Path A）：PUT /daily-records/{id}/body */
async function saveBody() {
    if (!todayRecord) return;
    const textarea = document.getElementById('bodyTextarea');
    const newBody = textarea.value.trim();
    if (!newBody) {
        setStatus('bodyEditStatus', '❌ 正文不能为空', 'error');
        return;
    }

    const btn = document.getElementById('saveBodyBtn');
    btn.disabled = true;
    btn.textContent = '保存中...';
    setStatus('bodyEditStatus', '保存中...', '');

    try {
        await apiFetch(`/daily-records/${todayRecord.id}/body`, {
            method: 'PUT',
            body: JSON.stringify({ body_text: newBody }),
        });
        setStatus('bodyEditStatus', '✅ 正文已保存，结构化数据已同步更新', 'success');
        // 重新加载以刷新摘要、子表
        await loadTodaySummary();
        // 清空历史 tab 缓存（子表已重建）
        for (const key in pageState.tabs) {
            pageState.tabs[key].data = null;
        }
        loadTabData(pageState.activeTab, pageState.tabs[pageState.activeTab].page);
    } catch (err) {
        setStatus('bodyEditStatus', `❌ ${err.message}`, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = '💾 保存正文';
    }
}

/** AI 重新生成正文（舍弃当前手动修改，基于会话全量重建） */
async function regenerateBody() {
    if (!todayRecord) return;
    if (!confirm('确定要放弃当前所有手动修改，并基于完整对话记录让 AI 重新生成日记正文吗？\n此操作将同时更新结构化数据。')) return;

    const btn = document.getElementById('regenerateBodyBtn');
    const statusEl = document.getElementById('bodyEditStatus');
    
    btn.disabled = true;
    btn.textContent = '生成中...';
    setStatus('bodyEditStatus', '正在通过 AI 重新生成...', '');

    try {
        await apiFetch(`/daily-records/${todayRecord.id}/supplement`, {
            method: 'POST',
            body: JSON.stringify({}),
        });

        setStatus('bodyEditStatus', '✅ 已重新生成并同步更新', 'success');
        // 重新加载以刷新摘要、子表及正文
        await loadTodaySummary();
        // 清空历史 tab 缓存
        for (const key in pageState.tabs) {
            pageState.tabs[key].data = null;
        }
        loadTabData(pageState.activeTab, pageState.tabs[pageState.activeTab].page);
    } catch (err) {
        setStatus('bodyEditStatus', `❌ ${err.message}`, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = '🤖 AI 重新生成';
    }
}

// ════════════════════════════════════════════════════════
// ── AI 补充对话区（Path B）────────────────────────────
// ════════════════════════════════════════════════════════

function renderSupplementPanel() {
    const panel = document.getElementById('supplementPanel');
    if (!panel) return;

    // 如果没有会话或会话不是 completed，禁用补充区
    if (!todayConversation || todayConversation.status !== 'completed') {
        hidePanel('supplementPanel');
        return;
    }

    showPanel('supplementPanel');

    // 清空本轮消息展示
    const msgContainer = document.getElementById('supplementMessages');
    if (msgContainer) msgContainer.innerHTML = '';

    // 重新渲染已有的本轮补充消息
    supplementMessages.forEach(msg => appendSupplementMessage(msg.role, msg.content));

    // 显隐"保存本次补充"按钮
    const saveBtn = document.getElementById('saveSupplementBtn');
    if (saveBtn) saveBtn.style.display = supplementMessages.length > 0 ? 'inline-flex' : 'none';

    setStatus('supplementStatus', '', '');
}

/** 发送补充消息（Path B 每一轮对话） */
async function sendSupplement() {
    if (!todayConversation || !todayRecord) return;

    const input = document.getElementById('supplementInput');
    const content = input.value.trim();
    if (!content) return;

    const btn = document.getElementById('sendSupplementBtn');
    btn.disabled = true;
    btn.textContent = '发送中...';
    input.disabled = true;

    // 立即展示用户消息
    appendSupplementMessage('user', content);
    input.value = '';

    try {
        const resp = await apiFetch(`/conversations/${todayConversation.id}/messages`, {
            method: 'POST',
            body: JSON.stringify({
                content_type: 'text',
                content: content,
                is_supplement: true,
            }),
        });

        // 记录本轮消息
        supplementMessages.push({ role: 'user', content: content });
        supplementMessages.push({ role: 'ai', content: resp.ai_message.content });

        // 展示 AI 回复
        appendSupplementMessage('ai', resp.ai_message.content);

        // 显示"保存本次补充"按钮
        const saveBtn = document.getElementById('saveSupplementBtn');
        if (saveBtn) saveBtn.style.display = 'inline-flex';

    } catch (err) {
        appendSupplementMessage('system', `发送失败：${err.message}`);
    } finally {
        btn.disabled = false;
        btn.textContent = '发送';
        input.disabled = false;
        input.focus();
    }
}

/** 向补充消息区追加一条消息 DOM */
function appendSupplementMessage(role, content) {
    const container = document.getElementById('supplementMessages');
    if (!container) return;

    const div = document.createElement('div');
    div.className = `supplement-msg supplement-msg-${role}`;

    const icon = role === 'user' ? '👤' : role === 'ai' ? '🤖' : '⚠️';
    div.innerHTML = `
        <div class="supplement-msg-icon">${icon}</div>
        <div class="supplement-msg-content">${escapeHtml(content)}</div>
    `;
    container.appendChild(div);

    // 自动滚动到底部
    container.scrollTop = container.scrollHeight;
}

/** 保存本次补充（Path B 最终确认） */
async function saveSupplement() {
    if (!todayRecord) return;

    const btn = document.getElementById('saveSupplementBtn');
    btn.disabled = true;
    btn.textContent = '处理中...';
    setStatus('supplementStatus', '正在重建日记内容...', '');

    try {
        await apiFetch(`/daily-records/${todayRecord.id}/supplement`, {
            method: 'POST',
            body: JSON.stringify({}),
        });

        setStatus('supplementStatus', '✅ 补充已保存，日记已更新', 'success');
        supplementMessages = [];

        // 重新加载以刷新正文、摘要、子表
        await loadTodaySummary();
        // 清空历史 tab 缓存
        for (const key in pageState.tabs) {
            pageState.tabs[key].data = null;
        }
        loadTabData(pageState.activeTab, pageState.tabs[pageState.activeTab].page);

    } catch (err) {
        setStatus('supplementStatus', `❌ ${err.message}`, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = '✅ 保存本次补充';
    }
}

// ── 通用状态文本设置 ──────────────────────────────
function setStatus(elementId, text, type) {
    const el = document.getElementById(elementId);
    if (!el) return;
    el.textContent = text;
    el.className = 'edit-status' + (type ? ` ${type}` : '');
}

// ════════════════════════════════════════════════════════
// ── 今日子数据折叠展示 ────────────────────────────────
// ════════════════════════════════════════════════════════

function renderTodaySubSections(record) {
    const sections = [];

    sections.push(renderCollapseSection('📋 事件', record.events || [], e =>
        `<span>${escapeHtml(e.content)}</span> ${sourceTag(e.source)} ${e.is_user_confirmed !== undefined ? confirmedIcon(e.is_user_confirmed) : ''}`
    ));
    sections.push(renderCollapseSection('😊 情绪', record.emotions || [], e =>
        `<span>${escapeHtml(e.emotion_label)}</span> ${formatEmotionIndex(e.emotion_label, e.intensity)} ${sourceTag(e.source)}`
    ));
    sections.push(renderCollapseSection('💰 消费', record.expenses || [], e =>
        `<span class="amount-cell">${formatAmount(e.amount, e.currency)}</span> <span>${escapeHtml(e.category || '—')}</span> ${e.description ? `<span style="color:var(--text-secondary);font-size:12px">${escapeHtml(e.description)}</span>` : ''} ${sourceTag(e.source)}`
    ));
    sections.push(renderCollapseSection('📍 地点', record.locations || [], e =>
        `<span>${escapeHtml(e.name)}</span> ${sourceTag(e.source)}`
    ));
    // 灵感区有内联编辑
    sections.push(renderInspirationsSection(record.inspirations || []));

    return sections.join('');
}

function renderCollapseSection(title, items, renderItem) {
    const count = items.length;
    const itemsHtml = count === 0
        ? '<div class="detail-empty">暂无数据</div>'
        : items.map(i => `<div class="collapse-item">${renderItem(i)}</div>`).join('');

    return `
        <div class="collapse-section">
            <div class="collapse-header" onclick="this.nextElementSibling.classList.toggle('open')">
                ${title} <span class="detail-section-count">${count}</span>
            </div>
            <div class="collapse-body">${itemsHtml}</div>
        </div>`;
}

/** 灵感区：支持内联编辑模式 */
function renderInspirationsSection(inspirations) {
    todayEditState.inspirationEditMode = false;
    todayEditState.pendingDeleteInspirationIds.clear();
    const count = inspirations.length;
    return `
        <div class="collapse-section">
            <div class="collapse-header">
                <span style="flex:1;cursor:pointer" onclick="document.getElementById('insCollapseBody').classList.toggle('open')">
                    💡 灵感 <span class="detail-section-count">${count}</span>
                </span>
                <button class="section-inline-edit-btn" id="insEditBtn" onclick="toggleInspirationEditMode()" title="编辑灵感">✏️</button>
            </div>
            <div class="collapse-body" id="insCollapseBody">
                <div id="insInnerContent">${renderInspirationsInner(inspirations, false)}</div>
            </div>
        </div>`;
}

function renderInspirationsInner(inspirations, editMode) {
    if (!editMode) {
        if (inspirations.length === 0) return '<div class="detail-empty">暂无灵感</div>';
        return `<div class="inline-tags-display">${
            inspirations.map(i => `<span class="keyword-tag">${escapeHtml(i.content)}</span> ${sourceTag(i.source)}`).join('')
        }</div>`;
    }
    const insHtml = inspirations.length === 0
        ? '<div class="detail-empty">暂无灵感，可在下方新增</div>'
        : inspirations.map(ins => {
            const isPending = todayEditState.pendingDeleteInspirationIds.has(String(ins.id));
            return `<span class="edit-tag ${isPending ? 'edit-tag-pending' : ''}">
                ${escapeHtml(ins.content)}
                <button class="edit-tag-del" onclick="toggleInspirationDelete('${ins.id}')" title="${isPending ? '撤销删除' : '删除灵感'}">${isPending ? '↩' : '×'}</button>
            </span>`;
        }).join('');
    return `
        <div class="inline-tags-edit">${insHtml}</div>
        <div class="tag-add-row">
            <input type="text" id="insAddInput" class="tag-add-input" placeholder="新增灵感，英文逗号分隔">
            <div class="tag-edit-actions">
                <button class="btn btn-primary btn-sm" onclick="saveInspirationEdits()">保存</button>
                <button class="btn btn-ghost btn-sm" onclick="cancelInspirationEdit()">取消</button>
                <span id="insEditStatus" class="edit-status"></span>
            </div>
        </div>`;
}

// ── Tab 切换 ──────────────────────────────────────────────
function switchTab(tabName) {
    pageState.activeTab = tabName;

    document.querySelectorAll('.tab-item').forEach(el => {
        el.classList.toggle('active', el.dataset.tab === tabName);
    });

    ['emotions', 'locations', 'expenses'].forEach(t => {
        const panel = document.getElementById(`tabFilter-${t}`);
        if (panel) panel.classList.toggle('visible', t === tabName);
    });

    const tabState = pageState.tabs[tabName];
    if (tabState.data) {
        renderTabTable(tabName, tabState.data);
    } else {
        loadTabData(tabName, tabState.page);
    }
}

// ── 日期筛选 ──────────────────────────────
function onDateFilterChange() {
    pageState.startDate = document.getElementById('filterStartDate').value || null;
    pageState.endDate = document.getElementById('filterEndDate').value || null;

    for (const key in pageState.tabs) {
        pageState.tabs[key].data = null;
        pageState.tabs[key].page = 1;
    }
    loadTabData(pageState.activeTab, 1);
}

function clearDateFilter() {
    document.getElementById('filterStartDate').value = '';
    document.getElementById('filterEndDate').value = '';
    pageState.startDate = null;
    pageState.endDate = null;
    onDateFilterChange();
}

// ── 加载表格数据 ──────────────────────────────────────────────
async function loadTabData(tabName, page) {
    const tableArea = document.getElementById('tableArea');
    tableArea.innerHTML = '<div class="status-box"><div class="loading-spinner"></div><div class="text" style="margin-top:12px">加载中...</div></div>';

    const tabState = pageState.tabs[tabName];
    tabState.page = page;

    const params = {
        page: page,
        page_size: tabState.pageSize,
        start_date: pageState.startDate,
        end_date: pageState.endDate,
        ...getLocalFilterParams(tabName),
    };

    try {
        const data = await apiFetch(TAB_ENDPOINTS[tabName] + buildQueryString(params));
        tabState.data = data;
        renderTabTable(tabName, data);
    } catch (err) {
        tableArea.innerHTML = `<div class="status-box"><div class="icon">❌</div><div class="text">${escapeHtml(err.message)}</div></div>`;
    }
}

function getLocalFilterParams(tabName) {
    if (tabName === 'emotions') {
        return {
            emotion_label: document.getElementById('f-emotion_label')?.value.trim() || null,
            min_intensity: document.getElementById('f-min_intensity')?.value || null,
            max_intensity: document.getElementById('f-max_intensity')?.value || null,
        };
    }
    if (tabName === 'locations') {
        return {
            name: document.getElementById('f-name')?.value.trim() || null,
        };
    }
    if (tabName === 'expenses') {
        return {
            category: document.getElementById('f-category')?.value.trim() || null,
            min_amount: document.getElementById('f-min_amount')?.value || null,
            max_amount: document.getElementById('f-max_amount')?.value || null,
        };
    }
    return {};
}

function applyTabFilter(tabName) {
    pageState.tabs[tabName].data = null;
    pageState.tabs[tabName].page = 1;
    loadTabData(tabName, 1);
}

function clearTabFilter(tabName) {
    if (tabName === 'emotions') {
        document.getElementById('f-emotion_label').value = '';
        document.getElementById('f-min_intensity').value = '';
        document.getElementById('f-max_intensity').value = '';
    } else if (tabName === 'locations') {
        document.getElementById('f-name').value = '';
    } else if (tabName === 'expenses') {
        document.getElementById('f-category').value = '';
        document.getElementById('f-min_amount').value = '';
        document.getElementById('f-max_amount').value = '';
    }
    applyTabFilter(tabName);
}

// ── 表格渲染分发 ──────────────────────────────
function renderTabTable(tabName, data) {
    const renderers = {
        events: renderEventsTable,
        emotions: renderEmotionsTable,
        expenses: renderExpensesTable,
        locations: renderLocationsTable,
        inspirations: renderInspirationsTable,
    };
    renderers[tabName](data);
}

function renderEventsTable(data) {
    const headers = ['日期', '事件内容', '来源', '确认', '时间'];
    const rows = data.records.map(r => `
        <tr onclick="goToDetail('${r.record_date}')">
            <td class="date-link">${r.record_date}</td>
            <td class="content-cell">${escapeHtml(r.content)}</td>
            <td>${sourceTag(r.source)}</td>
            <td>${confirmedIcon(r.is_user_confirmed)}</td>
            <td>${formatTime(r.created_at)}</td>
        </tr>`).join('');
    renderTable(headers, rows, data);
}

function renderEmotionsTable(data) {
    const headers = ['日期', '情绪', '情绪指数', '来源', '确认', '时间'];
    const rows = data.records.map(r => `
        <tr onclick="goToDetail('${r.record_date}')">
            <td class="date-link">${r.record_date}</td>
            <td>${escapeHtml(r.emotion_label)}</td>
            <td>${formatEmotionIndex(r.emotion_label, r.intensity)}</td>
            <td>${sourceTag(r.source)}</td>
            <td>${confirmedIcon(r.is_user_confirmed)}</td>
            <td>${formatTime(r.created_at)}</td>
        </tr>`).join('');
    renderTable(headers, rows, data);
}

function renderExpensesTable(data) {
    const headers = ['日期', '金额', '分类', '描述', '来源', '确认'];
    const rows = data.records.map(r => `
        <tr onclick="goToDetail('${r.record_date}')">
            <td class="date-link">${r.record_date}</td>
            <td class="amount-cell">${formatAmount(r.amount, r.currency)}</td>
            <td>${escapeHtml(r.category || '—')}</td>
            <td class="content-cell">${escapeHtml(r.description || '—')}</td>
            <td>${sourceTag(r.source)}</td>
            <td>${confirmedIcon(r.is_user_confirmed)}</td>
        </tr>`).join('');
    renderTable(headers, rows, data);
}

function renderLocationsTable(data) {
    const headers = ['日期', '地点', '来源', '确认', '时间'];
    const rows = data.records.map(r => `
        <tr onclick="goToDetail('${r.record_date}')">
            <td class="date-link">${r.record_date}</td>
            <td>${escapeHtml(r.name)}</td>
            <td>${sourceTag(r.source)}</td>
            <td>${confirmedIcon(r.is_user_confirmed)}</td>
            <td>${formatTime(r.created_at)}</td>
        </tr>`).join('');
    renderTable(headers, rows, data);
}

function renderInspirationsTable(data) {
    const headers = ['日期', '灵感内容', '来源', '时间'];
    const rows = data.records.map(r => `
        <tr onclick="goToDetail('${r.record_date}')">
            <td class="date-link">${r.record_date}</td>
            <td><span class="keyword-tag">${escapeHtml(r.content)}</span></td>
            <td>${sourceTag(r.source)}</td>
            <td>${formatTime(r.created_at)}</td>
        </tr>`).join('');
    renderTable(headers, rows, data);
}

function renderTable(headers, rowsHtml, data) {
    const tableArea = document.getElementById('tableArea');

    if (data.total_count === 0) {
        tableArea.innerHTML = '<div class="status-box"><div class="icon">📭</div><div class="text">暂无记录</div></div>';
        return;
    }

    const headerHtml = headers.map(h => `<th>${h}</th>`).join('');

    tableArea.innerHTML = `
        <div class="table-container">
            <table class="data-table">
                <thead><tr>${headerHtml}</tr></thead>
                <tbody>${rowsHtml}</tbody>
            </table>
            ${renderPagination(data)}
        </div>`;
}

function renderPagination(data) {
    const { total_count, total_pages, current_page } = data;
    const prevDisabled = current_page <= 1 ? 'disabled' : '';
    const nextDisabled = current_page >= total_pages ? 'disabled' : '';

    return `
        <div class="pagination">
            <div class="pagination-info">共 ${total_count} 条 · 第 ${current_page}/${total_pages} 页</div>
            <div class="pagination-actions">
                <button class="btn btn-secondary btn-sm" ${prevDisabled} onclick="loadTabData('${pageState.activeTab}', ${current_page - 1})">上一页</button>
                <button class="btn btn-secondary btn-sm" ${nextDisabled} onclick="loadTabData('${pageState.activeTab}', ${current_page + 1})">下一页</button>
            </div>
        </div>`;
}

function goToDetail(recordDate) {
    window.location.href = `detail.html?date=${recordDate}`;
}

// ════════════════════════════════════════════════════════
// ── 内联备注/关键词编辑 (今日卡片内) ────────────────────
// ════════════════════════════════════════════════════════

function showNoteKwEdit() {
    const form = document.getElementById('noteKwForm');
    const display = document.getElementById('noteDisplay');
    if (form) form.style.display = 'block';
    if (display) display.style.display = 'none';
    document.getElementById('note-inline')?.focus();
}

function hideNoteKwEdit() {
    const form = document.getElementById('noteKwForm');
    const display = document.getElementById('noteDisplay');
    if (form) form.style.display = 'none';
    if (display) display.style.display = 'flex';
}

async function saveNoteKw() {
    if (!todayRecord) return;
    setStatus('noteKwStatus', '保存中...', '');
    const noteVal = document.getElementById('note-inline').value;
    const userNote = noteVal.trim() || null;
    const keywords = document.getElementById('kw-inline').value
        .split(',').map(k => k.trim()).filter(k => k.length > 0);
    try {
        await apiFetch(`/daily-records/${todayRecord.id}`, {
            method: 'PUT',
            body: JSON.stringify({ user_note: userNote, keywords }),
        });
        setStatus('noteKwStatus', '✅ 已保存', 'success');
        await loadTodaySummary();
    } catch (err) {
        setStatus('noteKwStatus', `❌ ${err.message}`, 'error');
    }
}

// ════════════════════════════════════════════════════════
// ── 标签区内联编辑 ────────────────────────────────────
// ════════════════════════════════════════════════════════

function toggleInspirationEditMode() {
    todayEditState.inspirationEditMode = !todayEditState.inspirationEditMode;
    todayEditState.pendingDeleteInspirationIds.clear();
    const btn = document.getElementById('insEditBtn');
    if (btn) btn.textContent = todayEditState.inspirationEditMode ? '✕' : '✏️';
    const inner = document.getElementById('insInnerContent');
    if (inner && todayRecord) {
        inner.innerHTML = renderInspirationsInner(todayRecord.inspirations || [], todayEditState.inspirationEditMode);
        // 展开列表
        document.getElementById('insCollapseBody')?.classList.add('open');
    }
}

function toggleInspirationDelete(insId) {
    const id = String(insId);
    if (todayEditState.pendingDeleteInspirationIds.has(id)) {
        todayEditState.pendingDeleteInspirationIds.delete(id);
    } else {
        todayEditState.pendingDeleteInspirationIds.add(id);
    }
    const inner = document.getElementById('insInnerContent');
    if (inner && todayRecord) {
        inner.innerHTML = renderInspirationsInner(todayRecord.inspirations || [], true);
    }
}

async function saveInspirationEdits() {
    if (!todayRecord) return;
    setStatus('insEditStatus', '保存中...', '');

    const existingActiveInspirationContents = (todayRecord.inspirations || [])
        .filter(t => !todayEditState.pendingDeleteInspirationIds.has(String(t.id)))
        .map(t => t.content.toLowerCase());

    const rawNew = (document.getElementById('insAddInput')?.value || '')
        .split(',').map(t => t.trim()).filter(t => t.length > 0);
    const inspirationsToAdd = [...new Set(rawNew)].filter(t => !existingActiveInspirationContents.includes(t.toLowerCase()));

    try {
        await apiFetch(`/daily-records/${todayRecord.id}`, {
            method: 'PUT',
            body: JSON.stringify({
                inspirations_to_add: inspirationsToAdd,
                inspirations_to_remove: [...todayEditState.pendingDeleteInspirationIds],
            }),
        });
        setStatus('insEditStatus', '✅ 已保存', 'success');
        await loadTodaySummary();
    } catch (err) {
        setStatus('insEditStatus', `❌ ${err.message}`, 'error');
    }
}

function cancelInspirationEdit() {
    toggleInspirationEditMode();
}

