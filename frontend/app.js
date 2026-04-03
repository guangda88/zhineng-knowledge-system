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
    initBooks();
    initChat();
    initReasoning();
    initGuoxue();
    initSysbooks();
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
            } else if (targetTab === 'guoxue') {
                loadGuoxueStats();
                loadGuoxueBooks();
            } else if (targetTab === 'sysbooks') {
                loadSysbooksStats();
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

// ========== 书籍搜索功能 ==========

let currentSearchType = 'metadata';  // 当前搜索类型: metadata 或 content

// 初始化书籍搜索
function initBooks() {
    const searchInput = document.getElementById('book-search-input');
    const searchBtn = document.getElementById('book-search-btn');
    const categoryFilter = document.getElementById('book-category-filter');
    const dynastyFilter = document.getElementById('book-dynasty-filter');
    const toggleBtns = document.querySelectorAll('.toggle-btn');

    // 搜索类型切换
    toggleBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            toggleBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentSearchType = btn.dataset.type;

            // 更新搜索框提示
            if (currentSearchType === 'metadata') {
                searchInput.placeholder = '搜索书名、作者...';
            } else {
                searchInput.placeholder = '搜索章节内容...';
            }

            // 如果有搜索词，重新搜索
            if (searchInput.value.trim()) {
                performBookSearch();
            }
        });
    });

    // 搜索事件
    const doSearch = () => {
        const query = searchInput.value.trim();
        if (!query) {
            alert('请输入搜索关键词');
            return;
        }
        performBookSearch(query, categoryFilter.value, dynastyFilter.value);
    };

    searchBtn.addEventListener('click', doSearch);
    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') doSearch();
    });

    categoryFilter.addEventListener('change', () => {
        if (searchInput.value.trim()) doSearch();
    });

    dynastyFilter.addEventListener('change', () => {
        if (searchInput.value.trim()) doSearch();
    });

    // 自动加载书籍列表
    loadBooksList();
}

