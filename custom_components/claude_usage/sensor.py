"""Sensor platform for Claude Usage."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    COUNTDOWN_ATTRIBUTES,
    LIMIT_OPUS_WEEKLY,
    LIMIT_SESSION,
    LIMIT_WEEKLY,
)
from .coordinator import ClaudeUsageConfigEntry, ClaudeUsageCoordinator, LimitInfo
from .entity import (
    ClaudeUsageCountdownEntity,
    ClaudeUsageEntity,
    countdown,
    friendly_time,
    iso_or_none,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ClaudeUsageConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""
    coordinator = entry.runtime_data

    entities: list[SensorEntity] = [
        # Entity IDs below must stay exactly as they are. They are what the
        # companion gauge card and any existing automations refer to.
        ClaudeUsagePercentSensor(
            coordinator,
            limit_key=LIMIT_SESSION,
            key="session_usage",
            translation_key="session_usage",
            icon="mdi:gauge",
            attribute_prefix="session",
        ),
        ClaudeUsagePercentSensor(
            coordinator,
            limit_key=LIMIT_WEEKLY,
            key="weekly_usage",
            translation_key="weekly_usage",
            icon="mdi:calendar-range",
            attribute_prefix="week",
        ),
        ClaudeUsageResetTextSensor(
            coordinator,
            limit_key=LIMIT_SESSION,
            key="session_resets",
            translation_key="session_resets",
            icon="mdi:clock-outline",
        ),
        ClaudeUsageResetTextSensor(
            coordinator,
            limit_key=LIMIT_WEEKLY,
            key="weekly_resets",
            translation_key="weekly_resets",
            icon="mdi:calendar-clock",
        ),
        ClaudeUsageResetTimestampSensor(
            coordinator,
            limit_key=LIMIT_SESSION,
            key="session_reset_time",
            translation_key="session_reset_time",
            icon="mdi:clock-outline",
        ),
        ClaudeUsageResetTimestampSensor(
            coordinator,
            limit_key=LIMIT_WEEKLY,
            key="weekly_reset_time",
            translation_key="weekly_reset_time",
            icon="mdi:calendar-clock",
        ),
    ]

    # Only created when the account actually reports an Opus specific weekly
    # limit, so Pro users do not get a permanently unknown entity.
    if coordinator.data is not None and coordinator.data.get(LIMIT_OPUS_WEEKLY):
        entities.append(
            ClaudeUsagePercentSensor(
                coordinator,
                limit_key=LIMIT_OPUS_WEEKLY,
                key="opus_weekly_usage",
                translation_key="opus_weekly_usage",
                icon="mdi:brain",
                attribute_prefix="opus_week",
            )
        )

    async_add_entities(entities)


class ClaudeUsageLimitMixin:
    """Shared access to one limit block."""

    coordinator: ClaudeUsageCoordinator
    _limit_key: str

    @property
    def limit(self) -> LimitInfo | None:
        """Return the limit this entity tracks."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self._limit_key)


class ClaudeUsagePercentSensor(
    ClaudeUsageLimitMixin, ClaudeUsageCountdownEntity, SensorEntity
):
    """Percentage of a usage window consumed."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 0
    _unrecorded_attributes = frozenset(COUNTDOWN_ATTRIBUTES)

    def __init__(
        self,
        coordinator: ClaudeUsageCoordinator,
        *,
        limit_key: str,
        key: str,
        translation_key: str,
        icon: str,
        attribute_prefix: str,
    ) -> None:
        """Set up the sensor."""
        super().__init__(coordinator, key)
        self._limit_key = limit_key
        self._attr_translation_key = translation_key
        self._attr_icon = icon
        self._prefix = attribute_prefix

    @property
    def available(self) -> bool:
        """Only available once a real percentage has been seen."""
        limit = self.limit
        return super().available and limit is not None and limit.has_data

    @property
    def native_value(self) -> float | None:
        """Return the percentage used."""
        limit = self.limit
        return limit.utilization if limit else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return severity plus the reset attributes the gauge card reads."""
        limit = self.limit
        resets_at = limit.resets_at if limit else None
        return {
            "severity": limit.severity if limit else None,
            f"{self._prefix}_resets_at": iso_or_none(resets_at),
            f"{self._prefix}_resets": friendly_time(resets_at),
            f"{self._prefix}_resets_in": countdown(resets_at),
        }


class ClaudeUsageResetTextSensor(
    ClaudeUsageLimitMixin, ClaudeUsageEntity, SensorEntity
):
    """Friendly local reset time as text, kept for card compatibility."""

    def __init__(
        self,
        coordinator: ClaudeUsageCoordinator,
        *,
        limit_key: str,
        key: str,
        translation_key: str,
        icon: str,
    ) -> None:
        """Set up the sensor."""
        super().__init__(coordinator, key)
        self._limit_key = limit_key
        self._attr_translation_key = translation_key
        self._attr_icon = icon

    @property
    def native_value(self) -> str:
        """Return something like `Fri 3:45 PM`."""
        limit = self.limit
        return friendly_time(limit.resets_at if limit else None)


class ClaudeUsageResetTimestampSensor(
    ClaudeUsageLimitMixin, ClaudeUsageEntity, SensorEntity
):
    """Native timestamp for the reset, so the UI can render its own countdown."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self,
        coordinator: ClaudeUsageCoordinator,
        *,
        limit_key: str,
        key: str,
        translation_key: str,
        icon: str,
    ) -> None:
        """Set up the sensor."""
        super().__init__(coordinator, key)
        self._limit_key = limit_key
        self._attr_translation_key = translation_key
        self._attr_icon = icon

    @property
    def native_value(self) -> datetime | None:
        """Return the reset time."""
        limit = self.limit
        return limit.resets_at if limit else None
