// 灵知系统 - 书目检索模块
const SysbooksModule = {
    initialized: false,
    currentQuery: '',
    currentPage: 1,
    totalPages: 1,
    statsCache: null,

    init() {
        if (this.initialized) return;
        this.initialized = true;
        this.bindEvents();
        this.loadStats();
    },

    bindEvents() {
        const searchInput = document.getElementById('sysbooksSearchInput');
        const domainFilter = document.getElementById('sysbooksDomainFilter');
        const extFilter = document.getElementById('sysbooksExtFilter');

        const doSearch = () => {
            this.currentPage = 1;
            this.search(searchInput.value.trim(), {
                domain: domainFilter.value,
                extension: extFilter.value
            });
        };

        const debouncedSearch = Utils.debounce(doSearch, 500);

        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') doSearch();
        });
        searchInput.addEventListener('input', () => {
            if (searchInput.value.trim().length >= 2) debouncedSearch();
        });
        domainFilter.addEventListener('change', doSearch);
        extFilter.addEventListener('change', doSearch);
    },

    async loadStats() {
        try {
            const data = await API.sysbooks.getStats();
            this.statsCache = data.data;

            const headerStats = document.querySelector('#module-sysbooks .module-stats');
            if (headerStats && this.statsCache) {
                const total = this.statsCache.total || 0;
                headerStats.innerHTML = `
                    <span class="stat-item">📕 ${Utils.formatNumber(total)} 书目</span>
                `;
            }

            this.populateFilters();
        } catch (error) {
            console.error('加载统计失败:', error);
        }
    },

    populateFilters() {
        if (!this.statsCache) return;

        const domainFilter = document.getElementById('sysbooksDomainFilter');
        const extFilter = document.getElementById('sysbooksExtFilter');

        const domains = this.statsCache.by_domain || [];
        const extensions = this.statsCache.by_extension || [];

        if (domainFilter) {
            const topDomains = domains.slice(0, 30);
            domainFilter.innerHTML = '<option value="">全部领域</option>' +
                topDomains.map(d => `<option value="${Utils.escapeHtml(d.domain || d.name || d.key || '')}">${Utils.escapeHtml(d.domain || d.name || d.key || '')} (${Utils.formatNumber(d.count || 0)})</option>`).join('');
        }

        if (extFilter) {
            const topExts = extensions.slice(0, 15);
            extFilter.innerHTML = '<option value="">全部格式</option>' +
                topExts.map(e => `<option value="${Utils.escapeHtml(e.extension || e.name || e.key || '')}">${Utils.escapeHtml((e.extension || e.name || e.key || '').replace('.', ''))} (${Utils.formatNumber(e.count || 0)})</option>`).join('');
        }
    },

    async search(query, filters = {}) {
        const resultsDiv = document.getElementById('sysbooksResults');
        this.currentQuery = query;

        if (!query && !filters.domain && !filters.extension) {
            resultsDiv.innerHTML = `
                <div class="results-placeholder">
                    <div class="placeholder-icon">📕</div>
                    <h3>搜索书目</h3>
                    <p>输入书名、作者或路径进行检索</p>
                </div>
            `;
            return;
        }

        resultsDiv.innerHTML = '<div class="loading"><div class="spinner"></div><p>搜索中...</p></div>';

        try {
            const options = { ...filters, size: 30, page: this.currentPage };
            if (query) options.q = query;
            const data = await API.sysbooks.search(query, options);
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
        const resultsDiv = document.getElementById('sysbooksResults');
        const results = data.data?.results || data.data?.items || [];
        const total = data.data?.total || results.length;
        this.totalPages = Math.ceil(total / 30);

        if (!results.length) {
            resultsDiv.innerHTML = `
                <div class="results-placeholder">
                    <div class="placeholder-icon">🔍</div>
                    <h3>未找到结果</h3>
                    <p>尝试使用不同的关键词或筛选条件</p>
                </div>
            `;
            return;
        }

        resultsDiv.innerHTML = `
            <div style="margin-bottom:12px;color:var(--text-secondary);font-size:14px;">
                共找到 ${Utils.formatNumber(total)} 条结果
            </div>
            <div class="results-list">
                ${results.map(item => this.createResultCard(item)).join('')}
            </div>
            ${this.totalPages > 1 ? this.renderPagination() : ''}
        `;

        this.bindResultEvents(resultsDiv);
    },

    createResultCard(item) {
        const title = item.title || item.filename || item.name || '未知书目';
        const domain = item.domain || '';
        const subcategory = item.subcategory || '';
        const author = item.author || '';
        const ext = item.extension || item.ext || '';
        const size = item.size ? this.formatSize(item.size) : '';
        const year = item.year || '';

        return `
            <div class="result-card" data-id="${Utils.escapeHtml(String(item.id || ''))}">
                <div class="book-title">${Utils.escapeHtml(title)}</div>
                <div class="book-meta">
                    ${domain ? `<span class="tag">${Utils.escapeHtml(domain)}</span>` : ''}
                    ${subcategory ? `<span class="tag">${Utils.escapeHtml(subcategory)}</span>` : ''}
                    ${ext ? `<span>${Utils.escapeHtml(ext)}</span>` : ''}
                    ${size ? `<span>${size}</span>` : ''}
                    ${year ? `<span>${Utils.escapeHtml(String(year))}</span>` : ''}
                </div>
                ${author ? `<p class="text-small" style="margin-top:4px;">作者: ${Utils.escapeHtml(author)}</p>` : ''}
            </div>
        `;
    },

    formatSize(bytes) {
        if (bytes < 1024) return bytes + 'B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + 'KB';
        if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + 'MB';
        return (bytes / (1024 * 1024 * 1024)).toFixed(1) + 'GB';
    },

    renderPagination() {
        return `
            <div class="pagination" style="display:flex;justify-content:center;gap:8px;margin-top:16px;">
                <button class="btn btn-secondary sysbooks-prev-btn" ${this.currentPage <= 1 ? 'disabled' : ''}>上一页</button>
                <span style="padding:8px 16px;">${this.currentPage} / ${this.totalPages}</span>
                <button class="btn btn-secondary sysbooks-next-btn" ${this.currentPage >= this.totalPages ? 'disabled' : ''}>下一页</button>
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

        const prevBtn = container.querySelector('.sysbooks-prev-btn');
        const nextBtn = container.querySelector('.sysbooks-next-btn');

        if (prevBtn) {
            prevBtn.addEventListener('click', () => {
                if (this.currentPage > 1) {
                    this.currentPage--;
                    this.search(this.currentQuery, this.getCurrentFilters());
                }
            });
        }

        if (nextBtn) {
            nextBtn.addEventListener('click', () => {
                if (this.currentPage < this.totalPages) {
                    this.currentPage++;
                    this.search(this.currentQuery, this.getCurrentFilters());
                }
            });
        }
    },

    getCurrentFilters() {
        const domainFilter = document.getElementById('sysbooksDomainFilter');
        const extFilter = document.getElementById('sysbooksExtFilter');
        return {
            domain: domainFilter ? domainFilter.value : '',
            extension: extFilter ? extFilter.value : ''
        };
    },

    async showDetail(id) {
        try {
            const data = await API.sysbooks.get(id);
            const item = data.data;
            const modal = document.getElementById('modalContainer');
            const modalBody = document.getElementById('modalContent');

            const fields = [
                ['书名', item.title || item.filename],
                ['路径', item.path],
                ['领域', item.domain],
                ['子分类', item.subcategory],
                ['作者', item.author],
                ['年份', item.year ? String(item.year) : ''],
                ['分类', item.category],
                ['出版社', item.publisher],
                ['格式', item.extension || item.ext],
                ['大小', item.size ? this.formatSize(item.size) : ''],
                ['来源', item.source]
            ];

            modalBody.innerHTML = `
                <button class="modal-close" onclick="closeAllModals()">×</button>
                <h2>${Utils.escapeHtml(item.title || item.filename || '书目详情')}</h2>
                <div style="margin-top:16px;display:grid;gap:8px;">
                    ${fields.filter(([, v]) => v).map(([label, value]) => `
                        <div style="display:flex;gap:12px;padding:4px 0;border-bottom:1px solid var(--border-light);">
                            <span style="min-width:80px;color:var(--text-secondary);font-size:14px;">${label}:</span>
                            <span style="font-size:14px;">${Utils.escapeHtml(String(value))}</span>
                        </div>
                    `).join('')}
                </div>
            `;

            modal.classList.add('active');
        } catch (error) {
            alert('加载详情失败：' + error.message);
        }
    }
};

window.initSysbooks = function() {
    SysbooksModule.init();
};
