const todayPageState = {
    conversation: null,
    messages: [],
    todayRecord: null,
};

async function initTodayPage() {
    await refreshTodayPage();
}

async function refreshTodayPage() {
    const stage = document.getElementById('todayStage');
    stage.innerHTML = '<div class="status-box"><div class="loading-spinner"></div><div class="text" style="margin-top:12px">加载今日状态...</div></div>';
    renderTodayNotice('');

    // 隐藏内联编辑面板（刷新时重置）
    const inlinePanels = document.getElementById('todayInlinePanels');
    if (inlinePanels) inlinePanels.style.display = 'none';

    try {
        const [conversationResp, recordResp] = await Promise.all([
            apiFetch('/conversations/today'),
            apiFetch('/daily-records/today').catch(() => ({ has_record: false, is_generating: false, record: null })),
        ]);

        todayPageState.conversation = conversationResp.conversation || null;
        todayPageState.todayRecord = recordResp.record || null;

        if (!conversationResp.has_today) {
            renderStateNotStarted();
            return;
        }

        if (todayPageState.conversation?.status === 'recording') {
            await loadTodayMessages(todayPageState.conversation.id);
            renderStateRecording();
            return;
        }

        if (todayPageState.conversation?.status === 'completing' || recordResp.is_generating) {
            renderStateGenerating();
            return;
        }

        renderStateCompleted();
    } catch (err) {
        stage.innerHTML = `
            <div class="state-card">
                <div class="state-card__body">
                    <div class="state-card__title">加载失败</div>
                    <p class="state-card__text">${escapeHtml(err.message || '无法获取今日状态')}</p>
                    <div class="state-card__actions">
                        <button class="btn btn-primary" onclick="refreshTodayPage()">重新加载</button>
                    </div>
                </div>
            </div>
        `;
    }
}

function renderTodayNotice(text, type = '') {
    const el = document.getElementById('todayNotice');
    if (!text) {
        el.innerHTML = '';
        return;
    }
    el.innerHTML = `<div class="page-notice ${type ? `page-notice-${type}` : ''}">${escapeHtml(text)}</div>`;
}

function renderStateNotStarted() {
    const stage = document.getElementById('todayStage');
    stage.innerHTML = `
        <div class="state-card">
            <div class="state-card__body">
                <p class="state-card__eyebrow">状态 A</p>
                <div class="state-card__title">今天想从哪里开始说？</div>
                <p class="state-card__text">你今天还没有开始记录。点一下按钮，就可以进入今天的对话记录。</p>
                <div class="state-card__actions">
                    <button class="btn btn-primary" onclick="startTodayConversation()">开始今日记录</button>
                </div>
            </div>
        </div>
    `;
}

function renderStateGenerating() {
    const stage = document.getElementById('todayStage');
    stage.innerHTML = `
        <div class="state-card">
            <div class="state-card__body">
                <p class="state-card__eyebrow">状态处理中</p>
                <div class="state-card__title">正在整理今天的内容……</div>
                <p class="state-card__text">本次记录已经结束，系统正在生成今日日记。稍后刷新查看。</p>
                <div class="state-card__actions">
                    <button class="btn btn-secondary" onclick="refreshTodayPage()">刷新状态</button>
                </div>
            </div>
        </div>
    `;
}

function renderStateCompleted() {
    const stage = document.getElementById('todayStage');
    const recordDate = todayPageState.todayRecord?.record_date || todayPageState.conversation?.record_date || '今天';

    stage.innerHTML = `
        <div class="state-card" style="padding:0 16px 0">
            <div class="state-card__body">
                <p class="state-card__eyebrow">今日记录完成 ✨</p>
                <div class="state-card__title">今天的记录已完成</div>
                <p class="state-card__text">记录日期：${escapeHtml(recordDate)}</p>
                <div class="state-card__actions">
                    <button class="btn btn-secondary" onclick="refreshTodayPage()">刷新状态</button>
                </div>
            </div>
        </div>
    `;

    // 通知 today.html 显示内联编辑 / 补充面板
    if (typeof showTodayEditPanels === 'function') {
        setTimeout(showTodayEditPanels, 80);
    }
}

