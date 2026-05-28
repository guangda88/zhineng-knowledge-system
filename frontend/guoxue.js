import { API_BASE, escapeHtml } from './core.js';

let guoxueAllBooks = [];

function initGuoxue() {
    const searchInput = document.getElementById('guoxue-search-input');
    const searchBtn = document.getElementById('guoxue-search-btn');
    const bookFilter = document.getElementById('guoxue-book-filter');

    const doSearch = () => {
        const q = searchInput.value.trim();
        if (!q) return;
        searchGuoxue(q);
    };

    searchBtn.addEventListener('click', doSearch);
    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') doSearch();
    });

    bookFilter.addEventListener('input', () => {
        const keyword = bookFilter.value.trim().toLowerCase();
        const filtered = keyword
            ? guoxueAllBooks.filter(b => b.title.toLowerCase().includes(keyword))
            : guoxueAllBooks;
        renderGuoxueBookList(filtered);
    });

    loadGuoxueStats();
    loadGuoxueBooks();
}

async function loadGuoxueStats() {
    const statsDiv = document.getElementById('guoxue-stats');
    try {
        const resp = await fetch(`${API_BASE}/guoxue/stats`);
        const json = await resp.json();
        const d = json.data;
        const chars = d.total_chars >= 1e8
            ? (d.total_chars / 1e8).toFixed(1) + '亿'
            : d.total_chars >= 1e4
            ? (d.total_chars / 1e4).toFixed(0) + '万'
            : d.total_chars;
        statsDiv.innerHTML = `
            <span class="stat-badge">📚 ${d.book_count} 部典籍</span>
            <span class="stat-badge">📄 ${d.content_count.toLocaleString()} 条内容</span>
            <span class="stat-badge">📝 ${chars} 字</span>
        `;
    } catch (e) {
        statsDiv.innerHTML = '<span class="stat-badge error">统计数据加载失败</span>';
    }
}

async function loadGuoxueBooks() {
    const listDiv = document.getElementById('guoxue-book-list');
    listDiv.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
    try {
        const resp = await fetch(`${API_BASE}/guoxue/books?size=200`);
        const json = await resp.json();
        guoxueAllBooks = json.data.results || [];
        renderGuoxueBookList(guoxueAllBooks);
    } catch (e) {
        listDiv.innerHTML = '<div class="empty-state"><p>加载失败</p></div>';
    }
}

function renderGuoxueBookList(books) {
    const listDiv = document.getElementById('guoxue-book-list');
    if (!books.length) {
        listDiv.innerHTML = '<div class="empty-state"><p>无匹配典籍</p></div>';
        return;
    }
    listDiv.innerHTML = books.map(b => `
        <div class="guoxue-book-item" data-book-id="${b.book_id}">
            <span class="guoxue-book-title">${escapeHtml(b.title)}</span>
            <span class="guoxue-book-count">${b.content_count}条</span>
        </div>
    `).join('');

    listDiv.querySelectorAll('.guoxue-book-item').forEach(el => {
        el.addEventListener('click', () => {
            listDiv.querySelectorAll('.guoxue-book-item').forEach(x => x.classList.remove('active'));
            el.classList.add('active');
            loadGuoxueChapters(parseInt(el.dataset.bookId));
        });
    });
}

async function loadGuoxueChapters(bookId, page = 1) {
    const resultsDiv = document.getElementById('guoxue-results');
    const isNewLoad = (page === 1);
    if (isNewLoad) {
        resultsDiv.innerHTML = '<div class="loading"><div class="spinner"></div><p>加载章节...</p></div>';
    }

    try {
        const resp = await fetch(`${API_BASE}/guoxue/books/${bookId}/chapters?size=100&page=${page}`);
        const json = await resp.json();
        const d = json.data;
        const bookTitle = d.book.title;
        const totalPages = Math.ceil(d.total / 100);
        const hasMore = page < totalPages;

        if (isNewLoad) {
            resultsDiv.innerHTML = `
                <div class="guoxue-results-header">
                    <h3>${escapeHtml(bookTitle)}</h3>
                    <span class="result-meta">共 ${d.total} 条内容</span>
                </div>
                <div class="guoxue-chapter-list"></div>
                <div class="guoxue-chapter-pagination"></div>
            `;
        }

        const chapterList = resultsDiv.querySelector('.guoxue-chapter-list');
        const itemHtml = d.results.map(r => `
            <div class="guoxue-chapter-item" data-content-id="${r.id}">
                <span class="chapter-label">第${r.chapter_id}章</span>
                <span class="chapter-length">${r.body_length}字</span>
            </div>
        `).join('');

        if (isNewLoad) {
            chapterList.innerHTML = itemHtml;
        } else {
            chapterList.insertAdjacentHTML('beforeend', itemHtml);
        }

        const paginationDiv = resultsDiv.querySelector('.guoxue-chapter-pagination');
        if (hasMore) {
            paginationDiv.innerHTML = `
                <div style="text-align:center;padding:12px;">
                    <button class="btn btn-secondary guoxue-load-more-btn" data-book-id="${bookId}" data-page="${page + 1}">
                        加载更多（${page}/${totalPages}页）
                    </button>
                </div>
            `;
            paginationDiv.querySelector('.guoxue-load-more-btn').addEventListener('click', function() {
                this.disabled = true;
                this.textContent = '加载中...';
                loadGuoxueChapters(parseInt(this.dataset.bookId), parseInt(this.dataset.page));
            });
        } else if (totalPages > 1) {
            paginationDiv.innerHTML = `<div style="text-align:center;padding:8px;color:#666;">已加载全部 ${d.total} 条</div>`;
        } else {
            paginationDiv.innerHTML = '';
        }

        chapterList.querySelectorAll('.guoxue-chapter-item:not([data-bound])').forEach(el => {
            el.setAttribute('data-bound', '1');
            el.addEventListener('click', () => {
                loadGuoxueContent(parseInt(el.dataset.contentId));
            });
        });
    } catch (e) {
        resultsDiv.innerHTML = `<div class="error-state"><p>加载失败：${escapeHtml(e.message)}</p></div>`;
    }
}

