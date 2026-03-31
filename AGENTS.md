# AGENTS.md — Agent Guide for zhineng-knowledge-system

> **Project**: 智能知识系统 (Zhineng Knowledge System) — a RAG-based Q&A system for traditional Chinese culture (气功/Qigong, 中医/TCM, 儒家/Confucianism).
> **Stack**: Python 3.12 · FastAPI · AsyncPG · PostgreSQL 16 + pgvector · Redis 7 · Docker Compose
> **Version**: 1.1.0

---

## Quick Reference — Essential Commands

### Run the full stack (Docker)

```bash
docker-compose up -d          # Start all services
docker-compose ps              # Check status
docker-compose logs -f api     # Follow API logs
docker-compose down            # Stop all services
```

### Run without Docker (development)

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Tests

```bash
# All tests
pytest tests/ -v

# With coverage (must pass ≥60% in CI)
pytest tests/ -v --cov=backend --cov-report=term-missing

# Specific test file
pytest tests/test_api.py -v

# Only unit tests (no DB needed)
pytest tests/test_main.py -v
```

### Lint / Format / Type-check

```bash
# Format code (Black + isort)
black --line-length=100 --target-version=py312 backend/
isort --profile=black --line-length=100 backend/

# Lint
flake8 . --config=.flake8

# Type check
mypy --config-file=pyproject.toml backend/

# Security scan
bandit -c pyproject.toml -r backend/

# All-in-one check script
bash scripts/check_code.sh              # Check all
bash scripts/check_code.sh -f           # Auto-fix formatting
bash scripts/check_code.sh backend/     # Check specific dir

# Format-only script
bash scripts/format_code.sh             # Auto-format
bash scripts/format_code.sh -c          # Check only
```

### Pre-commit hooks

```bash
pre-commit install                # Install hooks
pre-commit run --all-files        # Run all hooks manually
pre-commit run black --all-files  # Run specific hook
```

### Health checks

```bash
curl http://localhost:8001/health       # Service health
curl http://localhost:8001/health/db    # Database health
docker-compose ps                       # Container status
```

---

## Project Structure