// 执行书籍搜索
async function performBookSearch(query, category = '', dynasty = '') {
    const resultsDiv = document.getElementById('book-search-results');
    resultsDiv.innerHTML = '<div class="loading"><div class="spinner"></div><p>搜索中...</p></div>';

    try {
        const API_BASE = '/api/v2';  // 使用v2 API

        let url = '';
        if (currentSearchType === 'metadata') {
            // 元数据搜索
            const params = new URLSearchParams({ q: query, page: 1, size: 20 });
            if (category) params.append('category', category);
            if (dynasty) params.append('dynasty', dynasty);
            url = `${API_BASE}/library/search?${params}`;
        } else {
            // 全文搜索
            const params = new URLSearchParams({ q: query, page: 1, size: 20 });
            if (category) params.append('category', category);
            url = `${API_BASE}/library/search/content?${params}`;
        }

        const response = await fetch(url);

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();

        if (data.results.length === 0 || data.total === 0) {
            resultsDiv.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">📚</div>
                    <p>没有找到相关书籍</p>
                    <p class="hint">试试搜索：周易、道德经、论语、黄帝内经</p>
                </div>
            `;
            return;
        }

        // 显示结果
        resultsDiv.innerHTML = `
            <p class="result-meta">找到 ${data.total || data.results.length} 条结果</p>
            <div class="results-list">
                ${data.results.map(item => currentSearchType === 'metadata'
                    ? createBookCard(item)
                    : createChapterCard(item)).join('')}
            </div>
        `;
    } catch (error) {
        console.error('搜索失败:', error);
        resultsDiv.innerHTML = `
            <div class="error-state">
                <div class="error-icon">⚠️</div>
                <p>搜索失败：${error.message}</p>
                <p class="hint">请检查API服务是否正常运行</p>
            </div>
        `;
    }
}

// 创建书籍卡片
function createBookCard(book) {
    const categoryTag = book.category ?
        `<span class="tag tag-${book.category}">${book.category}</span>` : '';

    const dynastyTag = book.dynasty ?
        `<span class="tag tag-dynasty">${book.dynasty}</span>` : '';

    return `
        <div class="result-card book-card" onclick="showBookDetail(${book.id})">
            <h3 class="book-title">${book.title}</h3>
            <div class="book-meta">
                <span class="author">👤 ${book.author || '佚名'}</span>
                ${categoryTag}
                ${dynastyTag}
            </div>
            <p class="book-description">${book.description || '暂无简介'}</p>
            <div class="book-stats">
                <span>📄 ${book.total_pages || 0} 页</span>
                <span>👁 ${book.view_count || 0} 次查看</span>
            </div>
        </div>
    `;
}

// 创建章节卡片
function createChapterCard(chapter) {
    return `
        <div class="result-card chapter-card" onclick="showChapterDetail(${chapter.book_id}, ${chapter.id})">
            <h3 class="chapter-title">${chapter.title || '无标题'}</h3>
            <p class="book-title">📖 ${chapter.book_title || '未知书籍'}</p>
            <p class="chapter-preview">${chapter.preview || ''}</p>
            <p class="chapter-meta">第${chapter.chapter_num}章 · ${chapter.char_count || 0} 字</p>
        </div>
    `;
}

// 显示书籍详情
async function showBookDetail(bookId) {
    try {
        const API_BASE = '/api/v2';
        const response = await fetch(`${API_BASE}/library/${bookId}`);
        const book = await response.json();

        // 创建详情弹窗
        const modal = document.createElement('div');
        modal.className = 'modal-overlay';
        modal.innerHTML = `
            <div class="modal-content book-detail-modal">
                <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">×</button>
                <h2>${book.title}</h2>
                <div class="detail-meta">
                    <p><strong>作者：</strong>${book.author || '佚名'}</p>
                    <p><strong>分类：</strong>${book.category || '未分类'}</p>
                    <p><strong>朝代：</strong>${book.dynasty || '未知'}</p>
                    <p><strong>年份：</strong>${book.year || '未知'}</p>
                </div>
                <div class="detail-description">
                    <h3>简介</h3>
                    <p>${book.description || '暂无简介'}</p>
                </div>
                <div class="detail-chapters">
                    <h3>目录</h3>
                    ${book.chapters && book.chapters.length > 0 ?
                        `<ul class="chapter-list">
                            ${book.chapters.map(ch => `
                                <li><a href="#" onclick="showChapterDetail(${bookId}, ${ch.id}); return false;">
                                    第${ch.chapter_num}章：${ch.title || '无标题'}
                                </a></li>
                            `).join('')}
                        </ul>` :
                        '<p class="hint">暂无目录</p>'
                    }
                </div>
                <div class="detail-actions">
                    <button onclick="showRelatedBooks(${bookId})">📚 相关推荐</button>
                    <button onclick="this.closest('.modal-overlay').remove()">关闭</button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
        modal.addEventListener('click', (e) => {
            if (e.target === modal) modal.remove();
        });
    } catch (error) {
        console.error('获取书籍详情失败:', error);
        alert('获取书籍详情失败：' + error.message);
    }
}

// 显示章节内容
async function showChapterDetail(bookId, chapterId) {
    try {
        const API_BASE = '/api/v2';
        const response = await fetch(`${API_BASE}/library/${bookId}/chapters/${chapterId}`);
        const chapter = await response.json();

        const modal = document.createElement('div');
        modal.className = 'modal-overlay';
        modal.innerHTML = `
            <div class="modal-content chapter-modal">
                <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">×</button>
                <h2>${chapter.title || '无标题'}</h2>
                <p class="chapter-meta">第${chapter.chapter_num}章 · ${chapter.char_count || 0} 字</p>
                <div class="chapter-content">
                    ${chapter.content || '内容暂无'}
                </div>
            </div>
        `;

        document.body.appendChild(modal);
        modal.addEventListener('click', (e) => {
            if (e.target === modal) modal.remove();
        });
    } catch (error) {
        console.error('获取章节失败:', error);
        alert('获取章节失败：' + error.message);
    }
}

// 显示相关书籍
async function showRelatedBooks(bookId) {
    try {
        const API_BASE = '/api/v2';
        const response = await fetch(`${API_BASE}/library/${bookId}/related?top_k=6&threshold=0.5`);
        const books = await response.json();

        if (books.length === 0) {
            alert('暂无相关书籍');
            return;
        }

        const modal = document.createElement('div');
        modal.className = 'modal-overlay';
        modal.innerHTML = `
            <div class="modal-content related-modal">
                <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">×</button>
                <h2>相关推荐</h2>
                <div class="related-books-list">
                    ${books.map(book => `
                        <div class="related-book" onclick="showBookDetail(${book.id}); this.closest('.modal-overlay').remove();">
                            <h4>${book.title}</h4>
                            <p>${book.author || '佚名'} · ${book.category || ''}</p>
                            <p class="similarity">相似度：${(book.similarity * 100).toFixed(1)}%</p>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;

        document.body.appendChild(modal);
        modal.addEventListener('click', (e) => {
            if (e.target === modal) modal.remove();
        });
    } catch (error) {
        console.error('获取相关书籍失败:', error);
        alert('获取相关书籍失败：' + error.message);
    }
}

// ========== 国学经典功能 ==========

let guoxueAllBooks = [];

function initGuoxue() {
    const searchInput = document.getElementById('guoxue-search-input');
    const searchBtn = document.getElementById('guoxue-search-btn');
    const bookFilter = document.getElementById('guoxue-book-filter');

    const doSearch = () => {
        const q = searchInput.value.trim();
        if (!q) return;
        searchGuoxue(q);
    };

    searchBtn.addEventListener('click', doSearch);
    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') doSearch();
    });

    bookFilter.addEventListener('input', () => {
        const keyword = bookFilter.value.trim().toLowerCase();
        const filtered = keyword
            ? guoxueAllBooks.filter(b => b.title.toLowerCase().includes(keyword))
            : guoxueAllBooks;
        renderGuoxueBookList(filtered);
    });

    loadGuoxueStats();
    loadGuoxueBooks();
}

