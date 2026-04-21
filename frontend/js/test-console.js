const consoleState = {
    userId: '',
    phone: '',
    conversationId: '',
    recordId: '',
    recordDate: '',
    lastResponseText: '',
};

document.addEventListener('DOMContentLoaded', () => {
    bindConsoleEvents();
    seedDefaultValues();
    syncContextView();
    updateHistoryFormState();

    if (getToken()) {
        refreshContext({ silent: true });
    }
});

function $(id) {
    return document.getElementById(id);
}

function valueOf(id) {
    return $(id).value.trim();
}

function setValue(id, value) {
    $(id).value = value ?? '';
}

function nowTime() {
    return new Date().toLocaleTimeString('zh-CN', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
    });
}

function splitCsv(raw) {
    return raw
        .split(',')
        .map((item) => item.trim())
        .filter(Boolean);
}

function previewToken(token) {
    if (!token) return '未登录';
    if (token.length <= 18) return token;
    return `${token.slice(0, 10)}...${token.slice(-6)}`;
}

function makeRandomPhone() {
    return `18${Math.floor(Math.random() * 900000000 + 100000000)}`;
}

function buildPathWithRawDate(basePath, rawDate) {
    const dateValue = (rawDate || '').trim();
    if (!dateValue) {
        throw new Error('请先填写日期');
    }
    return `${basePath}/${dateValue}`;
}

function pushLog(title, detail, type = 'info') {
    const logList = $('logList');
    const empty = logList.querySelector('.log-list__empty');
    if (empty) empty.remove();

    const item = document.createElement('li');
    item.className = `log-item log-item--${type}`;
    item.innerHTML = `
        <div class="log-item__time">${nowTime()}</div>
        <div class="log-item__body">
            <div class="log-item__title">${escapeHtml(title)}</div>
            <div class="log-item__detail">${escapeHtml(detail || '')}</div>
        </div>
    `;
    logList.prepend(item);
}

function renderResponse(meta, payload) {
    $('lastRequestMeta').textContent = meta;
    consoleState.lastResponseText = JSON.stringify(payload, null, 2);
    $('lastResponseBody').textContent = consoleState.lastResponseText;
}

async function requestApi(path, { method = 'GET', body = null, auth = true } = {}) {
    const headers = {};
    const token = getToken();

    if (auth && token) {
        headers.Authorization = `Bearer ${token}`;
    }

    if (body !== null) {
        headers['Content-Type'] = 'application/json';
    }

    const startedAt = performance.now();
    const response = await fetch(`${API_BASE}${path}`, {
        method,
        headers,
        body: body !== null ? JSON.stringify(body) : undefined,
    });

    const duration = Math.round(performance.now() - startedAt);
    const rawText = await response.text();

    let payload;
    try {
        payload = rawText ? JSON.parse(rawText) : {};
    } catch (err) {
        payload = { raw: rawText };
    }

    renderResponse(`${method} ${API_BASE}${path} · HTTP ${response.status} · ${duration}ms`, payload);

    if (!response.ok) {
        const message = payload.message || payload.detail || `请求失败 (${response.status})`;
        throw new Error(message);
    }

    return payload;
}

function ensureToken() {
    if (!getToken()) {
        throw new Error('当前未登录，请先完成登录');
    }
}

function getConversationId() {
    return valueOf('conversationId') || consoleState.conversationId;
}

function getRecordId() {
    return valueOf('recordId') || consoleState.recordId;
}

function applyConversationContext(conversation) {
    if (!conversation) return;
    consoleState.conversationId = conversation.id || consoleState.conversationId;
    consoleState.recordDate = conversation.record_date || consoleState.recordDate;
    setValue('conversationId', consoleState.conversationId);
    if (consoleState.recordDate) {
        setValue('recordDate', consoleState.recordDate);
        setValue('historyDetailDate', consoleState.recordDate);
    }
    syncContextView();
}

function applyRecordContext(record) {
    if (!record) return;
    consoleState.recordId = record.id || consoleState.recordId;
    consoleState.recordDate = record.record_date || consoleState.recordDate;
    setValue('recordId', consoleState.recordId);
    if (record.body_text !== undefined && record.body_text !== null) {
        setValue('dailyBodyText', record.body_text);
    }
    if (consoleState.recordDate) {
        setValue('recordDate', consoleState.recordDate);
        setValue('historyDetailDate', consoleState.recordDate);
    }
    syncContextView();
}

