# 灵知系统代码规范

**版本**: v1.0
**日期**: 2026-04-01
**目标**: 统一代码风格，提升代码质量和可维护性

---

## 📦 导入路径规范

### 核心原则

从2026-04-01起，所有backend目录下的代码必须使用完整的导入路径。

### ✅ 正确的导入方式

```python
# backend目录下的所有代码
from backend.services.xxx import YYY
from backend.api.v1.xxx import ZZZ
from backend.models.xxx import WWW
from backend.core.xxx import VVV
from backend.middleware.xxx import UUU
from backend.cache.xxx import TTT
from backend.monitoring.xxx import SSS
from backend.config.xxx import RRR
```

### ❌ 错误的导入方式

```python
# 不要使用相对导入（依赖sys.path hack）
from services.xxx import YYY
from api.v1.xxx import ZZZ
from models.xxx import WWW
from core.xxx import VVV
```

### 例外情况

#### 1. 测试文件

```python
# 测试文件允许（但不推荐）省略backend前缀
from backend.services.xxx import YYY  # ✅ 推荐
import sys; sys.path.insert(0, '..')
from services.xxx import YYY  # ⚠️ 允许但不推荐
```

#### 2. __init__.py文件

```python
# 在backend/xxx/__init__.py中，相对导入是允许的
from .yyy import YYY  # ✅ OK
from ..zzz import ZZZ  # ✅ OK
```

#### 3. 同目录导入

```python
# backend/services/xxx.py
# 需要导入同目录的yyy.py
from backend.services.yyy import YYY  # ✅ 推荐
from .yyy import YYY  # ✅ 也OK（相对导入）
```

---

## 🔍 自动检查

### 使用检查工具

```bash
# 检查单个文件
python scripts/check_imports.py backend/api/v1/analytics.py

# 检查整个目录
python scripts/check_imports.py --all backend/

# 集成到pre-commit钩子（自动检查）
pre-commit run check-imports --all-files
```

### Pre-commit钩子配置

在`.pre-commit-config.yaml`中添加：

```yaml
repos:
  - repo: local
    hooks:
      - id: check-imports
        name: 检查导入路径
        entry: python scripts/check_imports.py
        language: system
        files: ^backend/.*\.py$
```

### 安装和使用

```bash
# 安装pre-commit
pip install pre-commit

# 安装钩子
pre-commit install

# 手动运行所有钩子
pre-commit run --all-files

# 运行特定钩子
pre-commit run check-imports --all-files
```

---

## 📏 代码风格指南

### Python代码风格

遵循PEP 8标准，使用以下工具：

```bash
# 格式化代码
black backend/ --line-length=100

# 排序导入
isort backend/ --profile black

# 类型检查
mypy backend/

# 代码质量检查
pylint backend/
```

### 配置文件示例

**pyproject.toml**:

```toml
[tool.black]
line-length = 100
target-version = ['py38']
include = '\.pyi?$'
extend-exclude = '''
/(
  # 默认排除
  \.eggs
  | \.git
  | \.hg
  | \.mypy_cache
  | \.tox
  | \.venv
  | _build
  | buck-out
  | build
  | dist
  # 自定义排除
  | migrations
)/
'''

[tool.isort]
profile = "black"
line_length = 100
known_first_party = ["backend"]

[tool.mypy]
python_version = "3.8"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = false
plugins = ["pydantic.mypy"]

[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false
```

---

## 📝 命名规范

### 文件命名

```python
# ✅ 正确
user_profile.py
api_router.py
cache_manager.py

# ❌ 错误
userProfile.py  # 驼峰命名
APIRouter.py   # 大写开头
```

### 类命名

```python
# ✅ 正确 - PascalCase
class UserProfile:
    pass

class APIRouter:
    pass

# ❌ 错误
class user_profile:  # 小写+下划线
    pass
```

### 函数和变量命名

```python
# ✅ 正确 - snake_case
def get_user_profile():
    pass

user_name = "Alice"

# ❌ 错误
def getUserProfile():  # 驼峰命名
    pass

userName = "Alice"
```

### 常量命名

```python
# ✅ 正确 - UPPER_CASE
MAX_RETRIES = 3
DEFAULT_TIMEOUT = 30
API_BASE_URL = "https://api.example.com"

# ❌ 错误
max_retries = 3  # 应该是大写
```

---

## 🎯 文档字符串规范

### Google风格文档字符串

```python
def calculate_metrics(data: List[Dict]) -> Dict[str, float]:
    """计算系统指标

    Args:
        data: 包含系统运行数据的字典列表

    Returns:
        包含计算结果的字典，键为指标名称，值为指标值

    Raises:
        ValueError: 当输入数据为空时

    Example:
        >>> data = [{"cpu": 80.0, "memory": 60.0}]
        >>> calculate_metrics(data)
        {"avg_cpu": 80.0, "avg_memory": 60.0}
    """
    pass
```

### 类文档字符串

```python
class MetricsCollector:
    """系统指标收集器

    负责收集、聚合和分析系统运行指标

    Attributes:
        metrics_cache: 指标缓存字典
        collection_interval: 收集间隔（秒）

    Example:
        >>> collector = MetricsCollector(interval=60)
        >>> await collector.start()
    """

    def __init__(self, interval: int = 60):
        """初始化指标收集器

        Args:
            interval: 指标收集间隔，默认60秒
        """
        self.collection_interval = interval
        self.metrics_cache = {}
```

---

## 🔒 安全编码规范

### 输入验证