function renderStateRecording() {
    const stage = document.getElementById('todayStage');
    const conversation = todayPageState.conversation;
    const messages = todayPageState.messages;

    stage.innerHTML = `
        <section class="chat-layout">
            <div class="chat-layout__header">
                <div>
                    <p class="chat-layout__eyebrow">状态 B</p>
                    <h2 class="chat-layout__title">今天正在记录中</h2>
                </div>
                <div class="chat-layout__meta">
                    <span class="chat-meta-pill">会话日期 ${escapeHtml(conversation.record_date)}</span>
                    <span class="chat-meta-pill">消息数 ${messages.length}</span>
                </div>
            </div>

            <div class="chat-card">
                <div class="chat-messages" id="chatMessages">
                    ${renderTodayMessages(messages)}
                </div>

                <div class="chat-input-panel">
                    <label class="chat-input-label" for="todayMessageInput">今天发生了什么？</label>
                    <textarea id="todayMessageInput" rows="4" placeholder="直接说今天的事、感受、消费、地点都可以。"></textarea>
                    <div class="chat-actions">
                        <button class="btn btn-primary" id="sendTodayMessageBtn" onclick="sendTodayMessage()">发送</button>
                        <button class="btn btn-secondary" id="completeTodayBtn" onclick="completeTodayConversation()">结束今日记录</button>
                    </div>
                </div>
            </div>
        </section>
    `;

    const messagesEl = document.getElementById('chatMessages');
    if (messagesEl) {
        messagesEl.scrollTop = messagesEl.scrollHeight;
    }
}

function renderTodayMessages(messages) {
    if (!messages.length) {
        return `
            <div class="chat-empty">
                <div class="chat-empty__title">今天的对话还没开始</div>
                <p class="chat-empty__text">先发出第一条消息，Echo 会跟着你往下追问。</p>
            </div>
        `;
    }

    return messages.map((message) => {
        const isUser = message.role === 'user';
        return `
            <div class="chat-message ${isUser ? 'chat-message-user' : 'chat-message-ai'}">
                <div class="chat-message__label">${isUser ? '我' : 'Echo'}</div>
                <div class="chat-message__bubble">${escapeHtml(message.content || '')}</div>
            </div>
        `;
    }).join('');
}

async function loadTodayMessages(conversationId) {
    const data = await apiFetch(`/conversations/${conversationId}/messages?limit=100`);
    todayPageState.messages = data.messages || [];
}

async function startTodayConversation() {
    renderTodayNotice('');
    try {
        await apiFetch('/conversations', {
            method: 'POST',
        });
        await refreshTodayPage();
    } catch (err) {
        renderTodayNotice(err.message || '创建会话失败', 'error');
    }
}

async function sendTodayMessage() {
    const input = document.getElementById('todayMessageInput');
    const sendBtn = document.getElementById('sendTodayMessageBtn');
    const content = input.value.trim();

    if (!content) {
        renderTodayNotice('请输入消息内容后再发送', 'error');
        return;
    }

    try {
        renderTodayNotice('');
        sendBtn.disabled = true;
        sendBtn.textContent = '发送中...';

        const response = await apiFetch(`/conversations/${todayPageState.conversation.id}/messages`, {
            method: 'POST',
            body: JSON.stringify({
                content_type: 'text',
                content,
                is_supplement: false,
            }),
        });

        todayPageState.messages.push(response.user_message, response.ai_message);
        input.value = '';
        renderStateRecording();
    } catch (err) {
        renderTodayNotice(err.message || '发送失败', 'error');
    } finally {
        sendBtn.disabled = false;
        sendBtn.textContent = '发送';
    }
}

async function completeTodayConversation() {
    const completeBtn = document.getElementById('completeTodayBtn');

    try {
        renderTodayNotice('');
        completeBtn.disabled = true;
        completeBtn.textContent = '处理中...';

        await apiFetch(`/conversations/${todayPageState.conversation.id}/complete`, {
            method: 'POST',
        });

        await refreshTodayPage();
    } catch (err) {
        renderTodayNotice(err.message || '结束今日记录失败', 'error');
    } finally {
        completeBtn.disabled = false;
        completeBtn.textContent = '结束今日记录';
    }
}