function applyUserContext(user) {
    if (!user) return;
    consoleState.userId = user.id || consoleState.userId;
    consoleState.phone = user.phone || consoleState.phone;
    syncContextView();
}

function syncContextView() {
    $('ctxToken').textContent = previewToken(getToken());
    $('ctxUser').textContent = consoleState.userId || '-';
    $('ctxPhone').textContent = consoleState.phone || '-';
    $('ctxConversationId').textContent = consoleState.conversationId || '-';
    $('ctxRecordId').textContent = consoleState.recordId || '-';
    $('ctxRecordDate').textContent = consoleState.recordDate || '-';
}

function clearLocalState({ clearTokenOnly = false } = {}) {
    consoleState.userId = '';
    consoleState.phone = '';
    consoleState.conversationId = '';
    consoleState.recordId = '';
    consoleState.recordDate = '';

    if (!clearTokenOnly) {
        clearToken();
    }

    setValue('conversationId', '');
    setValue('recordId', '');
    setValue('recordDate', '');
    setValue('historyDetailDate', '');
    syncContextView();
}

function seedDefaultValues() {
    const today = new Date();
    const year = today.getFullYear();
    const month = String(today.getMonth() + 1).padStart(2, '0');
    const lastDay = new Date(year, today.getMonth() + 1, 0).getDate();

    setValue('authPhone', makeRandomPhone());
    setValue('authPassword', 'Password123!');
    setValue('authNickname', '联调用户');
    setValue('settingsTimezone', 'Asia/Shanghai');
    setValue('messageContent', '今天在公司开了很多会，还见了客户，整个人有点累。');
    setValue('historyStartDate', `${year}-${month}-01`);
    setValue('historyEndDate', `${year}-${month}-${String(lastDay).padStart(2, '0')}`);
    setValue('historyYear', String(year));
    setValue('historyMonth', String(Number(month)));
}

function bindConsoleEvents() {
    $('btnRandomPhone').addEventListener('click', () => {
        setValue('authPhone', makeRandomPhone());
        pushLog('生成测试手机号', $('authPhone').value, 'info');
    });

    $('btnRegister').addEventListener('click', registerUser);
    $('btnLogin').addEventListener('click', loginUser);
    $('btnGetMe').addEventListener('click', getCurrentUserProfile);
    $('btnLogout').addEventListener('click', logoutConsole);
    $('btnGetSettings').addEventListener('click', getSettings);
    $('btnSaveSettings').addEventListener('click', saveSettings);
    $('btnGetTodayConversation').addEventListener('click', getTodayConversation);
    $('btnCreateConversation').addEventListener('click', createTodayConversation);
    $('btnGetMessages').addEventListener('click', getMessages);
    $('btnSendMessage').addEventListener('click', sendMessage);
    $('btnCompleteConversation').addEventListener('click', completeConversation);
    $('btnGetTodayRecord').addEventListener('click', getTodayRecord);
    $('btnUpdateBody').addEventListener('click', updateBodyText);
    $('btnSaveSupplement').addEventListener('click', saveSupplement);
    $('btnSaveLightEdit').addEventListener('click', saveLightEdit);
    $('btnHistoryDetail').addEventListener('click', getHistoryDetail);
    $('btnHistoryQuery').addEventListener('click', queryHistory);
    $('btnRefreshContext').addEventListener('click', () => refreshContext({ silent: false }));
    $('btnClearLocalState').addEventListener('click', () => {
        clearLocalState();
        pushLog('清空本地状态', '已清空 token 与自动回填上下文', 'info');
    });
    $('btnClearLog').addEventListener('click', () => {
        $('logList').innerHTML = '<li class="log-list__empty">日志为空，开始操作后会显示在这里。</li>';
    });
    $('btnCopyResponse').addEventListener('click', copyResponse);
    $('historyEndpoint').addEventListener('change', updateHistoryFormState);

    document.querySelectorAll('[data-sample-message]').forEach((button) => {
        button.addEventListener('click', () => {
            setValue('messageContent', button.dataset.sampleMessage);
        });
    });
}

