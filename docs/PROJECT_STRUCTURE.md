# Project Structure

```
zhineng-knowledge-system/
├── backend/                    # All Python backend code
│   ├── main.py                # FastAPI app factory + entry point
│   ├── config/                # Pydantic-settings based config
│   │   ├── base.py            # BaseConfig (env, API, BGE, DeepSeek)
│   │   ├── database.py        # DatabaseConfig
│   │   ├── redis.py           # RedisConfig
│   │   ├── security.py        # SecurityConfig
│   │   └── lingzhi.py         # lingzhiConfig (legacy DB paths)
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
│   │   ├── lingzhi/           # Legacy lingzhi integration
│   │   └── knowledge_base/    # Knowledge base processing
│   ├── domains/               # Domain-specific handlers
│   │   ├── base.py            # BaseDomain ABC, DomainConfig, QueryResult, DomainType
│   │   ├── qigong.py          # 气功 domain
│   │   ├── tcm.py             # 中医 domain
│   │   ├── confucian.py       # 儒家 domain
│   │   ├── buddhist.py        # 佛家 domain
│   │   ├── daoist.py          # 道家 domain
│   │   ├── martial.py         # 武术 domain
│   │   ├── philosophy.py      # 哲学 domain
│   │   ├── science.py         # 科学 domain
│   │   ├── psychology.py      # 心理学 domain
│   │   ├── general.py         # 通用 fallback domain
│   │   ├── mixins.py          # DatabaseSearchMixin, QueryFormatterMixin, RelationMapMixin
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
