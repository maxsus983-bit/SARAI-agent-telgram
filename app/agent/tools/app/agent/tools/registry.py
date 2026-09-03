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


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

        self.total_calls = 0
        self.successful_calls = 0
        self.failed_calls = 0

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

        normalized_name = self._normalize_name(name)

        if not normalized_name:
            raise ValueError("Tool name bo'sh bo'lishi mumkin emas.")

        if not callable(handler):
            raise TypeError(
                f"Tool handler callable bo'lishi kerak: {normalized_name}"
            )

        if normalized_name in self._tools and not overwrite:
            raise ValueError(
                f"Tool allaqachon mavjud: {normalized_name}"
            )

        tool = ToolDefinition(
            name=normalized_name,
            description=description.strip(),
            handler=handler,
            enabled=enabled,
            dangerous=dangerous,
            timeout=max(0.1, float(timeout)),
            metadata=dict(metadata or {}),
        )

        self._tools[normalized_name] = tool

        logger.info(
            "Tool registered | %s | enabled=%s",
            normalized_name,
            enabled,
        )

        return tool

    def unregister(self, name: str) -> bool:
        name = self._normalize_name(name)

        if name not in self._tools:
            return False

        self._tools.pop(name, None)

        logger.info("Tool unregistered | %s", name)

        return True

    # =========================================================
    # GET
    # =========================================================

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(
            self._normalize_name(name)
        )

    def exists(self, name: str) -> bool:
        return self.get(name) is not None

    def is_enabled(self, name: str) -> bool:
        tool = self.get(name)

        return bool(tool and tool.enabled)

    def list_tools(
        self,
        *,
        enabled_only: bool = False,
    ) -> list[ToolDefinition]:

        tools = list(self._tools.values())

        if enabled_only:
            tools = [
                tool
                for tool in tools
                if tool.enabled
            ]

        return tools

    # =========================================================
    # ENABLE / DISABLE
    # =========================================================

    def enable(self, name: str) -> bool:
        tool = self.get(name)

        if tool is None:
            return False

        tool.enabled = True

        return True

    def disable(self, name: str) -> bool:
        tool = self.get(name)

        if tool is None:
            return False

        tool.enabled = False

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

        started = time.monotonic()

        tool_name = self._normalize_name(name)

        self.total_calls += 1

        tool = self._tools.get(tool_name)

        if tool is None:
            self.failed_calls += 1

            return ToolResult(
                success=False,
                tool_name=tool_name,
                error="tool_not_found",
                duration_seconds=time.monotonic() - started,
            )

        if not tool.enabled:
            self.failed_calls += 1

            return ToolResult(
                success=False,
                tool_name=tool_name,
                error="tool_disabled",
                duration_seconds=time.monotonic() - started,
            )

        if tool.dangerous and not allow_dangerous:
            self.failed_calls += 1

            return ToolResult(
                success=False,
                tool_name=tool_name,
                error="dangerous_tool_blocked",
                duration_seconds=time.monotonic() - started,
            )

        arguments = dict(arguments or {})

        try:
            result = await self._call_handler(
                tool,
                arguments,
            )

            self.successful_calls += 1

            return ToolResult(
                success=True,
                tool_name=tool_name,
                result=result,
                duration_seconds=time.monotonic() - started,
            )

        except asyncio.TimeoutError:
            self.failed_calls += 1

            return ToolResult(
                success=False,
                tool_name=tool_name,
                error="tool_timeout",
                duration_seconds=time.monotonic() - started,
            )

        except Exception as exc:
            self.failed_calls += 1

            logger.exception(
                "Tool execution failed | %s",
                tool_name,
            )

            return ToolResult(
                success=False,
                tool_name=tool_name,
                error=str(exc),
                duration_seconds=time.monotonic() - started,
            )

    async def _call_handler(
        self,
        tool: ToolDefinition,
        arguments: dict[str, Any],
    ) -> Any:

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
    # AI CONTEXT
    # =========================================================

    def build_tool_context(
        self,
        *,
        enabled_only: bool = True,
    ) -> str:

        tools = self.list_tools(
            enabled_only=enabled_only,
        )

        if not tools:
            return (
                "SARA AVAILABLE TOOLS\n"
                "====================\n"
                "Hozircha tool mavjud emas."
            )

        lines = [
            "SARA AVAILABLE TOOLS",
            "====================",
        ]

        for tool in tools:
            lines.append(
                f"- {tool.name}: {tool.description}"
            )

        return "\n".join(lines)

    # =========================================================
    # STATS
    # =========================================================

    def stats(self) -> dict[str, Any]:

        tools = self.list_tools()

        return {
            "total_tools": len(tools),
            "enabled_tools": sum(
                1 for tool in tools if tool.enabled
            ),
            "disabled_tools": sum(
                1 for tool in tools if not tool.enabled
            ),
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
        }

    @staticmethod
    def _normalize_name(name: str) -> str:
        return (
            str(name)
            .strip()
            .lower()
            .replace(" ", "_")
        )


tool_registry = ToolRegistry()