async function runAction(title, action, { successMessage } = {}) {
    try {
        const result = await action();
        pushLog(title, successMessage || '操作成功', 'success');
        return result;
    } catch (err) {
        pushLog(title, err.message || '操作失败', 'error');
        return null;
    }
}

async function registerUser() {
    await runAction('注册账号', async () => {
        const phone    = valueOf('authPhone');
        const password = valueOf('authPassword');

        // 1. 注册
        const regPayload = await requestApi('/auth/register', {
            method: 'POST',
            auth: false,
            body: {
                phone,
                password,
                nickname: valueOf('authNickname') || null,
            },
        });
        applyUserContext(regPayload.data);

        // 2. 注册成功后自动登录，避免用户二次手动点击
        const loginPayload = await requestApi('/auth/login', {
            method: 'POST',
            auth: false,
            body: { phone, password },
        });
        setToken(loginPayload.data.access_token);
        syncContextView();

        // 3. 静默拉取完整用户信息（失败不影响整体流程）
        try { await getCurrentUserProfile(true); } catch (_) {}

        return regPayload;
    }, { successMessage: `手机号 ${valueOf('authPhone')} 注册并自动登录成功` });
}

async function loginUser() {
    await runAction('登录', async () => {
        const payload = await requestApi('/auth/login', {
            method: 'POST',
            auth: false,
            body: {
                phone: valueOf('authPhone'),
                password: valueOf('authPassword'),
            },
        });
        setToken(payload.data.access_token);
        syncContextView();
        // 静默拉取用户信息：失败不应让已成功写入的 token 回滚成「登录失败」
        try { await getCurrentUserProfile(true); } catch (_) {}
        return payload;
    }, { successMessage: '登录成功，Token 已写入 localStorage' });
}

async function getCurrentUserProfile(silent = false) {
    if (!silent) {
        return runAction('读取当前用户', async () => {
            ensureToken();
            const payload = await requestApi('/users/me');
            applyUserContext(payload.data);
            return payload;
        });
    }

    ensureToken();
    const payload = await requestApi('/users/me');
    applyUserContext(payload.data);
    return payload;
}

function logoutConsole() {
    clearLocalState();
    pushLog('退出登录', '已清空 token 与当前上下文', 'info');
}

async function getSettings() {
    await runAction('读取设置', async () => {
        ensureToken();
        const payload = await requestApi('/settings');
        const settings = payload.data;
        setValue('settingsTimezone', settings.timezone || '');
        setValue('settingsInputPreference', settings.input_preference || 'text');
        $('settingsReminderEnabled').checked = Boolean(settings.reminder_enabled);
        setValue('settingsReminderTime', settings.reminder_time || '');
        return payload;
    });
}

async function saveSettings() {
    await runAction('保存设置', async () => {
        ensureToken();
        const reminderTime = valueOf('settingsReminderTime');
        const payload = await requestApi('/settings', {
            method: 'PUT',
            body: {
                timezone: valueOf('settingsTimezone'),
                input_preference: valueOf('settingsInputPreference'),
                reminder_enabled: $('settingsReminderEnabled').checked,
                reminder_time: reminderTime || null,
            },
        });
        return payload;
    }, { successMessage: '用户设置已更新' });
}

async function getTodayConversation() {
    await runAction('读取今日会话', async () => {
        ensureToken();
        const payload = await requestApi('/conversations/today');
        if (payload.data.has_today && payload.data.conversation) {
            applyConversationContext(payload.data.conversation);
        }
        return payload;
    });
}

async function createTodayConversation() {
    await runAction('创建今日会话', async () => {
        ensureToken();
        const payload = await requestApi('/conversations', { method: 'POST' });
        applyConversationContext(payload.data);
        return payload;
    });
}

async function getMessages() {
    await runAction('读取消息列表', async () => {
        ensureToken();
        const conversationId = getConversationId();
        if (!conversationId) {
            throw new Error('请先提供 conversation_id');
        }

        const query = buildQueryString({
            limit: valueOf('conversationLimit'),
            before_sequence: valueOf('conversationBeforeSequence'),
        });

        const payload = await requestApi(`/conversations/${conversationId}/messages${query}`);
        return payload;
    });
}

