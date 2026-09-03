from __future__ import annotations

import asyncio
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
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> ToolDefinition:
        name = str(tool.name or "").strip()

        if not name:
            raise ValueError("Tool name cannot be empty.")

        if not callable(tool.handler):
            raise TypeError(f"Tool handler is not callable: {name}")

        self._tools[name] = tool

        logger.info(
            "Tool registered | name=%s | enabled=%s | dangerous=%s",
            name,
            tool.enabled,
            tool.dangerous,
        )

        return tool

    def unregister(self, name: str) -> bool:
        name = str(name or "").strip()

        if name in self._tools:
            del self._tools[name]
            return True

        return False

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(str(name or "").strip())

    def exists(self, name: str) -> bool:
        return self.get(name) is not None

    def is_enabled(self, name: str) -> bool:
        tool = self.get(name)
        return bool(tool and tool.enabled)

    def list_tools(self) -> list[ToolDefinition]:
        return list(self._tools.values())

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

    def is_dangerous(self, name: str) -> bool:
        tool = self.get(name)
        return bool(tool and tool.dangerous)

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

        if tool is None:
            return ToolResult(
                success=False,
                tool_name=name,
                error=f"unknown_tool:{name}",
                duration_seconds=time.perf_counter() - started,
            )

        if require_enabled and not tool.enabled:
            return ToolResult(
                success=False,
                tool_name=name,
                error=f"tool_disabled:{name}",
                duration_seconds=time.perf_counter() - started,
            )

        if tool.dangerous and not allow_dangerous:
            return ToolResult(
                success=False,
                tool_name=name,
                error=f"dangerous_tool_blocked:{name}",
                duration_seconds=time.perf_counter() - started,
            )

        try:
            result = await asyncio.wait_for(
                tool.handler(**kwargs),
                timeout=float(tool.timeout),
            )

            duration = time.perf_counter() - started

            if isinstance(result, ToolResult):
                result.duration_seconds = duration
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
                duration_seconds=time.perf_counter() - started,
            )

        except Exception as exc:
            logger.exception("Tool execution failed: %s", name)

            return ToolResult(
                success=False,
                tool_name=name,
                error=str(exc),
                duration_seconds=time.perf_counter() - started,
            )

    def build_tool_context(self) -> list[dict[str, Any]]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "dangerous": tool.dangerous,
                "metadata": tool.metadata,
            }
            for tool in self._tools.values()
            if tool.enabled
        ]

    def stats(self) -> dict[str, Any]:
        tools = list(self._tools.values())

        return {
            "total": len(tools),
            "enabled": sum(tool.enabled for tool in tools),
            "disabled": sum(not tool.enabled for tool in tools),
            "dangerous": sum(tool.dangerous for tool in tools),
            "tools": [tool.name for tool in tools],
        }


tool_registry = ToolRegistry()


__all__ = [
    "ToolDefinition",
    "ToolResult",
    "ToolRegistry",
    "tool_registry",
]
