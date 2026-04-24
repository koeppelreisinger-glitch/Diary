/**
 * Echo 前端 — 通用 API 请求封装 + Token 管理
 */

const API_BASE = '/api/v1';

// ── Token 管理 ──────────────────────────────

function getToken() {
    return localStorage.getItem('echo_token');
}

function setToken(token) {
    localStorage.setItem('echo_token', token);
}

function clearToken() {
    localStorage.removeItem('echo_token');
}

function requireAuth() {
    if (!getToken()) {
        window.location.href = 'login.html';
        return false;
    }
    return true;
}

function logout() {
    clearToken();
    window.location.href = 'login.html';
}

// ── 请求封装 ──────────────────────────────

/**
 * 封装 fetch，自动带 Authorization header，自动解析 ApiResponse
 * @param {string} url - 相对于 API_BASE 的路径，如 '/daily-records/today'
 * @param {object} options - fetch options（method, body 等）
 * @returns {Promise<object>} - 解析后的 data 字段
 */
async function apiFetch(url, options = {}) {
    const token = getToken();
    const headers = {
        'Content-Type': 'application/json',
        ...(options.headers || {}),
    };
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${API_BASE}${url}`, {
        ...options,
        headers,
    });

    // 401 → 清 token 跳登录
    if (response.status === 401) {
        clearToken();
        window.location.href = 'login.html';
        throw new Error('未授权，请重新登录');
    }

    // 安全解析 JSON（后端 500 可能返回纯文本，避免 SyntaxError）
    let json;
    try {
        json = await response.json();
    } catch (e) {
        throw new Error(`服务器错误 (${response.status})，请稍后重试`);
    }

    // 业务错误
    if (!response.ok) {
        const msg = json?.message || `请求失败 (${response.status})`;
        throw new Error(msg);
    }

    // 返回 data 字段（ApiResponse 结构）
    return json.data;
}

/**
 * 登录专用（不需要 token）
 */
async function apiLogin(phone, password) {
    const response = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone, password }),
    });

    const json = await response.json();

    if (!response.ok) {
        throw new Error(json.message || '登录失败');
    }

    return json.data; // { access_token, token_type, expires_in }
}

// ── 工具函数 ──────────────────────────────

/**
 * 将对象构建为 query string，跳过 null/undefined/空字符串
 */
function buildQueryString(params) {
    const parts = [];
    for (const [key, value] of Object.entries(params)) {
        if (value !== null && value !== undefined && value !== '') {
            parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(value)}`);
        }
    }
    return parts.length > 0 ? '?' + parts.join('&') : '';
}

/**
 * 日期格式化：'2026-04-17' → '2026年4月17日'
 */
