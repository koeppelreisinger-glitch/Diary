/**
 * Echo 前端 — 回忆搜索结果页
 * 后端接口：GET /api/v1/history/daily-records?keyword=...
 */

const searchPageState = {
    keyword: '',
    page: 1,
    pageSize: 10,
};

function initMemorySearchPage() {
    const params = new URLSearchParams(window.location.search);
    searchPageState.keyword = (params.get('q') || '').trim();
    searchPageState.page = Math.max(1, Number(params.get('page') || 1));

    const input = document.getElementById('searchPageInput');
    if (input) input.value = searchPageState.keyword;

    if (!searchPageState.keyword) {
        renderSearchEmptyPrompt();
        return;
    }

    loadMemorySearchResults(searchPageState.page);
}

function submitMemorySearchPage() {
    const input = document.getElementById('searchPageInput');
    const keyword = (input?.value || '').trim();
    if (!keyword) {
        searchPageState.keyword = '';
        searchPageState.page = 1;
        window.history.replaceState(null, '', 'search.html');
        renderSearchEmptyPrompt();
        return;
    }

    searchPageState.keyword = keyword;
    searchPageState.page = 1;
    window.history.replaceState(null, '', `search.html?q=${encodeURIComponent(keyword)}`);
    loadMemorySearchResults(1);
}

async function loadMemorySearchResults(page) {
    const container = document.getElementById('searchResultContainer');
    const status = document.getElementById('searchPageStatus');
    const desc = document.getElementById('searchHeroDesc');

    searchPageState.page = page;
    if (status) status.textContent = `正在搜索“${searchPageState.keyword}”...`;
    if (desc) desc.textContent = `这些是和“${searchPageState.keyword}”有关的日记片段。`;
    if (container) {
        container.innerHTML = `
            <div class="status-box" style="padding:28px 0">
                <div class="loading-spinner"></div>
                <div class="text" style="margin-top:10px;font-size:13px">正在翻找记忆...</div>
            </div>`;
    }

    try {
        const data = await apiFetch('/history/daily-records' + buildQueryString({
            page,
            page_size: searchPageState.pageSize,
            keyword: searchPageState.keyword,
        }));
        renderSearchResults(data);
    } catch (err) {
        if (status) status.textContent = '搜索失败，请稍后重试。';
        if (container) {
            container.innerHTML = `<div class="status-box"><div class="icon">×</div><div class="text">${escapeHtml(err.message)}</div></div>`;
        }
    }
}

function renderSearchEmptyPrompt() {
    const status = document.getElementById('searchPageStatus');
    const desc = document.getElementById('searchHeroDesc');
    const container = document.getElementById('searchResultContainer');
    if (status) status.textContent = '输入关键词后，会从日记正文、摘要、关键词、备注和当天线索里查找。';
    if (desc) desc.textContent = '把一句话、一个人、一件小事重新翻出来。';
    if (container) {
        container.innerHTML = `
            <div class="memory-empty">
                <div class="memory-empty-title">想找哪段记忆？</div>
                <div class="memory-empty-text">输入一个词，Echo 会帮你从已经生成的日记里翻找。</div>
            </div>`;
    }
}

function renderSearchResults(data) {
    const container = document.getElementById('searchResultContainer');
    const status = document.getElementById('searchPageStatus');
    const records = data.records || [];
    const total = Number(data.total_count || 0);

    if (status) {
        status.textContent = total > 0
            ? `找到 ${total} 段和“${searchPageState.keyword}”有关的记忆。`
            : '没有找到这段记忆，换一个词试试。';
    }

    if (!container) return;
    if (!records.length) {
        container.innerHTML = `
            <div class="memory-empty">
                <div class="memory-empty-title">没有找到这段记忆</div>
                <div class="memory-empty-text">换一个更具体的词，或回到寻迹页查看地点、消费和情绪趋势。</div>
                <button class="btn btn-secondary btn-sm" onclick="location.href='index.html'">返回回忆</button>
            </div>`;
        return;
    }

    container.innerHTML = `
        <div class="search-result-list">
            ${records.map(renderSearchResultCard).join('')}
        </div>
        ${renderSearchPagination(data)}
    `;
}

