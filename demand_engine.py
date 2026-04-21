"""
Demand scoring engine for BuPlace Hotel.

Score = seasonal_base + day_of_week_boost + event_boost (capped at 100)
Static events come from EVENTS list below.
Dynamic events are loaded from data/events_*.json (written by scraper.py).
"""

import json
import pathlib
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple


# ── SEASONAL BASE (0–100 per month) ──────────────────────────────────────────
# Bangkok hotel with Thai/Chinese/Asian/European customer mix
MONTHLY_BASE: Dict[int, int] = {
    1:  68,  # Jan: Cool season peak; post-NYE glow; strong Western + Thai demand
    2:  72,  # Feb: Highest base — CNY + Valentine's + still-cool season
    3:  58,  # Mar: Shoulder — cool season fading, fewer Westerners
    4:  65,  # Apr: High — Songkran dominates Thai demand; Easter brings Europeans
    5:  42,  # May: Low — hot + rainy starts; post-Songkran lull
    6:  44,  # Jun: Rainy season; EU school holidays partially compensate
    7:  48,  # Jul: EU summer peak offsets Bangkok rain
    8:  52,  # Aug: EU still active; Thai domestic picks up for long weekends
    9:  40,  # Sep: Quietest — rainy + globally slow travel month
    10: 60,  # Oct: Cool season approaching; Chinese Golden Week; Thai holidays
    11: 65,  # Nov: Cool season; Western tourists arrive; Loi Krathong spike
    12: 72,  # Dec: Peak — Christmas + NYE; Europeans flood in
}

# ── DAY-OF-WEEK BOOST (+0 to +20) ────────────────────────────────────────────
DOW_BOOST: Dict[int, int] = {
    0:  0,   # Monday — quiet; mostly checkouts
    1:  0,   # Tuesday
    2:  3,   # Wednesday — midweek blip
    3:  8,   # Thursday — pre-weekend arrivals start
    4: 16,   # Friday — strong arrival day
    5: 20,   # Saturday — peak occupancy
    6:  8,   # Sunday — still occupied; checkouts begin
}