```
zhineng-knowledge-system/
├── backend/                    # All Python backend code
│   ├── main.py                # FastAPI app factory + entry point
│   ├── config/                # Pydantic-settings based config
│   │   ├── base.py            # BaseConfig (env, API, BGE, DeepSeek)
│   │   ├── database.py        # DatabaseConfig
│   │   ├── redis.py           # RedisConfig
│   │   ├── security.py        # SecurityConfig
│   │   └── lingzhi.py         # LingZhiConfig (legacy DB paths)
│   ├── api/v1/                # API route modules
│   │   ├── __init__.py        # Registers all sub-routers on api_router
│   │   ├── documents.py       # CRUD /api/v1/documents
│   │   ├── search.py          # Search + /ask + /categories + /stats
│   │   ├── reasoning.py       # /api/v1/reason (CoT/ReAct/GraphRAG)
│   │   ├── gateway.py         # Gateway endpoints
│   │   ├── health.py          # /health, /health/db
│   │   └── textbook_processing.py
│   ├── services/              # Business logic
│   │   ├── retrieval/         # VectorRetriever, BM25Retriever, HybridRetriever
│   │   ├── reasoning/         # BaseReasoner, CoTReasoner, ReactReasoner, GraphRAGReasoner
│   │   ├── rag/               # RAG orchestration
│   │   ├── lingzhi/           # Legacy LingZhi integration
│   │   └── knowledge_base/    # Knowledge base processing
│   ├── domains/               # Domain-specific handlers
│   │   ├── base.py            # BaseDomain ABC, DomainConfig, QueryResult
│   │   ├── qigong.py          # 气功 domain
│   │   ├── tcm.py             # 中医 domain
│   │   ├── confucian.py       # 儒家 domain
│   │   ├── general.py         # 通用 fallback domain
│   │   └── registry.py        # DomainRegistry, setup_domains(), get_registry()
│   ├── auth/                  # JWT authentication (RS256)
│   │   ├── jwt.py             # JWTAuth, TokenBlacklist, AuthConfig
│   │   ├── middleware.py      # Auth middleware
│   │   └── rbac.py            # Role-based access control
│   ├── gateway/               # API gateway pattern
│   │   ├── router.py          # APIGateway (domain-based routing)
│   │   ├── circuit_breaker.py # CircuitBreaker (CLOSED/OPEN/HALF_OPEN)
│   │   └── rate_limiter.py    # Rate limiting
│   ├── cache/                 # Multi-level caching (L1 memory + L2 Redis)
│   │   ├── manager.py         # CacheManager with TTL per resource type
│   │   ├── memory_cache.py    # L1 in-memory cache
│   │   ├── redis_cache.py     # L2 Redis cache
│   │   └── decorators.py      # @cached_with_monitor decorator
│   ├── core/                  # App infrastructure
│   │   ├── lifespan.py        # FastAPI lifespan (startup/shutdown)
│   │   ├── database.py        # DB pool management
│   │   ├── middleware.py      # Security headers, CORS, request logging
│   │   ├── dependency_injection.py
│   │   ├── service_manager.py
│   │   ├── services.py        # DatabaseService, CacheService, etc.
│   │   ├── request_stats.py
│   │   └── ai_action_wrapper.py, rules_checker.py, urgency_guard.py, data_verification_gate.py
│   ├── monitoring/            # Observability
│   │   ├── metrics.py         # MetricsCollector
│   │   ├── health.py          # HealthChecker
│   │   ├── prometheus.py      # PrometheusExporter
│   │   └── cache_metrics.py   # Cache hit/miss metrics
│   ├── common/                # Shared utilities
│   │   ├── db_helpers.py      # require_pool, row_to_dict, fetch_one_or_404, fetch_paginated
│   │   ├── singleton.py
│   │   └── typing.py
│   ├── middleware/             # HTTP middleware
│   │   └── rate_limit.py      # RateLimitMiddleware
│   ├── models.py              # Pydantic request/response models
│   ├── utils/
│   ├── skills/
│   └── textbook_processing/
├── frontend/                  # Static HTML/CSS/JS (served by Nginx)
├── tests/                     # Test suite
│   ├── conftest.py            # Fixtures: test_client, test_db, event_loop
│   ├── test_api.py
│   ├── test_main.py
│   ├── test_retrieval.py
│   ├── test_reasoning.py
│   ├── test_gateway.py
│   ├── test_deepseek_integration.py
│   ├── services/
│   ├── api/
│   ├── test_hooks/
│   └── performance/
├── nginx/nginx.conf           # Reverse proxy config
├── monitoring/                # Prometheus + Grafana configs
├── scripts/                   # DevOps scripts
│   ├── check_code.sh          # Lint + format + security + type check
│   ├── format_code.sh         # Black + isort auto-format
│   ├── deploy.sh
│   ├── health_check.sh
│   ├── emergency_memory_recovery.sh
│   └── ...
├── data/                      # Runtime data (SQLite, exports, vectors)
├── docker-compose.yml         # All services (postgres, redis, api, nginx, prometheus, grafana)
├── init.sql                   # Database schema (documents, chat_history, qigong_knowledge)
├── pyproject.toml             # Black, isort, mypy, bandit, pytest, coverage config
├── .flake8                    # Flake8 config
├── pytest.ini                 # Pytest config (asyncio_mode=auto, fail_under=60)
├── .pre-commit-config.yaml    # Pre-commit hooks
├── .editorconfig              # Editor formatting rules
└── DEVELOPMENT_RULES.md       # Comprehensive development rules (Chinese)
```

---

## Ports

| Service | Host Port | Container Port |
|---------|-----------|----------------|
| PostgreSQL | 5436 | 5432 |
| Redis | 6381 | 6379 |
| API (FastAPI/uvicorn) | 8001 | 8000 |
| Web (Nginx) | 8008 | 80 |
| Prometheus | 9090 | 9090 |
| Grafana | 3000 | 3000 |

Non-standard ports (5436, 6381, 8001, 8008) are chosen to avoid conflicts with local installations.

