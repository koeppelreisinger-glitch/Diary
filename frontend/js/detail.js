/**
 * Echo 前端 — 历史详情页逻辑 (detail.js)
 */

// ── 缓存 & 编辑状态 ──────────────────────────────
let detailData = null;
let searchTimer = null;

// 待删除标签 ID 集合（保存前暂存，不立即调用接口）
const editState = {
    pendingDeleteTagIds: new Set(),
};

// ── 初始化 ──────────────────────────────
function initDetail() {
    const params = new URLSearchParams(window.location.search);
    const date = params.get('date');

    if (!date) {
        document.getElementById('detailContent').innerHTML =
            '<div class="status-box"><div class="icon">❌</div><div class="text">缺少日期参数</div><a href="index.html" class="btn btn-primary btn-sm" style="margin-top:8px">返回主页</a></div>';
        return;
    }

    document.getElementById('navDate').textContent = formatDateCN(date) + ' 的记录详情';
    document.title = `Echo — ${date} 详情`;
    loadDailyRecordDetail(date);
}

// ── 加载数据 ──────────────────────────────
async function loadDailyRecordDetail(date) {
    const container = document.getElementById('detailContent');

    try {
        const data = await apiFetch(`/history/daily-records/${date}`);
        detailData = data;
        renderFullDetail(data);
        renderEditPanel(data); // 数据就绪后初始化编辑面板
    } catch (err) {
        container.innerHTML = `
            <div class="status-box">
                <div class="icon">📭</div>
                <div class="text">${escapeHtml(err.message)}</div>
                <a href="index.html" class="btn btn-primary btn-sm" style="margin-top:8px">返回主页</a>
            </div>`;
    }
}

// ── 完整渲染 ──────────────────────────────
function renderFullDetail(data, query) {
    const container = document.getElementById('detailContent');
    const hl = query ? (t => highlightText(t, query)) : escapeHtml;

    // 日期信息卡
    const keywordsHtml = (data.keywords || []).map(k =>
        `<span class="keyword-tag">${hl(k)}</span>`
    ).join('');

    // 总结区 — 搜索时只高亮，不隐藏
    const summaryMatch = !query || matchesQuery(data.summary_text, query);
    const noteMatch = !query || matchesQuery(data.user_note, query);

    const noteHtml = data.user_note
        ? `<div class="today-note">💬 ${hl(data.user_note)}</div>`
        : `<div class="today-note" style="opacity:0.5">💬 暂无备注</div>`;
    const bodyTextHtml = data.body_text
        ? `<div class="today-summary">${hl(data.body_text)}</div>`
        : `<div class="detail-empty">暂无正文</div>`;

    // 五类数据
    const eventsHtml = renderDetailSection('📋 事件', data.events || [], query,
        e => matchesQuery(e.content, query),
        e => `<span class="detail-item-main">${hl(e.content)}</span> ${sourceTag(e.source)} ${confirmedIcon(e.is_user_confirmed)}`
    );

    const emotionsHtml = renderDetailSection('😊 情绪', data.emotions || [], query,
        e => matchesQuery(e.emotion_label, query),
        e => `<span class="detail-item-main">${hl(e.emotion_label)}</span>
              <span class="intensity-stars">${formatIntensity(e.intensity)}</span>
              ${sourceTag(e.source)} ${confirmedIcon(e.is_user_confirmed)}`
    );

    const expensesHtml = renderDetailSection('💰 消费', data.expenses || [], query,
        e => matchesQuery(e.category, query) || matchesQuery(e.description, query),
        e => `<span class="amount-cell">${formatAmount(e.amount, e.currency)}</span>
              <span class="detail-item-main">${hl(e.category || '—')} ${e.description ? '· ' + hl(e.description) : ''}</span>
              ${sourceTag(e.source)} ${confirmedIcon(e.is_user_confirmed)}`
    );

    const locationsHtml = renderDetailSection('📍 地点', data.locations || [], query,
        e => matchesQuery(e.name, query),
        e => `<span class="detail-item-main">${hl(e.name)}</span> ${sourceTag(e.source)} ${confirmedIcon(e.is_user_confirmed)}`
    );

    const tagsHtml = renderDetailSection('🏷️ 标签', data.tags || [], query,
        e => matchesQuery(e.tag_name, query),
        e => `<span class="keyword-tag">${hl(e.tag_name)}</span> ${sourceTag(e.source)}`
    );

    container.innerHTML = `
        <div class="card card-accent">
            <div class="today-header">
                <div class="today-date">📅 ${formatDateCN(data.record_date)}</div>
                <div class="today-emotion">😊 ${data.emotion_overall_score}/10</div>
            </div>
            <div class="keywords-row">${keywordsHtml}</div>
        </div>

        <div class="card">
            <div class="detail-section-title">📝 单日摘要</div>
            <div class="today-summary">${hl(data.summary_text || '')}</div>
            ${noteHtml}
        </div>

        <div class="card">
            <div class="detail-section-title">📄 正文</div>
            ${bodyTextHtml}
        </div>

        ${eventsHtml}
        ${emotionsHtml}
        ${expensesHtml}
        ${locationsHtml}
        ${tagsHtml}
    `;
}

