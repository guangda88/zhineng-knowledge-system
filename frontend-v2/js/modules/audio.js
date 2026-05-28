// 灵知系统 - 音频处理模块
const AudioModule = {
    initialized: false,
    files: [],
    currentFileId: null,

    init() {
        if (this.initialized) return;
        this.initialized = true;
        this.bindEvents();
        this.loadFiles();
    },

    bindEvents() {
        const uploadBtn = document.getElementById('uploadAudioBtn');
        if (uploadBtn) {
            uploadBtn.addEventListener('click', () => this.showUploadDialog());
        }
    },

    async loadFiles() {
        const listDiv = document.getElementById('audioList');
        if (!listDiv) return;

        listDiv.innerHTML = '<div class="loading"><div class="spinner"></div><p>加载音频列表...</p></div>';

        try {
            const data = await API.audio.list({ size: 50 });
            this.files = data.data?.items || data.data?.results || data.data || [];
            this.renderFileList();
        } catch (error) {
            listDiv.innerHTML = `
                <div class="results-placeholder">
                    <div class="placeholder-icon">🎧</div>
                    <h3>加载失败</h3>
                    <p>${Utils.escapeHtml(error.message)}</p>
                </div>
            `;
        }
    },

    renderFileList() {
        const listDiv = document.getElementById('audioList');
        if (!listDiv) return;

        if (!this.files.length) {
            listDiv.innerHTML = `
                <div class="results-placeholder">
                    <div class="placeholder-icon">🎧</div>
                    <h3>暂无音频文件</h3>
                    <p>点击"上传音频"按钮添加文件</p>
                </div>
            `;
            return;
        }

        listDiv.innerHTML = `
            <div style="margin-bottom:12px;color:var(--text-secondary);font-size:14px;">
                共 ${this.files.length} 个音频文件
            </div>
            ${this.files.map(file => `
                <div class="result-card audio-file-item" data-id="${Utils.escapeHtml(String(file.id || file.file_id || ''))}" style="margin-bottom:8px;">
                    <div style="display:flex;justify-content:space-between;align-items:center;">
                        <div>
                            <div class="book-title">${Utils.escapeHtml(file.filename || file.name || '音频文件')}</div>
                            <div class="book-meta">
                                ${file.duration ? `<span>${this.formatDuration(file.duration)}</span>` : ''}
                                ${file.size ? `<span>${this.formatSize(file.size)}</span>` : ''}
                                ${file.status ? `<span class="tag">${Utils.escapeHtml(file.status)}</span>` : ''}
                                ${file.created_at ? `<span>${Utils.formatDate(file.created_at)}</span>` : ''}
                            </div>
                        </div>
                        <div style="display:flex;gap:4px;">
                            ${file.status === 'uploaded' || !file.transcribed ? `
                                <button class="btn btn-sm btn-primary audio-transcribe-btn" data-id="${Utils.escapeHtml(String(file.id || file.file_id || ''))}">转写</button>
                            ` : ''}
                            <button class="btn btn-sm btn-secondary audio-delete-btn" data-id="${Utils.escapeHtml(String(file.id || file.file_id || ''))}">删除</button>
                        </div>
                    </div>
                </div>
            `).join('')}
        `;

        this.bindListEvents();
    },

    bindListEvents() {
        const listDiv = document.getElementById('audioList');
        if (!listDiv) return;

        listDiv.querySelectorAll('.audio-file-item').forEach(el => {
            el.addEventListener('click', (e) => {
                if (e.target.closest('button')) return;
                this.showFileDetail(el.dataset.id);
            });
        });

        listDiv.querySelectorAll('.audio-transcribe-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.startTranscribe(btn.dataset.id);
            });
        });

        listDiv.querySelectorAll('.audio-delete-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                if (confirm('确定删除此音频文件？')) {
                    this.deleteFile(btn.dataset.id);
                }
            });
        });
    },

    async showFileDetail(fileId) {
        const editorDiv = document.getElementById('audioEditor');
        if (!editorDiv) return;

        this.currentFileId = fileId;
        editorDiv.innerHTML = '<div class="loading"><div class="spinner"></div><p>加载详情...</p></div>';

        try {
            const [fileData, segmentsData] = await Promise.allSettled([
                API.audio.get(fileId),
                API.audio.getSegments(fileId)
            ]);

            const file = fileData.status === 'fulfilled' ? fileData.value.data : null;
            const segments = segmentsData.status === 'fulfilled'
                ? (segmentsData.value.data?.segments || segmentsData.value.data?.items || segmentsData.value.data || [])
                : [];

            editorDiv.innerHTML = `
                <div style="padding:16px;">
                    <h3>${Utils.escapeHtml(file?.filename || file?.name || '音频详情')}</h3>
                    <div class="book-meta" style="margin:8px 0;">
                        ${file?.duration ? `<span>时长: ${this.formatDuration(file.duration)}</span>` : ''}
                        ${file?.size ? `<span>大小: ${this.formatSize(file.size)}</span>` : ''}
                        ${file?.status ? `<span class="tag">${Utils.escapeHtml(file.status)}</span>` : ''}
                    </div>
                    ${segments.length ? `
                        <h4 style="margin-top:16px;font-size:14px;">转写片段 (${segments.length})</h4>
                        <div style="max-height:400px;overflow-y:auto;margin-top:8px;">
                            ${segments.map((seg, i) => `
                                <div style="padding:8px 12px;border-bottom:1px solid var(--border-light);font-size:14px;">
                                    <span style="color:var(--text-secondary);font-size:12px;">
                                        ${seg.start_time ? this.formatTime(seg.start_time) : '#' + (i + 1)}
                                    </span>
                                    <p style="margin-top:2px;">${Utils.escapeHtml(seg.text || seg.content || '')}</p>
                                </div>
                            `).join('')}
                        </div>
                    ` : `
                        <p style="margin-top:16px;color:var(--text-secondary);">暂无转写内容</p>
                        <button class="btn btn-primary audio-detail-transcribe-btn" style="margin-top:8px;">开始转写</button>
                    `}
                </div>
            `;

            const transcribeBtn = editorDiv.querySelector('.audio-detail-transcribe-btn');
            if (transcribeBtn) {
                transcribeBtn.addEventListener('click', () => this.startTranscribe(fileId));
            }
        } catch (error) {
            editorDiv.innerHTML = `<p class="text-small">加载失败: ${Utils.escapeHtml(error.message)}</p>`;
        }
    },

    async startTranscribe(fileId) {
        try {
            await API.audio.transcribe(fileId);
            alert('转写任务已提交，请稍后查看结果');
            this.loadFiles();
            if (this.currentFileId === fileId) {
                this.showFileDetail(fileId);
            }
        } catch (error) {
            alert('转写失败：' + error.message);
        }
    },

    async deleteFile(fileId) {
        try {
            await API.audio.delete(fileId);
            this.files = this.files.filter(f => String(f.id || f.file_id) !== String(fileId));
            this.renderFileList();
            if (this.currentFileId === fileId) {
                document.getElementById('audioEditor').innerHTML = '';
            }
        } catch (error) {
            alert('删除失败：' + error.message);
        }
    },

    showUploadDialog() {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = 'audio/*';
        input.multiple = true;

        input.addEventListener('change', async () => {
            const files = Array.from(input.files);
            if (!files.length) return;

            for (const file of files) {
                try {
                    await API.audio.upload(file);
                } catch (error) {
                    alert(`上传 ${file.name} 失败: ${error.message}`);
                }
            }

            this.loadFiles();
        });

        input.click();
    },

    formatDuration(seconds) {
        if (!seconds) return '';
        const m = Math.floor(seconds / 60);
        const s = Math.floor(seconds % 60);
        return `${m}:${s.toString().padStart(2, '0')}`;
    },

    formatSize(bytes) {
        if (!bytes) return '';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + 'KB';
        return (bytes / (1024 * 1024)).toFixed(1) + 'MB';
    },

    formatTime(seconds) {
        if (!seconds) return '';
        const m = Math.floor(seconds / 60);
        const s = Math.floor(seconds % 60);
        return `${m}:${s.toString().padStart(2, '0')}`;
    }
};

window.initAudio = function() {
    AudioModule.init();
};
