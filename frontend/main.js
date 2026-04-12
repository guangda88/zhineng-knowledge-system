import { initSearch } from './search.js';
import { initDocuments, loadDocuments } from './documents.js';
import { initChat, loadStats } from './chat.js';
import { initBooks, showBookDetail, showChapterDetail, showRelatedBooks } from './books.js';
import { initGuoxue, loadGuoxueStats, loadGuoxueBooks } from './guoxue.js';
import { initSysbooks, loadSysbooksStats } from './sysbooks.js';
import { initReasoning } from './reasoning.js';
import { submitFeedback, submitChatFeedback } from './feedback.js';

function initTabs() {
    const tabs = document.querySelectorAll('.tab');
    const contents = document.querySelectorAll('.tab-content');

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const targetTab = tab.dataset.tab;

            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            contents.forEach(content => {
                content.classList.remove('active');
                if (content.id === `${targetTab}-section`) {
                    content.classList.add('active');
                }
            });

            if (targetTab === 'documents') {
                loadDocuments();
            } else if (targetTab === 'guoxue') {
                loadGuoxueStats();
                loadGuoxueBooks();
            } else if (targetTab === 'sysbooks') {
                loadSysbooksStats();
            }
        });
    });
}

window.submitFeedback = submitFeedback;
window.submitChatFeedback = submitChatFeedback;
window.showBookDetail = showBookDetail;
window.showChapterDetail = showChapterDetail;
window.showRelatedBooks = showRelatedBooks;

document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initSearch();
    initDocuments();
    initBooks();
    initChat();
    initReasoning();
    initGuoxue();
    initSysbooks();
    loadStats();
});
