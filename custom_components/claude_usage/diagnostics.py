"""Diagnostics for Claude Usage.

Exists so that a bug report can include the payload shape without the reporter
pasting their session cookie into a public GitHub issue.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_COOKIE, CONF_ORG_ID, CONF_ORG_NAME
from .coordinator import ClaudeUsageConfigEntry

TO_REDACT = {CONF_COOKIE, CONF_ORG_ID, CONF_ORG_NAME, "uuid", "email", "name"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ClaudeUsageConfigEntry
) -> dict[str, Any]:
    """Return redacted diagnostics."""
    coordinator = entry.runtime_data
    data = coordinator.data

    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "auth_failed": coordinator.auth_failed,
            "update_interval_seconds": (
                coordinator.update_interval.total_seconds()
                if coordinator.update_interval
                else None
            ),
            "consecutive_failures": coordinator.consecutive_failures,
            "consecutive_challenges": coordinator.consecutive_challenges,
            "last_successful_update": (
                coordinator.last_successful_update.isoformat()
                if coordinator.last_successful_update
                else None
            ),
            "stale_for_seconds": (
                round(coordinator.stale_for.total_seconds())
                if coordinator.stale_for
                else None
            ),
            "last_exception": str(coordinator.last_exception or ""),
        },
        "parsed_limits": {
            key: {
                "utilization": info.utilization,
                "resets_at": info.resets_at.isoformat() if info.resets_at else None,
                "severity": info.severity,
            }
            for key, info in (data.limits.items() if data else [])
        },
        # Keys only, not values. Enough to diagnose a payload shape change
        # without shipping anyone's usage history to an issue thread.
        "raw_payload_shape": _describe(data.raw if data else {}),
    }


def _describe(value: Any, depth: int = 0) -> Any:
    """Return the structure of a payload without its values."""
    if depth > 3:
        return "..."
    if isinstance(value, dict):
        return {key: _describe(item, depth + 1) for key, item in value.items()}
    if isinstance(value, list):
        if not value:
            return []
        return [_describe(value[0], depth + 1), f"...({len(value)} items)"]
    return type(value).__name__
