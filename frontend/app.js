// 智能知识系统 - 前端逻辑

// API 基础路径
const API_BASE = '/api/v1';

// 当前会话ID
let sessionId = null;

// DOM 加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initSearch();
    initDocuments();
    initChat();
    initReasoning();
    loadStats();
});

// 标签页切换
function initTabs() {
    const tabs = document.querySelectorAll('.tab');
    const contents = document.querySelectorAll('.tab-content');

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const targetTab = tab.dataset.tab;

            // 更新标签状态
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            // 更新内容显示
            contents.forEach(content => {
                content.classList.remove('active');
                if (content.id === `${targetTab}-section`) {
                    content.classList.add('active');
                }
            });

            // 加载对应数据
            if (targetTab === 'documents') {
                loadDocuments();
            }
        });
    });
}

// 初始化搜索
function initSearch() {
    const searchInput = document.getElementById('search-input');
    const searchBtn = document.getElementById('search-btn');
    const categoryFilter = document.getElementById('category-filter');

    const doSearch = () => {
        const query = searchInput.value.trim();
        if (!query) return;

        const category = categoryFilter.value;
        performSearch(query, category);
    };

    searchBtn.addEventListener('click', doSearch);
    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') doSearch();
    });
    categoryFilter.addEventListener('change', () => {
        if (searchInput.value.trim()) doSearch();
    });
}

// 执行搜索
async function performSearch(query, category = '') {
    const resultsDiv = document.getElementById('search-results');
    resultsDiv.innerHTML = '<div class="loading"><div class="spinner"></div><p>搜索中...</p></div>';

    try {
        const params = new URLSearchParams({ q: query });
        if (category) params.append('category', category);

        const response = await fetch(`${API_BASE}/search?${params}`);
        const data = await response.json();

        if (data.results.length === 0) {
            resultsDiv.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">🔍</div>
                    <p>没有找到相关结果</p>
                    <p>试试搜索：气功、八段锦、中医、儒家</p>
                </div>
            `;
            return;
        }

        resultsDiv.innerHTML = `
            <p class="result-meta">找到 ${data.total} 条结果</p>
            ${data.results.map(item => createResultItem(item)).join('')}
        `;
    } catch (error) {
        resultsDiv.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">❌</div>
                <p>搜索失败：${error.message}</p>
            </div>
        `;
    }
}

// 创建搜索结果项
function createResultItem(item) {
    const content = item.content.length > 200
        ? item.content.substring(0, 200) + '...'
        : item.content;

    return `
        <div class="result-item">
            <h3 class="result-title">${escapeHtml(item.title)}</h3>
            <p class="result-content">${escapeHtml(content)}</p>
            <div class="result-meta">
                <span class="category-tag ${item.category}">${item.category}</span>
                <span>ID: ${item.id}</span>
            </div>
        </div>
    `;
}

// 初始化文档列表
function initDocuments() {
    const refreshBtn = document.getElementById('refresh-docs');
    const categoryFilter = document.getElementById('doc-category-filter');

    const loadDocs = () => {
        const category = categoryFilter.value;
        loadDocuments(category);
    };

    refreshBtn.addEventListener('click', loadDocs);
    categoryFilter.addEventListener('change', loadDocs);
}

// 加载文档列表
async function loadDocuments(category = '') {
    const listDiv = document.getElementById('documents-list');
    listDiv.innerHTML = '<div class="loading"><div class="spinner"></div><p>加载中...</p></div>';

    try {
        const params = new URLSearchParams();
        if (category) params.append('category', category);
        params.append('limit', '50');

        const response = await fetch(`${API_BASE}/documents?${params}`);
        const data = await response.json();

        if (data.documents.length === 0) {
            listDiv.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">📄</div>
                    <p>暂无文档</p>
                </div>
            `;
            return;
        }

        listDiv.innerHTML = `
            <p class="result-meta">共 ${data.total} 篇文档</p>
            ${data.documents.map(item => createDocItem(item)).join('')}
        `;
    } catch (error) {
        listDiv.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">❌</div>
                <p>加载失败：${error.message}</p>
            </div>
        `;
    }
}

// 创建文档项
function createDocItem(item) {
    const tags = item.tags && Array.isArray(item.tags)
        ? item.tags.map(tag => `<span class="tag">${escapeHtml(tag)}</span>`).join(' ')
        : '';

    return `
        <div class="doc-item">
            <h3 class="doc-title">${escapeHtml(item.title)}</h3>
            <div class="doc-meta">
                <span class="category-tag ${item.category}">${item.category}</span>
                ${tags}
                <span>ID: ${item.id}</span>
            </div>
        </div>
    `;
}

// 初始化聊天
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

// 添加消息
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

// 发送问题
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
                session_id: sessionId
            })
        });

        const data = await response.json();
        sessionId = data.session_id;

        // 格式化回答
        const formattedAnswer = data.answer
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\n/g, '<br>');

        const assistantMessage = document.createElement('div');
        assistantMessage.className = 'message assistant';
        assistantMessage.innerHTML = `
            <div class="message-avatar">🤖</div>
            <div class="message-content">${formattedAnswer}</div>
        `;

        messagesDiv.appendChild(assistantMessage);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;

    } catch (error) {
        addMessage('assistant', `抱歉，出错了：${error.message}`);
    }
}

