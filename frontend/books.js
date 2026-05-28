import { API_BASE, escapeHtml } from './core.js';

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
                performBookSearch(searchInput.value.trim());
            }
        });
    });

    const doSearch = () => {
        const query = searchInput.value.trim();
        if (!query) {
            alert('请输入搜索关键词');
            return;
        }
        performBookSearch(query);
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

async function performBookSearch(query) {
    const resultsDiv = document.getElementById('book-search-results');
    resultsDiv.innerHTML = '<div class="loading"><div class="spinner"></div><p>搜索中...</p></div>';

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000);

    try {
        let url;
        if (currentSearchType === 'metadata') {
            const params = new URLSearchParams({ size: 50 });
            url = `${API_BASE}/guoxue/books?${params}`;
        } else {
            const params = new URLSearchParams({ q: query, size: 20 });
            url = `${API_BASE}/guoxue/search?${params}`;
        }

        const response = await fetch(url, { signal: controller.signal });
        clearTimeout(timeoutId);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const json = await response.json();
        const data = json.data || json;

        if (currentSearchType === 'metadata') {
            const results = (data.results || []).filter(b =>
                b.title.toLowerCase().includes(query.toLowerCase())
            );
            if (!results.length) {
                resultsDiv.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-state-icon">📚</div>
                        <p>没有找到相关书籍</p>
                        <p class="hint">试试搜索：周易、道德经、论语、黄帝内经</p>
                    </div>`;
                return;
            }
            resultsDiv.innerHTML = `
                <p class="result-meta">找到 ${results.length} 本相关典籍</p>
                <div class="results-list">
                    ${results.map(b => createBookCard(b)).join('')}
                </div>`;
        } else {
            if (!data.results || !data.results.length) {
                resultsDiv.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-state-icon">📚</div>
                        <p>没有找到相关内容</p>
                        <p class="hint">试试搜索：八段锦、气功、道德经</p>
                    </div>`;
                return;
            }
            resultsDiv.innerHTML = `
                <p class="result-meta">找到 ${data.total} 条结果</p>
                <div class="results-list">
                    ${data.results.map(r => createContentCard(r)).join('')}
                </div>`;

            resultsDiv.querySelectorAll('.content-card').forEach(el => {
                el.addEventListener('click', () => {
                    showContentDetail(parseInt(el.dataset.contentId));
                });
            });
        }
    } catch (error) {
        clearTimeout(timeoutId);
        if (error.name === 'AbortError') {
            resultsDiv.innerHTML = `
                <div class="error-state">
                    <div class="error-state-icon">⏱️</div>
                    <p>搜索超时，数据量较大，请尝试：</p>
                    <ul style="text-align:left;margin:10px 0;padding-left:20px;">
                        <li>使用更具体的关键词</li>
                        <li>切换到书籍搜索模式</li>
                    </ul>
                </div>`;
        } else {
            resultsDiv.innerHTML = `
                <div class="error-state">
                    <p>搜索失败：${escapeHtml(error.message)}</p>
                </div>`;
        }
    }
}

function createBookCard(book) {
    return `
        <div class="result-card book-card" data-book-id="${book.book_id || book.id}">
            <h3 class="book-title">${escapeHtml(book.title)}</h3>
            <p class="book-description">${escapeHtml(book.description || '暂无简介')}</p>
            <div class="book-stats">
                <span>📄 ${book.content_count || 0} 条内容</span>
            </div>
        </div>`;
}

function createContentCard(item) {
    return `
        <div class="result-card content-card" data-content-id="${item.id}">
            <h3 class="chapter-title">第${item.chapter_id}章</h3>
            <p class="book-title">📖 ${escapeHtml(item.book_title || '未知')}</p>
            <p class="chapter-preview">${escapeHtml(item.body_preview || '').substring(0, 200)}</p>
            <p class="chapter-meta">${item.body_length || 0} 字</p>
        </div>`;
}

