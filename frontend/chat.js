import { API_BASE, state, escapeHtml } from './core.js';
import { submitChatFeedback } from './feedback.js';

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
}

function addMessage(role, content) {
    const messagesDiv = document.getElementById('chat-messages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;

    const avatar = role === 'user' ? '👤' : '🤖';

    messageDiv.innerHTML = `
        <div class="message-avatar">${avatar}</div>
        <div class="message-content">${escapeHtml(content)}</div>
    `;

    messagesDiv.appendChild(messageDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

async function askQuestion(question) {
    const messagesDiv = document.getElementById('chat-messages');

    try {
        const response = await fetch(`${API_BASE}/ask`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                question: question,
                session_id: state.sessionId
            })
        });

        const data = await response.json();
        state.sessionId = data.session_id;

        const formattedAnswer = data.answer
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\n/g, '<br>');

        const feedbackHtml = `
            <div class="answer-feedback">
                <span class="feedback-label">这个回答对您有帮助吗？</span>
                <button class="feedback-btn helpful-btn" onclick="submitChatFeedback(event, 'helpful', '${escapeHtml(question)}')">👍 有帮助</button>
                <button class="feedback-btn not-helpful-btn" onclick="submitChatFeedback(event, 'not_helpful', '${escapeHtml(question)}')">👎 没帮助</button>
            </div>
        `;

        const assistantMessage = document.createElement('div');
        assistantMessage.className = 'message assistant';
        assistantMessage.innerHTML = `
            <div class="message-avatar">🤖</div>
            <div class="message-content">${formattedAnswer}${feedbackHtml}</div>
        `;

        messagesDiv.appendChild(assistantMessage);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;

    } catch (error) {
        addMessage('assistant', `抱歉，出错了：${error.message}`);
    }
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

export { initChat, loadStats };
