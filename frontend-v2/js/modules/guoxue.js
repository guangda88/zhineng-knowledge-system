// 灵知系统 - 国学经典模块
const GuoxueModule = {
    allBooks: [],
    currentBookId: null,

    init() {
        this.bindEvents();
        this.loadStats();
        this.loadBooks();
    },

    bindEvents() {
        const searchInput = document.getElementById('guoxueSearchInput');
        const searchBtn = searchInput.nextElementSibling;

        const doSearch = () => {
            const query = searchInput.value.trim();
            if (query) this.search(query);
        };

        searchBtn.addEventListener('click', doSearch);
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') doSearch();
        });
    },

    async loadStats() {
        try {
            const data = await API.guoxue.getStats();
            const statsDiv = document.getElementById('guoxueStats');
            if (statsDiv) {
                statsDiv.innerHTML = `
                    <span class="stat-badge">📚 ${data.data.book_count} 部典籍</span>
                    <span class="stat-badge">📄 ${Utils.formatNumber(data.data.content_count)} 条内容</span>
                `;
            }
        } catch (error) {
            console.error('加载统计失败:', error);
        }
    },

    async loadBooks() {
        const listDiv = document.getElementById('guoxueBookList');
        listDiv.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

        try {
            const data = await API.guoxue.getBooks({ size: 200 });
            this.allBooks = data.data.results || [];
            this.renderBookList(this.allBooks);
        } catch (error) {
            listDiv.innerHTML = '<p class="text-small">加载失败</p>';
        }
    },

    renderBookList(books) {
        const listDiv = document.getElementById('guoxueBookList');
        listDiv.innerHTML = books.map(book => `
            <div class="guoxue-book-item" data-book-id="${book.book_id}">
                <span class="book-title">${Utils.escapeHtml(book.title)}</span>
                <span class="book-count">${book.content_count}</span>
            </div>
        `).join('');

        // 绑定点击事件
        listDiv.querySelectorAll('.guoxue-book-item').forEach(el => {
            el.addEventListener('click', () => {
                const bookId = parseInt(el.dataset.bookId);
                this.loadChapters(bookId);
            });
        });
    },

    async loadChapters(bookId) {
        const contentDiv = document.getElementById('guoxueContent');
        contentDiv.innerHTML = '<div class="loading"><div class="spinner"></div><p>加载章节...</p></div>';

        try {
            const data = await API.guoxue.getChapters(bookId, { size: 100 });
            const chapters = data.data.results;

            contentDiv.innerHTML = `
                <div class="guoxue-chapters">
                    <h3>${Utils.escapeHtml(data.data.book.title)}</h3>
                    <p class="text-small text-muted">共 ${data.data.total} 条</p>
                    <div class="chapter-list">
                        ${chapters.map(ch => `
                            <div class="chapter-item" data-id="${ch.id}">
                                <span class="chapter-num">第${ch.chapter_id}章</span>
                                <span class="chapter-length">${ch.body_length}字</span>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;

            // 绑定章节点击
            contentDiv.querySelectorAll('.chapter-item').forEach(el => {
                el.addEventListener('click', () => {
                    this.showContent(parseInt(el.dataset.id));
                });
            });
        } catch (error) {
            contentDiv.innerHTML = `<p class="text-small">加载失败：${error.message}</p>`;
        }
    },

    async showContent(contentId) {
        try {
            const data = await API.guoxue.getContent(contentId);
            this.showContentModal(data.data);
        } catch (error) {
            alert('加载内容失败：' + error.message);
        }
    },

    showContentModal(content) {
        const modal = document.getElementById('modalContainer');
        const content = document.getElementById('modalContent');

        content.innerHTML = `
            <button class="modal-close" onclick="closeAllModals()">×</button>
            <h2>第${content.chapter_id}章</h2>
            <p class="text-small text-muted">${content.body_length}字</p>
            <div class="guoxue-body">${Utils.escapeHtml(content.body).replace(/\n/g, '<br>')}</div>
        `;

        modal.classList.add('active');
    },

    async search(query) {
        const contentDiv = document.getElementById('guoxueContent');
        contentDiv.innerHTML = '<div class="loading"><div class="spinner"></div><p>搜索中...</p></div>';

        try {
            const data = await API.guoxue.search(query, { size: 30 });
            const results = data.data.results;

            if (!results.length) {
                contentDiv.innerHTML = `
                    <div class="empty-state">
                        <div class="placeholder-icon">📜</div>
                        <p>没有找到相关内容</p>
                    </div>
                `;
                return;
            }

            contentDiv.innerHTML = `
                <h3>搜索结果 (${data.data.total} 条)</h3>
                <div class="search-results">
                    ${results.map(r => `
                        <div class="search-result-item" data-id="${r.id}">
                            <div class="result-meta">
                                <span>${Utils.escapeHtml(r.book_title)}</span>
                                <span>第${r.chapter_id}章</span>
                            </div>
                            <p class="result-preview">${Utils.escapeHtml(r.body_preview || '').substring(0, 200)}</p>
                        </div>
                    `).join('')}
                </div>
            `;

            contentDiv.querySelectorAll('.search-result-item').forEach(el => {
                el.addEventListener('click', () => {
                    this.showContent(parseInt(el.dataset.id));
                });
            });
        } catch (error) {
            contentDiv.innerHTML = `<p class="text-small">搜索失败：${error.message}</p>`;
        }
    }
};

window.initGuoxue = function() {
    GuoxueModule.init();
};
