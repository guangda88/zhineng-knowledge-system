"""保密数据安全搜索服务

提供安全的文档搜索功能，确保保密数据只被授权用户访问。

核心功能：
- 用户权限验证
- 安全级别过滤
- 访问审计日志
- 临时授权管理
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import asyncpg

logger = logging.getLogger(__name__)


class AccessControlError(Exception):
    """访问控制错误"""

    def __init__(self, message: str, reason: str = ""):
        self.message = message
        self.reason = reason
        super().__init__(message)


class SecureSearchService:
    """
    安全搜索服务

    确保文档搜索结果符合用户权限要求，所有访问都有审计日志。
    """

    # 安全级别定义
    SECURITY_LEVELS = {
        "public": 0,  # 公开 - 所有人可访问
        "internal": 1,  # 内部 - 需要内部权限
        "confidential": 2,  # 保密 - 需要保密权限
        "restricted": 3,  # 限制 - 需要限制权限（最高级别）
    }

    def __init__(self, db_url: str):
        """
        初始化安全搜索服务

        Args:
            db_url: PostgreSQL 数据库连接 URL
        """
        self.db_url = db_url
        self._pool: Optional[asyncpg.Pool] = None

    async def _get_pool(self) -> asyncpg.Pool:
        """获取连接池"""
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                self.db_url, min_size=2, max_size=10, timeout=10
            )
        return self._pool

    async def close(self):
        """关闭连接池"""
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def check_user_permission(
        self, user_id: str, required_level: str = "public"
    ) -> Dict[str, Any]:
        """
        检查用户是否有指定级别的访问权限

        Args:
            user_id: 用户 ID
            required_level: 需要的安全级别

        Returns:
            权限检查结果
        """
        if required_level == "public":
            return {
                "allowed": True,
                "user_id": user_id,
                "required_level": required_level,
                "actual_level": "public",
                "reason": "public access requires no permission",
            }

        pool = await self._get_pool()

        async with pool.acquire() as conn:
            # 检查用户权限
            row = await conn.fetchrow(
                """
                SELECT up.security_level, up.username, up.is_active, up.expires_at
                FROM user_permissions up
                WHERE up.user_id = $1
                  AND up.is_active = TRUE
                  AND (up.expires_at IS NULL OR up.expires_at > NOW())
                ORDER BY
                    CASE up.security_level
                        WHEN 'restricted' THEN 1
                        WHEN 'confidential' THEN 2
                        WHEN 'internal' THEN 3
                    END
                LIMIT 1
            """,
                user_id,
            )

            # 检查临时授权
            temp_grant = await conn.fetchrow(
                """
                SELECT tag.security_level, tag.expires_at, tag.access_count, tag.max_access_count
                FROM temporary_access_grants tag
                WHERE tag.user_id = $1
                  AND tag.is_active = TRUE
                  AND tag.expires_at > NOW()
                  AND (tag.max_access_count IS NULL OR tag.access_count < tag.max_access_count)
                ORDER BY
                    CASE tag.security_level
                        WHEN 'restricted' THEN 1
                        WHEN 'confidential' THEN 2
                        WHEN 'internal' THEN 3
                    END
                LIMIT 1
            """,
                user_id,
            )

            # 确定用户实际级别
            user_level = "public"
            if row:
                user_level = row["security_level"]
            if temp_grant:
                temp_level = temp_grant["security_level"]
                if self.SECURITY_LEVELS.get(temp_level, 0) > self.SECURITY_LEVELS.get(
                    user_level, 0
                ):
                    user_level = temp_level

            # 权限比较
            required_order = self.SECURITY_LEVELS.get(required_level, 0)
            user_order = self.SECURITY_LEVELS.get(user_level, 0)

            allowed = user_order >= required_order

            return {
                "allowed": allowed,
                "user_id": user_id,
                "required_level": required_level,
                "actual_level": user_level,
                "reason": (
                    "user has sufficient permission" if allowed else "insufficient permission level"
                ),
            }

    async def log_access(
        self,
        user_id: str,
        document_id: Optional[int],
        security_level: str,
        action: str,
        result: str = "success",
        denial_reason: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> int:
        """
        记录访问日志

        Args:
            user_id: 用户 ID
            document_id: 文档 ID（可选）
            security_level: 安全级别
            action: 操作类型
            result: 操作结果
            denial_reason: 拒绝原因
            ip_address: IP 地址
            user_agent: 用户代理

        Returns:
            日志 ID
        """
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            log_id = await conn.fetchval(
                """
                INSERT INTO access_audit_log (
                    user_id, document_id, security_level,
                    action, result, denial_reason,
                    ip_address, user_agent
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id
            """,
                user_id,
                document_id,
                security_level,
                action,
                result,
                denial_reason,
                ip_address,
                user_agent,
            )

            return int(log_id)

    async def search_documents(
        self,
        user_id: str,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10,
        offset: int = 0,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        安全搜索文档

        只返回用户有权限访问的文档，并记录访问日志。

        Args:
            user_id: 用户 ID
            query: 搜索关键词
            filters: 过滤条件
            limit: 返回数量限制
            offset: 偏移量
            ip_address: IP 地址
            user_agent: 用户代理

        Returns:
            搜索结果
        """
        pool = await self._get_pool()

        # 检查用户权限
        perm_check = await self.check_user_permission(user_id, "public")
        user_max_level = perm_check["actual_level"]
        user_level_order = self.SECURITY_LEVELS.get(user_max_level, 0)

        async with pool.acquire() as conn:
            # 构建安全查询 - 只返回用户有权限访问的文档
            # 1. 公开文档全部返回
            # 2. 保密文档只返回用户有权限的级别

            # 构建基础查询
            base_query = """
                SELECT d.id, d.title, d.file_path, d.category,
                       d.qigong_dims, d.created_at
                FROM documents d
                WHERE d.category = '气功'
                  AND (
                    -- 公开文档（不在保密表中或级别为public）
                    NOT EXISTS (
                        SELECT 1 FROM documents_confidential dc
                        WHERE dc.document_id = d.id
                    )
                    OR
                    -- 用户有权限的保密文档
                    EXISTS (
                        SELECT 1 FROM documents_confidential dc
                        WHERE dc.document_id = d.id
                          AND $2 <= (
                            CASE dc.security_level
                                WHEN 'restricted' THEN 3
                                WHEN 'confidential' THEN 2
                                WHEN 'internal' THEN 1
                                ELSE 0
                            END
                      )
                  )
            """

            # 添加搜索条件
            params = [query, user_level_order]
            if query:
                base_query += (
                    " AND (d.title ILIKE $"
                    + str(len(params) + 1)
                    + " OR d.content ILIKE $"
                    + str(len(params) + 2)
                    + ")"
                )
                params.extend([f"%{query}%", f"%{query}%"])

            # 添加过滤条件
            if filters:
                allowed_dims = {"功法", "流派", "理论", "实践", "养生", "哲学", "经典", "方法"}
                for key, value in filters.items():
                    if key.startswith("dim_") and value:
                        dim_name = key[4:]
                        if dim_name not in allowed_dims:
                            logger.warning(f"Rejected disallowed dimension filter: {dim_name}")
                            continue
                        base_query += (
                            " AND d.qigong_dims->>$"
                            + str(len(params) + 1)
                            + " = $"
                            + str(len(params) + 2)
                        )
                        params.extend([dim_name, value])

            # 统计总数
            count_query = f"SELECT COUNT(*) FROM ({base_query}) AS subq"
            total_count = await conn.fetchval(count_query, *params)

            # 获取结果
            base_query += (
                " ORDER BY d.created_at DESC LIMIT $"
                + str(len(params) + 1)
                + " OFFSET $"
                + str(len(params) + 2)
            )
            params.extend([limit, offset])

            rows = await conn.fetch(base_query, *params)

            results = [
                {
                    "id": r["id"],
                    "title": r["title"],
                    "file_path": r["file_path"],
                    "category": r["category"],
                    "qigong_dims": r["qigong_dims"],
                    "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                }
                for r in rows
            ]

            # 记录搜索日志
            await self.log_access(
                user_id=user_id,
                document_id=None,
                security_level="public",
                action="search",
                result="success",
                ip_address=ip_address,
                user_agent=user_agent,
            )

            return {
                "results": results,
                "total": total_count,
                "limit": limit,
                "offset": offset,
                "user_max_level": user_max_level,
            }

    async def get_document(
        self,
        user_id: str,
        document_id: int,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        获取文档详情（带权限检查）

        Args:
            user_id: 用户 ID
            document_id: 文档 ID
            ip_address: IP 地址
            user_agent: 用户代理

        Returns:
            文档详情

        Raises:
            AccessControlError: 用户无权限访问
        """
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            # 获取文档及其安全级别
            doc = await conn.fetchrow(
                """
                SELECT d.id, d.title, d.file_path, d.content,
                       d.category, d.qigong_dims, d.created_at,
                       COALESCE(dc.security_level, 'public') AS security_level
                FROM documents d
                LEFT JOIN documents_confidential dc ON d.id = dc.document_id
                WHERE d.id = $1
            """,
                document_id,
            )

            if not doc:
                raise AccessControlError("Document not found", "document_id")

            security_level = doc["security_level"]

            # 检查权限
            perm_check = await self.check_user_permission(user_id, security_level)

            if not perm_check["allowed"]:
                # 记录拒绝日志
                await self.log_access(
                    user_id=user_id,
                    document_id=document_id,
                    security_level=security_level,
                    action="view",
                    result="denied",
                    denial_reason=perm_check["reason"],
                    ip_address=ip_address,
                    user_agent=user_agent,
                )

                raise AccessControlError(
                    f"Access denied to document {document_id}", perm_check["reason"]
                )

            # 记录成功访问
            await self.log_access(
                user_id=user_id,
                document_id=document_id,
                security_level=security_level,
                action="view",
                result="success",
                ip_address=ip_address,
                user_agent=user_agent,
            )

            return {
                "id": doc["id"],
                "title": doc["title"],
                "file_path": doc["file_path"],
                "content": doc.get("content"),
                "category": doc["category"],
                "qigong_dims": doc["qigong_dims"],
                "security_level": security_level,
                "created_at": doc["created_at"].isoformat() if doc["created_at"] else None,
            }

    async def grant_permission(
        self,
        admin_user: str,
        target_user: str,
        target_username: str,
        security_level: str,
        expires_at: Optional[datetime] = None,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        授予用户权限（需要超级管理员权限）

        Args:
            admin_user: 执行操作的管理员用户
            target_user: 目标用户 ID
            target_username: 目标用户名
            security_level: 授予的安全级别
            expires_at: 过期时间（可选）
            reason: 授权原因

        Returns:
            授权结果
        """
        # 验证管理员权限
        admin_check = await self.check_user_permission(admin_user, "restricted")
        if not admin_check["allowed"]:
            raise AccessControlError(
                "Only administrators with restricted access can grant permissions",
                "insufficient_admin_privileges",
            )

        pool = await self._get_pool()

        async with pool.acquire() as conn:
            # 授予权限
            perm_id = await conn.fetchval(
                """
                INSERT INTO user_permissions (
                    user_id, username, security_level,
                    granted_by, expires_at, reason
                ) VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (user_id, security_level)
                DO UPDATE SET
                    is_active = TRUE,
                    expires_at = COALESCE($5, user_permissions.expires_at),
                    granted_by = $4,
                    reason = $6,
                    granted_at = NOW()
                RETURNING id
            """,
                target_user,
                target_username,
                security_level,
                admin_user,
                expires_at,
                reason,
            )

            # 记录日志
            await self.log_access(
                user_id=admin_user,
                document_id=None,
                security_level=security_level,
                action="grant_permission",
                result="success",
            )

            return {
                "success": True,
                "permission_id": perm_id,
                "user_id": target_user,
                "security_level": security_level,
                "expires_at": expires_at.isoformat() if expires_at else None,
            }

    async def create_temporary_grant(
        self,
        admin_user: str,
        security_level: str,
        expires_hours: int = 24,
        max_access_count: Optional[int] = None,
        document_ids: Optional[List[int]] = None,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        创建临时授权码

        Args:
            admin_user: 管理员用户
            security_level: 安全级别
            expires_hours: 有效期（小时）
            max_access_count: 最大访问次数（可选）
            document_ids: 限定文档ID列表（可选，为空表示全部该级别文档）
            reason: 原因

        Returns:
            授权码信息
        """
        # 验证管理员权限
        admin_check = await self.check_user_permission(admin_user, "restricted")
        if not admin_check["allowed"]:
            raise AccessControlError(
                "Only administrators can create temporary grants", "insufficient_admin_privileges"
            )

        # 生成授权码
        import secrets

        grant_code = secrets.token_urlsafe(16)

        pool = await self._get_pool()

        async with pool.acquire() as conn:
            expires_at = datetime.now() + timedelta(hours=expires_hours)

            grant_id = await conn.fetchval(
                """
                INSERT INTO temporary_access_grants (
                    grant_code, security_level, document_ids,
                    granted_by, expires_at, max_access_count, reason
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
            """,
                grant_code,
                security_level,
                document_ids,
                admin_user,
                expires_at,
                max_access_count,
                reason,
            )

            return {
                "success": True,
                "grant_id": grant_id,
                "grant_code": grant_code,
                "security_level": security_level,
                "expires_at": expires_at.isoformat(),
                "max_access_count": max_access_count,
            }

    async def use_temporary_grant(
        self, grant_code: str, user_id: str, username: str
    ) -> Dict[str, Any]:
        """
        使用临时授权码

        Args:
            grant_code: 授权码
            user_id: 用户 ID
            username: 用户名

        Returns:
            使用结果
        """
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            # 获取授权信息
            grant = await conn.fetchrow(
                """
                SELECT id, grant_code, security_level, document_ids,
                       expires_at, max_access_count, access_count, is_active
                FROM temporary_access_grants
                WHERE grant_code = $1
                  AND is_active = TRUE
                  AND expires_at > NOW()
            """,
                grant_code,
            )

            if not grant:
                raise AccessControlError("Invalid or expired grant code", "grant_not_found")

            # 检查访问次数
            if (
                grant["max_access_count"] is not None
                and grant["access_count"] >= grant["max_access_count"]
            ):
                raise AccessControlError(
                    "Grant code has reached maximum access count", "grant_exhausted"
                )

            # 创建用户权限
            perm_id = await conn.fetchval(
                """
                INSERT INTO user_permissions (
                    user_id, username, security_level,
                    granted_by, expires_at, reason
                ) VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (user_id, security_level)
                DO UPDATE SET
                    is_active = TRUE,
                    expires_at = $5,
                    granted_at = NOW()
                RETURNING id
            """,
                user_id,
                username,
                grant["security_level"],
                f"temp_grant:{grant_code}",
                grant["expires_at"],
                "Temporary access via grant code",
            )

            # 更新访问计数
            await conn.execute(
                """
                UPDATE temporary_access_grants
                SET access_count = access_count + 1
                WHERE id = $1
            """,
                grant["id"],
            )

            return {
                "success": True,
                "permission_id": perm_id,
                "security_level": grant["security_level"],
                "expires_at": grant["expires_at"].isoformat(),
            }

    async def get_access_statistics(
        self, user_id: Optional[str] = None, days: int = 30
    ) -> Dict[str, Any]:
        """
        获取访问统计信息

        Args:
            user_id: 用户 ID（为空则统计全部）
            days: 统计天数

        Returns:
            统计信息
        """
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            since_date = datetime.now() - timedelta(days=days)

            if user_id:
                # 单用户统计
                rows = await conn.fetch(
                    """
                    SELECT
                        action,
                        security_level,
                        result,
                        COUNT(*) AS count
                    FROM access_audit_log
                    WHERE user_id = $1
                      AND access_time >= $2
                    GROUP BY action, security_level, result
                    ORDER BY count DESC
                """,
                    user_id,
                    since_date,
                )
            else:
                # 全局统计
                rows = await conn.fetch(
                    """
                    SELECT
                        action,
                        security_level,
                        result,
                        COUNT(*) AS count
                    FROM access_audit_log
                    WHERE access_time >= $1
                    GROUP BY action, security_level, result
                    ORDER BY count DESC
                """,
                    since_date,
                )

            return {
                "period_days": days,
                "since": since_date.isoformat(),
                "statistics": [dict(r) for r in rows],
            }

    async def revoke_permission(
        self, admin_user: str, target_user: str, security_level: str
    ) -> Dict[str, Any]:
        """
        撤销用户权限

        Args:
            admin_user: 管理员用户
            target_user: 目标用户 ID
            security_level: 安全级别

        Returns:
            撤销结果
        """
        # 验证管理员权限
        admin_check = await self.check_user_permission(admin_user, "restricted")
        if not admin_check["allowed"]:
            raise AccessControlError(
                "Only administrators can revoke permissions", "insufficient_admin_privileges"
            )

        pool = await self._get_pool()

        async with pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE user_permissions
                SET is_active = FALSE
                WHERE user_id = $1
                  AND security_level = $2
                  AND is_active = TRUE
            """,
                target_user,
                security_level,
            )

            # 记录日志
            await self.log_access(
                user_id=admin_user,
                document_id=None,
                security_level=security_level,
                action="revoke_permission",
                result="success",
            )

            return {
                "success": True,
                "target_user": target_user,
                "security_level": security_level,
                "rows_affected": int(result.split()[-1]) if result else 0,
            }


# 便捷函数
async def get_secure_search_service(db_url: str) -> SecureSearchService:
    """
    获取安全搜索服务实例

    Args:
        db_url: 数据库连接 URL

    Returns:
        SecureSearchService 实例
    """
    return SecureSearchService(db_url)
