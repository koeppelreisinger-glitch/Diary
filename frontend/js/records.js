/**
 * Echo 前端 — 回忆页逻辑
 * 侧重日记正文、记忆摘录、照片回忆和日记时间流。
 */

const memoryState = {
    page: 1,
    pageSize: 10,
    keyword: '',
    latestRecords: [],
    quoteOffset: 0,
    searchTimer: null,
};

async function init() {
    await Promise.all([
        loadDiaryTimeline(1),
        loadPhotoToday(),
        loadPhotoStream(),
    ]);
}

function refreshAll() {
    memoryState.page = 1;
    memoryState.quoteOffset = 0;
    loadDiaryTimeline(1);
    loadPhotoToday();
    loadPhotoStream();
}

function applyMemorySearch() {
    const input = document.getElementById('memorySearchInput');
    memoryState.keyword = (input?.value || '').trim();
    memoryState.page = 1;
    memoryState.quoteOffset = 0;
    updateMemorySearchControls('搜索中...');
    loadDiaryTimeline(1);
}

function handleMemorySearchInput() {
    const input = document.getElementById('memorySearchInput');
    const nextKeyword = (input?.value || '').trim();
    const clearBtn = document.getElementById('memorySearchClearBtn');
    if (clearBtn) clearBtn.style.display = nextKeyword ? '' : 'none';

    clearTimeout(memoryState.searchTimer);
    memoryState.searchTimer = setTimeout(() => {
        if (nextKeyword === memoryState.keyword) return;
        memoryState.keyword = nextKeyword;
        memoryState.page = 1;
        memoryState.quoteOffset = 0;
        updateMemorySearchControls(nextKeyword ? '搜索中...' : null);
        loadDiaryTimeline(1);
    }, 350);
}

function clearMemorySearch() {
    const input = document.getElementById('memorySearchInput');
    if (input) input.value = '';
    clearTimeout(memoryState.searchTimer);
    memoryState.keyword = '';
    memoryState.page = 1;
    memoryState.quoteOffset = 0;
    updateMemorySearchControls(null);
    loadDiaryTimeline(1);
}

function updateMemorySearchControls(statusText) {
    const clearBtn = document.getElementById('memorySearchClearBtn');
    const status = document.getElementById('memorySearchStatus');
    if (clearBtn) clearBtn.style.display = memoryState.keyword ? '' : 'none';
    if (!status) return;
    if (statusText) {
        status.textContent = statusText;
        return;
    }
    status.textContent = memoryState.keyword
        ? `正在搜索“${memoryState.keyword}”`
        : '回忆页只读回日记和照片；地点、消费、情绪趋势放在寻迹里。';
}

async function loadDiaryTimeline(page) {
    const latest = document.getElementById('latestDiaryContainer');
    const timeline = document.getElementById('diaryTimelineContainer');
    const quotes = document.getElementById('quoteStreamContainer');

    if (timeline) {
        timeline.innerHTML = '<div class="status-box"><div class="loading-spinner"></div><div class="text" style="margin-top:12px">整理日记中...</div></div>';
    }

    const params = {
        page,
        page_size: memoryState.pageSize,
        keyword: memoryState.keyword || null,
    };

    try {
        const data = await apiFetch('/history/daily-records' + buildQueryString(params));
        memoryState.page = page;
        memoryState.latestRecords = data.records || [];
        renderLatestDiary(data.records || []);
        renderQuoteStream(data.records || []);
        renderDiaryTimeline(data);
        renderMemorySearchResult(data);
    } catch (err) {
        const html = `<div class="status-box"><div class="icon">×</div><div class="text">${escapeHtml(err.message)}</div></div>`;
        if (latest) latest.innerHTML = html;
        if (quotes) quotes.innerHTML = '';
        if (timeline) timeline.innerHTML = html;
        updateMemorySearchControls('搜索失败，请稍后重试。');
    }
}

function renderMemorySearchResult(data) {
    const status = document.getElementById('memorySearchStatus');
    if (!status) return;
    if (!memoryState.keyword) {
        updateMemorySearchControls(null);
        return;
    }
    const total = Number(data.total_count || 0);
    if (total > 0) {
        status.innerHTML = `
            找到 ${total} 段和“${escapeHtml(memoryState.keyword)}”有关的记忆。
            <button class="memory-search-view" onclick="goToMemorySearch()">点击查看</button>
        `;
    } else {
        status.textContent = '没有找到这段记忆，换一个词试试。';
    }
}