// 加载统计
async function loadStats() {
    try {
        const response = await fetch(`${API_BASE}/stats`);
        const data = await response.json();
        console.log('系统统计:', data);
    } catch (error) {
        console.error('加载统计失败:', error);
    }
}

// HTML 转义
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ========== 推理功能 ==========

// 初始化推理页面
function initReasoning() {
    const reasoningBtn = document.getElementById('reasoning-btn');
    const buildGraphBtn = document.getElementById('build-graph-btn');

    reasoningBtn.addEventListener('click', performReasoning);
    buildGraphBtn.addEventListener('click', buildGraph);

    // 初始加载图谱状态
    loadGraphStatus();
}

// 执行推理
async function performReasoning() {
    const questionInput = document.getElementById('reasoning-question');
    const mode = document.getElementById('reasoning-mode').value;
    const category = document.getElementById('reasoning-category').value;
    const useRag = document.getElementById('use-rag').checked;
    const resultDiv = document.getElementById('reasoning-result');

    const question = questionInput.value.trim();
    if (!question) {
        alert('请输入问题');
        return;
    }

    // 显示加载状态
    resultDiv.classList.remove('hidden');
    resultDiv.innerHTML = '<div class="loading"><div class="spinner"></div><p>推理中...</p></div>';

    try {
        const response = await fetch(`${API_BASE}/reason`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                question: question,
                mode: mode,
                category: category || null,
                use_rag: useRag
            })
        });

        const data = await response.json();
        displayReasoningResult(data);

    } catch (error) {
        resultDiv.innerHTML = `
            <div class="error-state">
                <p>推理失败：${error.message}</p>
            </div>
        `;
    }
}

// 显示推理结果
function displayReasoningResult(data) {
    const resultDiv = document.getElementById('reasoning-result');

    // 元信息
    const metaInfo = `
        模式: ${getModeName(data.mode)} |
        类型: ${getTypeName(data.query_type)} |
        耗时: ${data.reasoning_time?.toFixed(2)}s |
        置信度: ${Math.round(data.confidence * 100)}%
    `;

    // 推理步骤
    let stepsHtml = '';
    if (data.steps && data.steps.length > 0) {
        stepsHtml = `
            <div class="steps-container">
                <h4>🔍 推理过程 (${data.steps.length} 步)</h4>
                ${data.steps.map((step, i) => `
                    <div class="step-item">
                        <div class="step-number">${i + 1}</div>
                        <div class="step-content">
                            ${step.thought ? `<div class="step-thought">💭 ${escapeHtml(step.thought)}</div>` : ''}
                            ${step.content ? `<div class="step-text">${escapeHtml(step.content)}</div>` : ''}
                            ${step.action ? `<div class="step-action">⚡ 行动: ${escapeHtml(step.action)}</div>` : ''}
                            ${step.observation ? `<div class="step-observation">👁 观察: ${escapeHtml(step.observation)}</div>` : ''}
                        </div>
                    </div>
                `).join('')}
            </div>
        `;
    }

    // 答案
    const answerHtml = `
        <div class="answer-container">
            <h4>💡 答案</h4>
            <div class="answer-text">${formatAnswer(data.answer)}</div>
        </div>
    `;

    // 来源
    let sourcesHtml = '';
    if (data.sources && data.sources.length > 0) {
        sourcesHtml = `
            <div class="sources-container">
                <h4>📚 来源 (${data.sources.length})</h4>
                <div class="sources-list">
                    ${data.sources.slice(0, 3).map(source => `
                        <div class="source-item">
                            <span class="source-title">${escapeHtml(source.title || '未知')}</span>
                            <span class="source-score">${source.similarity ? `相似度: ${Math.round(source.similarity * 100)}%` : ''}</span>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }

    resultDiv.innerHTML = `
        <div class="result-header">
            <h3>推理结果</h3>
            <span id="reasoning-meta">${metaInfo}</span>
        </div>
        ${stepsHtml}
        ${answerHtml}
        ${sourcesHtml}
    `;
}

