from __future__ import annotations

import asyncio
import inspect
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable


logger = logging.getLogger("sara.agent.tools.registry")


ToolHandler = Callable[..., Awaitable[Any]]


@dataclass
class ToolDefinition:
    name: str
    description: str
    handler: ToolHandler
    enabled: bool = True
    dangerous: bool = False
    timeout: float = 30.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    success: bool
    tool_name: str
    result: Any = None
    error: str | None = None
    duration_seconds: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "tool_name": self.tool_name,
            "result": self.result,
            "error": self.error,
            "duration_seconds": self.duration_seconds,
            "metadata": self.metadata,
        }


class ToolRegistry:
    """
    SARA AI Tool Registry.

    ToolDefinition obyektlarini qabul qiladi:

        registry.register(
            ToolDefinition(
                name="memory",
                description="...",
                handler=handler,
            )
        )

    Shu bilan birga eski uslubni ham qo‘llab-quvvatlaydi:

        registry.register(
            "memory",
            "description",
            handler,
        )
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    # ========================================================
    # REGISTER
    # ========================================================

    def register(
        self,
        tool: ToolDefinition | str,
        description: str | None = None,
        handler: ToolHandler | None = None,
        *,
        enabled: bool = True,
        dangerous: bool = False,
        timeout: float = 30.0,
        metadata: dict[str, Any] | None = None,
    ) -> ToolDefinition:

        # ----------------------------------------------------
        # ToolDefinition obyektidan ro‘yxatdan o‘tkazish
        # ----------------------------------------------------

        if isinstance(tool, ToolDefinition):

            definition = tool

        # ----------------------------------------------------
        # Eski API:
        #
        # register(
        #     "name",
        #     "description",
        #     handler
        # )
        # ----------------------------------------------------

        else:

            name = str(tool or "").strip()

            if not name:
                raise ValueError(
                    "Tool name cannot be empty."
                )

            if not description:
                raise ValueError(
                    f"Tool description is required: {name}"
                )

            if handler is None:
                raise ValueError(
                    f"Tool handler is required: {name}"
                )

            if not callable(handler):
                raise TypeError(
                    f"Tool handler is not callable: {name}"
                )

            definition = ToolDefinition(
                name=name,
                description=str(description),
                handler=handler,
                enabled=enabled,
                dangerous=dangerous,
                timeout=float(timeout),
                metadata=dict(metadata or {}),
            )

        # ----------------------------------------------------
        # Validation
        # ----------------------------------------------------

        name = str(
            definition.name or ""
        ).strip()

        if not name:
            raise ValueError(
                "Tool name cannot be empty."
            )

        if not callable(
            definition.handler
        ):
            raise TypeError(
                f"Tool handler is not callable: {name}"
            )

        definition.name = name

        if not definition.description:
            definition.description = (
                f"SARA AI tool: {name}"
            )

        definition.timeout = max(
            0.1,
            float(definition.timeout),
        )

        self._tools[name] = definition

        logger.info(
            "Tool registered | name=%s | enabled=%s | dangerous=%s",
            name,
            definition.enabled,
            definition.dangerous,
        )

        return definition

    # ========================================================
    # UNREGISTER
    # ========================================================

    def unregister(
        self,
        name: str,
    ) -> bool:

        name = str(name or "").strip()

        if name in self._tools:
            del self._tools[name]

            logger.info(
                "Tool unregistered | name=%s",
                name,
            )

            return True

        return False

    # ========================================================
    # GET
    # ========================================================

    def get(
        self,
        name: str,
    ) -> ToolDefinition | None:

        return self._tools.get(
            str(name or "").strip()
        )

    # ========================================================
    # EXISTS
    # ========================================================

    def exists(
        self,
        name: str,
    ) -> bool:

        return self.get(name) is not None

    # ========================================================
    # ENABLED
    # ========================================================

    def is_enabled(
        self,
        name: str,
    ) -> bool:

        tool = self.get(name)

        return bool(
            tool and tool.enabled
        )

    # ========================================================
    # ENABLE
    # ========================================================

    def enable(
        self,
        name: str,
    ) -> bool:

        tool = self.get(name)

        if tool is None:
            return False

        tool.enabled = True

        logger.info(
            "Tool enabled | name=%s",
            name,
        )

        return True

    # ========================================================
    # DISABLE
    # ========================================================

    def disable(
        self,
        name: str,
    ) -> bool:

        tool = self.get(name)

        if tool is None:
            return False

        tool.enabled = False

        logger.info(
            "Tool disabled | name=%s",
            name,
        )

        return True

    # ========================================================
    # DANGEROUS
    # ========================================================

    def is_dangerous(
        self,
        name: str,
    ) -> bool:

        tool = self.get(name)

        return bool(
            tool and tool.dangerous
        )

    # ========================================================
    # LIST
    # ========================================================

    def list_tools(
        self,
    ) -> list[ToolDefinition]:

        return list(
            self._tools.values()
        )

    # ========================================================
    # EXECUTE
    # ========================================================

    async def execute(
        self,
        name: str,
        *,
        require_enabled: bool = True,
        allow_dangerous: bool = False,
        **kwargs: Any,
    ) -> ToolResult:

        name = str(name or "").strip()

        started = time.perf_counter()

        tool = self.get(name)

        # ----------------------------------------------------
        # Unknown
        # ----------------------------------------------------

        if tool is None:

            return ToolResult(
                success=False,
                tool_name=name,
                error=f"unknown_tool:{name}",
                duration_seconds=(
                    time.perf_counter()
                    - started
                ),
            )

        # ----------------------------------------------------
        # Disabled
        # ----------------------------------------------------

        if (
            require_enabled
            and not tool.enabled
        ):

            return ToolResult(
                success=False,
                tool_name=name,
                error=f"tool_disabled:{name}",
                duration_seconds=(
                    time.perf_counter()
                    - started
                ),
            )

        # ----------------------------------------------------
        # Dangerous
        # ----------------------------------------------------

        if (
            tool.dangerous
            and not allow_dangerous
        ):

            return ToolResult(
                success=False,
                tool_name=name,
                error=(
                    f"dangerous_tool_blocked:{name}"
                ),
                duration_seconds=(
                    time.perf_counter()
                    - started
                ),
            )

        # ----------------------------------------------------
        # Execute
        # ----------------------------------------------------

        try:

            result = tool.handler(
                **kwargs
            )

            # Handler async bo‘lmasa ham
            # registry yiqilib ketmasin.
            if inspect.isawaitable(result):

                result = await asyncio.wait_for(
                    result,
                    timeout=tool.timeout,
                )

            duration = (
                time.perf_counter()
                - started
            )

            if isinstance(
                result,
                ToolResult,
            ):

                result.duration_seconds = (
                    duration
                )

                return result

            return ToolResult(
                success=True,
                tool_name=name,
                result=result,
                duration_seconds=duration,
            )

        except asyncio.TimeoutError:

            return ToolResult(
                success=False,
                tool_name=name,
                error=f"tool_timeout:{name}",
                duration_seconds=(
                    time.perf_counter()
                    - started
                ),
            )

        except Exception as exc:

            logger.exception(
                "Tool execution failed | name=%s",
                name,
            )

            return ToolResult(
                success=False,
                tool_name=name,
                error=str(exc),
                duration_seconds=(
                    time.perf_counter()
                    - started
                ),
            )

    # ========================================================
    # TOOL CONTEXT
    # ========================================================

    def build_tool_context(
        self,
    ) -> list[dict[str, Any]]:

        tools: list[dict[str, Any]] = []

        for tool in self._tools.values():

            if not tool.enabled:
                continue

            tools.append(
                {
                    "name": tool.name,
                    "description": tool.description,
                    "dangerous": tool.dangerous,
                    "metadata": tool.metadata,
                }
            )

        return tools

    # ========================================================
    # STATS
    # ========================================================

    def stats(
        self,
    ) -> dict[str, Any]:

        tools = list(
            self._tools.values()
        )

        return {
            "total": len(tools),
            "enabled": sum(
                1
                for tool in tools
                if tool.enabled
            ),
            "disabled": sum(
                1
                for tool in tools
                if not tool.enabled
            ),
            "dangerous": sum(
                1
                for tool in tools
                if tool.dangerous
            ),
            "tools": [
                tool.name
                for tool in tools
            ],
        }


# ============================================================
# GLOBAL REGISTRY
# ============================================================

tool_registry = ToolRegistry()


__all__ = [
    "ToolDefinition",
    "ToolResult",
    "ToolRegistry",
    "tool_registry",
        ]
