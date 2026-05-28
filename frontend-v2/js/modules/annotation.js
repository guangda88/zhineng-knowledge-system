// 灵知系统 - 标注系统模块
const AnnotationModule = {
    initialized: false,
    currentTab: 'ocr',
    currentTask: null,
    stats: {},

    init() {
        if (this.initialized) return;
        this.initialized = true;
        this.bindEvents();
        this.loadStats();
    },

    bindEvents() {
        const listDiv = document.getElementById('annotationList');
        if (listDiv) {
            listDiv.addEventListener('click', (e) => {
                const item = e.target.closest('.annotation-list-item');
                if (item && item.dataset.taskId) {
                    this.loadTask(item.dataset.taskId);
                }
            });
        }

        const tabContainer = document.querySelector('.annotation-tabs');
        if (tabContainer) {
            tabContainer.addEventListener('click', (e) => {
                const btn = e.target.closest('.tab-btn');
                if (!btn) return;
                const tab = btn.dataset.tab;
                if (tab === this.currentTab) return;

                tabContainer.querySelectorAll('.tab-btn').forEach(b => {
                    b.classList.remove('active');
                    b.style.background = 'transparent';
                });
                btn.classList.add('active');
                btn.style.background = 'var(--bg-primary)';

                this.currentTab = tab;
                this.currentTask = null;
                const editorDiv = document.getElementById('annotationEditor');
                if (editorDiv) {
                    editorDiv.innerHTML = '<div class="editor-placeholder">选择内容开始标注</div>';
                }
                this.loadPendingTasks();
            });
        }
    },

    async loadStats() {
        try {
            const [ocrStats, transStats, generalStats] = await Promise.allSettled([
                API.annotation.ocrStats(),
                API.annotation.transcriptionStats(),
                API.annotation.annotationStats()
            ]);

            this.stats = {
                ocr: ocrStats.status === 'fulfilled' ? ocrStats.value.data : null,
                transcription: transStats.status === 'fulfilled' ? transStats.value.data : null,
                general: generalStats.status === 'fulfilled' ? generalStats.value.data : null
            };

            this.updateStatsDisplay();
            this.loadPendingTasks();
        } catch (error) {
            console.error('加载标注统计失败:', error);
        }
    },

    updateStatsDisplay() {
        const listDiv = document.getElementById('annotationList');
        if (!listDiv) return;

        const s = this.stats;
        const ocrPending = s.ocr?.pending_count || s.ocr?.pending || 0;
        const transPending = s.transcription?.pending_count || s.transcription?.pending || 0;
        const ocrTotal = s.ocr?.total_count || s.ocr?.total || 0;
        const transTotal = s.transcription?.total_count || s.transcription?.total || 0;
        const genTotal = s.general?.total_count || s.general?.total || 0;

        listDiv.innerHTML = `
            <div style="margin-bottom:16px;padding:12px;background:var(--bg-tertiary);border-radius:8px;">
                <h4 style="margin-bottom:8px;font-size:14px;">📊 标注统计</h4>
                <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;font-size:13px;">
                    <div>
                        <span style="color:var(--text-secondary);">OCR</span><br>
                        <strong>${ocrTotal}</strong> / <strong style="color:var(--accent-color);">${ocrPending}</strong> 待处理
                    </div>
                    <div>
                        <span style="color:var(--text-secondary);">转写</span><br>
                        <strong>${transTotal}</strong> / <strong style="color:var(--accent-color);">${transPending}</strong> 待处理
                    </div>
                    <div>
                        <span style="color:var(--text-secondary);">通用</span><br>
                        <strong>${genTotal}</strong> 总计
                    </div>
                </div>
            </div>
            <div id="annotationTaskList"></div>
        `;
    },

    async loadPendingTasks() {
        const taskListDiv = document.getElementById('annotationTaskList');
        if (!taskListDiv) return;

        taskListDiv.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

        try {
            let data;
            if (this.currentTab === 'ocr') {
                data = await API.annotation.ocrPending();
            } else if (this.currentTab === 'transcription') {
                data = await API.annotation.transcriptionPending();
            } else {
                taskListDiv.innerHTML = `
                    <div style="text-align:center;padding:16px;color:var(--text-secondary);">
                        <p>📝 通用标注通过文档详情页操作</p>
                    </div>
                `;
                return;
            }

            const tasks = data.data?.tasks || data.data?.items || data.data || [];

            if (!tasks.length) {
                taskListDiv.innerHTML = `
                    <div style="text-align:center;padding:16px;color:var(--text-secondary);">
                        <p>✅ 没有待处理的${this.currentTab === 'ocr' ? 'OCR' : '转写'}任务</p>
                    </div>
                `;
                return;
            }

            taskListDiv.innerHTML = `
                <h4 style="margin-bottom:8px;font-size:13px;color:var(--text-secondary);">待处理任务 (${tasks.length})</h4>
                ${tasks.slice(0, 20).map(task => `
                    <div class="annotation-list-item" data-task-id="${Utils.escapeHtml(String(task.task_id || task.id || ''))}" style="padding:8px 12px;border:1px solid var(--border-light);border-radius:6px;margin-bottom:6px;cursor:pointer;transition:background 0.2s;">
                        <div style="font-size:14px;font-weight:500;">${Utils.escapeHtml(task.filename || task.title || '任务 ' + (task.task_id || task.id || ''))}</div>
                        <div style="font-size:12px;color:var(--text-secondary);margin-top:2px;">
                            ${task.source ? Utils.escapeHtml(task.source) + ' · ' : ''}
                            ${task.created_at ? Utils.formatDate(task.created_at) : ''}
                        </div>
                    </div>
                `).join('')}
            `;
        } catch (error) {
            taskListDiv.innerHTML = `<p class="text-small">加载任务失败: ${Utils.escapeHtml(error.message)}</p>`;
        }
    },

    async loadTask(taskId) {
        const editorDiv = document.getElementById('annotationEditor');
        if (!editorDiv) return;

        editorDiv.innerHTML = '<div class="loading"><div class="spinner"></div><p>加载任务...</p></div>';

        try {
            const data = await API.annotation.ocrTask(taskId);
            const task = data.data;
            this.currentTask = task;

            const tabLabel = this.currentTab === 'ocr' ? 'OCR' : '转写';
            const correctFn = this.currentTab === 'ocr' ? 'ocrCorrect' : 'transcriptionCorrect';

            editorDiv.innerHTML = `
                <div style="padding:16px;">
                    <h3 style="margin-bottom:4px;">${Utils.escapeHtml(task.filename || task.title || '标注任务')}</h3>
                    <span style="display:inline-block;padding:2px 8px;border-radius:4px;font-size:12px;background:var(--bg-tertiary);color:var(--text-secondary);margin-bottom:12px;">${tabLabel}标注</span>
                    <div style="margin-bottom:16px;padding:12px;background:var(--bg-secondary);border-radius:8px;">
                        <p style="font-size:13px;color:var(--text-secondary);">原始文本</p>
                        <div style="margin-top:8px;white-space:pre-wrap;font-size:14px;line-height:1.8;">
                            ${Utils.escapeHtml(task.original_text || task.text || task.content || '（无文本内容）')}
                        </div>
                    </div>
                    <div style="margin-bottom:16px;">
                        <label style="font-size:13px;color:var(--text-secondary);">校正文本</label>
                        <textarea id="annotationCorrectedText" rows="8" style="width:100%;margin-top:4px;padding:12px;border:1px solid var(--border-color);border-radius:8px;font-size:14px;line-height:1.8;resize:vertical;">${Utils.escapeHtml(task.corrected_text || task.original_text || task.text || '')}</textarea>
                    </div>
                    <div style="display:flex;gap:8px;justify-content:flex-end;">
                        <button class="btn btn-secondary" id="annotationSkipBtn">跳过</button>
                        <button class="btn btn-primary" id="annotationSubmitBtn">提交校正</button>
                    </div>
                </div>
            `;

            document.getElementById('annotationSubmitBtn').addEventListener('click', () => {
                this.submitCorrection(taskId, correctFn);
            });

            document.getElementById('annotationSkipBtn').addEventListener('click', () => {
                this.currentTask = null;
                editorDiv.innerHTML = '<div class="editor-placeholder">选择内容开始标注</div>';
            });
        } catch (error) {
            editorDiv.innerHTML = `<p class="text-small">加载失败: ${Utils.escapeHtml(error.message)}</p>`;
        }
    },

    async submitCorrection(taskId, correctFn) {
        const textarea = document.getElementById('annotationCorrectedText');
        if (!textarea) return;

        const correctedText = textarea.value.trim();
        if (!correctedText) {
            alert('请输入校正文本');
            return;
        }

        const submitBtn = document.getElementById('annotationSubmitBtn');
        submitBtn.disabled = true;
        submitBtn.textContent = '提交中...';

        try {
            await API.annotation[correctFn]({
                task_id: taskId,
                corrected_text: correctedText
            });

            this.currentTask = null;
            const editorDiv = document.getElementById('annotationEditor');
            editorDiv.innerHTML = `
                <div style="text-align:center;padding:24px;">
                    <div style="font-size:48px;">✅</div>
                    <h3>校正已提交</h3>
                    <p style="color:var(--text-secondary);margin-top:8px;">感谢您的贡献</p>
                </div>
            `;

            this.loadPendingTasks();
            this.loadStats();
        } catch (error) {
            alert('提交失败：' + error.message);
            submitBtn.disabled = false;
            submitBtn.textContent = '提交校正';
        }
    }
};

window.initAnnotation = function() {
    AnnotationModule.init();
};
