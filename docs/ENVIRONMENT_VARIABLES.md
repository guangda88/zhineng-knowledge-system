# Environment Variables

Key variables (see `.env.example` for full list):

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ENVIRONMENT` | No | `development` | `development`, `testing`, `production` |
| `DATABASE_URL` | Prod | — | PostgreSQL connection string |
| `REDIS_URL` | No | — | Redis connection string |
| `POSTGRES_PASSWORD` | Yes | — | PostgreSQL password |
| `REDIS_PASSWORD` | Yes | — | Redis password |
| `DEEPSEEK_API_KEY` | No | — | DeepSeek AI API key |
| `ALLOWED_ORIGINS` | Prod | — | CORS origins (JSON array or comma-separated) |
| `JWT_PRIVATE_KEY` | Prod | — | RSA private key PEM |
| `JWT_PUBLIC_KEY` | Prod | — | RSA public key PEM |
| `LOG_LEVEL` | No | `INFO` | Logging level |
| `API_PORT` | No | `8000` | Internal API port |
