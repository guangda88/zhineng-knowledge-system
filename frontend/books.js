import { escapeHtml } from './core.js';

const BOOKS_API = '/api/v2';
let currentSearchType = 'metadata';

function initBooks() {
    const searchInput = document.getElementById('book-search-input');
    const searchBtn = document.getElementById('book-search-btn');
    const categoryFilter = document.getElementById('book-category-filter');
    const dynastyFilter = document.getElementById('book-dynasty-filter');
    const toggleBtns = document.querySelectorAll('.toggle-btn');

    toggleBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            toggleBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentSearchType = btn.dataset.type;

            if (currentSearchType === 'metadata') {
                searchInput.placeholder = '搜索书名、作者...';
            } else {
                searchInput.placeholder = '搜索章节内容...';
            }

            if (searchInput.value.trim()) {
                performBookSearch();
            }
        });
    });

    const doSearch = () => {
        const query = searchInput.value.trim();
        if (!query) {
            alert('请输入搜索关键词');
            return;
        }
        performBookSearch(query, categoryFilter.value, dynastyFilter.value);
    };

    searchBtn.addEventListener('click', doSearch);
    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') doSearch();
    });

    categoryFilter.addEventListener('change', () => {
        if (searchInput.value.trim()) doSearch();
    });

    dynastyFilter.addEventListener('change', () => {
        if (searchInput.value.trim()) doSearch();
    });

    loadBooksList();
}

