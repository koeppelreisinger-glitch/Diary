const todayPageState = {
    conversation: null,
    messages: [],
    todayRecord: null,
};

const QUICK_MODES = {
    expense: {
        title: '记账模式 💸',
        placeholder: '比如：晚餐 58，或者 打车 20',
        badge: '流水账',
        color: '#5A76D8'
    },
    inspiration: {
        title: '灵感记录 💡',
        placeholder: '此刻有什么一闪而过的想法？',
        badge: '灵感闪现',
        color: '#F5A623'
    },
    learning: {
        title: '学习进度 📚',
        placeholder: '今天学到了什么新知识？进度如何？',
        badge: '日进有功',
        color: '#4CAF7D'
    },
    chat: {
        title: '闲聊天模式 💬',
        placeholder: '想说什么都可以，我会一直听着...',
        badge: '倾诉心声',
        color: '#9D8FE0'
    }
};

let currentQuickMode = null;

// ── 图片上传状态 ──────────────────────────────
let _pendingImageId  = null;  // 已上传图片的 UUID
let _pendingImageSrc = null;  // 上传后的服务器 URL（或本地 ObjectURL）

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

    // 仅显示一行小提示，主要内容交给日记正文/补充面板
    stage.innerHTML = `
        <div style="display:flex;align-items:center;justify-content:space-between;
                    padding:6px 4px 10px;color:var(--text-muted);font-size:13px">
            <span>✨ 今日记录完成 · ${escapeHtml(recordDate)}</span>
            <button class="btn btn-ghost btn-sm" onclick="refreshTodayPage()"
                    style="font-size:12px;padding:2px 8px;color:var(--text-muted)">刷新</button>
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

                    <!-- 图片预览区（默认隐藏） -->
                    <div id="imgPreviewArea" style="display:none;align-items:center;gap:10px;
                         padding:8px 12px;background:var(--bg-secondary);border-radius:10px;
                         margin-bottom:8px;border:1px dashed var(--border)">
                        <div style="position:relative;width:56px;height:56px;border-radius:8px;overflow:hidden;flex-shrink:0">
                            <img id="imgPreviewThumb" src="" alt="预览"
                                 style="width:100%;height:100%;object-fit:cover">
                            <button onclick="clearImageSelection()"
                                    style="position:absolute;top:2px;right:2px;width:18px;height:18px;
                                           border-radius:50%;background:rgba(0,0,0,.55);color:#fff;
                                           font-size:11px;border:none;cursor:pointer;line-height:18px;padding:0">
                                ×
                            </button>
                        </div>
                        <span style="font-size:12px;color:var(--text-secondary)">已选择 1 张照片</span>
                        <span id="imgUploadStatus" style="font-size:11px;color:var(--text-muted)"></span>
                    </div>

                    <!-- 输入栏（📷 + textarea） -->
                    <div style="display:flex;align-items:flex-end;gap:8px">
                        <label for="imgFileInput" title="发送图片"
                               style="font-size:22px;cursor:pointer;opacity:.7;padding:4px;
                                      transition:opacity .2s;user-select:none;flex-shrink:0"
                               onmouseenter="this.style.opacity=1" onmouseleave="this.style.opacity=.7">📷</label>
                        <input type="file" id="imgFileInput" accept="image/*"
                               style="display:none" onchange="onImageSelected(event)">
                        <textarea id="todayMessageInput" rows="3"
                                  placeholder="直接说今天的事、感受、消费、地点都可以。"
                                  style="flex:1"></textarea>
                    </div>

                    <div class="chat-actions" style="margin-top:8px">
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
        const imgHtml = (isUser && message.image_url)
            ? `<div style="max-width:220px;border-radius:10px;overflow:hidden;margin-bottom:6px">
                   <img src="${escapeHtml(message.image_url)}" alt="发送的图片"
                        style="width:100%;height:auto;display:block;cursor:pointer"
                        onclick="window.open(this.src,'_blank')">
               </div>`
            : '';
        return `
            <div class="chat-message ${isUser ? 'chat-message-user' : 'chat-message-ai'}">
                <div class="chat-message__label">${isUser ? '我' : 'Echo'}</div>
                <div class="chat-message__bubble">${imgHtml}${escapeHtml(message.content || '')}</div>
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

    if (!content && !_pendingImageId) {
        renderTodayNotice('请输入文字或选择图片后再发送', 'error');
        return;
    }

    // 如果图片还在上传中（有 ObjectURL 但无 server URL），提示等待
    if (_pendingImageSrc && _pendingImageSrc.startsWith('blob:') && !_pendingImageId) {
        renderTodayNotice('图片仍在上传中，请稍等…', 'error');
        return;
    }

    try {
        renderTodayNotice('');
        sendBtn.disabled = true;
        sendBtn.textContent = '发送中...';

        const body = {
            content_type: 'text',
            content: content || '（图片消息）',
            is_supplement: false,
        };
        if (_pendingImageSrc) body.image_url = _pendingImageSrc;

        const response = await apiFetch(`/conversations/${todayPageState.conversation.id}/messages`, {
            method: 'POST',
            body: JSON.stringify(body),
        });

        todayPageState.messages.push(response.user_message, response.ai_message);
        input.value = '';
        clearImageSelection();
        renderStateRecording();
    } catch (err) {
        renderTodayNotice(err.message || '发送失败', 'error');
    } finally {
        sendBtn.disabled = false;
        sendBtn.textContent = '发送';
    }
}