function formatDateCN(dateStr) {
    if (!dateStr) return '';
    const d = new Date(dateStr + 'T00:00:00');
    return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`;
}

/**
 * 日期格式化：'2026-04-17' → '04-17'
 */
function formatDateShort(dateStr) {
    if (!dateStr) return '';
    return dateStr.substring(5); // 'MM-DD'
}

/**
 * 时间格式化：'2026-04-17T10:30:00' → '10:30'
 */
function formatTime(datetimeStr) {
    if (!datetimeStr) return '';
    const d = new Date(datetimeStr);
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false });
}

/**
 * 金额格式化：12.5 → '¥12.50'
 */
function formatAmount(amount, currency) {
    const num = Number(amount).toFixed(2);
    if (currency === 'CNY' || !currency) return `¥${num}`;
    return `${currency} ${num}`;
}

/**
 * 情绪能量指数映射表
 * 能量尺度：5=极高激活(激动/兴奋/期待)  1=极低落(悲伤/低落)
 * 模型依据情绪的激活度 + 语气倾向（正/负）综合评分
 */
const EMOTION_INDEX_MAP = {
    // Level 5: 极高激活 — 正向激动态
    '激动': 5, '兴奋': 5, '期待': 5, '热情': 5, '振奋': 5,
    '狂喜': 5, '喜悦': 5, '惊喜': 5, '亢奋': 5, '激情': 5,
    // Level 4: 高能量 — 正向稳定态
    '开心': 4, '高兴': 4, '满足': 4, '快乐': 4, '愉快': 4,
    '感动': 4, '温暖': 4, '放松': 4, '感恩': 4, '幸福': 4,
    '轻松': 4, '自信': 4, '踏实': 4, '愉悦': 4, '开朗': 4,
    // Level 3: 中性 — 低激活中立态
    '平静': 3, '淡然': 3, '平常': 3, '沉静': 3, '沉稳': 3,
    '无感': 3, '尚可': 3, '思念': 3, '怀念': 3, '普通': 3,
    '安心': 3, '平和': 3, '宁静': 3,
    // Level 2: 较低能量 — 负向活跃态
    '烦躁': 2, '焦虑': 2, '紧张': 2, '担忧': 2, '郁闷': 2,
    '委屈': 2, '不安': 2, '压抑': 2, '愤怒': 2, '不满': 2,
    '疲惫': 2, '忧虑': 2, '困惑': 2, '孤独': 2, '急躁': 2,
    '失望': 2, '抗拒': 2, '内疚': 2,
    // Level 1: 极低能量 — 负向沉浸态
    '低落': 1, '悲伤': 1, '痛苦': 1, '绝望': 1, '失落': 1,
    '空虚': 1, '哀愁': 1, '悲痛': 1, '哀伤': 1, '崩溃': 1,
    '心碎': 1, '沉沦': 1, '悲愁': 1,
};

/**
 * 情绪标签 → 能量指数 (1-5)
 * 支持模糊匹配，找不到则用 intensity 备用值
 */
function getEmotionIndex(label, intensityFallback) {
    if (!label) return intensityFallback || 3;
    const key = label.trim();
    if (EMOTION_INDEX_MAP[key] !== undefined) return EMOTION_INDEX_MAP[key];
    // 包含匹配
    for (const [word, score] of Object.entries(EMOTION_INDEX_MAP)) {
        if (key.includes(word) || word.includes(key)) return score;
    }
    // 使用备用履干，将 intensity(1-5) 直接当作指数
    return intensityFallback || 3;
}

/**
 * 情绪标签 → 彩色点指示器 HTML
 * 示例：开心(4) → ‘●●●●○’ (绳色)
 */
function formatEmotionIndex(label, intensityFallback) {
    const index = getEmotionIndex(label, intensityFallback);
    const colorMap = [
        null,
        '#c0392b',  // 1: 深红 低落
        '#e67e22',  // 2: 橙色 负向
        '#95a5a6',  // 3: 默灰 中性
        '#27ae60',  // 4: 綠色 积极
        '#2980b9',  // 5: 蓝色 激动
    ];
    const color = colorMap[index] || '#95a5a6';
    const filled = '●'.repeat(index);
    const empty = '○'.repeat(5 - index);
    return `<span class="emotion-index" style="color:${color};letter-spacing:2px" title="情绪指数 ${index}/5">${filled}${empty}</span>`;
}

// 向后兼容：保留旧接口（尚未升级的页面可能仍在使用）
function formatIntensity(intensity, max = 5) {
    return formatEmotionIndex(null, intensity);
}

/**
 * 来源标签 HTML
 */
function sourceTag(source) {
    const cls = source === 'user' ? 'source-user' : 'source-ai';
    return `<span class="source-tag ${cls}">${source}</span>`;
}

/**
 * 确认状态图标
 */
function confirmedIcon(isConfirmed) {
    return isConfirmed ? '<span class="confirmed-yes">✅</span>' : '<span class="confirmed-no">⬜</span>';
}

/**
 * 安全转义 HTML
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * 初始化页面顶部日期标签（page-intro-label）
 * 例：2026年4月20日  周日
 */
function initDateLabel(labelId = 'todayDateLabel') {
    const el = document.getElementById(labelId);
    if (!el) return;
    const now = new Date();
    const weekDays = ['周日','周一','周二','周三','周四','周五','周六'];
    const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    el.textContent = `${now.getFullYear()}年${now.getMonth()+1}月${now.getDate()}日  ${weekDays[now.getDay()]}`;
}

// 页面加载后自动运行
document.addEventListener('DOMContentLoaded', () => initDateLabel());