async function loadGuoxueStats() {
    const statsDiv = document.getElementById('guoxue-stats');
    try {
        const resp = await fetch(`${API_BASE}/guoxue/stats`);
        const json = await resp.json();
        const d = json.data;
        const chars = d.total_chars >= 1e8
            ? (d.total_chars / 1e8).toFixed(1) + '亿'
            : d.total_chars >= 1e4
            ? (d.total_chars / 1e4).toFixed(0) + '万'
            : d.total_chars;
        statsDiv.innerHTML = `
            <span class="stat-badge">📚 ${d.book_count} 部典籍</span>
            <span class="stat-badge">📄 ${d.content_count.toLocaleString()} 条内容</span>
            <span class="stat-badge">📝 ${chars} 字</span>
        `;
    } catch (e) {
        statsDiv.innerHTML = '<span class="stat-badge error">统计数据加载失败</span>';
    }
}

async function loadGuoxueBooks() {
    const listDiv = document.getElementById('guoxue-book-list');
    listDiv.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
    try {
        const resp = await fetch(`${API_BASE}/guoxue/books?size=200`);
        const json = await resp.json();
        guoxueAllBooks = json.data.results || [];
        renderGuoxueBookList(guoxueAllBooks);
    } catch (e) {
        listDiv.innerHTML = '<div class="empty-state"><p>加载失败</p></div>';
    }
}

function renderGuoxueBookList(books) {
    const listDiv = document.getElementById('guoxue-book-list');
    if (!books.length) {
        listDiv.innerHTML = '<div class="empty-state"><p>无匹配典籍</p></div>';
        return;
    }
    listDiv.innerHTML = books.map(b => `
        <div class="guoxue-book-item" data-book-id="${b.book_id}">
            <span class="guoxue-book-title">${escapeHtml(b.title)}</span>
            <span class="guoxue-book-count">${b.content_count}条</span>
        </div>
    `).join('');

    listDiv.querySelectorAll('.guoxue-book-item').forEach(el => {
        el.addEventListener('click', () => {
            listDiv.querySelectorAll('.guoxue-book-item').forEach(x => x.classList.remove('active'));
            el.classList.add('active');
            loadGuoxueChapters(parseInt(el.dataset.bookId));
        });
    });
}

async function loadGuoxueChapters(bookId) {
    const resultsDiv = document.getElementById('guoxue-results');
    resultsDiv.innerHTML = '<div class="loading"><div class="spinner"></div><p>加载章节...</p></div>';
    try {
        const resp = await fetch(`${API_BASE}/guoxue/books/${bookId}/chapters?size=100`);
        const json = await resp.json();
        const d = json.data;
        const bookTitle = d.book.title;

        resultsDiv.innerHTML = `
            <div class="guoxue-results-header">
                <h3>${escapeHtml(bookTitle)}</h3>
                <span class="result-meta">共 ${d.total} 条内容</span>
            </div>
            <div class="guoxue-chapter-list">
                ${d.results.map(r => `
                    <div class="guoxue-chapter-item" data-content-id="${r.id}">
                        <span class="chapter-label">第${r.chapter_id}章</span>
                        <span class="chapter-length">${r.body_length}字</span>
                    </div>
                `).join('')}
            </div>
        `;

        resultsDiv.querySelectorAll('.guoxue-chapter-item').forEach(el => {
            el.addEventListener('click', () => {
                loadGuoxueContent(parseInt(el.dataset.contentId));
            });
        });
    } catch (e) {
        resultsDiv.innerHTML = `<div class="error-state"><p>加载失败：${escapeHtml(e.message)}</p></div>`;
    }
}