---

## Architecture & Key Patterns

### App Factory Pattern
`backend/main.py` uses `create_app()` returning a configured `FastAPI` instance. Lifespan events (startup/shutdown) are handled via `core/lifespan.py` using `@asynccontextmanager`.

### Configuration
- **Pydantic Settings** (`pydantic-settings`): `backend/config/` uses multiple inheritance (`Config(BaseConfig, DatabaseConfig, RedisConfig, SecurityConfig, LingZhiConfig)`).
- Singleton via `get_config()`.
- Environment variable driven; `.env` file supported.
- Production mode enforces stricter validation (DATABASE_URL required, RSA keys required for JWT).

### Async-first
All I/O operations use `async/await`. Database access uses `asyncpg` with connection pools (`asyncpg.create_pool`). HTTP calls use `httpx.AsyncClient`.

### Database
- **PostgreSQL 16 + pgvector** for vector similarity search (1024-dim embeddings).
- Raw SQL with parameterized queries via `asyncpg` (no ORM).
- Helper functions in `common/db_helpers.py` (`fetch_one_or_404`, `fetch_paginated`, `row_to_dict`).
- Schema in `init.sql`: tables `documents`, `chat_history`, `qigong_knowledge`.
- Index naming: `idx_{table}_{column}`.

### Caching
Multi-level: L1 (in-memory `MemoryCache`) + L2 (Redis `RedisCache`). Managed by `cache/manager.py` with per-resource-type TTL configuration.

### Domain System
Four domains implementing `BaseDomain` ABC: `QigongDomain`, `TcmDomain`, `ConfucianDomain`, `GeneralDomain`. Registered in `DomainRegistry` via `setup_domains()`. Domain-based routing in `gateway/router.py`.

### API Gateway
`gateway/` provides circuit breaker, rate limiting, and domain-based request routing.

### Authentication
RS256 JWT with access/refresh token pairs, token blacklist, and RBAC. See `auth/jwt.py`.

---

## Code Conventions

### Formatting
- **Black** with `--line-length=100`, target Python 3.12.
- **isort** with `--profile=black`.
- **4 spaces** indentation for Python (`.editorconfig`).
- Max line length: **100** characters.
- **LF** line endings, UTF-8 encoding.

### Naming (from DEVELOPMENT_RULES.md)
| Type | Convention | Example |
|------|-----------|---------|
| Python modules | `lowercase_underscore` | `services/retrieval.py` |
| Classes | `PascalCase` | `VectorRetriever` |
| Functions/methods | `lowercase_underscore` | `search_documents` |
| Constants | `UPPER_SNAKE_CASE` | `MAX_RESULTS` |
| Private members | `_leading_underscore` | `_internal_func` |
| SQL tables | `lowercase_underscore`, plural | `documents`, `chat_history` |
| SQL columns | `lowercase_underscore` | `created_at`, `user_id` |
| SQL indexes | `idx_{table}_{column}` | `idx_documents_category` |

### Docstrings
- All public functions must have docstrings (Google style with `Args:`, `Returns:`).
- Chinese comments are common throughout the codebase.

### Type Annotations
Required on all public functions. The project uses `typing` module extensively.

### Error Handling
- Catch specific exceptions, never bare `except:`.
- Log errors with context (`logger.error(f"...: {e}", exc_info=True)`).
- Never log sensitive data.

### API Design
- RESTful: `GET /api/v1/resources`, `POST /api/v1/resources`, etc.
- Unified response format: `{"status": "ok", "data": {...}}` or `{"status": "error", "error": {...}}`.
- Versioned prefix: `/api/v1/`.
- Categories validated against fixed set: `气功`, `中医`, `儒家`.

---

## Git Workflow

### Branch Strategy (GitFlow)
```
main (production, protected)
  └── develop (integration)
        ├── feature/xxx
        ├── fix/xxx
        └── hotfix/xxx
```

### Commit Convention (Conventional Commits)
```
<type>(<scope>): <subject>

Types: feat, fix, docs, style, refactor, perf, test, chore, revert
Scopes: backend, frontend, api, db, auth, docs, ci
```