async function performBookSearch(query, category = '', dynasty = '') {
    const resultsDiv = document.getElementById('book-search-results');
    resultsDiv.innerHTML = '<div class="loading"><div class="spinner"></div><p>搜索中...</p></div>';

    try {
        let url = '';
        if (currentSearchType === 'metadata') {
            const params = new URLSearchParams({ q: query, page: 1, size: 20 });
            if (category) params.append('category', category);
            if (dynasty) params.append('dynasty', dynasty);
            url = `${BOOKS_API}/library/search?${params}`;
        } else {
            const params = new URLSearchParams({ q: query, page: 1, size: 20 });
            if (category) params.append('category', category);
            url = `${BOOKS_API}/library/search/content?${params}`;
        }

        const response = await fetch(url);

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();

        if (data.results.length === 0 || data.total === 0) {
            resultsDiv.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">📚</div>
                    <p>没有找到相关书籍</p>
                    <p class="hint">试试搜索：周易、道德经、论语、黄帝内经</p>
                </div>
            `;
            return;
        }

        resultsDiv.innerHTML = `
            <p class="result-meta">找到 ${data.total || data.results.length} 条结果</p>
            <div class="results-list">
                ${data.results.map(item => currentSearchType === 'metadata'
                    ? createBookCard(item)
                    : createChapterCard(item)).join('')}
            </div>
        `;
    } catch (error) {
        console.error('搜索失败:', error);
        resultsDiv.innerHTML = `
            <div class="error-state">
                <div class="error-icon">⚠️</div>
                <p>搜索失败：${error.message}</p>
                <p class="hint">请检查API服务是否正常运行</p>
            </div>
        `;
    }
}

function createBookCard(book) {
    const categoryTag = book.category ?
        `<span class="tag tag-${book.category}">${book.category}</span>` : '';

    const dynastyTag = book.dynasty ?
        `<span class="tag tag-dynasty">${book.dynasty}</span>` : '';

    return `
        <div class="result-card book-card" onclick="showBookDetail(${book.id})">
            <h3 class="book-title">${book.title}</h3>
            <div class="book-meta">
                <span class="author">👤 ${book.author || '佚名'}</span>
                ${categoryTag}
                ${dynastyTag}
            </div>
            <p class="book-description">${book.description || '暂无简介'}</p>
            <div class="book-stats">
                <span>📄 ${book.total_pages || 0} 页</span>
                <span>👁 ${book.view_count || 0} 次查看</span>
            </div>
        </div>
    `;
}

function createChapterCard(chapter) {
    return `
        <div class="result-card chapter-card" onclick="showChapterDetail(${chapter.book_id}, ${chapter.id})">
            <h3 class="chapter-title">${chapter.title || '无标题'}</h3>
            <p class="book-title">📖 ${chapter.book_title || '未知书籍'}</p>
            <p class="chapter-preview">${chapter.preview || ''}</p>
            <p class="chapter-meta">第${chapter.chapter_num}章 · ${chapter.char_count || 0} 字</p>
        </div>
    `;
}

async function showBookDetail(bookId) {
    try {
        const response = await fetch(`${BOOKS_API}/library/${bookId}`);
        const book = await response.json();

        const modal = document.createElement('div');
        modal.className = 'modal-overlay';
        modal.innerHTML = `
            <div class="modal-content book-detail-modal">
                <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">×</button>
                <h2>${book.title}</h2>
                <div class="detail-meta">
                    <p><strong>作者：</strong>${book.author || '佚名'}</p>
                    <p><strong>分类：</strong>${book.category || '未分类'}</p>
                    <p><strong>朝代：</strong>${book.dynasty || '未知'}</p>
                    <p><strong>年份：</strong>${book.year || '未知'}</p>
                </div>
                <div class="detail-description">
                    <h3>简介</h3>
                    <p>${book.description || '暂无简介'}</p>
                </div>
                <div class="detail-chapters">
                    <h3>目录</h3>
                    ${book.chapters && book.chapters.length > 0 ?
                        `<ul class="chapter-list">
                            ${book.chapters.map(ch => `
                                <li><a href="#" onclick="showChapterDetail(${bookId}, ${ch.id}); return false;">
                                    第${ch.chapter_num}章：${ch.title || '无标题'}
                                </a></li>
                            `).join('')}
                        </ul>` :
                        '<p class="hint">暂无目录</p>'
                    }
                </div>
                <div class="detail-actions">
                    <button onclick="showRelatedBooks(${bookId})">📚 相关推荐</button>
                    <button onclick="this.closest('.modal-overlay').remove()">关闭</button>
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
}

async function showChapterDetail(bookId, chapterId) {
    try {
        const response = await fetch(`${BOOKS_API}/library/${bookId}/chapters/${chapterId}`);
        const chapter = await response.json();

        const modal = document.createElement('div');
        modal.className = 'modal-overlay';
        modal.innerHTML = `
            <div class="modal-content chapter-modal">
                <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">×</button>
                <h2>${chapter.title || '无标题'}</h2>
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
}

async function showRelatedBooks(bookId) {
    try {
        const response = await fetch(`${BOOKS_API}/library/${bookId}/related?top_k=6&threshold=0.5`);
        const books = await response.json();

        if (books.length === 0) {
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
                    ${books.map(book => `
                        <div class="related-book" onclick="showBookDetail(${book.id}); this.closest('.modal-overlay').remove();">
                            <h4>${book.title}</h4>
                            <p>${book.author || '佚名'} · ${book.category || ''}</p>
                            <p class="similarity">相似度：${(book.similarity * 100).toFixed(1)}%</p>
                        </div>
                    `).join('')}
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
}

async function loadBooksList() {
    const resultsDiv = document.getElementById('book-search-results');

    try {
        const response = await fetch(`${BOOKS_API}/library/search?page=1&size=20`);
        const data = await response.json();

        if (data.results.length === 0) {
            resultsDiv.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">📚</div>
                    <p>暂无书籍数据</p>
                    <p class="hint">请先导入书籍数据</p>
                </div>
            `;
            return;
        }

        resultsDiv.innerHTML = `
            <p class="result-meta">共 ${data.total} 本书籍</p>
            <div class="results-list">
                ${data.results.map(book => createBookCard(book)).join('')}
            </div>
        `;
    } catch (error) {
        console.error('加载书籍列表失败:', error);
        resultsDiv.innerHTML = `
            <div class="error-state">
                <div class="error-icon">⚠️</div>
                <p>加载失败：${error.message}</p>
            </div>
        `;
    }
}

export { initBooks, showBookDetail, showChapterDetail, showRelatedBooks };