async function sendMessage() {
    await runAction('发送消息', async () => {
        ensureToken();
        const conversationId = getConversationId();
        if (!conversationId) {
            throw new Error('请先提供 conversation_id');
        }

        const payload = await requestApi(`/conversations/${conversationId}/messages`, {
            method: 'POST',
            body: {
                content_type: valueOf('messageContentType'),
                content: valueOf('messageContent') || null,
                media_file_id: valueOf('messageMediaFileId') || null,
                is_supplement: $('messageIsSupplement').checked,
            },
        });
        return payload;
    }, { successMessage: '消息已发送并收到 ai_message' });
}

async function completeConversation() {
    await runAction('完成会话', async () => {
        ensureToken();
        const conversationId = getConversationId();
        if (!conversationId) {
            throw new Error('请先提供 conversation_id');
        }

        const payload = await requestApi(`/conversations/${conversationId}/complete`, {
            method: 'POST',
        });
        consoleState.conversationId = payload.data.conversation_id || conversationId;
        applyRecordContext(payload.data.daily_record);
        syncContextView();
        return payload;
    }, { successMessage: '会话已完成，并返回 daily_record' });
}

async function getTodayRecord() {
    await runAction('读取今日记录', async () => {
        ensureToken();
        const payload = await requestApi('/daily-records/today');
        if (payload.data.has_record && payload.data.record) {
            applyRecordContext(payload.data.record);
        }
        return payload;
    });
}

async function updateBodyText() {
    await runAction('正文重建', async () => {
        ensureToken();
        const recordId = getRecordId();
        if (!recordId) {
            throw new Error('请先提供 record_id');
        }

        const payload = await requestApi(`/daily-records/${recordId}/body`, {
            method: 'PUT',
            body: {
                body_text: valueOf('dailyBodyText'),
            },
        });
        applyRecordContext(payload.data);
        return payload;
    }, { successMessage: 'body_text 已更新并完成重建' });
}

async function saveSupplement() {
    await runAction('保存本次补充', async () => {
        ensureToken();
        const recordId = getRecordId();
        if (!recordId) {
            throw new Error('请先提供 record_id');
        }

        const note = valueOf('supplementNote');
        const body = note ? { note } : {};
        const payload = await requestApi(`/daily-records/${recordId}/supplement`, {
            method: 'POST',
            body,
        });
        applyRecordContext(payload.data);
        return payload;
    }, { successMessage: '补写内容已保存并完成重建' });
}

async function saveLightEdit() {
    await runAction('轻量编辑', async () => {
        ensureToken();
        const recordId = getRecordId();
        if (!recordId) {
            throw new Error('请先提供 record_id');
        }

        const payload = await requestApi(`/daily-records/${recordId}`, {
            method: 'PUT',
            body: {
                user_note: valueOf('editUserNote') || null,
                keywords: splitCsv(valueOf('editKeywords')),
                tags_to_add: splitCsv(valueOf('editTagsToAdd')),
                tags_to_remove: splitCsv(valueOf('editTagsToRemove')),
            },
        });
        applyRecordContext(payload.data);
        return payload;
    }, { successMessage: '轻量编辑已保存' });
}

async function getHistoryDetail() {
    await runAction('历史详情', async () => {
        ensureToken();
        const path = buildPathWithRawDate('/history/daily-records', valueOf('historyDetailDate') || consoleState.recordDate);
        const payload = await requestApi(path);
        applyRecordContext(payload.data);
        return payload;
    });
}

function updateHistoryFormState() {
    const endpoint = valueOf('historyEndpoint');

    const mapping = {
        'history-list-only': ['daily-records', 'events', 'emotions', 'expenses', 'locations', 'tags'],
        'history-date-range': ['daily-records', 'events', 'emotions', 'expenses', 'locations', 'tags', 'timeline'],
        'history-calendar-only': ['calendar'],
        'history-timeline-only': ['timeline'],
        'history-daily-only': ['daily-records'],
        'history-events-only': ['events'],
        'history-emotions-only': ['emotions'],
        'history-expenses-only': ['expenses'],
        'history-locations-only': ['locations'],
        'history-tags-only': ['tags'],
    };

    Object.entries(mapping).forEach(([className, endpoints]) => {
        document.querySelectorAll(`.${className}`).forEach((node) => {
            if (!endpoints.includes(endpoint)) {
                node.style.display = 'none';
                return;
            }

            if (node.classList.contains('form-grid')) {
                node.style.display = 'grid';
            } else if (node.classList.contains('field')) {
                node.style.display = 'flex';
            } else {
                node.style.display = 'block';
            }
        });
    });
}