async function loadGuoxueContent(contentId) {
    const modal = document.getElementById('modal-overlay');
    const content = document.getElementById('modal-content');
    content.innerHTML = '<div class="loading"><div class="spinner"></div><p>加载正文...</p></div>';
    modal.classList.add('active');

    try {
        const resp = await fetch(`${API_BASE}/guoxue/content/${contentId}`);
        const json = await resp.json();
        const d = json.data;
        const bodyHtml = escapeHtml(d.body).replace(/\n/g, '<br>');

        content.innerHTML = `
            <button class="modal-close" onclick="document.getElementById('modal-overlay').classList.remove('active')">×</button>
            <h2>第${d.chapter_id}章 <span style="font-size:0.85em;color:#666">(${d.body_length.toLocaleString()}字)</span></h2>
            <div class="guoxue-content-body">${bodyHtml}</div>
        `;
    } catch (e) {
        content.innerHTML = `<div class="error-state"><p>加载失败：${escapeHtml(e.message)}</p></div>`;
    }
}

async function searchGuoxue(query, bookId = null) {
    const resultsDiv = document.getElementById('guoxue-results');
    resultsDiv.innerHTML = '<div class="loading"><div class="spinner"></div><p>搜索中...</p></div>';
    try {
        const params = new URLSearchParams({ q: query, size: 30 });
        if (bookId) params.append('book_id', bookId);
        const resp = await fetch(`${API_BASE}/guoxue/search?${params}`);
        const json = await resp.json();
        const d = json.data;

        if (!d.results.length) {
            resultsDiv.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">📜</div>
                    <p>没有找到相关内容</p>
                    <p>试试：论语、道德经、史记、黄帝内经</p>
                </div>
            `;
            return;
        }

        resultsDiv.innerHTML = `
            <div class="guoxue-results-header">
                <h3>搜索结果</h3>
                <span class="result-meta">找到 ${d.total} 条</span>
            </div>
            <div class="guoxue-search-list">
                ${d.results.map(r => `
                    <div class="guoxue-search-item" data-content-id="${r.id}">
                        <div class="guoxue-search-meta">
                            <span class="book-label">${escapeHtml(r.book_title || '未知')}</span>
                            <span>第${r.chapter_id}章</span>
                            <span>${r.body_length}字</span>
                        </div>
                        <div class="guoxue-search-preview">${escapeHtml(r.body_preview || '').substring(0, 300)}</div>
                    </div>
                `).join('')}
            </div>
        `;

        resultsDiv.querySelectorAll('.guoxue-search-item').forEach(el => {
            el.addEventListener('click', () => {
                loadGuoxueContent(parseInt(el.dataset.contentId));
            });
        });
    } catch (e) {
        resultsDiv.innerHTML = `<div class="error-state"><p>搜索失败：${escapeHtml(e.message)}</p></div>`;
    }
}

// ========== 书目检索功能 ==========

let sysbooksStatsCache = null;

function initSysbooks() {
    const searchInput = document.getElementById('sysbooks-search-input');
    const searchBtn = document.getElementById('sysbooks-search-btn');
    const domainFilter = document.getElementById('sysbooks-domain-filter');
    const extFilter = document.getElementById('sysbooks-extension-filter');

    const doSearch = () => {
        searchSysbooks(searchInput.value.trim(), domainFilter.value, extFilter.value);
    };

    searchBtn.addEventListener('click', doSearch);
    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') doSearch();
    });
    domainFilter.addEventListener('change', doSearch);
    extFilter.addEventListener('change', doSearch);

    loadSysbooksStats();
}

async function loadSysbooksStats() {
    const statsDiv = document.getElementById('sysbooks-stats');
    try {
        const resp = await fetch(`${API_BASE}/sysbooks/stats`);
        const json = await resp.json();
        sysbooksStatsCache = json.data;
        const d = json.data;

        const total = d.total >= 1e4
            ? (d.total / 1e4).toFixed(0) + '万'
            : d.total;
        statsDiv.innerHTML = `<span class="stat-badge">📖 ${total} 条书目</span>`;

        const domainFilter = document.getElementById('sysbooks-domain-filter');
        domainFilter.innerHTML = '<option value="">全部领域</option>' +
            d.by_domain.slice(0, 30).map(r =>
                `<option value="${escapeHtml(r.domain || '')}">${escapeHtml(r.domain || '未知')} (${r.count.toLocaleString()})</option>`
            ).join('');

        const extFilter = document.getElementById('sysbooks-extension-filter');
        extFilter.innerHTML = '<option value="">全部格式</option>' +
            d.by_extension.slice(0, 15).map(r =>
                `<option value="${escapeHtml(r.extension || '')}">.${escapeHtml(r.extension || '?')} (${r.count.toLocaleString()})</option>`
            ).join('');
    } catch (e) {
        statsDiv.innerHTML = '<span class="stat-badge error">统计加载失败</span>';
    }
}

async function searchSysbooks(query = '', domain = '', extension = '', page = 1) {
    const resultsDiv = document.getElementById('sysbooks-results');
    resultsDiv.innerHTML = '<div class="loading"><div class="spinner"></div><p>搜索中...</p></div>';
    try {
        const params = new URLSearchParams({ page, size: 30 });
        if (query) params.set('q', query);
        if (domain) params.set('domain', domain);
        if (extension) params.set('extension', extension);

        const resp = await fetch(`${API_BASE}/sysbooks/search?${params}`);
        const json = await resp.json();
        const d = json.data;

        if (!d.results.length) {
            resultsDiv.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">📖</div>
                    <p>没有找到相关书目</p>
                </div>
            `;
            return;
        }

        resultsDiv.innerHTML = `
            <p class="result-meta">找到 ${d.total.toLocaleString()} 条结果 (第${d.page}页)</p>
            <div class="sysbooks-list">
                ${d.results.map(r => `
                    <div class="sysbook-item" data-book-id="${r.id}">
                        <div class="sysbook-name">${escapeHtml(r.filename || r.path || '未知')}</div>
                        <div class="sysbook-meta">
                            ${r.domain ? `<span class="tag">${escapeHtml(r.domain)}</span>` : ''}
                            ${r.extension ? `<span class="tag">.${escapeHtml(r.extension)}</span>` : ''}
                            ${r.author ? `<span>👤 ${escapeHtml(r.author)}</span>` : ''}
                            ${r.year ? `<span>${r.year}</span>` : ''}
                            ${r.category ? `<span>${escapeHtml(r.category)}</span>` : ''}
                        </div>
                    </div>
                `).join('')}
            </div>
        `;

        resultsDiv.querySelectorAll('.sysbook-item').forEach(el => {
            el.addEventListener('click', () => {
                showSysbookDetail(parseInt(el.dataset.bookId));
            });
        });
    } catch (e) {
        resultsDiv.innerHTML = `<div class="error-state"><p>搜索失败：${escapeHtml(e.message)}</p></div>`;
    }
}

