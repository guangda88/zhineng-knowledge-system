// 灵知系统 - 知识库模块
const LibraryModule = {
    currentCategory: 'all',
    initialized: false,

    init() {
        if (this.initialized) return;
        this.initialized = true;
        this.bindEvents();
        this.loadDocuments();
    },

    bindEvents() {
        // 树形分类点击
        document.querySelectorAll('.tree-item').forEach(item => {
            item.addEventListener('click', () => {
                const category = item.dataset.category;
                this.currentCategory = category;
                this.updateTreeSelection(item);
                this.loadDocuments(category);
            });
        });

        // 刷新按钮
        document.getElementById('refreshLibraryBtn')?.addEventListener('click', () => {
            this.loadDocuments(this.currentCategory);
        });

        // 添加文档按钮
        document.getElementById('addDocumentBtn')?.addEventListener('click', () => {
            this.showAddDocumentModal();
        });
    },

    async loadDocuments(category = 'all') {
        const listDiv = document.getElementById('documentList');
        listDiv.innerHTML = '<div class="loading"><div class="spinner"></div><p>加载中...</p></div>';

        try {
            const options = { limit: 50 };
            if (category !== 'all') {
                options.category = category;
            }

            const data = await API.documents.list(options);
            this.displayDocuments(data);
        } catch (error) {
            listDiv.innerHTML = `
                <div class="error-state">
                    <div class="error-icon">⚠️</div>
                    <p>加载失败：${Utils.escapeHtml(error.message)}</p>
                </div>
            `;
        }
    },

    displayDocuments(data) {
        const listDiv = document.getElementById('documentList');

        if (!data.documents || data.documents.length === 0) {
            listDiv.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">📄</div>
                    <p>暂无文档</p>
                </div>
            `;
            return;
        }

        listDiv.innerHTML = `
            <p class="result-meta">共 ${Utils.formatNumber(data.total)} 篇文档</p>
            <div class="document-grid">
                ${data.documents.map(doc => this.createDocumentCard(doc)).join('')}
            </div>
        `;
    },

    createDocumentCard(doc) {
        const tags = doc.tags && Array.isArray(doc.tags) ?
            doc.tags.map(t => `<span class="tag">${Utils.escapeHtml(t)}</span>`).join(' ') : '';

        return `
            <div class="document-card" data-id="${Utils.escapeHtml(String(doc.id))}">
                <h3 class="document-title">${Utils.escapeHtml(doc.title)}</h3>
                <div class="document-meta">
                    ${doc.category ? `<span class="tag">${Utils.escapeHtml(doc.category)}</span>` : ''}
                    ${tags}
                </div>
                <p class="document-preview">${Utils.escapeHtml(Utils.truncate(doc.content, 100))}</p>
                <div class="document-footer">
                    <span class="document-date">${Utils.formatDate(doc.created_at)}</span>
                </div>
            </div>
        `;
    },

    updateTreeSelection(selectedItem) {
        document.querySelectorAll('.tree-item').forEach(item => {
            item.classList.toggle('active', item === selectedItem);
        });
    },

    showAddDocumentModal() {
        const modal = document.getElementById('modalContainer');
        const modalBody = document.getElementById('modalContent');

        modalBody.innerHTML = `
            <button class="modal-close" onclick="closeAllModals()">×</button>
            <h2>添加文档</h2>
            <div style="margin-top:16px;">
                <div class="settings-section">
                    <div class="setting-item" style="margin-bottom:12px;">
                        <label style="display:block;margin-bottom:4px;font-size:14px;">标题</label>
                        <input type="text" id="newDocTitle" class="setting-input" placeholder="文档标题..." style="width:100%;padding:8px 12px;border:1px solid var(--border-color);border-radius:6px;">
                    </div>
                    <div class="setting-item" style="margin-bottom:12px;">
                        <label style="display:block;margin-bottom:4px;font-size:14px;">分类</label>
                        <select id="newDocCategory" style="width:100%;padding:8px 12px;border:1px solid var(--border-color);border-radius:6px;">
                            <option value="">无分类</option>
                            <option value="气功">气功</option>
                            <option value="中医">中医</option>
                            <option value="儒家">儒家</option>
                            <option value="国学">国学</option>
                            <option value="佛学">佛学</option>
                            <option value="道家">道家</option>
                            <option value="武术">武术</option>
                            <option value="哲学">哲学</option>
                        </select>
                    </div>
                    <div class="setting-item" style="margin-bottom:12px;">
                        <label style="display:block;margin-bottom:4px;font-size:14px;">标签（逗号分隔）</label>
                        <input type="text" id="newDocTags" class="setting-input" placeholder="标签1, 标签2..." style="width:100%;padding:8px 12px;border:1px solid var(--border-color);border-radius:6px;">
                    </div>
                    <div class="setting-item" style="margin-bottom:16px;">
                        <label style="display:block;margin-bottom:4px;font-size:14px;">内容</label>
                        <textarea id="newDocContent" rows="8" style="width:100%;padding:8px 12px;border:1px solid var(--border-color);border-radius:6px;font-size:14px;line-height:1.6;resize:vertical;" placeholder="输入文档内容..."></textarea>
                    </div>
                    <div style="display:flex;gap:8px;justify-content:flex-end;">
                        <button class="btn btn-secondary" onclick="closeAllModals()">取消</button>
                        <button class="btn btn-primary" id="submitDocBtn" style="min-width:100px;">提交</button>
                    </div>
                </div>
            </div>
        `;

        document.getElementById('submitDocBtn').addEventListener('click', async () => {
            const title = document.getElementById('newDocTitle').value.trim();
            const content = document.getElementById('newDocContent').value.trim();
            if (!title || !content) {
                alert('请填写标题和内容');
                return;
            }

            const btn = document.getElementById('submitDocBtn');
            btn.disabled = true;
            btn.textContent = '提交中...';

            try {
                const tags = document.getElementById('newDocTags').value.trim();
                await API.documents.create({
                    title,
                    content,
                    category: document.getElementById('newDocCategory').value,
                    tags: tags ? tags.split(',').map(t => t.trim()).filter(Boolean) : []
                });
                closeAllModals();
                this.loadDocuments(this.currentCategory);
            } catch (error) {
                alert('添加失败：' + error.message);
                btn.disabled = false;
                btn.textContent = '提交';
            }
        });

        modal.classList.add('active');
    }
};

window.initLibrary = function() {
    LibraryModule.init();
};
