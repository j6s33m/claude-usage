"""Binary sensor platform for Claude Usage."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import ClaudeUsageConfigEntry
from .entity import ClaudeUsageEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ClaudeUsageConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors."""
    async_add_entities([ClaudeCookieStaleBinarySensor(entry.runtime_data)])


class ClaudeCookieStaleBinarySensor(ClaudeUsageEntity, BinarySensorEntity):
    """Reports whether the cookie has stopped working.

    Home Assistant's repair and reauth flow is now the primary signal, but this
    entity is kept because the YAML package exposed it and people have built
    conditional cards and automations on it.
    """

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:cookie-alert"

    def __init__(self, coordinator) -> None:  # noqa: ANN001
        """Set up the sensor."""
        super().__init__(coordinator, "cookie_stale")
        self._attr_translation_key = "cookie_stale"

    @property
    def available(self) -> bool:
        """Always available.

        A sensor whose job is to report failure is useless if it goes
        unavailable at the moment things fail.
        """
        return True

    @property
    def is_on(self) -> bool:
        """Return True when the last poll failed."""
        return self.coordinator.auth_failed or not self.coordinator.last_update_success

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Explain why, so the state is actionable without reading the log."""
        if self.coordinator.auth_failed:
            reason = "cookie_rejected"
        elif not self.coordinator.last_update_success:
            reason = "update_failed"
        else:
            reason = "ok"
        return {
            "reason": reason,
            "last_error": str(self.coordinator.last_exception or ""),
        }