// ── 渲染单个详情区域 ──────────────────────────────
function renderDetailSection(title, items, query, matchFn, renderItemFn) {
    let filteredItems = items;
    let countInfo = `${items.length}`;

    if (query) {
        filteredItems = items.filter(matchFn);
        countInfo = `${filteredItems.length} / ${items.length}`;
    }

    const bodyHtml = filteredItems.length === 0
        ? `<div class="detail-empty">${query ? '无匹配结果' : '暂无数据'}</div>`
        : filteredItems.map(item => `<div class="detail-item">${renderItemFn(item)}</div>`).join('');

    return `
        <div class="card detail-section">
            <div class="detail-section-title">${title} <span class="detail-section-count">${countInfo}</span></div>
            ${bodyHtml}
        </div>`;
}

// ── 搜索 ──────────────────────────────
function onSearchInput() {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
        const query = document.getElementById('searchInput').value.trim();
        if (!detailData) return;

        if (!query) {
            renderFullDetail(detailData);
        } else {
            renderFullDetail(detailData, query);
        }
    }, 300);
}

function clearSearch() {
    document.getElementById('searchInput').value = '';
    if (detailData) renderFullDetail(detailData);
}

// ── 搜索工具 ──────────────────────────────
function matchesQuery(text, query) {
    if (!text || !query) return false;
    return text.toLowerCase().includes(query.toLowerCase());
}

function highlightText(text, query) {
    if (!text) return '';
    if (!query) return escapeHtml(text);

    const escaped = escapeHtml(text);
    const escapedQuery = escapeHtml(query);

    // 大小写不敏感替换
    const regex = new RegExp(`(${escapedQuery.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
    return escaped.replace(regex, '<mark>$1</mark>');
}

// ════════════════════════════════════════════════════════
// ── 轻量编辑功能 ──────────────────────────────────────
// ════════════════════════════════════════════════════════

/** 用当前 detailData 初始化/重置编辑面板 */
function renderEditPanel(data) {
    const panel = document.getElementById('editPanel');
    if (!panel) return;
    panel.style.display = 'block';

    document.getElementById('edit-note').value = data.user_note || '';
    document.getElementById('edit-keywords').value = (data.keywords || []).join(', ');
    editState.pendingDeleteTagIds.clear();
    document.getElementById('edit-tags-add').value = '';
    renderCurrentTags(data.tags || []);

    const statusEl = document.getElementById('edit-status');
    if (statusEl) { statusEl.textContent = ''; statusEl.className = 'edit-status'; }
}

/** 渲染"当前标签"区，含待删划线视觉 */
function renderCurrentTags(tags) {
    const container = document.getElementById('edit-tags-current');
    if (!container) return;
    if (tags.length === 0) {
        container.innerHTML = '<span class="detail-empty">暂无标签</span>';
        return;
    }
    container.innerHTML = tags.map(tag => {
        const isPending = editState.pendingDeleteTagIds.has(String(tag.id));
        return `<span class="edit-tag ${isPending ? 'edit-tag-pending' : ''}">
            ${escapeHtml(tag.tag_name)}
            <button class="edit-tag-del" onclick="toggleTagDelete('${tag.id}')"
                title="${isPending ? '撤销删除' : '标记为待删除'}">${isPending ? '↩' : '×'}</button>
        </span>`;
    }).join('');
}

/** 切换某标签的待删状态（不立刻调接口，仅本地标记） */
function toggleTagDelete(tagId) {
    const id = String(tagId);
    if (editState.pendingDeleteTagIds.has(id)) {
        editState.pendingDeleteTagIds.delete(id);
    } else {
        editState.pendingDeleteTagIds.add(id);
    }
    renderCurrentTags(detailData ? detailData.tags || [] : []);
}

/** 保存修改：收集表单 → PUT /daily-records/{id} → 重新加载 */
async function saveEdits() {
    if (!detailData) return;
    const statusEl = document.getElementById('edit-status');
    statusEl.textContent = '保存中...';
    statusEl.className = 'edit-status';

    // user_note：空字符串 → null（后端解释为清空）
    const noteVal = document.getElementById('edit-note').value;
    const userNote = noteVal.trim() === '' ? null : noteVal;

    // keywords：整体替换，允许为空数组
    const keywords = document.getElementById('edit-keywords').value
        .split(',').map(k => k.trim()).filter(k => k.length > 0);

    // tags_to_add：去重 + 过滤与现有未删标签重复的
    const existingActiveTagNames = (detailData.tags || [])
        .filter(t => !editState.pendingDeleteTagIds.has(String(t.id)))
        .map(t => t.tag_name.toLowerCase());

    const rawNew = document.getElementById('edit-tags-add').value
        .split(',').map(t => t.trim()).filter(t => t.length > 0);
    const tagsToAdd = [...new Set(rawNew)].filter(
        t => !existingActiveTagNames.includes(t.toLowerCase())
    );

    const body = {
        user_note: userNote,
        keywords: keywords,
        tags_to_add: tagsToAdd,
        tags_to_remove: [...editState.pendingDeleteTagIds],
    };

    try {
        await apiFetch(`/daily-records/${detailData.id}`, {
            method: 'PUT',
            body: JSON.stringify(body),
        });
        statusEl.textContent = '✅ 保存成功';
        statusEl.className = 'edit-status success';
        await loadDailyRecordDetail(detailData.record_date);
    } catch (err) {
        statusEl.textContent = `❌ ${err.message}`;
        statusEl.className = 'edit-status error';
    }
}

/** 重置：丢弃本地未提交编辑，恢复为当前加载的原始数据 */
function resetEdits() {
    if (!detailData) return;
    renderEditPanel(detailData);
}