// 格式化答案
function formatAnswer(answer) {
    return answer
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\n/g, '<br>')
        .replace(/\d+\.\s+/g, '<br>$&');
}

// 获取模式名称
function getModeName(mode) {
    const names = {
        'cot': '链式推理',
        'react': 'ReAct',
        'graph_rag': '图谱推理',
        'auto': '自动'
    };
    return names[mode] || mode;
}

// 获取类型名称
function getTypeName(type) {
    const names = {
        'factual': '事实查询',
        'reasoning': '推理',
        'multi_hop': '多跳推理',
        'comparison': '对比分析',
        'explanation': '解释说明'
    };
    return names[type] || type;
}

// 构建知识图谱
async function buildGraph() {
    const statsDiv = document.getElementById('graph-stats');
    const buildBtn = document.getElementById('build-graph-btn');

    buildBtn.disabled = true;
    buildBtn.textContent = '构建中...';
    statsDiv.innerHTML = '<div class="loading-text">正在从文档构建知识图谱...</div>';

    try {
        const response = await fetch(`${API_BASE}/graph/build`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json();

        statsDiv.innerHTML = `
            <div class="graph-stats-info">
                <span>📊 实体: ${data.entity_count}</span>
                <span>🔗 关系: ${data.relation_count}</span>
                <span>📄 文档: ${data.document_count}</span>
            </div>
        `;

        // 加载并可视化图谱
        loadGraphVisualization();

    } catch (error) {
        statsDiv.innerHTML = `<div class="error-text">构建失败: ${error.message}</div>`;
    } finally {
        buildBtn.disabled = false;
        buildBtn.textContent = '构建图谱';
    }
}

// 加载图谱状态
async function loadGraphStatus() {
    try {
        const response = await fetch(`${API_BASE}/reasoning/status`);
        const data = await response.json();

        const statsDiv = document.getElementById('graph-stats');
        statsDiv.innerHTML = `
            <div class="graph-stats-info">
                <span>📊 实体: ${data.graph_entity_count}</span>
                <span>🔗 关系: ${data.graph_relation_count}</span>
                <span>🔑 API: ${data.api_configured ? '已配置' : '未配置'}</span>
            </div>
        `;

        // 如果有实体数据，加载可视化
        if (data.graph_entity_count > 0) {
            loadGraphVisualization();
        }
    } catch (error) {
        console.error('加载图谱状态失败:', error);
    }
}

// 加载图谱可视化
async function loadGraphVisualization() {
    try {
        const response = await fetch(`${API_BASE}/graph/data`);
        const data = await response.json();

        if (data.entities.length > 0) {
            drawGraph(data);
        }
    } catch (error) {
        console.error('加载图谱数据失败:', error);
    }
}

// 绘制图谱 (简单 Canvas 实现)
function drawGraph(graphData) {
    const canvas = document.getElementById('graph-canvas');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const container = canvas.parentElement;
    canvas.width = container.offsetWidth;
    canvas.height = 400;

    // 清空画布
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // 实体位置（简单布局）
    const entityPositions = new Map();
    const centerX = canvas.width / 2;
    const centerY = canvas.height / 2;
    const radius = Math.min(canvas.width, canvas.height) * 0.35;

    // 放置实体
    graphData.entities.forEach((entity, i) => {
        const angle = (2 * Math.PI * i) / graphData.entities.length;
        const x = centerX + radius * Math.cos(angle);
        const y = centerY + radius * Math.sin(angle);
        entityPositions.set(entity.id, { x, y, ...entity });
    });

    // 绘制关系
    ctx.strokeStyle = '#ccc';
    ctx.lineWidth = 1;
    graphData.relations.forEach(rel => {
        const source = entityPositions.get(rel.source);
        const target = entityPositions.get(rel.target);
        if (source && target) {
            ctx.beginPath();
            ctx.moveTo(source.x, source.y);
            ctx.lineTo(target.x, target.y);
            ctx.stroke();
        }
    });

    // 绘制实体节点
    entityPositions.forEach((pos) => {
        // 绘制节点
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, 20, 0, 2 * Math.PI);

        // 根据类型设置颜色
        const colors = {
            '功法': '#4CAF50',
            '穴位': '#2196F3',
            '概念': '#FF9800',
            '动作': '#9C27B0',
            '脏腑': '#F44336'
        };
        ctx.fillStyle = colors[pos.type] || '#999';
        ctx.fill();
        ctx.strokeStyle = '#333';
        ctx.stroke();

        // 绘制名称
        ctx.fillStyle = '#333';
        ctx.font = '12px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(pos.name.substring(0, 4), pos.x, pos.y + 35);
    });
}
