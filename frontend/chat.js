import { API_BASE, state, escapeHtml, saveState, loadState, clearState } from './core.js';
import { submitChatFeedback } from './feedback.js';

const STORAGE_MESSAGES_KEY = 'zhineng_messages';
const MAX_LOCAL_MESSAGES = 200;

function saveMessagesLocal(messages) {
    try {
        const trimmed = messages.slice(-MAX_LOCAL_MESSAGES);
        localStorage.setItem(STORAGE_MESSAGES_KEY, JSON.stringify(trimmed));
    } catch (e) {}
}

function loadMessagesLocal() {
    try {
        const raw = localStorage.getItem(STORAGE_MESSAGES_KEY);
        return raw ? JSON.parse(raw) : [];
    } catch (e) {
        return [];
    }
}

function clearMessagesLocal() {
    try { localStorage.removeItem(STORAGE_MESSAGES_KEY); } catch (e) {}
}

let localMessages = [];

function initChat() {
    const sendBtn = document.getElementById('send-btn');
    const questionInput = document.getElementById('question-input');

    const sendMessage = () => {
        const question = questionInput.value.trim();
        if (!question) return;

        addMessage('user', question);
        questionInput.value = '';

        askQuestion(question);
    };

    sendBtn.addEventListener('click', sendMessage);
    questionInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Auto-restore session on page load
    restoreSession();
}

function addMessage(role, content, prepend = false) {
    const messagesDiv = document.getElementById('chat-messages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;

    const avatar = role === 'user' ? '👤' : '🤖';

    const formattedContent = role === 'assistant'
        ? content.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/\n/g, '<br>')
        : escapeHtml(content);

    messageDiv.innerHTML = `
        <div class="message-avatar">${avatar}</div>
        <div class="message-content">${formattedContent}</div>
    `;

    if (prepend) {
        messagesDiv.prepend(messageDiv);
    } else {
        messagesDiv.appendChild(messageDiv);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
    }

    // Track locally
    const msg = { role, content, ts: Date.now() };
    if (prepend) {
        localMessages.unshift(msg);
    } else {
        localMessages.push(msg);
    }
    saveMessagesLocal(localMessages);
}

async function askQuestion(question) {
    const messagesDiv = document.getElementById('chat-messages');
    state.interrupted = false;

    try {
        const response = await fetch(`${API_BASE}/ask`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                question: question,
                session_id: state.sessionId
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        state.sessionId = data.session_id;
        saveState();

        const answer = data.answer;

        const feedbackHtml = `
            <div class="answer-feedback">
                <span class="feedback-label">这个回答对您有帮助吗？</span>
                <button class="feedback-btn helpful-btn" onclick="submitChatFeedback(event, 'helpful', '${escapeHtml(question)}')">👍 有帮助</button>
                <button class="feedback-btn not-helpful-btn" onclick="submitChatFeedback(event, 'not_helpful', '${escapeHtml(question)}')">👎 没帮助</button>
            </div>
        `;

        const assistantMessage = document.createElement('div');
        assistantMessage.className = 'message assistant';
        const formattedAnswer = answer
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\n/g, '<br>');
        assistantMessage.innerHTML = `
            <div class="message-avatar">🤖</div>
            <div class="message-content">${formattedAnswer}${feedbackHtml}</div>
        `;

        messagesDiv.appendChild(assistantMessage);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;

        // Track assistant message locally
        localMessages.push({ role: 'assistant', content: answer, ts: Date.now() });
        saveMessagesLocal(localMessages);

    } catch (error) {
        state.interrupted = true;
        saveState();

        // Mark session as interrupted on server
        if (state.sessionId) {
            fetch(`${API_BASE}/sessions/${state.sessionId}/interrupt`, {
                method: 'POST'
            }).catch(() => {});
        }

        addMessage('assistant', `⚠️ 请求中断：${error.message}。页面会自动保存进度，刷新后可恢复。`);
    }
}

async function restoreSession() {
    const hadState = loadState();

    if (!hadState || !state.sessionId) {
        // No previous session — clean start
        localMessages = [];
        return;
    }

    // Try to restore from server first
    try {
        const resp = await fetch(`${API_BASE}/sessions/${state.sessionId}/history?limit=100`);
        if (resp.ok) {
            const data = await resp.json();
            if (data.messages && data.messages.length > 0) {
                const messagesDiv = document.getElementById('chat-messages');
                messagesDiv.innerHTML = '';

                for (const msg of data.messages) {
                    const messageDiv = document.createElement('div');
                    messageDiv.className = `message ${msg.role}`;
                    const avatar = msg.role === 'user' ? '👤' : '🤖';
                    const formattedContent = msg.role === 'assistant'
                        ? msg.content.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/\n/g, '<br>')
                        : escapeHtml(msg.content);
                    messageDiv.innerHTML = `
                        <div class="message-avatar">${avatar}</div>
                        <div class="message-content">${formattedContent}</div>
                    `;
                    messagesDiv.appendChild(messageDiv);
                }
                messagesDiv.scrollTop = messagesDiv.scrollHeight;

                localMessages = data.messages.map(m => ({ role: m.role, content: m.content, ts: Date.now() }));
                saveMessagesLocal(localMessages);

                // Resume session on server
                if (state.interrupted) {
                    await fetch(`${API_BASE}/sessions/${state.sessionId}/resume`, { method: 'POST' });
                    state.interrupted = false;
                    saveState();
                }
                return;
            }
        }
    } catch (e) {
        // Server unreachable — try local cache
    }

    // Fallback: restore from localStorage
    localMessages = loadMessagesLocal();
    if (localMessages.length > 0) {
        const messagesDiv = document.getElementById('chat-messages');
        messagesDiv.innerHTML = '';

        for (const msg of localMessages) {
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${msg.role}`;
            const avatar = msg.role === 'user' ? '👤' : '🤖';
            const formattedContent = msg.role === 'assistant'
                ? msg.content.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/\n/g, '<br>')
                : escapeHtml(msg.content);
            messageDiv.innerHTML = `
                <div class="message-avatar">${avatar}</div>
                <div class="message-content">${formattedContent}</div>
            `;
            messagesDiv.appendChild(messageDiv);
        }
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
    }
}

function startNewSession() {
    clearState();
    clearMessagesLocal();
    localMessages = [];
    const messagesDiv = document.getElementById('chat-messages');
    if (messagesDiv) messagesDiv.innerHTML = '';
}

async function loadStats() {
    try {
        const response = await fetch(`${API_BASE}/stats`);
        const data = await response.json();
        console.log('系统统计:', data);
    } catch (error) {
        console.error('加载统计失败:', error);
    }
}

export { initChat, loadStats, askQuestion, addMessage, restoreSession, startNewSession };
