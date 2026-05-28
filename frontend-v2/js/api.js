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

        const isFormData = (typeof FormData !== 'undefined' && body instanceof FormData);

        let lastError;
        for (let i = 0; i < retries; i++) {
            try {
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), timeout);

                const config = {
                    method,
                    headers: isFormData
                        ? { ...headers }
                        : { 'Content-Type': 'application/json', ...headers }
                };

                if (body) {
                    config.body = isFormData ? body : JSON.stringify(body);
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
        async ocrStats() {
            return API.request(`/annotation/ocr/stats`);
        },

        async ocrPending() {
            return API.request(`/annotation/ocr/tasks/pending`);
        },

        async ocrTask(taskId) {
            return API.request(`/annotation/ocr/task/${taskId}`);
        },

        async ocrCorrect(data) {
            return API.request(`/annotation/ocr/correct`, {
                method: 'POST',
                body: data
            });
        },

        async transcriptionStats() {
            return API.request(`/annotation/transcription/stats`);
        },

        async transcriptionPending() {
            return API.request(`/annotation/transcription/tasks/pending`);
        },

        async transcriptionCorrect(data) {
            return API.request(`/annotation/transcription/correct`, {
                method: 'POST',
                body: data
            });
        },

        async annotationStats() {
            return API.request(`/annotation/stats`);
        }
    },

    // 音频 API
    audio: {
        async list(options = {}) {
            const params = new URLSearchParams(options);
            return API.request(`/audio/files?${params}`);
        },

        async get(fileId) {
            return API.request(`/audio/files/${fileId}`);
        },

        async delete(fileId) {
            return API.request(`/audio/files/${fileId}`, { method: 'DELETE' });
        },

        async upload(file) {
            const formData = new FormData();
            formData.append('file', file);
            return API.request(`/audio/upload`, {
                method: 'POST',
                headers: {},
                body: formData
            });
        },

        async importData(data) {
            return API.request(`/audio/import`, {
                method: 'POST',
                body: data
            });
        },

        async transcribe(fileId) {
            return API.request(`/audio/transcribe/${fileId}`, {
                method: 'POST'
            });
        },

        async transcribeLocal(fileId) {
            return API.request(`/audio/transcribe-local/${fileId}`, {
                method: 'POST'
            });
        },

        async transcribeStatus(fileId) {
            return API.request(`/audio/transcribe/${fileId}/status`);
        },

        async getSegments(fileId) {
            return API.request(`/audio/files/${fileId}/segments`);
        },

        async search(query, options = {}) {
            const params = new URLSearchParams({ q: query, ...options });
            return API.request(`/audio/search?${params}`);
        },

        async vectorize(fileId) {
            return API.request(`/audio/vectorize/${fileId}`, { method: 'POST' });
        },

        async getAnnotations(fileId) {
            return API.request(`/audio/annotations/audio/${fileId}`);
        },

        async addAnnotation(data) {
            return API.request(`/audio/annotations`, {
                method: 'POST',
                body: data
            });
        }
    },

    // 导入 API
    importData: {
        async audioImport(data) {
            return API.request(`/audio/import`, {
                method: 'POST',
                body: data
            });
        },

        async processTextbook(data) {
            return API.request(`/textbook-processing/process`, {
                method: 'POST',
                body: data
            });
        },

        async processBatch(data) {
            return API.request(`/textbook-processing/process/batch`, {
                method: 'POST',
                body: data
            });
        },

        async getTasks(options = {}) {
            const params = new URLSearchParams(options);
            return API.request(`/textbook-processing/tasks?${params}`);
        }
    },

    // 数据分析 API
    analytics: {
        async dashboard() {
            return API.request(`${Config.api.baseURL}/analytics/dashboard`);
        },

        async track(data) {
            return API.request(`${Config.api.baseURL}/analytics/track`, {
                method: 'POST',
                body: data
            });
        },

        async feedbackInstant(data) {
            return API.request(`${Config.api.baseURL}/analytics/feedback/instant`, {
                method: 'POST',
                body: data
            });
        }
    },

    // 系统状态 API
    system: {
        async getHealth() {
            return API.request(`/health`);
        },

        async getStats() {
            return API.request(`${Config.api.baseURL}/stats`);
        },

        async getDomains() {
            return API.request(`${Config.api.baseURL}/domains`);
        },

        async getCategories() {
            return API.request(`${Config.api.baseURL}/categories`);
        }
    }
};

// 导出 API
if (typeof module !== 'undefined' && module.exports) {
    module.exports = API;
}
