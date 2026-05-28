// 灵知系统 - 古籍文档模块
const GujiModule = {
    initialized: false,
    currentQuery: '',
    currentPage: 1,
    totalPages: 1,
    stats: null,

    init() {
        if (this.initialized) return;
        this.initialized = true;
        this.bindEvents();
        this.loadStats();
    },

    bindEvents() {
        const searchInput = document.getElementById('gujiSearchInput');
        const collectionFilter = document.getElementById('gujiCollectionFilter');

        const doSearch = () => {
            const query = searchInput.value.trim();
            const collection = collectionFilter.value;
            this.currentPage = 1;
            this.search(query, { collection });
        };

        const debouncedSearch = Utils.debounce(doSearch, 500);

        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') doSearch();
        });
        searchInput.addEventListener('input', () => {
            if (searchInput.value.trim().length >= 2) debouncedSearch();
        });
        collectionFilter.addEventListener('change', doSearch);
    },

    async loadStats() {
        try {
            const data = await API.guji.getStats();
            this.stats = data.data;
            const headerStats = document.querySelector('#module-guji .module-stats');
            if (headerStats && this.stats) {
                const bookCount = this.stats.book_count || this.stats.total_books || 0;
                const fileCount = this.stats.file_count || this.stats.total_files || 0;
                headerStats.innerHTML = `
                    <span class="stat-item">📖 ${Utils.formatNumber(bookCount)} 种书</span>
                    <span class="stat-item">📄 ${Utils.formatNumber(fileCount)} 文件</span>
                `;
            }
        } catch (error) {
            console.error('加载统计失败:', error);
        }
    },

    async search(query, filters = {}) {
        const resultsDiv = document.getElementById('gujiResults');
        this.currentQuery = query;

        if (!query) {
            resultsDiv.innerHTML = `
                <div class="results-placeholder">
                    <div class="placeholder-icon">📖</div>
                    <h3>搜索古籍文档</h3>
                    <p>输入关键词搜索扫描文档，如：黄帝内经、道德经、四部丛刊</p>
                </div>
            `;
            return;
        }

        resultsDiv.innerHTML = '<div class="loading"><div class="spinner"></div><p>搜索中...</p></div>';

        try {
            const options = { ...filters, size: 30, page: this.currentPage };
            const data = await API.guji.search(query, options);
            this.displayResults(data);
        } catch (error) {
            resultsDiv.innerHTML = `
                <div class="results-placeholder">
                    <div class="placeholder-icon">❌</div>
                    <h3>搜索失败</h3>
                    <p>${Utils.escapeHtml(error.message)}</p>
                </div>
            `;
        }
    },

    displayResults(data) {
        const resultsDiv = document.getElementById('gujiResults');
        const results = data.data?.results || data.data?.items || [];
        const total = data.data?.total || results.length;
        this.totalPages = Math.ceil(total / 30);

        if (!results.length) {
            resultsDiv.innerHTML = `
                <div class="results-placeholder">
                    <div class="placeholder-icon">🔍</div>
                    <h3>未找到结果</h3>
                    <p>尝试使用不同的关键词搜索</p>
                </div>
            `;
            return;
        }

        resultsDiv.innerHTML = `
            <div class="guji-result-header">
                <span>共找到 ${Utils.formatNumber(total)} 条结果</span>
            </div>
            <div class="results-list">
                ${results.map(item => this.createResultCard(item)).join('')}
            </div>
            ${this.totalPages > 1 ? this.renderPagination() : ''}
        `;

        this.bindResultEvents(resultsDiv);
    },

    createResultCard(item) {
        const title = item.title || item.filename || item.name || '未命名文档';
        const collection = item.collection || item.source || '';
        const preview = item.body_preview || item.preview || item.description || '';
        const score = item.score || item.relevance || 0;
        const fileExt = item.extension || item.ext || '';

        return `
            <div class="result-card" data-id="${Utils.escapeHtml(String(item.id || ''))}">
                <div class="book-title">${Utils.escapeHtml(title)}</div>
                <div class="book-meta">
                    ${collection ? `<span class="tag">${Utils.escapeHtml(collection)}</span>` : ''}
                    ${fileExt ? `<span class="tag">${Utils.escapeHtml(fileExt)}</span>` : ''}
                    ${score ? `<span>相关度: ${(score * 100).toFixed(1)}%</span>` : ''}
                </div>
                ${preview ? `<p class="text-small" style="margin-top:8px;color:var(--text-secondary);">${Utils.escapeHtml(preview).substring(0, 200)}</p>` : ''}
            </div>
        `;
    },

    renderPagination() {
        return `
            <div class="pagination" style="display:flex;justify-content:center;gap:8px;margin-top:16px;">
                <button class="btn btn-secondary guji-prev-btn" ${this.currentPage <= 1 ? 'disabled' : ''}>上一页</button>
                <span style="padding:8px 16px;">${this.currentPage} / ${this.totalPages}</span>
                <button class="btn btn-secondary guji-next-btn" ${this.currentPage >= this.totalPages ? 'disabled' : ''}>下一页</button>
            </div>
        `;
    },

    bindResultEvents(container) {
        container.querySelectorAll('.result-card').forEach(el => {
            el.addEventListener('click', () => {
                const id = el.dataset.id;
                if (id) this.showDetail(id);
            });
        });

        const prevBtn = container.querySelector('.guji-prev-btn');
        const nextBtn = container.querySelector('.guji-next-btn');

        if (prevBtn) {
            prevBtn.addEventListener('click', () => {
                if (this.currentPage > 1) {
                    this.currentPage--;
                    this.search(this.currentQuery, {});
                }
            });
        }

        if (nextBtn) {
            nextBtn.addEventListener('click', () => {
                if (this.currentPage < this.totalPages) {
                    this.currentPage++;
                    this.search(this.currentQuery, {});
                }
            });
        }
    },

    async showDetail(id) {
        try {
            const data = await API.guji.getDocumentInfo(id);
            const item = data.data;
            const modal = document.getElementById('modalContainer');
            const modalBody = document.getElementById('modalContent');

            modalBody.innerHTML = `
                <button class="modal-close" onclick="closeAllModals()">×</button>
                <h2>${Utils.escapeHtml(item.title || item.filename || '文档详情')}</h2>
                <div style="margin-top:12px;">
                    ${item.collection ? `<p><strong>集合:</strong> ${Utils.escapeHtml(item.collection)}</p>` : ''}
                    ${item.filename ? `<p><strong>文件名:</strong> ${Utils.escapeHtml(item.filename)}</p>` : ''}
                    ${item.path ? `<p><strong>路径:</strong> ${Utils.escapeHtml(item.path)}</p>` : ''}
                    ${item.body ? `<div style="margin-top:16px;padding:12px;background:var(--bg-secondary);border-radius:8px;max-height:400px;overflow-y:auto;"><p style="white-space:pre-wrap;">${Utils.escapeHtml(item.body).substring(0, 5000)}</p></div>` : ''}
                </div>
            `;

            modal.classList.add('active');
        } catch (error) {
            alert('加载详情失败：' + error.message);
        }
    }
};

window.initGuji = function() {
    GujiModule.init();
};