async function loadGuoxueContent(contentId) {
    const modal = document.getElementById('modal-overlay');
    const content = document.getElementById('modal-content');
    content.innerHTML = '<div class="loading"><div class="spinner"></div><p>加载正文...</p></div>';
    modal.classList.add('active');

    try {
        const resp = await fetch(`${API_BASE}/guoxue/content/${contentId}`);
        const json = await resp.json();
        const d = json.data;
        const bodyHtml = escapeHtml(d.body).replace(/\n/g, '<br>');

        content.innerHTML = `
            <button class="modal-close" onclick="document.getElementById('modal-overlay').classList.remove('active')">×</button>
            <h2>第${d.chapter_id}章 <span style="font-size:0.85em;color:#666">(${d.body_length.toLocaleString()}字)</span></h2>
            <div class="guoxue-content-body">${bodyHtml}</div>
        `;
    } catch (e) {
        content.innerHTML = `<div class="error-state"><p>加载失败：${escapeHtml(e.message)}</p></div>`;
    }
}

async function searchGuoxue(query, bookId = null) {
    const resultsDiv = document.getElementById('guoxue-results');
    resultsDiv.innerHTML = '<div class="loading"><div class="spinner"></div><p>搜索中...</p></div>';

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000);

    try {
        const params = new URLSearchParams({ q: query, size: 30 });
        if (bookId) params.append('book_id', bookId);
        const resp = await fetch(`${API_BASE}/guoxue/search?${params}`, { signal: controller.signal });
        clearTimeout(timeoutId);
        const json = await resp.json();
        const d = json.data;

        if (!d.results.length) {
            resultsDiv.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">📜</div>
                    <p>没有找到相关内容</p>
                    <p>试试：论语、道德经、史记、黄帝内经</p>
                </div>
            `;
            return;
        }

        resultsDiv.innerHTML = `
            <div class="guoxue-results-header">
                <h3>搜索结果</h3>
                <span class="result-meta">找到 ${d.total} 条</span>
            </div>
            <div class="guoxue-search-list">
                ${d.results.map(r => `
                    <div class="guoxue-search-item" data-content-id="${r.id}">
                        <div class="guoxue-search-meta">
                            <span class="book-label">${escapeHtml(r.book_title || '未知')}</span>
                            <span>第${r.chapter_id}章</span>
                            <span>${r.body_length}字</span>
                        </div>
                        <div class="guoxue-search-preview">${escapeHtml(r.body_preview || '').substring(0, 300)}</div>
                    </div>
                `).join('')}
            </div>
        `;

        resultsDiv.querySelectorAll('.guoxue-search-item').forEach(el => {
            el.addEventListener('click', () => {
                loadGuoxueContent(parseInt(el.dataset.contentId));
            });
        });
    } catch (e) {
        clearTimeout(timeoutId);
        if (e.name === 'AbortError') {
            resultsDiv.innerHTML = `
                <div class="error-state">
                    <div class="error-state-icon">⏱️</div>
                    <p>搜索超时，数据量较大，请尝试：</p>
                    <ul style="text-align:left;margin:10px 0;padding-left:20px;">
                        <li>使用更具体的关键词</li>
                        <li>先选择一部典籍再搜索</li>
                        <li>在左侧典籍列表中浏览内容</li>
                    </ul>
                </div>`;
        } else {
            resultsDiv.innerHTML = `<div class="error-state"><p>搜索失败：${escapeHtml(e.message)}</p></div>`;
        }
    }
}

export { initGuoxue, loadGuoxueStats, loadGuoxueBooks };
