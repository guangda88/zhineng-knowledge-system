# Development Workflow

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

## Testing

### Framework
- **pytest** with **pytest-asyncio** (`asyncio_mode=auto`).
- Test files in `tests/` following `test_*.py` naming.
- Fixtures in `tests/conftest.py`: `test_client` (FastAPI TestClient), `test_db` (asyncpg pool).

### Coverage
- Baseline: **36%** (current actual coverage, enforced via `--cov-fail-under=36`)
- Target: 80% for core modules, 70% for API, 60% for utilities (staged: 36%→50%→60%→80%)

### Running Tests
```bash
pytest tests/ -v                                    # All tests
pytest tests/test_api.py -v                         # Single file
pytest tests/ -v --cov=backend --cov-report=html    # With HTML coverage report
```

### Test Patterns
Tests use `fastapi.testclient.TestClient` for synchronous HTTP testing. Status code assertions typically accept multiple codes (`assert response.status_code in [200, 500]`) because DB may not be available in test environments.

## CI/CD

**GitHub Actions** (`.github/workflows/ci.yml`):
- **lint** job: flake8 check
- **test** job: pytest with PostgreSQL + Redis service containers, coverage baseline ≥36% (target 60%+)
- **security** job: bandit scan
- **status-check** job: gates PR merge on lint + test passing
