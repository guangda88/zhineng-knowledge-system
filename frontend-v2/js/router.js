// 灵知系统 - 路由管理
const Router = {
    currentModule: 'search',
    history: [],

    init() {
        // 监听哈希变化
        window.addEventListener('hashchange', () => this.handleRoute());
        window.addEventListener('load', () => this.handleRoute());

        // 监听导航点击
        document.addEventListener('click', (e) => {
            const navItem = e.target.closest('.nav-item');
            if (navItem && navItem.dataset.module) {
                e.preventDefault();
                this.navigate(navItem.dataset.module);
            }
        });
    },

    handleRoute() {
        const hash = window.location.hash.slice(1) || 'search';
        const [module, ...params] = hash.split('/');

        if (Config.routes.modules.includes(module)) {
            this.showModule(module, params);
        }
    },

    navigate(module, params = []) {
        // 保存历史
        this.history.push(this.currentModule);

        // 更新哈希
        window.location.hash = module + (params.length ? '/' + params.join('/') : '');
    },

    showModule(module, params = []) {
        // 隐藏所有模块
        document.querySelectorAll('.module').forEach(el => {
            el.classList.remove('active');
        });

        // 显示目标模块
        const targetModule = document.getElementById(`module-${module}`);
        if (targetModule) {
            targetModule.classList.add('active');
            this.currentModule = module;

            // 更新导航状态
            this.updateNav(module);

            // 更新面包屑
            this.updateBreadcrumb(module);

            // 触发模块初始化
            this.initModule(module, params);
        }
    },

    updateNav(module) {
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.toggle('active', item.dataset.module === module);
        });
    },

    updateBreadcrumb(module) {
        const breadcrumb = document.getElementById('breadcrumb');
        const moduleName = this.getModuleName(module);
        breadcrumb.innerHTML = `
            <span class="breadcrumb-item">首页</span>
            <span class="breadcrumb-separator">/</span>
            <span class="breadcrumb-item">${moduleName}</span>
        `;
    },

    getModuleName(module) {
        const names = {
            'search': '智能搜索',
            'library': '知识库',
            'ai-assistant': 'AI助手',
            'reasoning': '深度推理',
            'guoxue': '国学经典',
            'guji': '古籍文档',
            'sysbooks': '书目检索',
            'annotation': '标注系统',
            'audio': '音频处理',
            'import': '数据导入',
            'analytics': '数据分析',
            'settings': '系统设置'
        };
        return names[module] || module;
    },

    initModule(module, params) {
        // 调用模块初始化函数
        const moduleInit = window[`init${module.charAt(0).toUpperCase() + module.slice(1)}`];
        if (typeof moduleInit === 'function') {
            moduleInit(params);
        }
    },

    back() {
        if (this.history.length > 0) {
            const prev = this.history.pop();
            this.navigate(prev);
        }
    }
};

// 导出路由
if (typeof module !== 'undefined' && module.exports) {
    module.exports = Router;
}
