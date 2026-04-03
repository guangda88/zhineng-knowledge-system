// 灵知系统 - 书目检索模块
const SysbooksModule = {
    init() {
        this.bindEvents();
        this.loadStats();
    },

    bindEvents() {
        const searchInput = document.getElementById('sysbooksSearchInput');
        const domainFilter = document.getElementById('sysbooksDomainFilter');
        const extFilter = document.getElementById('sysbooksExtFilter');

        const doSearch = () => {
            this.search(searchInput.value.trim(), {
                domain: domainFilter.value,
                extension: extFilter.value
            });
        };

        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') doSearch();
        });

        domainFilter.addEventListener('change', doSearch);
        extFilter.addEventListener('change', doSearch);
    },

    async loadStats() {
        try {
            const data = await API.sysbooks.getStats();
            // 更新统计显示
        } catch (error) {
            console.error('加载统计失败:', error);
        }
    },

    async search(query, filters = {}) {
        // 实现搜索逻辑
    }
};

window.initSysbooks = function() {
    SysbooksModule.init();
};
