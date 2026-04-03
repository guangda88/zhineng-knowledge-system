// 灵知系统 - 古籍文档模块
const GujiModule = {
    init() {
        this.bindEvents();
        this.loadStats();
    },

    bindEvents() {
        const searchInput = document.getElementById('gujiSearchInput');
        const collectionFilter = document.getElementById('gujiCollectionFilter');

        const doSearch = () => {
            const query = searchInput.value.trim();
            const collection = collectionFilter.value;
            this.search(query, { collection });
        };

        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') doSearch();
        });

        collectionFilter.addEventListener('change', doSearch);
    },

    async loadStats() {
        try {
            const data = await API.guji.getStats();
            // 更新统计显示
        } catch (error) {
            console.error('加载统计失败:', error);
        }
    },

    async search(query, filters = {}) {
        const resultsDiv = document.getElementById('gujiResults');
        resultsDiv.innerHTML = '<div class="loading"><div class="spinner"></div><p>搜索中...</p></div>';

        try {
            const data = await API.guji.search(query, filters);
            this.displayResults(data);
        } catch (error) {
            resultsDiv.innerHTML = `<p class="text-small">搜索失败：${error.message}</p>`;
        }
    },

    displayResults(data) {
        const resultsDiv = document.getElementById('gujiResults');
        // 显示结果
    }
};

window.initGuji = function() {
    GujiModule.init();
};
