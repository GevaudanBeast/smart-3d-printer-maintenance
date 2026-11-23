"""Print session state machine for 3D Printer Maintenance.

Pure functions, no Home Assistant import, so they can be unit tested.
"""

from __future__ import annotations

# States that say nothing about the printer (offline, restarting HA, Wi-Fi drop).
UNAVAILABLE_STATES = ("unknown", "unavailable", "")

# PrusaLink reports "finished"; Moonraker "complete"; others "completed".
DEFAULT_COMPLETED = ["completed", "complete", "finish", "finished"]

CONF_COMPLETED_STATES = "completed_states"


def classify_transition(
    prev: str | None,
    new: str,
    printing: list[str],
    paused: list[str],
    completed: list[str],
    failure: list[str],
) -> str:
    """Classify a printer status change.

    Args:
        prev: last real printer state (never unknown/unavailable), or None.
        new: new state reported by the status entity.

    Returns:
        "ignore" (no information, keep the session as is), "start", "resume",
        "pause", "end_ok", "end_ko", "end_other" or "none".
    """
    if new in UNAVAILABLE_STATES:
        return "ignore"
    was_printing = prev in printing
    was_paused = prev in paused
    if new in printing:
        if was_printing:
            return "none"
        return "resume" if was_paused else "start"
    if new in paused:
        return "pause" if was_printing else "none"
    if was_printing or was_paused:
        if new in completed:
            return "end_ok"
        if new in failure:
            return "end_ko"
        return "end_other"
    return "none"


def migrate_options_1_2(options: dict) -> dict:
    """Config entry 1.1 -> 1.2: add "finished" to stored completed states."""
    migrated = dict(options)
    states = migrated.get(CONF_COMPLETED_STATES)
    if states is not None and "finished" not in states:
        migrated[CONF_COMPLETED_STATES] = [*states, "finished"]
    return migrated
