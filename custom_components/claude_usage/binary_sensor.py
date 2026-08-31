"""Binary sensor platform for Claude Usage."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import STALE_AFTER
from .coordinator import ClaudeUsageConfigEntry, ClaudeUsageCoordinator
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

    It answers "does a human need to go get a new cookie", not "did the last
    HTTP request succeed". Those are different questions: polls fail routinely
    for reasons that have nothing to do with the cookie, and a sensor that
    reports every one of them as a problem trains its owner to ignore it.
    """

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:cookie-alert"
    # These change on every poll and carry no analytical value, so they update
    # in the UI without writing a recorder row each cycle. `reason` is left
    # recorded: its history is the useful part when diagnosing a flapping
    # install.
    _unrecorded_attributes = frozenset(
        {"consecutive_failures", "last_error", "last_successful_update"}
    )

    def __init__(self, coordinator: ClaudeUsageCoordinator) -> None:
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
        """Return True when the cookie genuinely needs replacing.

        Three cases, in order:

        1. claude.ai rejected the cookie, or challenged us repeatedly. That is
           a real auth failure and it will not clear on its own, so report it
           at once.
        2. Polls are failing but one succeeded recently. Transient. Stay off
           and let `reason` carry the detail for anyone looking.
        3. Nothing has succeeded for `STALE_AFTER`. The data on the dashboard
           is now old enough to be misleading, whatever the cause.
        """
        coordinator = self.coordinator
        if coordinator.auth_failed:
            return True
        if coordinator.last_update_success:
            return False
        stale_for = coordinator.stale_for
        if stale_for is None:
            return True
        return stale_for >= STALE_AFTER

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Explain why, so the state is actionable without reading the log."""
        coordinator = self.coordinator
        stale_for = coordinator.stale_for

        if coordinator.auth_failed:
            reason = "cookie_rejected"
        elif coordinator.last_update_success:
            reason = "ok"
        elif self.is_on:
            reason = "no_data"
        else:
            # Polls are failing, but recently enough that it is not yet worth
            # anyone's attention.
            reason = "recovering"

        return {
            "reason": reason,
            "consecutive_failures": coordinator.consecutive_failures,
            "last_successful_update": (
                coordinator.last_successful_update.isoformat()
                if coordinator.last_successful_update
                else None
            ),
            "stale_for_minutes": (
                round(stale_for.total_seconds() / 60) if stale_for else None
            ),
            "last_error": str(coordinator.last_exception or ""),
        }
