"""Shared entity base for Claude Usage."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import COUNTDOWN_REFRESH_SECONDS, DOMAIN
from .coordinator import ClaudeUsageCoordinator


class ClaudeUsageEntity(CoordinatorEntity[ClaudeUsageCoordinator]):
    """Base entity.

    The device is deliberately named "Claude" so that Home Assistant generates
    the same entity IDs the YAML package produced (`sensor.claude_session_usage`
    and friends). Changing the device name would rename every entity and break
    existing dashboards and automations.
    """

    _attr_has_entity_name = True

    def __init__(self, coordinator: ClaudeUsageCoordinator, key: str) -> None:
        """Set up the entity."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.unique_id or entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
            name="Claude",
            manufacturer="Anthropic",
            model="Claude usage",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://claude.ai/settings/usage",
        )


class ClaudeUsageCountdownEntity(ClaudeUsageEntity):
    """Entity that exposes a live countdown attribute.

    The countdown has to tick between polls or it is wrong for up to five
    minutes. Ticking it means writing state every minute, so the countdown
    attributes are declared unrecorded: they update in memory and in the UI, but
    the recorder does not keep a history of a string that changes 1,440 times a
    day and has no analytical value.
    """

    _unsub_timer: Callable[[], None] | None = None

    async def async_added_to_hass(self) -> None:
        """Start the per-minute refresh."""
        await super().async_added_to_hass()
        self._unsub_timer = async_track_time_interval(
            self.hass,
            self._handle_countdown_tick,
            timedelta(seconds=COUNTDOWN_REFRESH_SECONDS),
        )
        self.async_on_remove(self._cancel_timer)

    @callback
    def _cancel_timer(self) -> None:
        """Stop the refresh timer."""
        if self._unsub_timer is not None:
            self._unsub_timer()
            self._unsub_timer = None

    @callback
    def _handle_countdown_tick(self, _now: datetime) -> None:
        """Rewrite state so the countdown attribute stays accurate."""
        if self.hass is not None and self.enabled:
            self.async_write_ha_state()


def friendly_time(value: datetime | None) -> str:
    """Format a reset time the way the YAML package did, e.g. `Fri 3:45 PM`."""
    if value is None:
        return "unknown"
    local = dt_util.as_local(value)
    hour = local.hour % 12 or 12
    meridiem = "AM" if local.hour < 12 else "PM"
    return f"{local.strftime('%a')} {hour}:{local.strftime('%M')} {meridiem}"


def countdown(value: datetime | None) -> str:
    """Format the time remaining, e.g. `2h 14m`, `3d 4h`, `now`."""
    if value is None:
        return "unknown"
    delta = int((value - dt_util.utcnow()).total_seconds())
    if delta <= 0:
        return "now"
    days, remainder = divmod(delta, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes = remainder // 60
    if days > 0:
        return f"{days}d {hours}h"
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def iso_or_none(value: datetime | None) -> str | None:
    """Return an ISO timestamp string, matching the old attribute format."""
    return value.isoformat() if value is not None else None
