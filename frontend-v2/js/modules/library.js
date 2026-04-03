// 灵知系统 - 知识库模块
const LibraryModule = {
    currentCategory: 'all',

    init() {
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
                    <p>加载失败：${error.message}</p>
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
        const categoryClass = doc.category ? `tag-${doc.category}` : '';
        const tags = doc.tags && Array.isArray(doc.tags) ?
            doc.tags.map(t => `<span class="tag">${Utils.escapeHtml(t)}</span>`).join(' ') : '';

        return `
            <div class="document-card" data-id="${doc.id}">
                <h3 class="document-title">${Utils.escapeHtml(doc.title)}</h3>
                <div class="document-meta">
                    ${doc.category ? `<span class="tag ${categoryClass}">${doc.category}</span>` : ''}
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
        // TODO: 实现添加文档功能
        alert('添加文档功能开发中...');
    }
};

window.initLibrary = function() {
    LibraryModule.init();
};
