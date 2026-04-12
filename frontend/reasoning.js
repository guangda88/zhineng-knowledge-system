import { API_BASE, escapeHtml } from './core.js';

function initReasoning() {
    const reasoningBtn = document.getElementById('reasoning-btn');
    const buildGraphBtn = document.getElementById('build-graph-btn');

    reasoningBtn.addEventListener('click', performReasoning);
    buildGraphBtn.addEventListener('click', buildGraph);

    loadGraphStatus();
}

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

function displayReasoningResult(data) {
    const resultDiv = document.getElementById('reasoning-result');

    const metaInfo = `
        模式: ${getModeName(data.mode)} |
        类型: ${getTypeName(data.query_type)} |
        耗时: ${data.reasoning_time?.toFixed(2)}s |
        置信度: ${Math.round(data.confidence * 100)}%
    `;

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

    const answerHtml = `
        <div class="answer-container">
            <h4>💡 答案</h4>
            <div class="answer-text">${formatAnswer(data.answer)}</div>
        </div>
    `;

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

function formatAnswer(answer) {
    return answer
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\n/g, '<br>')
        .replace(/\d+\.\s+/g, '<br>$&');
}

function getModeName(mode) {
    const names = {
        'cot': '链式推理',
        'react': 'ReAct',
        'graph_rag': '图谱推理',
        'auto': '自动'
    };
    return names[mode] || mode;
}

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

        loadGraphVisualization();

    } catch (error) {
        statsDiv.innerHTML = `<div class="error-text">构建失败: ${error.message}</div>`;
    } finally {
        buildBtn.disabled = false;
        buildBtn.textContent = '构建图谱';
    }
}

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

        if (data.graph_entity_count > 0) {
            loadGraphVisualization();
        }
    } catch (error) {
        console.error('加载图谱状态失败:', error);
    }
}

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

function drawGraph(graphData) {
    const canvas = document.getElementById('graph-canvas');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const container = canvas.parentElement;
    canvas.width = container.offsetWidth;
    canvas.height = 400;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const entityPositions = new Map();
    const centerX = canvas.width / 2;
    const centerY = canvas.height / 2;
    const radius = Math.min(canvas.width, canvas.height) * 0.35;

    graphData.entities.forEach((entity, i) => {
        const angle = (2 * Math.PI * i) / graphData.entities.length;
        const x = centerX + radius * Math.cos(angle);
        const y = centerY + radius * Math.sin(angle);
        entityPositions.set(entity.id, { x, y, ...entity });
    });

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

    entityPositions.forEach((pos) => {
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, 20, 0, 2 * Math.PI);

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

        ctx.fillStyle = '#333';
        ctx.font = '12px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(pos.name.substring(0, 4), pos.x, pos.y + 35);
    });
}

export { initReasoning };
