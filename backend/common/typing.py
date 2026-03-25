"""类型定义模块

定义项目通用的类型别名，提高代码可读性和复用性。
"""

from typing import Any, Dict, List, Optional

# ========== 通用类型别名 ==========

# JSON响应类型
JSONResponse = Dict[str, Any]

# 文档记录类型
DocumentRecord = Dict[str, Any]

# 文档列表类型
DocumentList = List[Dict[str, Any]]

# API结果类型
APIResult = Dict[str, Any]

# 会话ID类型
SessionID = str

# 分类类型
Category = str

# 查询结果类型
QueryResult = Dict[str, Any]

# 搜索结果类型
SearchResult = Dict[str, Any]

# 健康检查结果类型
HealthStatus = Dict[str, Any]

# 统计信息类型
Stats = Dict[str, Any]


# ========== 常用类型组合 ==========

class OptionalDict:
    """可选字典类型的便捷标记"""
    pass


class TypedResponse:
    """带类型的响应"""
    pass
