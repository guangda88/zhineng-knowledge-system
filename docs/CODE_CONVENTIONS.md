# Code Conventions

## Formatting
- **Black** with `--line-length=100`, target Python 3.12.
- **isort** with `--profile=black`.
- **4 spaces** indentation for Python (`.editorconfig`).
- Max line length: **100** characters.
- **LF** line endings, UTF-8 encoding.

## Naming (from DEVELOPMENT_RULES.md)
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

## Docstrings
- All public functions must have docstrings (Google style with `Args:`, `Returns:`).
- Chinese comments are common throughout the codebase.

## Type Annotations
Required on all public functions. The project uses `typing` module extensively.

## Error Handling
- Catch specific exceptions, never bare `except:`.
- Log errors with context (`logger.error(f"...: {e}", exc_info=True)`).
- Never log sensitive data.

## API Design
- RESTful: `GET /api/v1/resources`, `POST /api/v1/resources`, etc.
- Unified response format: `{"status": "ok", "data": {...}}` or `{"status": "error", "error": {...}}`.
- Versioned prefix: `/api/v1/`.
- Categories validated against fixed set: `气功`, `中医`, `儒家`, `佛家`, `道家`, `武术`, `哲学`, `科学`, `心理学`.
