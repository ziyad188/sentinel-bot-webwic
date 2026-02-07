from dataclasses import dataclass
from typing import Literal

from .base import BaseAnthropicTool
from .bash import BashTool20250124
from .playwright_tool import PlaywrightComputerTool

ToolVersion = Literal[
    "sentinel_playwright",
]
BetaFlag = Literal[
    "computer-use-2025-01-24",
]


@dataclass(frozen=True, kw_only=True)
class ToolGroup:
    version: ToolVersion
    tools: list[type[BaseAnthropicTool]]
    beta_flag: BetaFlag | None = None


TOOL_GROUPS: list[ToolGroup] = [
    ToolGroup(
        version="sentinel_playwright",
        tools=[PlaywrightComputerTool, BashTool20250124],
        beta_flag="computer-use-2025-01-24",
    ),
]

TOOL_GROUPS_BY_VERSION = {tool_group.version: tool_group for tool_group in TOOL_GROUPS}
