# Important Gotchas & Non-obvious Patterns

### 1. Python Path Setup
`backend/main.py` does `sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))` to enable relative imports. When importing backend modules from tests or scripts, you may need to adjust `PYTHONPATH` or import from `backend.xxx`.

### 2. Config Singleton
`backend/config/__init__.py` uses a global `_config` singleton accessed via `get_config()`. There's also a module-level `config = get_config()` for backward compatibility. Do not instantiate `Config()` directly in production code.

### 3. Lifespan Dependency Chain
Startup order in `core/lifespan.py`: DatabaseService → CacheService → VectorService → MonitoringService. The service manager orchestrates this. If any service fails to start, previously started services are cleaned up.

### 4. Optional Module Imports
Many modules use try/except ImportError for optional features (monitoring, domains, config watcher). This is by design — the app degrades gracefully when optional services are unavailable.

### 5. Test Client Import
`tests/conftest.py` imports `from backend.main import app` (using the backend package path), while `tests/test_api.py` uses the `test_client` fixture from conftest. Both patterns coexist.

### 6. Docker Compose API Port Mapping
The API container listens on port 8000 internally but is mapped to **8001** on the host. The healthcheck inside the container uses `localhost:8000`.

### 7. Categories are Chinese Strings
Valid categories are `气功`, `中医`, `儒家` (Chinese characters). Pydantic validators enforce this: `pattern="^(气功|中医|儒家)$"`.

### 8. AsyncPG Parameterized Queries
Use `$1`, `$2` positional parameters (not `%s` or `?`):
```python
await db.fetch("SELECT * FROM documents WHERE id = $1", doc_id)
```

### 9. Embedding Service
`VectorRetriever.embed_text()` uses `sentence-transformers` with `BAAI/bge-small-zh-v1.5` (default, 512-dim). Model controlled by `EMBEDDING_MODEL` env var. `enhanced_vector_service.py` provides local-first with remote API fallback.

**GPU Available**: Host machine has GTX 1660 Ti (6GB) with CUDA 13.1. `torch.cuda.is_available()=True`. For bulk embedding tasks (thousands of rows), **always use host Python + CUDA** instead of the Docker embedding service (which runs CPU-only). GPU is ~40x faster (3s vs 118s per 500 texts). Model path on host: `/data/models/bge-small-zh`.

### 10. DEVELOPMENT_RULES.md is Authoritative
The project has a comprehensive `DEVELOPMENT_RULES.md` (in Chinese) that is the single source of truth for all conventions. It includes resource management, emergency response procedures, and hook-based enforcement mechanisms.

### 11. Dual Database Access (asyncpg + SQLAlchemy)
The project uses both raw SQL via asyncpg for performance-critical paths and SQLAlchemy ORM for model definitions and structured queries (books, analytics, evolution, annotations). SQLAlchemy is in `requirements.txt` and actively used across ~24 files.
