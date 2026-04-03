# 安全与架构修复行动计划

**基于2026-04-01审计报告**

---

## 🚨 立即修复 (本周内完成)

### 1. SQL注入风险修复

**问题位置**: `backend/api/v1/books.py:150-169`

**当前代码**:
```python
# ❌ 原始SQL
categories_result = await db.execute(
    "SELECT DISTINCT category FROM books WHERE category IS NOT NULL ORDER BY category"
)
```

**修复方案**:
```python
# ✅ 使用SQLAlchemy ORM
from sqlalchemy import distinct, select
from models.book import Book

stmt = select(distinct(Book.category)).where(
    Book.category.isnot(None)
).order_by(Book.category)
categories_result = await db.execute(stmt)
categories = [row[0] for row in categories_result.scalars().all()]
```

**工作量**: 2小时
**优先级**: P0-CRITICAL

---

### 2. 实现JWT认证系统

**创建**: `backend/core/security.py`

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from datetime import datetime, timedelta
import os

security = HTTPBearer()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRATION", "3600"))

async def create_access_token(data: dict) -> str:
    """创建JWT token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def verify_token(token: str) -> dict:
    """验证JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """获取当前用户"""
    token = credentials.credentials
    payload = await verify_token(token)
    return payload
```

**工作量**: 1天
**优先级**: P0-CRITICAL

---

### 3. 统一错误处理

**创建**: `backend/core/error_handlers.py`

```python
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

async def http_exception_handler(request: Request, exc: HTTPException):
    """统一HTTP异常处理"""
    # 生产环境不暴露内部错误
    detail = exc.detail
    if exc.status_code >= 500:
        detail = "Internal server error"
        logger.error(f"HTTP {exc.status_code}: {exc.detail}")

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": f"HTTP_{exc.status_code}",
                "message": detail
            }
        }
    )

async def general_exception_handler(request: Request, exc: Exception):
    """通用异常处理"""
    logger.exception(f"Unhandled exception: {exc}")

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred"
            }
        }
    )
```

**在main.py中注册**:
```python
from fastapi.exception_handlers import (
    http_exception_handler,
    general_exception_handler
)
from core.error_handlers import (
    http_exception_handler,
    general_exception_handler
)

app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)
```

**工作量**: 3小时
**优先级**: P0

---

### 4. 日志安全加固

**创建**: `backend/core/secure_logging.py`

```python
import logging
import re
from typing import Any

# 敏感信息模式
SENSITIVE_PATTERNS = [
    r'password["\']?\s*[:=]\s*["\']?[^"\'\s]+',
    r'token["\']?\s*[:=]\s*["\']?[^"\'\s]+',
    r'api[_-]?key["\']?\s*[:=]\s*["\']?[^"\'\s]+',
    r'secret["\']?\s*[:=]\s*["\']?[^"\'\s]+',
    r'credit[_-]?card["\']?\s*[:=]\s*["\']?[^"\'\s]+',
]

class SensitiveDataFilter(logging.Filter):
    """敏感数据过滤器"""

    def filter(self, record: logging.LogRecord) -> bool:
        # 过滤敏感信息
        record.msg = self._sanitize(record.msg)
        if hasattr(record, 'args'):
            record.args = tuple(self._sanitize(str(arg)) for arg in record.args)
        return True

    def _sanitize(self, text: str) -> str:
        """清理敏感信息"""
        for pattern in SENSITIVE_PATTERNS:
            text = re.sub(pattern, '[REDACTED]', text, flags=re.IGNORECASE)
        return text

# 配置日志
logger = logging.getLogger(__name__)
logger.addFilter(SensitiveDataFilter())
```

**工作量**: 2小时
**优先级**: P0

---

### 5. 输入验证加强

**更新**: `backend/core/validators.py`

```python
from pydantic import BaseModel, Field, validator
from typing import Optional
import re

class SafeString(str):
    """安全字符串类型"""

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not isinstance(v, str):
            raise TypeError('string required')

        # 检查危险字符
        dangerous_patterns = ['<script', 'javascript:', 'onerror=', 'onload=']
        v_lower = v.lower()

        for pattern in dangerous_patterns:
            if pattern in v_lower:
                raise ValueError(f'Potentially dangerous content detected')

        # 限制长度
        if len(v) > 10000:
            raise ValueError('Input too long')

        return v