function renderLatestDiary(records) {
    const container = document.getElementById('latestDiaryContainer');
    if (!container) return;

    if (!records.length) {
        const title = memoryState.keyword ? '没有找到这段记忆' : '还没有可翻阅的日记';
        const text = memoryState.keyword ? '换一个词试试，或者去寻迹里查地点、消费和情绪趋势。' : '完成一次今日记录后，它会出现在这里。';
        container.innerHTML = `
            <div class="memory-empty">
                <div class="memory-empty-title">${escapeHtml(title)}</div>
                <div class="memory-empty-text">${escapeHtml(text)}</div>
                ${memoryState.keyword
                    ? '<button class="btn btn-secondary btn-sm" onclick="clearMemorySearch()">清除搜索</button>'
                    : '<button class="btn btn-primary btn-sm" onclick="location.href=\'today.html\'">去记录</button>'}
            </div>`;
        return;
    }

    const record = records[0];
    container.innerHTML = renderDiaryFeature(record);
}

function renderDiaryFeature(record) {
    const diaryText = record.body_text || record.summary_text || '';
    const quote = pickMemoryQuote(diaryText);
    const preview = buildPreview(diaryText, 150);
    const keywords = renderKeywordTags(record.keywords || []);
    return `
        <article class="memory-feature" onclick="goToDetail('${record.record_date}')">
            <div class="memory-feature-head">
                <div>
                    <div class="memory-date">${formatMemoryDate(record.record_date)}</div>
                    <div class="memory-mood">${emotionMood(record.emotion_overall_score)}</div>
                </div>
                <span class="memory-read-link">继续阅读</span>
            </div>
            <blockquote class="memory-quote">“${escapeHtml(quote)}”</blockquote>
            <p class="memory-preview">${escapeHtml(preview)}</p>
            ${keywords ? `<div class="memory-keywords">${keywords}</div>` : ''}
        </article>`;
}

function renderQuoteStream(records) {
    const container = document.getElementById('quoteStreamContainer');
    if (!container) return;

    if (!records.length) {
        container.innerHTML = '<div class="memory-empty memory-empty-compact">没有找到这段记忆，换一个词试试。</div>';
        return;
    }

    const quotes = records.map(record => ({
        record,
        quote: pickMemoryQuote(record.body_text || record.summary_text || ''),
    })).filter(item => item.quote);

    const visible = quotes.slice(memoryState.quoteOffset, memoryState.quoteOffset + 3);
    const fallback = visible.length ? visible : quotes.slice(0, 3);

    container.innerHTML = `
        <div class="memory-quote-grid">
            ${fallback.map(item => `
                <button class="memory-quote-card" onclick="goToDetail('${item.record.record_date}')">
                    <span class="memory-quote-text">“${escapeHtml(item.quote)}”</span>
                    <span class="memory-quote-meta">${formatDateShort(item.record.record_date)} / ${emotionMood(item.record.emotion_overall_score)}</span>
                </button>
            `).join('')}
        </div>`;
}

function shuffleQuotes() {
    if (!memoryState.latestRecords.length) return;
    memoryState.quoteOffset += 3;
    if (memoryState.quoteOffset >= memoryState.latestRecords.length) {
        memoryState.quoteOffset = 0;
    }
    renderQuoteStream(memoryState.latestRecords);
}

function renderDiaryTimeline(data) {
    const container = document.getElementById('diaryTimelineContainer');
    if (!container) return;

    const records = data.records || [];
    if (!records.length) {
        const text = memoryState.keyword
            ? '没有找到这段记忆，换一个词试试。'
            : '还没有日记。完成今日记录后，时间流会慢慢长出来。';
        container.innerHTML = `<div class="memory-empty">${escapeHtml(text)}</div>`;
        return;
    }

    container.innerHTML = `
        <div class="memory-timeline">
            ${records.map(renderDiaryTimelineItem).join('')}
        </div>
        ${renderMemoryPagination(data)}
    `;
}

function renderDiaryTimelineItem(record) {
    const diaryText = record.body_text || record.summary_text || '';
    const quote = pickMemoryQuote(diaryText);
    const preview = buildPreview(diaryText, 120);
    return `
        <article class="memory-diary-item" onclick="goToDetail('${record.record_date}')">
            <div class="memory-timeline-dot"></div>
            <div class="memory-diary-card">
                <div class="memory-diary-date">${formatMemoryDate(record.record_date)}</div>
                <div class="memory-diary-mood">${emotionMood(record.emotion_overall_score)}</div>
                <div class="memory-diary-quote">“${escapeHtml(quote)}”</div>
                <div class="memory-diary-preview">${escapeHtml(preview)}</div>
                ${renderKeywordTags(record.keywords || []) ? `<div class="memory-keywords">${renderKeywordTags(record.keywords || [])}</div>` : ''}
            </div>
        </article>`;
}