### Pre-commit Checks
Before every commit, the pre-commit hooks run:
1. **trailing-whitespace** + **end-of-file-fixer**
2. **black** (auto-format)
3. **isort** (auto-sort imports)
4. **flake8** (lint)
5. **bandit** (security)
6. **mypy** (type check)
7. Various file checks (YAML, JSON, TOML, large files, private keys, merge conflicts)

---

## Testing

### Framework
- **pytest** with **pytest-asyncio** (`asyncio_mode=auto`).
- Test files in `tests/` following `test_*.py` naming.
- Fixtures in `tests/conftest.py`: `test_client` (FastAPI TestClient), `test_db` (asyncpg pool).

### Coverage
- Minimum: **60%** (enforced in CI via `--cov-fail-under=60`).
- Target: 80% for core modules, 70% for API, 60% for utilities.

### Running Tests
```bash
pytest tests/ -v                                    # All tests
pytest tests/test_api.py -v                         # Single file
pytest tests/ -v --cov=backend --cov-report=html    # With HTML coverage report
```

### Test Patterns
Tests use `fastapi.testclient.TestClient` for synchronous HTTP testing. Status code assertions typically accept multiple codes (`assert response.status_code in [200, 500]`) because DB may not be available in test environments.

---

## CI/CD

**GitHub Actions** (`.github/workflows/ci.yml`):
- **lint** job: flake8 check
- **test** job: pytest with PostgreSQL + Redis service containers, coverage ≥60%
- **security** job: bandit scan
- **status-check** job: gates PR merge on lint + test passing

---

## Environment Variables

Key variables (see `.env.example` for full list):

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ENVIRONMENT` | No | `development` | `development`, `testing`, `production` |
| `DATABASE_URL` | Prod | — | PostgreSQL connection string |
| `REDIS_URL` | No | — | Redis connection string |
| `POSTGRES_PASSWORD` | No | `zhineng123` | PostgreSQL password |
| `REDIS_PASSWORD` | No | `redis123` | Redis password |
| `DEEPSEEK_API_KEY` | No | — | DeepSeek AI API key |
| `ALLOWED_ORIGINS` | Prod | — | CORS origins (JSON array or comma-separated) |
| `JWT_PRIVATE_KEY` | Prod | — | RSA private key PEM |
| `JWT_PUBLIC_KEY` | Prod | — | RSA public key PEM |
| `LOG_LEVEL` | No | `INFO` | Logging level |
| `API_PORT` | No | `8000` | Internal API port |

---

## Important Gotchas & Non-obvious Patterns

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

### 9. Embedding Placeholder
`VectorRetriever.embed_text()` currently uses a SHA-256 hash-based placeholder. Production needs a real BGE embedding service integration.

### 10. DEVELOPMENT_RULES.md is Authoritative
The project has a comprehensive `DEVELOPMENT_RULES.md` (in Chinese) that is the single source of truth for all conventions. It includes resource management, emergency response procedures, and hook-based enforcement mechanisms.

### 11. No ORM
The project uses raw SQL via asyncpg. There is no SQLAlchemy ORM usage despite it being in requirements.txt (listed as `sqlalchemy==2.0.35`).

---

## Key Files for Quick Orientation

| Need | File |
|------|------|
| Where does the app start? | `backend/main.py` |
| What are the API endpoints? | `backend/api/v1/__init__.py` + individual route files |
| What are the data models? | `backend/models.py` |
| How is config loaded? | `backend/config/__init__.py` → `get_config()` |
| How does startup work? | `backend/core/lifespan.py` |
| Database schema | `init.sql` |
| How does caching work? | `backend/cache/manager.py` |
| How does search work? | `backend/services/retrieval/` (vector, bm25, hybrid) |
| How does auth work? | `backend/auth/jwt.py` |
| What are the domains? | `backend/domains/` (qigong, tcm, confucian, general) |
| Docker services | `docker-compose.yml` |
| All development rules | `DEVELOPMENT_RULES.md` |