async function showSysbookDetail(bookId) {
    const modal = document.getElementById('modal-overlay');
    const content = document.getElementById('modal-content');
    content.innerHTML = '<div class="loading"><div class="spinner"></div><p>加载中...</p></div>';
    modal.classList.add('active');

    try {
        const resp = await fetch(`${API_BASE}/sysbooks/${bookId}`);
        const json = await resp.json();
        const d = json.data;

        const fields = [
            ['文件名', d.filename],
            ['路径', d.path],
            ['领域', d.domain],
            ['子分类', d.subcategory],
            ['作者', d.author],
            ['年份', d.year],
            ['分类', d.category],
            ['出版社', d.publisher],
            ['格式', d.extension],
            ['大小', d.size],
            ['来源', d.source],
        ].filter(([, v]) => v);

        content.innerHTML = `
            <button class="modal-close" onclick="document.getElementById('modal-overlay').classList.remove('active')">×</button>
            <h2>${escapeHtml(d.filename || '书目详情')}</h2>
            <div class="sysbook-detail-fields">
                ${fields.map(([label, val]) => `
                    <div class="detail-row">
                        <span class="detail-label">${label}</span>
                        <span class="detail-value">${escapeHtml(String(val))}</span>
                    </div>
                `).join('')}
            </div>
        `;
    } catch (e) {
        content.innerHTML = `<div class="error-state"><p>加载失败：${escapeHtml(e.message)}</p></div>`;
    }
}

// 加载书籍列表（默认显示所有）
async function loadBooksList() {
    const resultsDiv = document.getElementById('book-search-results');

    try {
        const API_BASE = '/api/v2';
        const response = await fetch(`${API_BASE}/library/search?page=1&size=20`);
        const data = await response.json();

        if (data.results.length === 0) {
            resultsDiv.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">📚</div>
                    <p>暂无书籍数据</p>
                    <p class="hint">请先导入书籍数据</p>
                </div>
            `;
            return;
        }

        resultsDiv.innerHTML = `
            <p class="result-meta">共 ${data.total} 本书籍</p>
            <div class="results-list">
                ${data.results.map(book => createBookCard(book)).join('')}
            </div>
        `;
    } catch (error) {
        console.error('加载书籍列表失败:', error);
        resultsDiv.innerHTML = `
            <div class="error-state">
                <div class="error-icon">⚠️</div>
                <p>加载失败：${error.message}</p>
            </div>
        `;
    }
}
