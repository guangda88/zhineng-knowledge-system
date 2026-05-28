// 灵知系统 - 数据导入模块
const ImportModule = {
    initialized: false,
    importing: false,

    init() {
        if (this.initialized) return;
        this.initialized = true;
        this.bindEvents();
        this.loadImportLog();
    },

    bindEvents() {
        const container = document.querySelector('.import-container');
        if (!container) return;

        container.addEventListener('click', (e) => {
            const card = e.target.closest('.import-source-card');
            if (!card) return;

            const source = card.dataset.source;
            if (e.target.closest('.btn')) {
                switch (source) {
                    case 'local':
                        this.showLocalUpload();
                        break;
                    case '115':
                        this.showImportConfig('115网盘');
                        break;
                    case 'tingwu':
                        this.showImportConfig('听悟API');
                        break;
                }
            }
        });
    },

    async showLocalUpload() {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = '.txt,.pdf,.epub,.mobi,.azw3,.djvu,.json,.csv,.xml';
        input.multiple = true;

        input.addEventListener('change', async () => {
            const files = Array.from(input.files);
            if (!files.length) return;

            this.addLog('info', `开始处理 ${files.length} 个文件...`);
            this.importing = true;

            try {
                const formData = new FormData();
                for (const file of files) {
                    formData.append('files', file);
                }

                const result = await API.request('/textbook-processing/upload', {
                    method: 'POST',
                    headers: {},
                    body: formData
                });

                const taskId = result.data?.task_id || result.task_id || 'unknown';
                this.addLog('success', `✅ ${files.length} 个文件上传成功，任务ID: ${taskId}`);
                this.pollImportStatus();
            } catch (error) {
                this.addLog('error', `❌ 上传失败: ${error.message}`);
                this.importing = false;
            }
        });

        input.click();
    },

    showImportConfig(sourceName) {
        const modal = document.getElementById('modalContainer');
        const modalBody = document.getElementById('modalContent');

        modalBody.innerHTML = `
            <button class="modal-close" onclick="closeAllModals()">×</button>
            <h2>配置 ${Utils.escapeHtml(sourceName)} 导入</h2>
            <div style="margin-top:16px;">
                <div class="settings-section">
                    <div class="setting-item" style="margin-bottom:12px;">
                        <label style="display:block;margin-bottom:4px;font-size:14px;">导入路径或URL</label>
                        <input type="text" id="importPathInput" class="setting-input" placeholder="输入路径或URL..." style="width:100%;padding:8px 12px;border:1px solid var(--border-color);border-radius:6px;">
                    </div>
                    <div class="setting-item" style="margin-bottom:12px;">
                        <label style="display:block;margin-bottom:4px;font-size:14px;">文件类型筛选</label>
                        <select id="importTypeFilter" style="width:100%;padding:8px 12px;border:1px solid var(--border-color);border-radius:6px;">
                            <option value="">全部类型</option>
                            <option value="pdf">PDF</option>
                            <option value="txt">TXT</option>
                            <option value="epub">EPUB</option>
                            <option value="djvu">DJVU</option>
                        </select>
                    </div>
                    <div class="setting-item" style="margin-bottom:16px;">
                        <label style="font-size:14px;">
                            <input type="checkbox" id="importRecursive" checked>
                            递归处理子目录
                        </label>
                    </div>
                    <button class="btn btn-primary" id="importStartBtn" style="width:100%;">开始导入</button>
                </div>
            </div>
        `;

        document.getElementById('importStartBtn').addEventListener('click', () => {
            const path = document.getElementById('importPathInput').value.trim();
            if (!path) {
                alert('请输入路径');
                return;
            }
            closeAllModals();
            this.startImport(sourceName, {
                path,
                file_type: document.getElementById('importTypeFilter').value,
                recursive: document.getElementById('importRecursive').checked
            });
        });

        modal.classList.add('active');
    },

    async startImport(sourceName, config) {
        this.importing = true;
        this.addLog('info', `开始从${Utils.escapeHtml(sourceName)}导入...`);

        try {
            const data = await API.importData.processTextbook(config);
            this.addLog('success', `导入任务已创建，任务ID: ${data.data?.task_id || 'unknown'}`);
            this.pollImportStatus();
        } catch (error) {
            this.addLog('error', `导入失败: ${error.message}`);
            this.importing = false;
        }
    },

    async pollImportStatus() {
        let attempts = 0;
        const maxAttempts = 60;

        const poll = async () => {
            if (attempts >= maxAttempts || !this.importing) return;
            attempts++;

            try {
                const data = await API.importData.getTasks({ size: 5 });
                const tasks = data.data?.tasks || data.data?.items || data.data || [];
                const latest = tasks[0];

                if (latest) {
                    if (latest.status === 'completed' || latest.status === 'done') {
                        this.addLog('success', `导入完成！处理了 ${latest.processed_count || latest.total || 0} 个文件`);
                        this.importing = false;
                        return;
                    } else if (latest.status === 'failed' || latest.status === 'error') {
                        this.addLog('error', `导入失败: ${latest.error || '未知错误'}`);
                        this.importing = false;
                        return;
                    } else {
                        this.addLog('info', `导入进行中... 状态: ${latest.status}，进度: ${latest.progress || 0}%`);
                    }
                }

                setTimeout(poll, 5000);
            } catch (error) {
                this.addLog('error', `状态检查失败: ${error.message}`);
                setTimeout(poll, 10000);
            }
        };

        setTimeout(poll, 3000);
    },

    addLog(type, message) {
        const logDiv = document.getElementById('importLog');
        if (!logDiv) return;

        const colors = {
            info: 'var(--info)',
            success: 'var(--success)',
            error: 'var(--danger)',
            warning: 'var(--warning)'
        };

        const time = new Date().toLocaleTimeString('zh-CN');
        const entry = document.createElement('div');
        entry.style.cssText = `padding:6px 12px;border-left:3px solid ${colors[type] || 'var(--text-secondary)'};margin-bottom:4px;font-size:13px;background:var(--bg-tertiary);border-radius:0 4px 4px 0;`;
        entry.innerHTML = `<span style="color:var(--text-tertiary);">[${time}]</span> ${Utils.escapeHtml(message)}`;

        if (logDiv.firstChild) {
            logDiv.insertBefore(entry, logDiv.firstChild);
        } else {
            logDiv.appendChild(entry);
        }
    },

    loadImportLog() {
        const logDiv = document.getElementById('importLog');
        if (!logDiv) return;

        logDiv.innerHTML = `
            <div style="text-align:center;padding:16px;color:var(--text-secondary);font-size:13px;">
                导入日志将显示在这里
            </div>
        `;
    }
};

window.initImport = function() {
    ImportModule.init();
};