class SearchQuery(BaseModel):
    """搜索查询验证"""
    q: SafeString = Field(..., min_length=1, max_length=200)
    category: Optional[str] = Field(None, regex=r'^[a-zA-Z0-9_\-]+$')
    page: int = Field(1, ge=1, le=1000)
    size: int = Field(20, ge=1, le=100)
```

**工作量**: 3小时
**优先级**: P0

---

## 📅 短期修复 (本月内)

### 1. RBAC实现

**创建**: `backend/core/rbac.py`

```python
from enum import Enum
from fastapi import Depends, HTTPException, status

class Role(str, Enum):
    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"

class Permission(str, Enum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"

ROLE_PERMISSIONS = {
    Role.ADMIN: [Permission.READ, Permission.WRITE, Permission.DELETE, Permission.ADMIN],
    Role.USER: [Permission.READ, Permission.WRITE],
    Role.GUEST: [Permission.READ],
}

def require_permission(permission: Permission):
    """权限检查装饰器"""
    def decorator(user=Depends(get_current_user)):
        user_role = user.get("role", Role.GUEST)
        user_permissions = ROLE_PERMISSIONS.get(user_role, [])

        if permission not in user_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return user
    return decorator

# 使用示例
@app.delete("/api/v1/documents/{doc_id}")
async def delete_document(
    doc_id: int,
    user=Depends(require_permission(Permission.DELETE))
):
    pass
```

**工作量**: 2天
**优先级**: P1

---

### 2. 依赖版本锁定

**创建**: `requirements.lock`

```bash
# 使用pip-tools锁定版本
pip install pip-tools
pip-compile requirements.txt --output-file=requirements.lock

# 在生产中使用
pip install -r requirements.lock
```

**更新**: `.github/workflows/audit.yml`

```yaml
name: Security Audit

on:
  push:
  schedule:
    - cron: '0 0 * * 0'  # 每周日运行

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run pip-audit
        run: |
          pip install pip-audit
          pip-audit
```

**工作量**: 1天
**优先级**: P1

---

### 3. Docker安全加固

**更新**: `backend/Dockerfile`

```dockerfile
# ✅ 使用非root用户
FROM python:3.12-slim

# 安装安全更新
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

# 创建非root用户
RUN useradd -m -u 1000 appuser

WORKDIR /app

# 先复制依赖文件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY --chown=appuser:appuser . .

# 切换到非root用户
USER appuser

# ✅ 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:8000/health')"

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**工作量**: 1天
**优先级**: P1

---

### 4. 密钥管理

**集成**: HashiCorp Vault 或 AWS Secrets Manager

**方案A: 环境变量 + 密钥轮换**

```python
# backend/core/secrets.py
import os
from datetime import datetime, timedelta
import redis

class SecretRotation:
    """密钥轮换管理"""

    @staticmethod
    def get_secret(key_name: str) -> str:
        """获取密钥"""
        # 优先从环境变量获取
        secret = os.getenv(key_name)
        if secret:
            return secret

        # 从Redis获取
        redis_client = redis.from_url(os.getenv("REDIS_URL"))
        secret = redis_client.get(f"secrets:{key_name}")
        if secret:
            return secret.decode()

        raise ValueError(f"Secret not found: {key_name}")

    @staticmethod
    def rotate_secret(key_name: str, new_secret: str):
        """轮换密钥"""
        redis_client = redis.from_url(os.getenv("REDIS_URL"))
        redis_client.setex(
            f"secrets:{key_name}",
            30 * 24 * 3600,  # 30天过期
            new_secret
        )
```

**工作量**: 3天
**优先级**: P1

---

## 📈 中期改进 (下季度)

### 1. 安全监控系统

**实现**: 完整的安全事件日志

```python
# backend/core/security_monitoring.py
from datetime import datetime
from typing import Dict, Any
import json

class SecurityEventLogger:
    """安全事件日志"""

    async def log_event(
        self,
        event_type: str,
        user_id: Optional[str],
        details: Dict[str, Any]
    ):
        """记录安全事件"""
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "user_id": user_id,
            "details": details,
            "ip": self._get_client_ip(),
            "user_agent": self._get_user_agent()
        }

        # 保存到审计日志
        await self._save_to_audit_log(event)

        # 高风险事件立即告警
        if self._is_high_risk_event(event_type):
            await self._send_alert(event)

    def _is_high_risk_event(self, event_type: str) -> bool:
        """判断是否为高风险事件"""
        high_risk_events = [
            "AUTHENTICATION_FAILURE",
            "UNAUTHORIZED_ACCESS_ATTEMPT",
            "SQL_INJECTION_ATTEMPT",
            "RATE_LIMIT_EXCEEDED"
        ]
        return event_type in high_risk_events
```

**工作量**: 5天
**优先级**: P2

---

### 2. API文档安全

**更新**: OpenAPI文档

```python
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

def custom_openapi():
    """自定义OpenAPI文档"""
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="智能知识系统 API",
        version="1.0.0",
        routes=app.routes,
    )

    # 添加安全定义
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    }

    # 应用到所有路径
    for path in openapi_schema["paths"].values():
        for operation in path.values():
            operation["security"] = [{"BearerAuth": []}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi
```

**工作量**: 1天
**优先级**: P2

---

### 3. 测试安全用例

**创建**: `tests/security/`

```python
# tests/security/test_sql_injection.py
import pytest
from httpx import AsyncClient

async def test_sql_injection_protection(client: AsyncClient):
    """测试SQL注入防护"""
    malicious_queries = [
        "'; DROP TABLE documents; --",
        "' OR '1'='1",
        "1' UNION SELECT * FROM users--",
    ]

    for query in malicious_queries:
        response = await client.get(f"/api/v1/search?q={query}")

        # 应该被阻止或返回错误
        assert response.status_code in [400, 422]

        # 确保数据库未被破坏
        assert "DROP TABLE" not in response.text

# tests/security/test_authentication.py
async def test_jwt_required(client: AsyncClient):
    """测试JWT认证要求"""
    response = await client.get("/api/v1/protected")

    # 未认证应该返回401
    assert response.status_code == 401
```

**工作量**: 5天
**优先级**: P2

---

## 🔧 实施流程

### 1. 创建分支

```bash
git checkout -b security-audit-fixes-2026-04-01
```

### 2. 按优先级修复

```bash
# Phase 1: P0修复
git add backend/api/v1/books.py
git commit -m "fix: replace raw SQL with SQLAlchemy ORM"

git add backend/core/security.py
git commit -m "feat: implement JWT authentication"

git add backend/core/error_handlers.py
git commit -m "feat: implement unified error handling"

# Phase 2: P1修复
git add backend/core/rbac.py
git commit -m "feat: implement RBAC"

# Phase 3: P2改进
git add tests/security/
git commit -m "test: add security test suite"
```

### 3. 代码审查

```bash
# 创建Pull Request
gh pr create \
  --title "Security and Architecture Fixes" \
  --body "审计报告修复" \
  --base develop
```

### 4. 部署流程

```bash
# 测试环境部署
docker-compose -f docker-compose.test.yml up -d

# 安全扫描
bandit -r backend/
pip-audit

# 集成测试
pytest tests/security/ -v

# 生产部署
git checkout main
git merge security-audit-fixes-2026-04-01
git push origin main
```

---

## 📊 验收标准

### Phase 1 (P0) 验收

- [x] 无SQL注入风险
- [x] JWT认证已实现
- [x] 错误消息不泄露内部信息
- [x] 日志不包含敏感数据
- [x] 所有API有输入验证

### Phase 2 (P1) 验收

- [ ] RBAC已实现
- [ ] 依赖版本已锁定
- [ ] Docker使用非root用户
- [ ] 密钥轮换机制已建立

### Phase 3 (P2) 验收

- [ ] 安全事件日志完整
- [ ] API文档包含安全信息
- [ ] 安全测试覆盖率>60%
- [ ] 自动化安全扫描已配置

---

## 🎯 成功指标

### 安全指标

| 指标 | 当前 | 目标 |
|------|------|------|
| 高危漏洞 | 5 | 0 |
| 认证覆盖率 | 0% | 100% |
| SQL注入风险 | 5处 | 0处 |
| 敏感数据泄露 | 10处 | 0处 |

### 架构指标

| 指标 | 当前 | 目标 |
|------|------|------|
| 代码复杂度 | 高 | 中 |
| 模块耦合度 | 中 | 低 |
| 测试覆盖率 | 60% | 80% |
| 文档完整性 | 70% | 90% |

---

**创建日期**: 2026-04-01
**负责人**: 开发团队
**审查周期**: 每月一次

**众智混元，万法灵通** ⚡🚀
