"""Hermes plugin for Reachy Mini robot control."""

from .reachy_tools import TOOL_DEFINITIONS, TOOLSET, EMOJI, _check_reachy_available


def register(ctx):
    """Register all Reachy Mini tools with the Hermes tool registry."""
    for defn in TOOL_DEFINITIONS:
        ctx.register_tool(
            name=defn["schema"]["name"],
            toolset=TOOLSET,
            schema=defn["schema"],
            handler=defn["handler"],
            check_fn=_check_reachy_available,
            emoji=EMOJI,
        )
