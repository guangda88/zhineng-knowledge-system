// 灵知系统 - AI助手模块
const ChatModule = {
    currentSessionId: null,
    isStreaming: false,

    init() {
        this.bindEvents();
        this.loadSession();
    },

    bindEvents() {
        const sendBtn = document.getElementById('sendBtn');
        const chatInput = document.getElementById('chatInput');
        const charCount = document.querySelector('.char-count');

        // 发送消息
        sendBtn.addEventListener('click', () => this.sendMessage());

        // 回车发送（Shift+Enter换行）
        chatInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // 字符计数
        chatInput.addEventListener('input', () => {
            const len = chatInput.value.length;
            charCount.textContent = `${len} / 2000`;
            if (len > 2000) {
                charCount.classList.add('over-limit');
            } else {
                charCount.classList.remove('over-limit');
            }
        });
    },

    loadSession() {
        this.currentSessionId = localStorage.getItem(Config.storage.sessionId);
        this.updateSessionDisplay();
    },

    updateSessionDisplay() {
        const display = document.getElementById('chatSessionId');
        if (display) {
            display.textContent = this.currentSessionId || '未开始';
        }
    },

    async sendMessage() {
        const chatInput = document.getElementById('chatInput');
        const message = chatInput.value.trim();

        if (!message || this.isStreaming) return;

        // 清空输入
        chatInput.value = '';
        document.querySelector('.char-count').textContent = '0 / 2000';

        // 添加用户消息
        this.addMessage('user', message);

        // 显示加载状态
        const loadingId = this.addLoading();

        try {
            const response = await API.chat.ask(message, this.currentSessionId);
            this.removeLoading(loadingId);

            // 保存会话ID
            if (response.session_id) {
                this.currentSessionId = response.session_id;
                localStorage.setItem(Config.storage.sessionId, response.session_id);
                this.updateSessionDisplay();
            }

            // 添加助手回复
            this.addMessage('assistant', response.answer, response.sources);
        } catch (error) {
            this.removeLoading(loadingId);
            this.addMessage('assistant', `抱歉，出错了：${error.message}`);
        }
    },

    addMessage(role, content, sources = null) {
        const messagesDiv = document.getElementById('chatMessages');
        const messageDiv = document.createElement('div');
        messageDiv.className = `message message-${role}`;

        const avatar = role === 'user' ? '👤' : '🤖';

        // 格式化内容
        const formattedContent = this.formatContent(content);

        let sourcesHtml = '';
        if (sources && sources.length > 0) {
            sourcesHtml = `
                <div class="message-sources">
                    <h5>📚 来源</h5>
                    ${sources.map(s => `
                        <span class="source-tag">${Utils.escapeHtml(s.title || '未知')}</span>
                    `).join('')}
                </div>
            `;
        }

        messageDiv.innerHTML = `
            <div class="message-avatar">${avatar}</div>
            <div class="message-bubble">
                <div class="message-content">${formattedContent}</div>
                ${sourcesHtml}
                <div class="message-time">${new Date().toLocaleTimeString('zh-CN', {hour: '2-digit', minute:'2-digit'})}</div>
            </div>
        `;

        messagesDiv.appendChild(messageDiv);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;

        // 隐藏欢迎消息
        const welcome = messagesDiv.querySelector('.welcome-message');
        if (welcome) welcome.remove();
    },

    addLoading() {
        const messagesDiv = document.getElementById('chatMessages');
        const loadingDiv = document.createElement('div');
        const loadingId = 'loading-' + Date.now();
        loadingDiv.id = loadingId;
        loadingDiv.className = 'message message-assistant';
        loadingDiv.innerHTML = `
            <div class="message-avatar">🤖</div>
            <div class="message-bubble">
                <div class="typing-indicator">
                    <span></span><span></span><span></span>
                </div>
            </div>
        `;
        messagesDiv.appendChild(loadingDiv);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
        return loadingId;
    },

    removeLoading(loadingId) {
        const loading = document.getElementById(loadingId);
        if (loading) loading.remove();
    },

    formatContent(text) {
        if (!text) return '';
        return text
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*([^*]+)\*/g, '<em>$1</em>')
            .replace(/`([^`]+)`/g, '<code>$1</code>')
            .replace(/\n/g, '<br>');
    }
};

// 模块初始化函数
window.initAiAssistant = function() {
    ChatModule.init();
};
