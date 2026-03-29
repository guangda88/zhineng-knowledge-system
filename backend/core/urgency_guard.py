"""
紧急问题守卫
检查系统是否处于紧急状态，拦截不合适的操作
"""
import asyncio
import logging
import subprocess
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class UrgencyGuard:
    """
    紧急问题守卫

    负责检查系统是否处于紧急状态，如果是，则只允许修复紧急问题的操作。

    紧急问题包括：
    1. 系统健康检查失败
    2. API容器处于unhealthy状态
    3. 存在未定义变量等代码错误
    """

    # 允许的紧急操作
    ALLOWED_URGENT_ACTIONS = [
        "fix_urgent_issue",
        "debug_system",
        "restart_service",
        "check_logs",
        "view_status"
    ]

    # 阻止的非紧急操作
    BLOCKED_NON_URGENT_ACTIONS = [
        "add_tests",
        "refactor_code",
        "modify_documentation",
        "improve_coverage",
        "modify_rules",
        "generate_report"
    ]

    def __init__(self):
        """初始化守卫"""
        self._emergency_cache = None
        self._cache_time = None
        self._cache_ttl = 30  # 缓存30秒

        logger.info("UrgencyGuard initialized")

    async def check_and_intercept(self, action_type: str, action_data: Dict[str, Any]):
        """
        检查并拦截操作

        如果系统处于紧急状态，只允许修复紧急问题的操作。

        Args:
            action_type: 操作类型
            action_data: 操作数据

        Raises:
            PermissionError: 如果操作被拦截
        """
        if self.is_emergency_mode():
            logger.warning(f"System in emergency mode, checking action: {action_type}")

            if action_type in self.BLOCKED_NON_URGENT_ACTIONS:
                current_emergencies = self.get_current_emergencies()
                raise PermissionError(
                    f"违反规则 13.1: 系统处于紧急状态（{', '.join(current_emergencies)}）。\n"
                    f"只允许修复紧急问题，禁止执行 '{action_type}'。\n\n"
                    f"允许的操作: {', '.join(self.ALLOWED_URGENT_ACTIONS)}\n"
                    f"请优先修复紧急问题，然后再执行其他操作。"
                )

            logger.info(f"Action {action_type} allowed in emergency mode")

    def is_emergency_mode(self) -> bool:
        """
        检查系统是否处于紧急状态

        Returns:
            bool: 如果有任一紧急问题，返回True
        """
        # 使用缓存避免频繁检查
        if self._emergency_cache is not None:
            cache_age = asyncio.get_event_loop().time() - self._cache_time
            if cache_age < self._cache_ttl:
                return self._emergency_cache

        # 执行检查
        emergencies = self._check_all_emergencies()
        is_emergency = len(emergencies) > 0

        # 更新缓存
        self._emergency_cache = is_emergency
        self._cache_time = asyncio.get_event_loop().time()

        if is_emergency:
            logger.warning(f"Emergency mode activated: {emergencies}")

        return is_emergency

    def get_current_emergencies(self) -> List[str]:
        """
        获取当前紧急问题列表

        Returns:
            list: 紧急问题名称列表
        """
        return self._check_all_emergencies()

    def _check_all_emergencies(self) -> List[str]:
        """
        检查所有紧急问题

        Returns:
            list: 存在的紧急问题列表
        """
        emergencies = []

        # 检查1: 系统健康检查
        if self._check_system_health():
            emergencies.append("system_health_check_failed")

        # 检查2: API容器状态
        if self._check_api_container():
            emergencies.append("api_container_unhealthy")

        # 检查3: 导入错误
        if self._check_import_errors():
            emergencies.append("import_errors_detected")

        return emergencies

    def _check_system_health(self) -> bool:
        """
        检查系统健康状态

        Returns:
            bool: 如果健康检查失败，返回True（表示有紧急问题）
        """
        try:
            result = subprocess.run(
                ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                 "http://localhost:8000/health"],
                capture_output=True,
                text=True,
                timeout=3
            )

            # 如果不是200，认为有紧急问题
            return result.stdout.strip() != "200"

        except subprocess.TimeoutExpired:
            logger.warning("Health check timeout")
            return True
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return True

    def _check_api_container(self) -> bool:
        """
        检查API容器状态

        Returns:
            bool: 如果容器unhealthy，返回True（表示有紧急问题）
        """
        try:
            result = subprocess.run(
                ["docker", "ps", "--filter", "name=zhineng-api",
                 "--format", "{{.Status}}"],
                capture_output=True,
                text=True,
                timeout=3
            )

            output = result.stdout.strip()

            # 如果包含unhealthy，认为有紧急问题
            return "unhealthy" in output.lower()

        except subprocess.TimeoutExpired:
            logger.warning("Docker check timeout")
            return False  # 超时不认为是紧急问题
        except Exception as e:
            logger.warning(f"Docker check failed: {e}")
            return False

    def _check_import_errors(self) -> bool:
        """
        检查导入错误

        Returns:
            bool: 如果有导入错误，返回True（表示有紧急问题）
        """
        try:
            result = subprocess.run(
                ["python", "-m", "flake8", "backend", "--select=F821"],
                capture_output=True,
                text=True,
                timeout=10,
                cwd="/home/ai/zhineng-knowledge-system"
            )

            # 如果有输出，说明有导入错误
            return len(result.stdout.strip()) > 0

        except subprocess.TimeoutExpired:
            logger.warning("Flake8 check timeout")
            return False
        except Exception as e:
            logger.warning(f"Flake8 check failed: {e}")
            return False

    def get_allowed_actions(self) -> List[str]:
        """获取允许的紧急操作列表"""
        return self.ALLOWED_URGENT_ACTIONS.copy()

    def get_blocked_actions(self) -> List[str]:
        """获取阻止的非紧急操作列表"""
        return self.BLOCKED_NON_URGENT_ACTIONS.copy()