// ── 图片上传相关 ──────────────────────────────────────────────

/** 用户选择图片后触发：本地预览 + 后台上传 */
async function onImageSelected(event) {
    const file = event.target.files[0];
    if (!file) return;

    // 本地预览（立即显示）
    const objectUrl = URL.createObjectURL(file);
    _pendingImageSrc = objectUrl;
    _pendingImageId  = null;

    const previewArea  = document.getElementById('imgPreviewArea');
    const previewThumb = document.getElementById('imgPreviewThumb');
    const uploadStatus = document.getElementById('imgUploadStatus');
    if (previewArea)  previewArea.style.display  = 'flex';
    if (previewThumb) previewThumb.src = objectUrl;
    if (uploadStatus) uploadStatus.textContent = '上传中…';

    // 后台上传
    try {
        const formData = new FormData();
        formData.append('file', file);

        const resp = await fetch('/api/v1/media/upload', {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${getToken()}` },
            body: formData,
        });
        const json = await resp.json();
        if (json && json.data) {
            _pendingImageId  = json.data.id;
            _pendingImageSrc = json.data.url;  // 切换为服务器 URL
            if (uploadStatus) uploadStatus.textContent = '✅ 已上传';
        } else {
            throw new Error(json?.message || '上传失败');
        }
    } catch (e) {
        if (uploadStatus) uploadStatus.textContent = '⚠️ 上传失败，仅本地预览';
        console.warn('[today] image upload error:', e);
    }
}

/** 取消图片选择，清除状态 */
function clearImageSelection() {
    _pendingImageId  = null;
    _pendingImageSrc = null;
    const fileInput  = document.getElementById('imgFileInput');
    const previewArea = document.getElementById('imgPreviewArea');
    if (fileInput)   fileInput.value = '';
    if (previewArea) previewArea.style.display = 'none';
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

// ── 快速记录弹层逻辑 ──────────────────────────────────────────

function openQuickRecord(mode) {
    const config = QUICK_MODES[mode];
    if (!config) return;

    currentQuickMode = mode;
    
    document.getElementById('quickModalTitle').textContent = config.title;
    const badge = document.getElementById('quickModalBadge');
    badge.textContent = config.badge;
    badge.style.background = config.color + '22'; // 14% opacity
    badge.style.color = config.color;
    
    const input = document.getElementById('quickModalInput');
    input.value = '';
    input.placeholder = config.placeholder;
    
    document.getElementById('quickModalOverlay').classList.add('active');
    setTimeout(() => input.focus(), 100);
}

function closeQuickRecord() {
    document.getElementById('quickModalOverlay').classList.remove('active');
    currentQuickMode = null;
}

async function sendQuickMessage() {
    const input = document.getElementById('quickModalInput');
    const content = input.value.trim();
    const btn = document.getElementById('quickModalSendBtn');

    if (!content) return;

    // 1. 如果今天还没开始记录，先开始
    if (!todayPageState.conversation) {
        try {
            btn.disabled = true;
            btn.textContent = '正在开启记录...';
            await startTodayConversation();
        } catch (err) {
            alert('开启记录失败: ' + err.message);
            btn.disabled = false;
            btn.textContent = '发送并保存';
            return;
        }
    }

    // 2. 发送消息
    try {
        btn.disabled = true;
        btn.textContent = '保存中...';

        const body = {
            content_type: 'text',
            content: content,
            is_supplement: false,
            mode: currentQuickMode,
        };

        const response = await apiFetch(`/conversations/${todayPageState.conversation.id}/messages`, {
            method: 'POST',
            body: JSON.stringify(body),
        });

        if (todayPageState.messages) {
            todayPageState.messages.push(response.user_message, response.ai_message);
        }

        // 成功后关闭并刷新
        closeQuickRecord();
        await refreshTodayPage();
        
        // 滚动到记录区域
        setTimeout(() => {
            const stage = document.getElementById('todayStage');
            if (stage) stage.scrollIntoView({ behavior: 'smooth' });
        }, 300);

    } catch (err) {
        alert('发送失败: ' + err.message);
    } finally {
        btn.disabled = false;
        btn.textContent = '发送并保存';
    }
}