# ── SPECIAL EVENTS (+0 to +40 each, capped at +40 total per day) ─────────────
# Format: (label, date, boost, segment_tag)
EVENTS: List[Tuple[str, date, int, str]] = [

    # ══ 2025 ══════════════════════════════════════════════════════════════════

    # New Year 2025
    ("New Year's Day",        date(2025, 1, 1),  38, "all"),
    ("New Year Holiday",      date(2025, 1, 2),  20, "all"),

    # Chinese New Year 2025 — Jan 29
    ("CNY Eve",               date(2025, 1, 28), 22, "chinese"),
    ("Chinese New Year",      date(2025, 1, 29), 35, "chinese"),
    ("CNY Holiday",           date(2025, 1, 30), 28, "chinese"),
    ("CNY Holiday",           date(2025, 1, 31), 22, "chinese"),
    ("CNY Holiday",           date(2025, 2, 1),  16, "chinese"),
    ("CNY Holiday",           date(2025, 2, 2),  10, "chinese"),

    # Makha Bucha
    ("Makha Bucha",           date(2025, 2, 12), 14, "thai"),
    # Valentine's Day
    ("Valentine's Day",       date(2025, 2, 14), 18, "couple"),

    # Chakri Day
    ("Chakri Day",            date(2025, 4, 6),  14, "thai"),
    # Easter 2025 — Apr 18–21
    ("Good Friday",           date(2025, 4, 18), 12, "european"),
    ("Easter Sunday",         date(2025, 4, 19), 18, "european"),
    ("Easter Monday",         date(2025, 4, 20), 14, "european"),

    # Songkran 2025 — biggest Thai holiday
    ("Songkran Eve",          date(2025, 4, 12), 28, "thai"),
    ("Songkran",              date(2025, 4, 13), 40, "thai"),
    ("Songkran",              date(2025, 4, 14), 40, "thai"),
    ("Songkran",              date(2025, 4, 15), 38, "thai"),
    ("Songkran (extended)",   date(2025, 4, 16), 24, "thai"),

    # Japan / Korea Golden Week 2025
    ("JP/KR Golden Week",     date(2025, 4, 29), 14, "asian"),
    ("JP/KR Golden Week",     date(2025, 4, 30), 14, "asian"),
    ("JP/KR Golden Week",     date(2025, 5, 1),  14, "asian"),
    ("JP/KR Golden Week",     date(2025, 5, 2),  12, "asian"),
    ("JP/KR Golden Week",     date(2025, 5, 3),  14, "asian"),
    ("JP/KR Golden Week",     date(2025, 5, 4),  14, "asian"),
    ("JP/KR Golden Week",     date(2025, 5, 5),  14, "asian"),

    # Labour Day + China Labour Day (overlap)
    ("Labour Day",            date(2025, 5, 1),  12, "thai"),
    ("China Labour Day",      date(2025, 5, 1),  16, "chinese"),
    ("China Labour Day",      date(2025, 5, 2),  14, "chinese"),
    ("China Labour Day",      date(2025, 5, 3),  12, "chinese"),

    # Coronation Day
    ("Coronation Day",        date(2025, 5, 5),  12, "thai"),
    # Visakha Bucha
    ("Visakha Bucha",         date(2025, 5, 12), 14, "thai"),
    # Queen's Birthday
    ("Queen's Birthday",      date(2025, 6, 3),  10, "thai"),
    # Asalha Bucha
    ("Asalha Bucha",          date(2025, 7, 10), 14, "thai"),
    # King's Birthday
    ("King's Birthday",       date(2025, 7, 28), 14, "thai"),
    # Mother's Day TH
    ("Mother's Day",          date(2025, 8, 12), 14, "thai"),

    # China Mid-Autumn Festival 2025 — approx Oct 6
    ("Mid-Autumn Festival",   date(2025, 10, 6), 16, "chinese"),

    # China Golden Week 2025 — Oct 1–7
    ("China Golden Week",     date(2025, 10, 1), 24, "chinese"),
    ("China Golden Week",     date(2025, 10, 2), 24, "chinese"),
    ("China Golden Week",     date(2025, 10, 3), 22, "chinese"),
    ("China Golden Week",     date(2025, 10, 4), 20, "chinese"),
    ("China Golden Week",     date(2025, 10, 5), 18, "chinese"),
    ("China Golden Week",     date(2025, 10, 6), 16, "chinese"),
    ("China Golden Week",     date(2025, 10, 7), 14, "chinese"),

    # Chulalongkorn Day
    ("Chulalongkorn Day",     date(2025, 10, 23), 14, "thai"),
    # Loi Krathong 2025 — Nov 5
    ("Loi Krathong",          date(2025, 11, 5), 20, "all"),
    # King Rama IX Memorial
    ("King Rama IX Day",      date(2025, 10, 13), 10, "thai"),

    # Constitution Day
    ("Constitution Day",      date(2025, 12, 10), 10, "thai"),
    # Father's Day TH
    ("Father's Day",          date(2025, 12, 5),  12, "thai"),

    # Christmas
    ("Christmas Eve",         date(2025, 12, 24), 22, "european"),
    ("Christmas Day",         date(2025, 12, 25), 26, "european"),
    ("Christmas Holiday",     date(2025, 12, 26), 20, "european"),

    # New Year 2026
    ("New Year's Eve",        date(2025, 12, 31), 38, "all"),
    ("New Year's Day",        date(2026, 1, 1),   38, "all"),
    ("New Year Holiday",      date(2026, 1, 2),   22, "all"),

    # ══ 2026 ══════════════════════════════════════════════════════════════════

    # Chinese New Year 2026 — Feb 17
    ("CNY Eve 2026",          date(2026, 2, 16), 22, "chinese"),
    ("Chinese New Year 2026", date(2026, 2, 17), 35, "chinese"),
    ("CNY Holiday",           date(2026, 2, 18), 28, "chinese"),
    ("CNY Holiday",           date(2026, 2, 19), 22, "chinese"),
    ("CNY Holiday",           date(2026, 2, 20), 16, "chinese"),
    ("CNY Holiday",           date(2026, 2, 21), 10, "chinese"),

    # Valentine's 2026
    ("Valentine's Day",       date(2026, 2, 14), 18, "couple"),
    # Makha Bucha 2026 — approx Mar 3
    ("Makha Bucha",           date(2026, 3, 3),  14, "thai"),

    # Easter 2026 — Apr 3–6
    ("Good Friday",           date(2026, 4, 3),  12, "european"),
    ("Easter Sunday",         date(2026, 4, 5),  18, "european"),
    ("Easter Monday / Chakri",date(2026, 4, 6),  22, "all"),    # Easter Mon + Chakri overlap

    # Songkran 2026 — Apr 13 (Mon), 14 (Tue), 15 (Wed)
    ("Songkran Eve",          date(2026, 4, 12), 28, "thai"),
    ("Songkran",              date(2026, 4, 13), 40, "thai"),
    ("Songkran",              date(2026, 4, 14), 40, "thai"),
    ("Songkran",              date(2026, 4, 15), 38, "thai"),
    ("Songkran (extended)",   date(2026, 4, 16), 24, "thai"),

    # Japan / Korea Golden Week 2026
    ("JP/KR Golden Week",     date(2026, 4, 29), 14, "asian"),
    ("JP/KR Golden Week",     date(2026, 4, 30), 14, "asian"),
    ("JP/KR Golden Week",     date(2026, 5, 1),  14, "asian"),
    ("JP/KR Golden Week",     date(2026, 5, 2),  12, "asian"),
    ("JP/KR Golden Week",     date(2026, 5, 3),  14, "asian"),
    ("JP/KR Golden Week",     date(2026, 5, 4),  14, "asian"),
    ("JP/KR Golden Week",     date(2026, 5, 5),  14, "asian"),

    # Labour Day 2026 + China Labour Day (overlap)
    ("Labour Day",            date(2026, 5, 1),  12, "thai"),
    ("China Labour Day",      date(2026, 5, 1),  16, "chinese"),
    ("China Labour Day",      date(2026, 5, 2),  14, "chinese"),
    ("China Labour Day",      date(2026, 5, 3),  12, "chinese"),
    ("China Labour Day",      date(2026, 5, 4),  10, "chinese"),
    ("China Labour Day",      date(2026, 5, 5),  10, "chinese"),

    # Coronation Day 2026
    ("Coronation Day",        date(2026, 5, 4),  12, "thai"),
    # Visakha Bucha 2026 — approx Jun 1
    ("Visakha Bucha",         date(2026, 6, 1),  14, "thai"),
    # Queen's Birthday 2026
    ("Queen's Birthday",      date(2026, 6, 3),  10, "thai"),

    # Asalha Bucha 2026 — approx Jul 27
    ("Asalha Bucha",          date(2026, 7, 27), 14, "thai"),
    # King's Birthday 2026
    ("King's Birthday",       date(2026, 7, 28), 14, "thai"),
    # Mother's Day TH 2026
    ("Mother's Day",          date(2026, 8, 12), 14, "thai"),

    # China Golden Week 2026 — Oct 1–7
    ("China Golden Week",     date(2026, 10, 1), 24, "chinese"),
    ("China Golden Week",     date(2026, 10, 2), 24, "chinese"),
    ("China Golden Week",     date(2026, 10, 3), 22, "chinese"),
    ("China Golden Week",     date(2026, 10, 4), 20, "chinese"),
    ("China Golden Week",     date(2026, 10, 5), 18, "chinese"),
    ("China Golden Week",     date(2026, 10, 6), 16, "chinese"),
    ("China Golden Week",     date(2026, 10, 7), 14, "chinese"),

    # Chulalongkorn Day 2026
    ("Chulalongkorn Day",     date(2026, 10, 23), 14, "thai"),
    # Loi Krathong 2026 — approx Oct 24
    ("Loi Krathong",          date(2026, 10, 24), 20, "all"),

    # Christmas 2026
    ("Christmas Eve",         date(2026, 12, 24), 22, "european"),
    ("Christmas Day",         date(2026, 12, 25), 26, "european"),
    ("Christmas Holiday",     date(2026, 12, 26), 20, "european"),

    # New Year 2027
    ("New Year's Eve",        date(2026, 12, 31), 38, "all"),
    ("New Year's Day 2027",   date(2027, 1, 1),   38, "all"),
    ("New Year Holiday",      date(2027, 1, 2),   22, "all"),
]


