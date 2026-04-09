"""Gamification: streaks, XP, milestones. Persists to .brainsync/gamification.json."""
from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

_FILE = ".brainsync/gamification.json"

MILESTONES       = [10, 25, 50, 100, 250, 500, 1000]
STREAK_TRIGGERS  = [3, 7, 14, 30, 100]
XP_PER_NOTE      = 10
XP_PER_WIKILINK  = 5

_LEVELS = [
    (0,    "Beginner"),
    (100,  "Note Taker"),
    (300,  "Chronicler"),
    (600,  "Knowledge Builder"),
    (1000, "Archivist"),
    (2000, "Vault Master"),
    (5000, "Grand Sage"),
]


def level_for_xp(xp: int) -> str:
    name = _LEVELS[0][1]
    for threshold, label in _LEVELS:
        if xp >= threshold:
            name = label
    return name


def load(vault_path: str) -> dict:
    path = Path(vault_path) / _FILE
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.debug("gamification: load: %s", exc)
    return {}


def _persist(vault_path: str, data: dict) -> None:
    path = Path(vault_path) / _FILE
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.warning("gamification: save: %s", exc)


def on_note_saved(vault_path: str, wikilinks_added: int = 0) -> list[str]:
    """Call after every successful note save.

    Updates streak, XP, checks milestones.
    Returns a list of notification strings (empty if nothing special happened).
    """
    data = load(vault_path)
    today      = date.today().isoformat()
    yesterday  = (date.today() - timedelta(days=1)).isoformat()
    notifications: list[str] = []

    # ── Streak ────────────────────────────────────────────────────────────────
    last = data.get("last_note_date", "")
    if last == today:
        pass                                          # already saved today
    elif last == yesterday:
        data["streak_days"] = data.get("streak_days", 0) + 1
    else:
        data["streak_days"] = 1                       # new or broken streak

    data["last_note_date"] = today
    streak = data["streak_days"]

    announced_streaks: set[int] = set(data.get("streaks_announced", []))
    for sm in STREAK_TRIGGERS:
        if streak >= sm and sm not in announced_streaks:
            announced_streaks.add(sm)
            notifications.append(f"🔥 {streak}-day streak! Keep it up!")
    data["streaks_announced"] = sorted(announced_streaks)

    # ── XP ────────────────────────────────────────────────────────────────────
    data["total_xp"]       = data.get("total_xp", 0) + XP_PER_NOTE + wikilinks_added * XP_PER_WIKILINK
    data["notes_all_time"] = data.get("notes_all_time", 0) + 1
    n   = data["notes_all_time"]
    xp  = data["total_xp"]

    announced_m: set[int] = set(data.get("milestones_announced", []))
    for m in MILESTONES:
        if n >= m and m not in announced_m:
            announced_m.add(m)
            notifications.append(
                f"🎉 Milestone: {m} notes! Level: {level_for_xp(xp)} · XP: {xp}"
            )
    data["milestones_announced"] = sorted(announced_m)

    _persist(vault_path, data)
    return notifications
