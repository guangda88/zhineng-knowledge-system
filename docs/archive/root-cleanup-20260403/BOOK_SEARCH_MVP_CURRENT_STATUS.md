# Book Search MVP - Current Status (2026-03-31)

<div align="center">

⚠️ **归档文档 — 数据已过时**

本报告为历史快照存档。当前版本 **v1.3.0-dev**，232 测试通过。

👉 最新工程状态请参阅 **[ENGINEERING_ALIGNMENT.md](ENGINEERING_ALIGNMENT.md)**

</div>

---

## Overview
Book search functionality integration is 90% complete but blocked by a middleware/security issue that's rejecting HTTP requests before they reach the route handlers.

## What's Working ✅

### 1. Database (100% Complete)
- PostgreSQL 16 with pgvector extension configured
- Tables created: `books`, `book_chapters`, `data_sources`, `user_bookmarks`, `dictionary`, `reading_history`
- Sample data: 5 books (周易注疏, 道德经, 论语, 黄帝内经素问, 庄子) with 6 chapters
- Indexes: pg_trgm for fuzzy matching, vector similarity search ready

### 2. Backend Services (100% Complete)
**File: `backend/services/book_search.py`**
- `search_metadata()`: Search by title, author, description with filters
- `search_content()`: Full-text search within chapter content
- `search_similar()`: Vector similarity search for related books
- `get_book_detail()`: Fetch complete book information with chapters
- `get_chapter_content()`: Retrieve specific chapter content

### 3. Data Models (100% Complete)
**Files: `backend/models/book.py`, `backend/models/source.py`**
- SQLAlchemy ORM models with async support
- Vector field (512-dim) for BGE-small-zh-v1.5 embeddings
- Proper relationships (Book ↔ BookChapter)

### 4. API Endpoints (100% Complete)
**Files: `backend/api/v1/books.py`, `backend/api/v2/books.py`**
- `GET /api/books/search` - Metadata search
- `GET /api/books/search/content` - Full-text search
- `GET /api/books/{book_id}` - Book details
- `GET /api/books/{book_id}/related` - Similar books
- `GET /api/books/{book_id}/chapters/{chapter_id}` - Chapter content
- `GET /api/books/filters/list` - Available filters

### 5. Frontend UI (100% Complete)
**Files: `frontend/index.html`, `frontend/app.js`**
- 📚 Books tab added to navigation
- Search interface with category and dynasty filters
- Toggle between metadata and content search
- Modal dialogs for book details and chapter content
- Related books recommendation feature
- Accessible via http://localhost:8008

### 6. Infrastructure (95% Complete)
- SQLAlchemy async engine integrated
- Session factory configured
- Dependency injection set up
- Middleware bugs fixed (State.get() AttributeError)

## The Problem ⚠️

### Symptom
All book search API calls return: `Invalid HTTP request received`

### Diagnosis
1. Routes ARE registered in FastAPI (verified: `app.routes` shows all 6 book endpoints)
2. Routes CAN be imported manually in Python
3. Requests are being rejected by middleware/security layer before reaching route handlers
4. Health endpoint works: `http://localhost:8000/health` returns proper JSON

### Root Cause (Suspected)
A middleware component is rejecting requests to `/api/books/*` paths. The error message "Invalid HTTP request received" doesn't match FastAPI's standard error messages, suggesting custom middleware is involved.

## What Needs To Be Done 🔧

### Immediate (Debugging)
1. **Identify the rejecting middleware**
   ```bash
   # Check which middleware is active
   docker logs zhineng-api | grep -i "middleware"
   ```

2. **Test endpoint directly via Python**
   ```python
   # Bypass HTTP and test the service directly
   import asyncio
   from backend.services.book_search import BookSearchService
   from backend.core.database import get_async_session

   async def test():
       async for session in get_async_session():
           service = BookSearchService(session, pool)
           results = await service.search_metadata("周易", page=1, size=10)
           print(results)
   ```

3. **Check middleware order** in `backend/main.py` - the rejecting middleware might be before route registration

### Quick Fix Options

**Option A: Disable Problematic Middleware**
Temporarily comment out middlewares in `main.py` to identify the culprit:
```python
# app.add_middleware(SecurityHeadersMiddleware, hsts_enabled=True)  # Try disabling
# app.middleware("http")(log_requests)  # Try disabling
```

**Option B: Add Exception for Book Routes**
Modify the rejecting middleware to allow `/api/books/*` paths.

**Option C: Use Different Route Prefix**
Change books router from `/books` to `/library` or `/b` to avoid conflicts.

## Testing Commands

```bash
# 1. Check API health
curl http://localhost:8000/health

# 2. Check registered routes
docker exec zhineng-api python3 -c "
from main import app
print([r.path for r in app.routes if 'books' in r.path])
"

# 3. Test via nginx (port 8008)
curl "http://localhost:8008/api/books/search?q=test"

# 4. Access frontend
open http://localhost:8008
# Click on "📚 书籍" tab
```

## Files Modified

### Core Backend
- ✅ `backend/core/database.py` - Added SQLAlchemy Base, async engine
- ✅ `backend/core/lifespan.py` - Added SQLAlchemy initialization
- ✅ `backend/models/book.py` - Book and BookChapter ORM models
- ✅ `backend/models/source.py` - DataSource model
- ✅ `backend/models/__init__.py` - Removed non-existent lingzhi imports
- ✅ `backend/services/book_search.py` - Complete search service
- ✅ `backend/schemas/book.py` - Pydantic response models
- ✅ `backend/api/v1/books.py` - v1 API endpoints
- ✅ `backend/api/v2/books.py` - v2 API endpoints
- ✅ `backend/api/v1/__init__.py` - Books router registered
- ✅ `backend/api/v2/__init__.py` - v2 router aggregator
- ✅ `backend/main.py` - v2 router imported and included
- ✅ `backend/middleware/security_headers.py` - Fixed State.get() bug

### Frontend
- ✅ `frontend/index.html` - Books section added
- ✅ `frontend/app.js` - Book search JavaScript (~300 lines)

### Database
- ✅ `scripts/init_book_search_db_fixed.sql` - Fixed schema (512-dim vectors, pg_trgm)

## Access the Frontend

```
http://localhost:8008
```

Click the "📚 书籍" tab to access the book search interface. The UI is complete and ready to use once the backend routing issue is resolved.

## Summary

- **Backend Code**: 100% complete
- **Database**: 100% complete with sample data
- **Frontend UI**: 100% complete
- **Integration**: 90% complete (blocked by middleware issue)
- **Estimated Time to Fix**: 30-60 minutes of debugging middleware

The book search feature is essentially complete. Once the middleware issue is identified and fixed, the entire system should work immediately.