def _build_static_map() -> Dict[date, List[Tuple[str, int, str]]]:
    m: Dict[date, List[Tuple[str, int, str]]] = {}
    for label, d, boost, seg in EVENTS:
        m.setdefault(d, []).append((label, boost, seg))
    return m


def _load_dynamic_map() -> Dict[date, List[Tuple[str, int, str]]]:
    """Load the most recent scraper output and expand date ranges into daily entries."""
    data_dir = pathlib.Path(__file__).parent / "data"
    if not data_dir.exists():
        return {}

    files = sorted(data_dir.glob("events_*.json"), reverse=True)
    if not files:
        return {}

    try:
        with open(files[0], encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}

    m: Dict[date, List[Tuple[str, int, str]]] = {}
    for ev in data.get("events", []):
        try:
            start = date.fromisoformat(ev["date_start"])
            end   = date.fromisoformat(ev["date_end"])
            boost = int(ev.get("boost", 10))
            label = f"[web] {ev['name']}"
            seg   = ev.get("segment", "all")
            d = start
            while d <= end:
                m.setdefault(d, []).append((label, boost, seg))
                d += timedelta(days=1)
        except (KeyError, ValueError):
            continue

    return m


_STATIC_MAP  = _build_static_map()
_DYNAMIC_MAP: Optional[Dict[date, List[Tuple[str, int, str]]]] = None


def _get_dynamic_map() -> Dict[date, List[Tuple[str, int, str]]]:
    global _DYNAMIC_MAP
    if _DYNAMIC_MAP is None:
        _DYNAMIC_MAP = _load_dynamic_map()
    return _DYNAMIC_MAP


def reload_dynamic_events() -> None:
    """Force re-read of the scraped events file (call after scraper runs)."""
    global _DYNAMIC_MAP
    _DYNAMIC_MAP = _load_dynamic_map()


def get_demand_score(d: date) -> Tuple[int, List[str]]:
    """Return (demand score 0-100, event labels active on this date).

    Labels prefixed with [web] came from the daily web scraper.
    """
    base = MONTHLY_BASE[d.month]
    dow  = DOW_BOOST[d.weekday()]

    static_events  = _STATIC_MAP.get(d, [])
    dynamic_events = _get_dynamic_map().get(d, [])
    all_events     = static_events + dynamic_events

    # Cap total event boost at 40 to prevent small-event stacking
    event_boost  = min(40, sum(b for _, b, _ in all_events))
    event_labels = [lbl for lbl, _, _ in all_events]

    return min(100, base + dow + event_boost), event_labels