function renderMemoryPagination(data) {
    if ((data.total_pages || 0) <= 1) return '';
    const prevDisabled = data.current_page <= 1 ? 'disabled' : '';
    const nextDisabled = data.current_page >= data.total_pages ? 'disabled' : '';
    return `
        <div class="memory-pagination">
            <button class="btn btn-secondary btn-sm" ${prevDisabled} onclick="loadDiaryTimeline(${data.current_page - 1})">上一页</button>
            <span>${data.current_page}/${data.total_pages}</span>
            <button class="btn btn-secondary btn-sm" ${nextDisabled} onclick="loadDiaryTimeline(${data.current_page + 1})">下一页</button>
        </div>`;
}

async function loadPhotoToday() {
    const container = document.getElementById('photoTodayContainer');
    const row = document.getElementById('photoTodayRow');
    if (!container) return;
    try {
        const data = await apiFetch('/media/on-this-day');
        if (!data.items || data.items.length === 0) {
            if (row) row.style.display = 'none';
            container.style.display = 'none';
            return;
        }
        if (row) row.style.display = '';
        container.style.display = '';
        container.innerHTML = data.items.map(renderPhotoDateGroup).join('');
    } catch (e) {
        if (row) row.style.display = 'none';
        container.style.display = 'none';
    }
}

async function loadPhotoStream() {
    const container = document.getElementById('photoStreamContainer');
    const row = document.getElementById('photoStreamRow');
    if (!container) return;
    container.innerHTML = '<div class="status-box" style="padding:14px 0"><div class="loading-spinner"></div></div>';
    try {
        const data = await apiFetch('/media/history?page=1&page_size=18');
        if (!data.items || data.items.length === 0) {
            container.innerHTML = `
                <div class="memory-empty memory-empty-compact">
                    有些记忆不是写下来的，是被拍下来的。<br>
                    在今日记录里发一张图，它会和那天的日记一起留下。
                </div>`;
            return;
        }
        if (row) row.style.display = '';
        container.innerHTML = data.items.map(renderPhotoDateGroup).join('');
    } catch (e) {
        container.innerHTML = `<div class="memory-empty memory-empty-compact">${escapeHtml(e.message)}</div>`;
    }
}

function renderPhotoDateGroup(group) {
    const d = new Date(group.record_date + 'T00:00:00');
    const dateLabel = `${d.getMonth() + 1}月${d.getDate()}日`;
    const images = (group.images || []).slice(0, 6);
    return `
        <section class="memory-photo-group">
            <div class="memory-photo-date">${dateLabel}</div>
            <div class="memory-photo-grid">
                ${images.map(renderPhotoItem).join('')}
            </div>
        </section>`;
}

function renderPhotoItem(img) {
    const src = img.thumbnail_url || img.url;
    const caption = img.ai_caption || '';
    return `
        <button class="memory-photo-item" onclick="window.open('${escapeAttribute(img.url)}','_blank')" title="${escapeAttribute(caption)}">
            <img src="${escapeAttribute(src)}" alt="${escapeAttribute(caption)}" loading="lazy">
            ${caption ? `<span>${escapeHtml(caption)}</span>` : ''}
        </button>`;
}

function pickMemoryQuote(text) {
    const clean = (text || '').replace(/\s+/g, ' ').trim();
    if (!clean) return '这一天也被好好保存下来了';
    const sentences = clean.split(/[。！？!?；;\n]/).map(s => s.trim()).filter(Boolean);
    const preferred = sentences.find(s => s.length >= 16 && s.length <= 56) || sentences.find(s => s.length >= 8) || clean;
    return buildPreview(preferred, 56);
}

function buildPreview(text, maxLength) {
    const clean = (text || '').replace(/\s+/g, ' ').trim();
    if (clean.length <= maxLength) return clean;
    return clean.slice(0, maxLength) + '...';
}

function emotionMood(score) {
    const n = Number(score || 5);
    if (n <= 2) return '有点低落';
    if (n <= 4) return '有点疲惫';
    if (n === 5) return '平静的一天';
    if (n <= 7) return '慢慢恢复';
    if (n === 8) return '有完成感';
    return '被点亮的一天';
}

function renderKeywordTags(keywords) {
    return (keywords || []).slice(0, 4).map(k => `<span class="keyword-tag">${escapeHtml(k)}</span>`).join('');
}

function formatMemoryDate(dateStr) {
    if (!dateStr) return '';
    const d = new Date(dateStr + 'T00:00:00');
    const weekDays = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六'];
    return `${d.getMonth() + 1}月${d.getDate()}日 ${weekDays[d.getDay()]}`;
}

function goToDetail(recordDate) {
    window.location.href = `detail.html?date=${recordDate}`;
}

function goToMemorySearch() {
    if (!memoryState.keyword) return;
    window.location.href = `search.html?q=${encodeURIComponent(memoryState.keyword)}`;
}

function escapeAttribute(text) {
    return escapeHtml(text || '').replace(/'/g, '&#39;');
}