```python
# ✅ 正确 - 验证输入
from pydantic import BaseModel, validator

class UserInput(BaseModel):
    email: str
    age: int

    @validator('email')
    def email_must_be_valid(cls, v):
        if '@' not in v:
            raise ValueError('无效的邮箱地址')
        return v

    @validator('age')
    def age_must_be_positive(cls, v):
        if v < 0:
            raise ValueError('年龄不能为负数')
        return v
```

### SQL注入防护

```python
# ✅ 正确 - 使用参数化查询
async def get_user(user_id: int):
    query = "SELECT * FROM users WHERE id = $1"
    return await db.fetchval(query, user_id)

# ❌ 错误 - SQL注入风险
async def get_user(user_id: int):
    query = f"SELECT * FROM users WHERE id = {user_id}"  # 危险！
    return await db.fetchval(query)
```

### 敏感信息处理

```python
# ✅ 正确 - 不记录敏感信息
logger.info(f"用户登录成功: user_id={user_id}")  # OK

# ❌ 错误 - 泄露密码
logger.info(f"用户登录: {user.email}, {user.password}")  # 危险！
```

---

## 🧪 测试规范

### 测试文件组织

```
tests/
├── api/              # API测试
│   ├── test_analytics.py
│   └── test_evolution.py
├── services/         # 服务测试
│   ├── test_multi_ai.py
│   └── test_comparison.py
└── conftest.py       # pytest配置
```

### 测试命名

```python
# ✅ 正确的测试函数命名
def test_user_profile_creation():
    pass

def test_user_profile_with_invalid_email():
    pass

def test_user_profile_update_success():
    pass
```

### 测试结构

```python
import pytest
from httpx import AsyncClient
from backend.main import app

@pytest.mark.asyncio
async def test_create_user_profile():
    """测试创建用户配置文件"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/user/profile",
            json={"name": "Alice", "email": "alice@example.com"}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Alice"
    assert data["email"] == "alice@example.com"
```

---

## 📊 类型提示规范

### 函数类型提示

```python
# ✅ 正确 - 完整的类型提示
from typing import List, Dict, Optional

def get_users(
    limit: int = 100,
    offset: int = 0,
    filters: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """获取用户列表"""
    pass

# ❌ 错误 - 缺少类型提示
def get_users(limit=100, offset=0, filters=None):
    """获取用户列表"""
    pass
```

### 使用TypedDict

```python
from typing import TypedDict

class UserProfile(TypedDict):
    """用户配置文件类型定义"""
    id: int
    name: str
    email: str
    created_at: str

def process_profile(profile: UserProfile) -> bool:
    """处理用户配置文件"""
    pass
```

---

## 🎨 代码组织规范

### 模块导入顺序

```python
# 1. 标准库导入
import asyncio
import logging
from pathlib import Path

# 2. 第三方库导入
from fastapi import FastAPI
from pydantic import BaseModel

# 3. 本地导入（按字母顺序）
from backend.api.v1 import api_router
from backend.config import Config
from backend.services.xxx import YYY
```

### 类成员顺序

```python
class MyClass:
    """类成员按以下顺序组织"""

    # 1. 类属性
    CLASS_CONSTANT = "value"

    # 2. __init__方法
    def __init__(self):
        self.instance_var = None

    # 3. 公共方法
    def public_method(self):
        pass

    # 4. 保护方法（单下划线）
    def _protected_method(self):
        pass

    # 5. 私有方法（双下划线）
    def __private_method(self):
        pass

    # 6. 特殊方法（魔术方法）
    def __str__(self):
        return str(self.instance_var)
```

---

## 🚀 性能优化规范

### 异步编程

```python
# ✅ 正确 - 使用异步操作
async def fetch_data():
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()

# ❌ 错误 - 在异步函数中使用同步操作
async def fetch_data():
    response = requests.get(url)  # 阻塞事件循环！
    return response.json()
```

### 数据库查询

```python
# ✅ 正确 - 使用连接池
async def get_user(user_id: int):
    async with db_pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM users WHERE id = $1",
            user_id
        )

# ❌ 错误 - N+1查询问题
async def get_users_with_posts():
    users = await db.fetch("SELECT * FROM users")
    result = []
    for user in users:
        # 每个用户都查询一次，导致N+1问题
        posts = await db.fetch(
            "SELECT * FROM posts WHERE user_id = $1",
            user['id']
        )
        result.append({**user, 'posts': posts})
    return result
```

---

## 📋 代码审查清单

提交代码前，请确认：

- [ ] 所有导入使用完整路径（`from backend.xxx`）
- [ ] 代码通过类型检查（mypy）
- [ ] 代码通过格式化检查（black, isort）
- [ ] 添加了适当的类型提示
- [ ] 添加了文档字符串
- [ ] 添加了单元测试
- [ ] 所有测试通过
- [ ] 不存在安全漏洞
- [ ] 性能影响可接受
- [ ] 没有硬编码的配置值

---

## 🔄 代码重构原则

### 重构时机

- 代码重复超过3次 → 提取函数/类
- 函数超过50行 → 拆分函数
- 类超过300行 → 拆分类
- 嵌套超过3层 → 提取变量/函数
- 参数超过5个 → 使用参数对象

### 重构步骤

1. 编写测试保护现有功能
2. 小步重构，频繁运行测试
3. 每次只改一个方面
4. 保持代码可运行状态

---

**众智混元，万法灵通** ⚡🚀

本规范会持续更新，请关注最新版本。
