// 灵知系统 - 知识库模块（恢复v2 Library API）
const LibraryModule = {
    currentCategory: 'all',
    currentSearchType: 'metadata',
    initialized: false,
    API_BASE: '/api/v2',

    init() {
        if (this.initialized) return;
        this.initialized = true;
        this.bindEvents();
    },

    bindEvents() {
        const searchInput = document.getElementById('librarySearchInput');
        const searchBtn = document.getElementById('librarySearchBtn');
        const categoryFilter = document.getElementById('libraryCategoryFilter');
        const dynastyFilter = document.getElementById('libraryDynastyFilter');
        const toggleBtns = document.querySelectorAll('#librarySearchTypeToggle .toggle-btn');

        toggleBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                toggleBtns.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.currentSearchType = btn.dataset.type;
                if (this.currentSearchType === 'metadata') {
                    searchInput.placeholder = '搜索书名、作者...';
                } else {
                    searchInput.placeholder = '搜索章节内容...';
                }
                if (searchInput.value.trim()) {
                    this.performSearch();
                }
            });
        });

        const doSearch = () => {
            const query = searchInput.value.trim();
            if (!query) {
                alert('请输入搜索关键词');
                return;
            }
            this.performSearch();
        };

        searchBtn?.addEventListener('click', doSearch);
        searchInput?.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') doSearch();
        });

        categoryFilter?.addEventListener('change', () => {
            if (searchInput?.value.trim()) doSearch();
        });

        dynastyFilter?.addEventListener('change', () => {
            if (searchInput?.value.trim()) doSearch();
        });

        document.querySelectorAll('.tree-item').forEach(item => {
            item.addEventListener('click', () => {
                const category = item.dataset.category;
                this.currentCategory = category;
                this.updateTreeSelection(item);
                if (category !== 'all') {
                    document.getElementById('libraryCategoryFilter').value = category;
                } else {
                    document.getElementById('libraryCategoryFilter').value = '';
                }
                const searchInput = document.getElementById('librarySearchInput');
                if (searchInput.value.trim()) {
                    this.performSearch();
                }
            });
        });

        document.getElementById('refreshLibraryBtn')?.addEventListener('click', () => {
            const searchInput = document.getElementById('librarySearchInput');
            if (searchInput?.value.trim()) {
                this.performSearch();
            }
        });

        document.getElementById('addDocumentBtn')?.addEventListener('click', () => {
            this.showAddDocumentModal();
        });
    },

    async performSearch() {
        const resultsDiv = document.getElementById('libraryResults');
        const searchInput = document.getElementById('librarySearchInput');
        const categoryFilter = document.getElementById('libraryCategoryFilter');
        const dynastyFilter = document.getElementById('libraryDynastyFilter');
        const query = searchInput.value.trim();

        if (!query) return;

        resultsDiv.innerHTML = '<div class="loading"><div class="spinner"></div><p>搜索中...</p></div>';

        try {
            const category = categoryFilter?.value || '';
            const dynasty = dynastyFilter?.value || '';
            const params = new URLSearchParams({ q: query, page: 1, size: 20 });
            if (category) params.append('category', category);
            if (dynasty) params.append('dynasty', dynasty);

            let url;
            if (this.currentSearchType === 'metadata') {
                url = `${this.API_BASE}/library/search?${params}`;
            } else {
                url = `${this.API_BASE}/library/search/content?${params}`;
            }

            const response = await fetch(url);
            if (!response.ok) throw new Error(`HTTP ${response.status}: ${response.statusText}`);

            const data = await response.json();

            if (!data.results || data.results.length === 0) {
                resultsDiv.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-state-icon">📚</div>
                        <p>没有找到相关书籍</p>
                        <p class="hint">试试搜索：周易、道德经、论语、黄帝内经</p>
                    </div>
                `;
                return;
            }

            const statsDiv = document.getElementById('libraryStats');
            if (statsDiv) {
                statsDiv.innerHTML = `<span class="stat-item">找到 ${data.total || data.results.length} 条结果</span>`;
            }

            resultsDiv.innerHTML = `
                <p class="result-meta">找到 ${data.total || data.results.length} 条结果</p>
                <div class="results-list">
                    ${data.results.map(item => this.currentSearchType === 'metadata'
                        ? this.createBookCard(item)
                        : this.createChapterCard(item)).join('')}
                </div>
            `;
        } catch (error) {
            console.error('搜索失败:', error);
            resultsDiv.innerHTML = `
                <div class="error-state">
                    <div class="error-icon">⚠️</div>
                    <p>搜索失败：${Utils.escapeHtml(error.message)}</p>
                    <p class="hint">请检查API服务是否正常运行</p>
                </div>
            `;
        }
    },

    createBookCard(book) {
        const categoryTag = book.category ?
            `<span class="tag">${Utils.escapeHtml(book.category)}</span>` : '';
        const dynastyTag = book.dynasty ?
            `<span class="tag">${Utils.escapeHtml(book.dynasty)}</span>` : '';
        const id = typeof book.id === 'number' ? book.id : `'${Utils.escapeHtml(String(book.id))}'`;

        return `
            <div class="result-card book-card" style="cursor:pointer" onclick="LibraryModule.showBookDetail(${id})">
                <h3>${Utils.escapeHtml(book.title)}</h3>
                <div class="book-meta">
                    <span>👤 ${Utils.escapeHtml(book.author || '佚名')}</span>
                    ${categoryTag}
                    ${dynastyTag}
                </div>
                <p class="book-description">${Utils.escapeHtml(book.description || '暂无简介')}</p>
                <div class="book-stats">
                    <span>📄 ${book.total_pages || 0} 页</span>
                    <span>👁 ${book.view_count || 0} 次查看</span>
                </div>
            </div>
        `;
    },

    createChapterCard(chapter) {
        const bookId = typeof chapter.book_id === 'number' ? chapter.book_id : `'${Utils.escapeHtml(String(chapter.book_id))}'`;
        const chId = typeof chapter.id === 'number' ? chapter.id : `'${Utils.escapeHtml(String(chapter.id))}'`;

        return `
            <div class="result-card chapter-card" style="cursor:pointer" onclick="LibraryModule.showChapterDetail(${bookId}, ${chId})">
                <h3>${Utils.escapeHtml(chapter.title || '无标题')}</h3>
                <p>📖 ${Utils.escapeHtml(chapter.book_title || '未知书籍')}</p>
                <p>${Utils.escapeHtml(chapter.preview || '')}</p>
                <p class="chapter-meta">第${chapter.chapter_num}章 · ${chapter.char_count || 0} 字</p>
            </div>
        `;
    },

    async showBookDetail(bookId) {
        try {
            const response = await fetch(`${this.API_BASE}/library/${bookId}`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const book = await response.json();

            const id = typeof bookId === 'number' ? bookId : `'${Utils.escapeHtml(String(bookId))}'`;
            const modal = document.createElement('div');
            modal.className = 'modal-overlay';
            modal.innerHTML = `
                <div class="modal-content book-detail-modal">
                    <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">×</button>
                    <h2>${Utils.escapeHtml(book.title)}</h2>
                    <div class="detail-meta">
                        <p><strong>作者：</strong>${Utils.escapeHtml(book.author || '佚名')}</p>
                        <p><strong>分类：</strong>${Utils.escapeHtml(book.category || '未分类')}</p>
                        <p><strong>朝代：</strong>${Utils.escapeHtml(book.dynasty || '未知')}</p>
                        <p><strong>年份：</strong>${Utils.escapeHtml(book.year || '未知')}</p>
                    </div>
                    <div class="detail-description">
                        <h3>简介</h3>
                        <p>${Utils.escapeHtml(book.description || '暂无简介')}</p>
                    </div>
                    <div class="detail-chapters">
                        <h3>目录</h3>
                        ${book.chapters && book.chapters.length > 0 ?
                            `<ul class="chapter-list">
                                ${book.chapters.map(ch => {
                                    const chId = typeof ch.id === 'number' ? ch.id : `'${Utils.escapeHtml(String(ch.id))}'`;
                                    return `<li><a href="#" onclick="LibraryModule.showChapterDetail(${id}, ${chId}); return false;">
                                        第${ch.chapter_num}章：${Utils.escapeHtml(ch.title || '无标题')}
                                    </a></li>`;
                                }).join('')}
                            </ul>` :
                            '<p class="hint">暂无目录</p>'
                        }
                    </div>
                    <div class="detail-actions" style="display:flex;gap:8px;margin-top:16px;">
                        <button class="btn btn-primary" onclick="LibraryModule.showRelatedBooks(${id})">📚 相关推荐</button>
                        <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">关闭</button>
                    </div>
                </div>
            `;

            document.body.appendChild(modal);
            modal.addEventListener('click', (e) => {
                if (e.target === modal) modal.remove();
            });
        } catch (error) {
            console.error('获取书籍详情失败:', error);
            alert('获取书籍详情失败：' + error.message);
        }
    },

    async showChapterDetail(bookId, chapterId) {
        try {
            const response = await fetch(`${this.API_BASE}/library/${bookId}/chapters/${chapterId}`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const chapter = await response.json();

            const modal = document.createElement('div');
            modal.className = 'modal-overlay';
            modal.innerHTML = `
                <div class="modal-content chapter-modal">
                    <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">×</button>
                    <h2>${Utils.escapeHtml(chapter.title || '无标题')}</h2>
                    <p class="chapter-meta">第${chapter.chapter_num}章 · ${chapter.char_count || 0} 字</p>
                    <div class="chapter-content">
                        ${chapter.content || '内容暂无'}
                    </div>
                </div>
            `;

            document.body.appendChild(modal);
            modal.addEventListener('click', (e) => {
                if (e.target === modal) modal.remove();
            });
        } catch (error) {
            console.error('获取章节失败:', error);
            alert('获取章节失败：' + error.message);
        }
    },

    async showRelatedBooks(bookId) {
        try {
            const response = await fetch(`${this.API_BASE}/library/${bookId}/related?top_k=6&threshold=0.5`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const books = await response.json();

            if (!books || books.length === 0) {
                alert('暂无相关书籍');
                return;
            }

            const modal = document.createElement('div');
            modal.className = 'modal-overlay';
            modal.innerHTML = `
                <div class="modal-content related-modal">
                    <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">×</button>
                    <h2>相关推荐</h2>
                    <div class="related-books-list">
                        ${books.map(book => {
                            const id = typeof book.id === 'number' ? book.id : `'${Utils.escapeHtml(String(book.id))}'`;
                            return `
                                <div class="related-book" style="cursor:pointer;padding:12px;border:1px solid var(--border-color);border-radius:8px;margin-bottom:8px;" onclick="LibraryModule.showBookDetail(${id}); this.closest('.modal-overlay').remove();">
                                    <h4>${Utils.escapeHtml(book.title)}</h4>
                                    <p>${Utils.escapeHtml(book.author || '佚名')} · ${Utils.escapeHtml(book.category || '')}</p>
                                    <p style="color:var(--text-secondary);font-size:12px;">相似度：${(book.similarity * 100).toFixed(1)}%</p>
                                </div>
                            `;
                        }).join('')}
                    </div>
                </div>
            `;

            document.body.appendChild(modal);
            modal.addEventListener('click', (e) => {
                if (e.target === modal) modal.remove();
            });
        } catch (error) {
            console.error('获取相关书籍失败:', error);
            alert('获取相关书籍失败：' + error.message);
        }
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
                this.performSearch();
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
