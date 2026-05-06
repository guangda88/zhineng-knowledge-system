# Architecture & Key Patterns

## App Factory Pattern
`backend/main.py` uses `create_app()` returning a configured `FastAPI` instance. Lifespan events (startup/shutdown) are handled via `core/lifespan.py` using `@asynccontextmanager`.

## Configuration
- **Pydantic Settings** (`pydantic-settings`): `backend/config/` uses multiple inheritance (`Config(BaseConfig, DatabaseConfig, RedisConfig, SecurityConfig, LingZhiConfig)`).
- Singleton via `get_config()`.
- Environment variable driven; `.env` file supported.
- Production mode enforces stricter validation (DATABASE_URL required, RSA keys required for JWT).

## Async-first
All I/O operations use `async/await`. Database access uses `asyncpg` with connection pools (`asyncpg.create_pool`). HTTP calls use `httpx.AsyncClient`.

## Database
- **PostgreSQL 16 + pgvector** for vector similarity search (1024-dim embeddings).
- Raw SQL with parameterized queries via `asyncpg` (no ORM).
- Helper functions in `common/db_helpers.py` (`fetch_one_or_404`, `fetch_paginated`, `row_to_dict`).
- Schema in `init.sql`: tables `documents`, `chat_history`, `qigong_knowledge`.
- Index naming: `idx_{table}_{column}`.

## Caching
Multi-level: L1 (in-memory `MemoryCache`) + L2 (Redis `RedisCache`). Managed by `cache/manager.py` with per-resource-type TTL configuration.

## Domain System
Ten domains implementing `BaseDomain` ABC: `QigongDomain`, `TcmDomain`, `ConfucianDomain`, `BuddhistDomain`, `DaoistDomain`, `MartialDomain`, `PhilosophyDomain`, `ScienceDomain`, `PsychologyDomain`, `GeneralDomain`. Registered in `DomainRegistry` via `setup_domains()`. Domain-based routing in `gateway/router.py`.

## API Gateway
`gateway/` provides circuit breaker, rate limiting, and domain-based request routing.

## Authentication
RS256 JWT with access/refresh token pairs, token blacklist, and RBAC. See `auth/jwt.py`.