function renderSearchResultCard(record) {
    const diaryText = record.body_text || record.summary_text || '';
    const quote = pickSearchQuote(diaryText);
    const preview = buildSearchPreview(diaryText, 150);
    const keywords = renderSearchKeywordTags(record.keywords || []);
    return `
        <article class="search-result-card" onclick="goToSearchDetail('${record.record_date}')">
            <div class="search-result-top">
                <div>
                    <div class="search-result-date">${formatSearchDate(record.record_date)}</div>
                    <div class="memory-diary-mood">${searchEmotionMood(record.emotion_overall_score)}</div>
                </div>
                <span class="memory-read-link">查看详情</span>
            </div>
            <div class="search-result-quote">“${escapeHtml(quote)}”</div>
            <div class="search-result-preview">${highlightSearchKeyword(preview)}</div>
            ${keywords ? `<div class="memory-keywords">${keywords}</div>` : ''}
        </article>`;
}

function renderSearchPagination(data) {
    if ((data.total_pages || 0) <= 1) return '';
    const prevDisabled = data.current_page <= 1 ? 'disabled' : '';
    const nextDisabled = data.current_page >= data.total_pages ? 'disabled' : '';
    return `
        <div class="memory-pagination">
            <button class="btn btn-secondary btn-sm" ${prevDisabled} onclick="goToSearchPage(${data.current_page - 1})">上一页</button>
            <span>${data.current_page}/${data.total_pages}</span>
            <button class="btn btn-secondary btn-sm" ${nextDisabled} onclick="goToSearchPage(${data.current_page + 1})">下一页</button>
        </div>`;
}

function goToSearchPage(page) {
    if (!searchPageState.keyword) return;
    window.history.replaceState(null, '', `search.html?q=${encodeURIComponent(searchPageState.keyword)}&page=${page}`);
    loadMemorySearchResults(page);
}

function goToSearchDetail(recordDate) {
    window.location.href = `detail.html?date=${recordDate}`;
}

function pickSearchQuote(text) {
    const clean = (text || '').replace(/\s+/g, ' ').trim();
    if (!clean) return '这一天也被好好保存下来了';
    const keyword = searchPageState.keyword;
    const sentences = clean.split(/[。！？!?；;\n]/).map(s => s.trim()).filter(Boolean);
    const matched = keyword ? sentences.find(s => s.includes(keyword)) : null;
    const preferred = matched || sentences.find(s => s.length >= 16 && s.length <= 60) || sentences.find(s => s.length >= 8) || clean;
    return buildSearchPreview(preferred, 68);
}

function buildSearchPreview(text, maxLength) {
    const clean = (text || '').replace(/\s+/g, ' ').trim();
    if (clean.length <= maxLength) return clean;
    return clean.slice(0, maxLength) + '...';
}

function highlightSearchKeyword(text) {
    const escaped = escapeHtml(text || '');
    const keyword = searchPageState.keyword;
    if (!keyword) return escaped;
    const escapedKeyword = escapeHtml(keyword).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    return escaped.replace(new RegExp(escapedKeyword, 'gi'), match => `<mark class="search-highlight">${match}</mark>`);
}

function renderSearchKeywordTags(keywords) {
    return (keywords || []).slice(0, 5).map(k => `<span class="keyword-tag">${escapeHtml(k)}</span>`).join('');
}

function searchEmotionMood(score) {
    const n = Number(score || 5);
    if (n <= 2) return '有点低落';
    if (n <= 4) return '有点疲惫';
    if (n === 5) return '平静的一天';
    if (n <= 7) return '慢慢恢复';
    if (n === 8) return '有完成感';
    return '被点亮的一天';
}

function formatSearchDate(dateStr) {
    if (!dateStr) return '';
    const d = new Date(dateStr + 'T00:00:00');
    const weekDays = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六'];
    return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日 ${weekDays[d.getDay()]}`;
}