function buildHistoryQuery() {
    const endpoint = valueOf('historyEndpoint');

    if (endpoint === 'calendar') {
        return {
            path: `/history/calendar${buildQueryString({
                year: valueOf('historyYear'),
                month: valueOf('historyMonth'),
            })}`,
        };
    }

    if (endpoint === 'timeline') {
        return {
            path: `/history/timeline${buildQueryString({
                start_date: valueOf('historyStartDate'),
                end_date: valueOf('historyEndDate'),
                limit: valueOf('historyLimit'),
            })}`,
        };
    }

    const common = {
        start_date: valueOf('historyStartDate'),
        end_date: valueOf('historyEndDate'),
        page: valueOf('historyPage'),
        page_size: valueOf('historyPageSize'),
    };

    if (endpoint === 'daily-records') {
        return {
            path: `/history/daily-records${buildQueryString({
                ...common,
                keyword: valueOf('historyDailyKeyword'),
                tag: valueOf('historyDailyTag'),
                min_emotion_score: valueOf('historyMinEmotionScore'),
                max_emotion_score: valueOf('historyMaxEmotionScore'),
            })}`,
        };
    }

    if (endpoint === 'events') {
        return {
            path: `/history/events${buildQueryString({
                ...common,
                keyword: valueOf('historyEventsKeyword'),
            })}`,
        };
    }

    if (endpoint === 'emotions') {
        return {
            path: `/history/emotions${buildQueryString({
                ...common,
                emotion_label: valueOf('historyEmotionLabel'),
                min_intensity: valueOf('historyMinIntensity'),
                max_intensity: valueOf('historyMaxIntensity'),
            })}`,
        };
    }

    if (endpoint === 'expenses') {
        return {
            path: `/history/expenses${buildQueryString({
                ...common,
                category: valueOf('historyExpenseCategory'),
                min_amount: valueOf('historyMinAmount'),
                max_amount: valueOf('historyMaxAmount'),
            })}`,
        };
    }

    if (endpoint === 'locations') {
        return {
            path: `/history/locations${buildQueryString({
                ...common,
                name: valueOf('historyLocationName'),
            })}`,
        };
    }

    return {
        path: `/history/tags${buildQueryString({
            ...common,
            tag_name: valueOf('historyTagName'),
        })}`,
    };
}

async function queryHistory() {
    await runAction('历史查询', async () => {
        ensureToken();
        const { path } = buildHistoryQuery();
        return requestApi(path);
    });
}

async function refreshContext({ silent = false } = {}) {
    if (!getToken()) {
        if (!silent) {
            pushLog('刷新上下文', '当前没有 token，可先注册或登录', 'info');
        }
        syncContextView();
        return;
    }

    try {
        await getCurrentUserProfile(true);
    } catch (_) {}

    try {
        const todayConversation = await requestApi('/conversations/today');
        if (todayConversation.data.has_today && todayConversation.data.conversation) {
            applyConversationContext(todayConversation.data.conversation);
        }
    } catch (_) {}

    try {
        const todayRecord = await requestApi('/daily-records/today');
        if (todayRecord.data.has_record && todayRecord.data.record) {
            applyRecordContext(todayRecord.data.record);
        }
    } catch (_) {}

    if (!silent) {
        pushLog('刷新上下文', '已尝试同步当前用户、今日会话和今日记录', 'success');
    }
}

async function copyResponse() {
    if (!consoleState.lastResponseText) {
        pushLog('复制响应', '当前没有可复制的响应内容', 'info');
        return;
    }

    try {
        await navigator.clipboard.writeText(consoleState.lastResponseText);
        pushLog('复制响应', '最后响应已复制到剪贴板', 'success');
    } catch (err) {
        pushLog('复制响应', '复制失败，请检查浏览器剪贴板权限', 'error');
    }
}
