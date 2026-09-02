from __future__ import annotations

import asyncio
import inspect
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

logger = logging.getLogger("sara.agent.tools")


ToolHandler = Callable[..., Any]


@dataclass
class ToolDefinition:
    """
    SARA uchun bitta tool ta'rifi.

    name:
        Tool nomi.

    description:
        AI/Agent uchun tool nima qilishini tushuntiradi.

    handler:
        Tool chaqirilganda bajariladigan funksiya.

    enabled:
        Tool hozir ishlatilishi mumkinmi.

    dangerous:
        Keyinchalik xavfli actionlarni alohida himoyalash uchun.

    timeout:
        Tool maksimal qancha sekund ishlashi mumkin.

    metadata:
        Qo'shimcha ma'lumotlar.
    """

    name: str
    description: str
    handler: ToolHandler

    enabled: bool = True
    dangerous: bool = False
    timeout: float = 30.0

    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    """
    Tool bajarilgandan keyingi standart natija.
    """

    success: bool
    tool_name: str

    result: Any = None
    error: str | None = None

    duration_seconds: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class ToolRegistry:
    """
    SARA AI Tool Registry.

    Vazifasi:

    Brain
       ↓
    Planner
       ↓
    Executor
       ↓
    ToolRegistry
       ↓
    kerakli tool

    Barcha tool chaqiruvlari shu markaz orqali o'tadi.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

        self.total_calls = 0
        self.successful_calls = 0
        self.failed_calls = 0

        self._lock = asyncio.Lock()

    # =========================================================
    # REGISTER
    # =========================================================

    def register(
        self,
        name: str,
        description: str,
        handler: ToolHandler,
        *,
        enabled: bool = True,
        dangerous: bool = False,
        timeout: float = 30.0,
        metadata: dict[str, Any] | None = None,
        overwrite: bool = False,
    ) -> ToolDefinition:
        """
        Yangi tool qo'shadi.
        """

        normalized_name = self._normalize_name(name)

        if not normalized_name:
            raise ValueError("Tool name bo'sh bo'lishi mumkin emas.")

        if not callable(handler):
            raise TypeError(
                f"Tool handler callable bo'lishi kerak: {normalized_name}"
            )

        if timeout <= 0:
            raise ValueError("Tool timeout 0 dan katta bo'lishi kerak.")

        if (
            normalized_name in self._tools
            and not overwrite
        ):
            raise ValueError(
                f"Tool allaqachon mavjud: {normalized_name}"
            )

        tool = ToolDefinition(
            name=normalized_name,
            description=description.strip(),
            handler=handler,
            enabled=enabled,
            dangerous=dangerous,
            timeout=timeout,
            metadata=dict(metadata or {}),
        )

        self._tools[normalized_name] = tool

        logger.info(
            "Tool registered | name=%s | enabled=%s | dangerous=%s",
            normalized_name,
            enabled,
            dangerous,
        )

        return tool

    def unregister(self, name: str) -> bool:
        """
        Toolni registry'dan o'chiradi.
        """

        normalized_name = self._normalize_name(name)

        if normalized_name not in self._tools:
            return False

        self._tools.pop(normalized_name, None)

        logger.info(
            "Tool unregistered | name=%s",
            normalized_name,
        )

        return True

    # =========================================================
    # GET
    # =========================================================

    def get(self, name: str) -> ToolDefinition | None:
        """
        Toolni nomi orqali oladi.
        """

        normalized_name = self._normalize_name(name)

        return self._tools.get(normalized_name)

    def exists(self, name: str) -> bool:
        return self.get(name) is not None

    def is_enabled(self, name: str) -> bool:
        tool = self.get(name)

        if tool is None:
            return False

        return tool.enabled

    def list_tools(
        self,
        *,
        enabled_only: bool = False,
    ) -> list[ToolDefinition]:
        """
        Registry'dagi tool'larni qaytaradi.
        """

        tools = list(self._tools.values())

        if enabled_only:
            tools = [
                tool
                for tool in tools
                if tool.enabled
            ]

        return tools

    def tool_names(
        self,
        *,
        enabled_only: bool = False,
    ) -> list[str]:
        return [
            tool.name
            for tool in self.list_tools(
                enabled_only=enabled_only,
            )
        ]

    # =========================================================
    # ENABLE / DISABLE
    # =========================================================

    def enable(self, name: str) -> bool:
        tool = self.get(name)

        if tool is None:
            return False

        tool.enabled = True

        logger.info(
            "Tool enabled | name=%s",
            tool.name,
        )

        return True

    def disable(self, name: str) -> bool:
        tool = self.get(name)

        if tool is None:
            return False

        tool.enabled = False

        logger.info(
            "Tool disabled | name=%s",
            tool.name,
        )

        return True

    # =========================================================
    # EXECUTE
    # =========================================================

    async def execute(
        self,
        name: str,
        *,
        arguments: dict[str, Any] | None = None,
        allow_dangerous: bool = False,
    ) -> ToolResult:
        """
        Toolni xavfsiz tarzda ishga tushiradi.
        """

        started = time.monotonic()

        normalized_name = self._normalize_name(name)

        self.total_calls += 1

        tool = self._tools.get(normalized_name)

        if tool is None:
            self.failed_calls += 1

            return ToolResult(
                success=False,
                tool_name=normalized_name,
                error="tool_not_found",
                duration_seconds=time.monotonic() - started,
            )

        if not tool.enabled:
            self.failed_calls += 1

            return ToolResult(
                success=False,
                tool_name=normalized_name,
                error="tool_disabled",
                duration_seconds=time.monotonic() - started,
            )

        if tool.dangerous and not allow_dangerous:
            self.failed_calls += 1

            logger.warning(
                "Dangerous tool blocked | name=%s",
                normalized_name,
            )

            return ToolResult(
                success=False,
                tool_name=normalized_name,
                error="dangerous_tool_blocked",
                duration_seconds=time.monotonic() - started,
            )

        arguments = dict(arguments or {})

        try:
            async with self._lock:
                result = await self._call_handler(
                    tool,
                    arguments,
                )

            self.successful_calls += 1

            duration = time.monotonic() - started

            logger.info(
                "Tool executed successfully | name=%s | duration=%.3fs",
                normalized_name,
                duration,
            )

            return ToolResult(
                success=True,
                tool_name=normalized_name,
                result=result,
                duration_seconds=duration,
            )

        except asyncio.TimeoutError:
            self.failed_calls += 1

            duration = time.monotonic() - started

            logger.warning(
                "Tool timeout | name=%s | timeout=%s",
                normalized_name,
                tool.timeout,
            )

            return ToolResult(
                success=False,
                tool_name=normalized_name,
                error="tool_timeout",
                duration_seconds=duration,
            )

        except TypeError as exc:
            self.failed_calls += 1

            duration = time.monotonic() - started

            logger.exception(
                "Tool argument error | name=%s",
                normalized_name,
            )

            return ToolResult(
                success=False,
                tool_name=normalized_name,
                error=f"invalid_arguments: {exc}",
                duration_seconds=duration,
            )

        except Exception as exc:
            self.failed_calls += 1

            duration = time.monotonic() - started

            logger.exception(
                "Tool execution failed | name=%s",
                normalized_name,
            )

            return ToolResult(
                success=False,
                tool_name=normalized_name,
                error=str(exc),
                duration_seconds=duration,
            )

    async def _call_handler(
        self,
        tool: ToolDefinition,
        arguments: dict[str, Any],
    ) -> Any:
        """
        Sync yoki async handler bilan ishlaydi.
        """

        handler = tool.handler

        if inspect.iscoroutinefunction(handler):
            return await asyncio.wait_for(
                handler(**arguments),
                timeout=tool.timeout,
            )

        loop = asyncio.get_running_loop()

        return await asyncio.wait_for(
            loop.run_in_executor(
                None,
                lambda: handler(**arguments),
            ),
            timeout=tool.timeout,
        )

    # =========================================================
    # DESCRIPTION FOR AI
    # =========================================================

    def build_tool_context(
        self,
        *,
        enabled_only: bool = True,
    ) -> str:
        """
        AI context uchun tool ro'yxatini text ko'rinishida yaratadi.
        """

        tools = self.list_tools(
            enabled_only=enabled_only,
        )

        if not tools:
            return (
                "SARA TOOLS\n"
                "===========\n"
                "Hozircha foydalanish mumkin bo'lgan tool mavjud emas."
            )

        lines = [
            "SARA AVAILABLE TOOLS",
            "====================",
        ]

        for tool in tools:
            danger = " [DANGEROUS]" if tool.dangerous else ""

            lines.append(
                f"- {tool.name}{danger}: "
                f"{tool.description}"
            )

        return "\n".join(lines)

    # =========================================================
    # HEALTH
    # =========================================================

    def health(self) -> dict[str, Any]:
        tools = self.list_tools()

        enabled = sum(
            1
            for tool in tools
            if tool.enabled
        )

        dangerous = sum(
            1
            for tool in tools
            if tool.dangerous
        )

        return {
            "total_tools": len(tools),
            "enabled_tools": enabled,
            "disabled_tools": len(tools) - enabled,
            "dangerous_tools": dangerous,
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
        }

    def stats(self) -> dict[str, Any]:
        return self.health()

    # =========================================================
    # INTERNAL
    # =========================================================

    @staticmethod
    def _normalize_name(name: str) -> str:
        return str(name).strip().lower().replace(" ", "_")


# =============================================================
# GLOBAL REGISTRY
# =============================================================

tool_registry = ToolRegistry()


# =============================================================
# BUILT-IN SAFE TOOL
# =============================================================

async def _health_tool() -> dict[str, Any]:
    """
    Registry health tekshiruvi.
    """

    return tool_registry.health()


tool_registry.register(
    name="tool_health",
    description=(
        "SARA tool tizimining holatini tekshiradi."
    ),
    handler=_health_tool,
    enabled=True,
    dangerous=False,
    timeout=5.0,
      )
