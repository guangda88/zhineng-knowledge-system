// 灵知系统 - 搜索模块
const SearchModule = {
    currentQuery: '',
    currentCategory: '',
    currentMode: 'semantic',

    init() {
        this.bindEvents();
        this.loadRecentSearches();
    },

    bindEvents() {
        const searchInput = document.getElementById('mainSearchInput');
        const searchBtn = document.getElementById('mainSearchBtn');
        const categorySelect = document.getElementById('searchCategory');
        const modeToggles = document.querySelectorAll('.filter-toggle .toggle-btn');

        // 搜索按钮
        searchBtn.addEventListener('click', () => this.performSearch());

        // 回车搜索
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.performSearch();
        });

        // 分类筛选
        categorySelect.addEventListener('change', () => {
            this.currentCategory = categorySelect.value;
            if (this.currentQuery) this.performSearch();
        });

        // 模式切换
        modeToggles.forEach(btn => {
            btn.addEventListener('click', () => {
                modeToggles.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.currentMode = btn.dataset.mode;
                if (this.currentQuery) this.performSearch();
            });
        });

        // 搜索建议
        searchInput.addEventListener('input', Utils.debounce((e) => {
            this.showSuggestions(e.target.value);
        }, 300));
    },

    async performSearch() {
        const searchInput = document.getElementById('mainSearchInput');
        const query = searchInput.value.trim();
        const resultsDiv = document.getElementById('searchResults');

        if (!query) {
            this.showPlaceholder();
            return;
        }

        this.currentQuery = query;

        // 显示加载状态
        resultsDiv.innerHTML = `
            <div class="loading">
                <div class="spinner"></div>
                <p>搜索中...</p>
            </div>
        `;

        try {
            let results;
            if (this.currentMode === 'semantic') {
                results = await API.search.semantic(query, {
                    category: this.currentCategory || undefined
                });
            } else if (this.currentMode === 'keyword') {
                results = await API.search.semantic(query, {
                    category: this.currentCategory || undefined,
                    mode: 'keyword'
                });
            } else {
                results = await API.search.hybrid(query, {
                    category: this.currentCategory || undefined
                });
            }

            this.saveRecentSearch(query);
            this.displayResults(results);
        } catch (error) {
            resultsDiv.innerHTML = `
                <div class="error-state">
                    <div class="error-icon">⚠️</div>
                    <p>搜索失败：${error.message}</p>
                    <button class="btn btn-secondary" onclick="SearchModule.retry()">重试</button>
                </div>
            `;
        }
    },

    displayResults(data) {
        const resultsDiv = document.getElementById('searchResults');

        if (!data.results || data.results.length === 0) {
            resultsDiv.innerHTML = `
                <div class="results-placeholder">
                    <div class="placeholder-icon">🔍</div>
                    <h3>没有找到相关结果</h3>
                    <p>试试其他关键词，如：气功、中医、儒家、国学经典</p>
                </div>
            `;
            return;
        }

        const metaHtml = `
            <div class="results-meta">
                <span>找到 ${Utils.formatNumber(data.total || data.results.length)} 条结果</span>
                <span class="meta-time">耗时 ${data.time || 0.1}秒</span>
            </div>
        `;

        const resultsHtml = `
            <div class="results-list">
                ${data.results.map(item => this.createResultCard(item)).join('')}
            </div>
        `;

        resultsDiv.innerHTML = metaHtml + resultsHtml;
    },

    createResultCard(item) {
        const categoryTag = item.category ?
            `<span class="tag tag-${item.category}">${item.category}</span>` : '';

        const preview = Utils.escapeHtml(
            Utils.truncate(item.content || item.body || '', 150)
        );

        const relevance = item.similarity || item.score ?
            `<span class="relevance-score">相似度: ${Math.round((item.similarity || item.score) * 100)}%</span>` : '';

        return `
            <div class="result-card" data-id="${item.id}">
                <h3 class="result-title">${Utils.escapeHtml(item.title || '无标题')}</h3>
                <p class="result-preview">${preview}</p>
                <div class="result-footer">
                    ${categoryTag}
                    ${relevance}
                    <span class="result-id">ID: ${item.id}</span>
                </div>
            </div>
        `;
    },

    showPlaceholder() {
        const resultsDiv = document.getElementById('searchResults');
        resultsDiv.innerHTML = `
            <div class="results-placeholder">
                <div class="placeholder-icon">🔍</div>
                <h3>开始探索知识</h3>
                <p>输入关键词，如：八段锦、黄帝内经、论语、道德经</p>
                <div class="quick-searches">
                    <button class="quick-search-btn" data-query="八段锦">八段锦</button>
                    <button class="quick-search-btn" data-query="黄帝内经">黄帝内经</button>
                    <button class="quick-search-btn" data-query="论语">论语</button>
                    <button class="quick-search-btn" data-query="道德经">道德经</button>
                </div>
            </div>
        `;

        // 绑定快捷搜索按钮
        resultsDiv.querySelectorAll('.quick-search-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.getElementById('mainSearchInput').value = btn.dataset.query;
                this.performSearch();
            });
        });
    },

    showSuggestions(query) {
        // TODO: 实现搜索建议
    },

    saveRecentSearch(query) {
        let searches = JSON.parse(localStorage.getItem(Config.storage.recentSearches) || '[]');
        searches = searches.filter(s => s !== query);
        searches.unshift(query);
        searches = searches.slice(0, 10);
        localStorage.setItem(Config.storage.recentSearches, JSON.stringify(searches));
    },

    loadRecentSearches() {
        const searches = JSON.parse(localStorage.getItem(Config.storage.recentSearches) || '[]');
        // 可以在搜索框下方显示最近搜索
    },

    retry() {
        this.performSearch();
    }
};

// 模块初始化函数
window.initSearch = function() {
    SearchModule.init();
};