async function showContentDetail(contentId) {
    const modal = document.getElementById('modal-overlay');
    const content = document.getElementById('modal-content');
    content.innerHTML = '<div class="loading"><div class="spinner"></div><p>加载正文...</p></div>';
    modal.classList.add('active');

    try {
        const response = await fetch(`${API_BASE}/guoxue/content/${contentId}`);
        const json = await response.json();
        const d = json.data;
        const bodyHtml = escapeHtml(d.body).replace(/\n/g, '<br>');

        content.innerHTML = `
            <button class="modal-close" onclick="document.getElementById('modal-overlay').classList.remove('active')">×</button>
            <h2>第${d.chapter_id}章 <span style="font-size:0.85em;color:#666">(${d.body_length.toLocaleString()}字)</span></h2>
            <div class="guoxue-content-body">${bodyHtml}</div>`;
    } catch (error) {
        content.innerHTML = `<div class="error-state"><p>加载失败：${escapeHtml(error.message)}</p></div>`;
    }
}

async function showBookDetail(bookId) {
    const modal = document.getElementById('modal-overlay');
    const content = document.getElementById('modal-content');
    content.innerHTML = '<div class="loading"><div class="spinner"></div><p>加载章节...</p></div>';
    modal.classList.add('active');

    try {
        const response = await fetch(`${API_BASE}/guoxue/books/${bookId}/chapters?size=200`);
        const json = await response.json();
        const d = json.data;
        const bookTitle = d.book.title;

        content.innerHTML = `
            <button class="modal-close" onclick="document.getElementById('modal-overlay').classList.remove('active')">×</button>
            <h2>${escapeHtml(bookTitle)}</h2>
            <p class="result-meta">共 ${d.total} 条内容</p>
            <div class="guoxue-chapter-list">
                ${d.results.map(ch => `
                    <div class="guoxue-chapter-item" data-content-id="${ch.id}">
                        <span class="chapter-label">第${ch.chapter_id}章</span>
                        <span class="chapter-length">${ch.body_length}字</span>
                    </div>
                `).join('')}
            </div>`;

        content.querySelectorAll('.guoxue-chapter-item').forEach(el => {
            el.addEventListener('click', () => {
                const cid = parseInt(el.dataset.contentId);
                fetch(`${API_BASE}/guoxue/content/${cid}`)
                    .then(r => r.json())
                    .then(j => {
                        const dd = j.data;
                        const bodyHtml = escapeHtml(dd.body).replace(/\n/g, '<br>');
                        const chapterList = content.querySelector('.guoxue-chapter-list');
                        if (chapterList) {
                            chapterList.innerHTML = `
                                <div style="margin-bottom:10px;">
                                    <button onclick="showBookDetail(${bookId})" class="btn btn-secondary" style="padding:6px 12px;">← 返回目录</button>
                                    <span style="margin-left:10px;">第${dd.chapter_id}章 (${dd.body_length.toLocaleString()}字)</span>
                                </div>
                                <div class="guoxue-content-body" style="max-height:60vh;overflow-y:auto;">${bodyHtml}</div>`;
                        }
                    });
            });
        });
    } catch (error) {
        content.innerHTML = `<div class="error-state"><p>加载失败：${escapeHtml(error.message)}</p></div>`;
    }
}

async function loadBooksList() {
    const resultsDiv = document.getElementById('book-search-results');

    try {
        const response = await fetch(`${API_BASE}/guoxue/books?size=50`);
        const json = await response.json();
        const data = json.data || json;
        const results = data.results || [];

        if (!results.length) {
            resultsDiv.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">📚</div>
                    <p>暂无书籍数据</p>
                </div>`;
            return;
        }

        resultsDiv.innerHTML = `
            <p class="result-meta">共 ${results.length} 部典籍</p>
            <div class="results-list">
                ${results.map(b => createBookCard(b)).join('')}
            </div>`;

        resultsDiv.querySelectorAll('.book-card').forEach(el => {
            el.addEventListener('click', () => {
                const bookId = parseInt(el.dataset.bookId);
                if (bookId) showBookDetail(bookId);
            });
        });
    } catch (error) {
        console.error('加载书籍列表失败:', error);
        resultsDiv.innerHTML = `
            <div class="error-state">
                <div class="error-icon">⚠️</div>
                <p>加载失败：${escapeHtml(error.message)}</p>
            </div>`;
    }
}

export { initBooks, showBookDetail };
