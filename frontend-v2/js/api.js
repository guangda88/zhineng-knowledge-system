// 灵知系统 - API 统一调用层
const API = {
    // 基础请求方法
    async request(url, options = {}) {
        const {
            method = 'GET',
            headers = {},
            body = null,
            timeout = Config.api.timeout,
            retries = Config.api.retryAttempts
        } = options;

        let lastError;
        for (let i = 0; i < retries; i++) {
            try {
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), timeout);

                const config = {
                    method,
                    headers: {
                        'Content-Type': 'application/json',
                        ...headers
                    }
                };

                if (body) {
                    config.body = JSON.stringify(body);
                }

                const response = await fetch(url, {
                    ...config,
                    signal: controller.signal
                });

                clearTimeout(timeoutId);

                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }

                return await response.json();
            } catch (error) {
                lastError = error;
                if (i < retries - 1) {
                    await new Promise(resolve => setTimeout(resolve, Config.api.retryDelay));
                }
            }
        }

        throw lastError;
    },

    // 搜索 API
    search: {
        async semantic(query, options = {}) {
            const params = new URLSearchParams({ q: query, ...options });
            return API.request(`${Config.api.baseURL}/search?${params}`);
        },

        async hybrid(query, options = {}) {
            const params = new URLSearchParams({ q: query, mode: 'hybrid', ...options });
            return API.request(`${Config.api.baseURL}/search/hybrid?${params}`);
        }
    },

    // 文档 API
    documents: {
        async list(options = {}) {
            const params = new URLSearchParams(options);
            return API.request(`${Config.api.baseURL}/documents?${params}`);
        },

        async get(id) {
            return API.request(`${Config.api.baseURL}/documents/${id}`);
        },

        async create(data) {
            return API.request(`${Config.api.baseURL}/documents`, {
                method: 'POST',
                body: data
            });
        },

        async update(id, data) {
            return API.request(`${Config.api.baseURL}/documents/${id}`, {
                method: 'PUT',
                body: data
            });
        },

        async delete(id) {
            return API.request(`${Config.api.baseURL}/documents/${id}`, {
                method: 'DELETE'
            });
        }
    },

    // 书籍 API (v2)
    library: {
        async search(query, options = {}) {
            const params = new URLSearchParams({ q: query, ...options });
            return API.request(`${Config.api.apiV2}/library/search?${params}`);
        },

        async searchContent(query, options = {}) {
            const params = new URLSearchParams({ q: query, ...options });
            return API.request(`${Config.api.apiV2}/library/search/content?${params}`);
        },

        async get(id) {
            return API.request(`${Config.api.apiV2}/library/${id}`);
        },

        async getChapters(bookId, options = {}) {
            const params = new URLSearchParams(options);
            return API.request(`${Config.api.apiV2}/library/${bookId}/chapters?${params}`);
        },

        async getChapter(bookId, chapterId) {
            return API.request(`${Config.api.apiV2}/library/${bookId}/chapters/${chapterId}`);
        },

        async getRelated(id, options = {}) {
            const params = new URLSearchParams(options);
            return API.request(`${Config.api.apiV2}/library/${id}/related?${params}`);
        }
    },

    // 国学 API
    guoxue: {
        async getStats() {
            return API.request(`${Config.api.baseURL}/guoxue/stats`);
        },

        async getBooks(options = {}) {
            const params = new URLSearchParams(options);
            return API.request(`${Config.api.baseURL}/guoxue/books?${params}`);
        },

        async getChapters(bookId, options = {}) {
            const params = new URLSearchParams(options);
            return API.request(`${Config.api.baseURL}/guoxue/books/${bookId}/chapters?${params}`);
        },

        async getContent(id) {
            return API.request(`${Config.api.baseURL}/guoxue/content/${id}`);
        },

        async search(query, options = {}) {
            const params = new URLSearchParams({ q: query, ...options });
            return API.request(`${Config.api.baseURL}/guoxue/search?${params}`);
        }
    },

    // 古档文档 API
    guji: {
        async getStats() {
            return API.request(`${Config.api.baseURL}/guji/stats`);
        },

        async search(query, options = {}) {
            const params = new URLSearchParams({ q: query, ...options });
            return API.request(`${Config.api.baseURL}/guji/search?${params}`);
        },

        async getScanFiles(options = {}) {
            const params = new URLSearchParams(options);
            return API.request(`${Config.api.baseURL}/guji/scans?${params}`);
        },

        async getDocumentInfo(scanId) {
            return API.request(`${Config.api.baseURL}/guji/scans/${scanId}`);
        }
    },

    // 系统书目 API
    sysbooks: {
        async getStats() {
            return API.request(`${Config.api.baseURL}/sysbooks/stats`);
        },

        async search(query, options = {}) {
            const params = new URLSearchParams({ q: query, ...options });
            return API.request(`${Config.api.baseURL}/sysbooks/search?${params}`);
        },

        async get(id) {
            return API.request(`${Config.api.baseURL}/sysbooks/${id}`);
        },

        async getDomains() {
            const stats = await this.getStats();
            return stats.data.by_domain || [];
        },

        async getExtensions() {
            const stats = await this.getStats();
            return stats.data.by_extension || [];
        }
    },

    // AI 助手 API
    chat: {
        async ask(question, sessionId = null) {
            return API.request(`${Config.api.baseURL}/ask`, {
                method: 'POST',
                body: { question, session_id: sessionId }
            });
        },

        async stream(question, sessionId = null, onChunk) {
            const response = await fetch(`${Config.api.baseURL}/ask`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ question, session_id: sessionId })
            });

            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const text = decoder.decode(value);
                if (onChunk) onChunk(text);
            }
        }
    },

    // 推理 API
    reasoning: {
        async perform(question, options = {}) {
            return API.request(`${Config.api.baseURL}/reason`, {
                method: 'POST',
                body: { question, ...options }
            });
        },

        async getStatus() {
            return API.request(`${Config.api.baseURL}/reasoning/status`);
        }
    },

    // 知识图谱 API
    graph: {
        async build() {
            return API.request(`${Config.api.baseURL}/graph/build`, {
                method: 'POST'
            });
        },

        async getData() {
            return API.request(`${Config.api.baseURL}/graph/data`);
        },

        async query(entity, relation) {
            return API.request(`${Config.api.baseURL}/graph/query`, {
                method: 'POST',
                body: { entity, relation }
            });
        }
    },

    // 标注 API
    annotation: {
        async list(options = {}) {
            const params = new URLSearchParams(options);
            return API.request(`${Config.api.baseURL}/annotations?${params}`);
        },

        async create(data) {
            return API.request(`${Config.api.baseURL}/annotations`, {
                method: 'POST',
                body: data
            });
        },

        async update(id, data) {
            return API.request(`${Config.api.baseURL}/annotations/${id}`, {
                method: 'PUT',
                body: data
            });
        },

        async delete(id) {
            return API.request(`${Config.api.baseURL}/annotations/${id}`, {
                method: 'DELETE'
            });
        }
    },

    // 音频 API
    audio: {
        async list(options = {}) {
            const params = new URLSearchParams(options);
            return API.request(`${Config.api.baseURL}/audio?${params}`);
        },

        async upload(file) {
            const formData = new FormData();
            formData.append('file', file);
            return API.request(`${Config.api.baseURL}/audio/upload`, {
                method: 'POST',
                headers: {}, // 让浏览器自动设置 Content-Type
                body: formData
            });
        },

        async transcribe(id) {
            return API.request(`${Config.api.baseURL}/audio/${id}/transcribe`, {
                method: 'POST'
            });
        },

        async getSegments(id) {
            return API.request(`${Config.api.baseURL}/audio/${id}/segments`);
        }
    },

    // 系统状态 API
    system: {
        async getHealth() {
            return API.request(`${Config.api.baseURL}/health`);
        },

        async getStats() {
            return API.request(`${Config.api.baseURL}/stats`);
        }
    }
};

// 导出 API
if (typeof module !== 'undefined' && module.exports) {
    module.exports = API;
}
