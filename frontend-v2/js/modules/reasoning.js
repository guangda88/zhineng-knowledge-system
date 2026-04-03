// 灵知系统 - 推理模块
const ReasoningModule = {
    init() {
        this.bindEvents();
        this.loadGraphStatus();
    },

    bindEvents() {
        const reasoningBtn = document.getElementById('reasoningBtn');
        const buildGraphBtn = document.getElementById('buildGraphBtn');

        reasoningBtn.addEventListener('click', () => this.performReasoning());
        buildGraphBtn.addEventListener('click', () => this.buildGraph());
    },

    async performReasoning() {
        const input = document.getElementById('reasoningInput');
        const mode = document.getElementById('reasoningMode').value;
        const domain = document.getElementById('reasoningDomain').value;
        const useRag = document.getElementById('useRag').checked;
        const outputDiv = document.getElementById('reasoningOutput');

        const question = input.value.trim();
        if (!question) {
            alert('请输入问题');
            return;
        }

        outputDiv.innerHTML = `
            <div class="loading">
                <div class="spinner"></div>
                <p>推理中...</p>
            </div>
        `;

        try {
            const data = await API.reasoning.perform(question, {
                mode: mode,
                category: domain || null,
                use_rag: useRag
            });

            this.displayResult(data);
        } catch (error) {
            outputDiv.innerHTML = `
                <div class="error-state">
                    <p>推理失败：${error.message}</p>
                </div>
            `;
        }
    },

    displayResult(data) {
        const outputDiv = document.getElementById('reasoningOutput');

        let stepsHtml = '';
        if (data.steps && data.steps.length > 0) {
            stepsHtml = `
                <div class="reasoning-steps">
                    <h4>🔍 推理过程 (${data.steps.length} 步)</h4>
                    ${data.steps.map((step, i) => `
                        <div class="step-item">
                            <div class="step-number">${i + 1}</div>
                            <div class="step-content">
                                ${step.thought ? `<div class="step-thought">💭 ${Utils.escapeHtml(step.thought)}</div>` : ''}
                                ${step.content ? `<div class="step-text">${Utils.escapeHtml(step.content)}</div>` : ''}
                                ${step.action ? `<div class="step-action">⚡ ${Utils.escapeHtml(step.action)}</div>` : ''}
                                ${step.observation ? `<div class="step-observation">👁 ${Utils.escapeHtml(step.observation)}</div>` : ''}
                            </div>
                        </div>
                    `).join('')}
                </div>
            `;
        }

        let answerHtml = `
            <div class="reasoning-answer">
                <h4>💡 答案</h4>
                <div class="answer-content">${this.formatAnswer(data.answer)}</div>
            </div>
        `;

        let sourcesHtml = '';
        if (data.sources && data.sources.length > 0) {
            sourcesHtml = `
                <div class="reasoning-sources">
                    <h4>📚 来源 (${data.sources.length})</h4>
                    ${data.sources.map(s => `
                        <div class="source-item">
                            <span class="source-title">${Utils.escapeHtml(s.title || '未知')}</span>
                            <span class="source-score">${s.similarity ? `相似度: ${Math.round(s.similarity * 100)}%` : ''}</span>
                        </div>
                    `).join('')}
                </div>
            `;
        }

        const metaHtml = `
            <div class="reasoning-meta">
                <span>模式: ${this.getModeName(data.mode)}</span>
                <span>类型: ${this.getTypeName(data.query_type)}</span>
                <span>耗时: ${data.reasoning_time?.toFixed(2)}s</span>
                <span>置信度: ${Math.round((data.confidence || 0) * 100)}%</span>
            </div>
        `;

        outputDiv.innerHTML = `
            ${metaHtml}
            ${stepsHtml}
            ${answerHtml}
            ${sourcesHtml}
        `;
    },

    formatAnswer(text) {
        return text
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\n/g, '<br>');
    },

    getModeName(mode) {
        const names = { 'cot': '链式推理', 'react': 'ReAct', 'graph_rag': '图谱推理', 'auto': '自动' };
        return names[mode] || mode;
    },

    getTypeName(type) {
        const names = { 'factual': '事实查询', 'reasoning': '推理', 'multi_hop': '多跳推理', 'comparison': '对比分析', 'explanation': '解释说明' };
        return names[type] || type;
    },

    async loadGraphStatus() {
        try {
            const data = await API.reasoning.getStatus();
            const statsDiv = document.getElementById('graphStats');
            statsDiv.innerHTML = `
                <span class="graph-stat">📊 实体: ${data.graph_entity_count || 0}</span>
                <span class="graph-stat">🔗 关系: ${data.graph_relation_count || 0}</span>
            `;
        } catch (error) {
            console.error('加载图谱状态失败:', error);
        }
    },

    async buildGraph() {
        const btn = document.getElementById('buildGraphBtn');
        btn.disabled = true;
        btn.textContent = '构建中...';

        try {
            const data = await API.graph.build();

            document.getElementById('graphStats').innerHTML = `
                <span class="graph-stat">📊 实体: ${data.entity_count}</span>
                <span class="graph-stat">🔗 关系: ${data.relation_count}</span>
                <span class="graph-stat">📄 文档: ${data.document_count}</span>
            `;

            this.drawGraph(data);
        } catch (error) {
            alert('构建图谱失败：' + error.message);
        } finally {
            btn.disabled = false;
            btn.textContent = '构建图谱';
        }
    },

    drawGraph(data) {
        // 简化版图谱绘制
        const canvas = document.getElementById('graphCanvas');
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        const container = canvas.parentElement;
        canvas.width = container.offsetWidth;
        canvas.height = 400;

        ctx.clearRect(0, 0, canvas.width, canvas.height);

        // 绘制节点
        const centerX = canvas.width / 2;
        const centerY = canvas.height / 2;
        const radius = Math.min(canvas.width, canvas.height) * 0.3;

        data.entities.forEach((entity, i) => {
            const angle = (2 * Math.PI * i) / data.entities.length;
            const x = centerX + radius * Math.cos(angle);
            const y = centerY + radius * Math.sin(angle);

            // 绘制节点
            ctx.beginPath();
            ctx.arc(x, y, 20, 0, 2 * Math.PI);
            ctx.fillStyle = this.getEntityColor(entity.type);
            ctx.fill();

            // 绘制名称
            ctx.fillStyle = '#333';
            ctx.font = '12px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(entity.name.substring(0, 4), x, y + 30);
        });

        // 绘制关系
        ctx.strokeStyle = '#ccc';
        ctx.lineWidth = 1;
        data.relations.forEach(rel => {
            // 简化处理，实际需要记录节点位置
        });
    },

    getEntityColor(type) {
        const colors = { '功法': '#4CAF50', '穴位': '#2196F3', '概念': '#FF9800', '动作': '#9C27B0', '脏腑': '#F44336' };
        return colors[type] || '#999';
    }
};

window.initReasoning = function() {
    ReasoningModule.init();
};
