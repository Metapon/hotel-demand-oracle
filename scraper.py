"""
BuPlace Hotel — Web Event Scraper

Architecture:
  1. DuckDuckGo search (free, no key) -> get short result snippets
  2. Claude Haiku -> read snippets, extract structured event JSON

This keeps token usage low and avoids rate limits.
Writes results to data/events_YYYY-MM-DD.json for demand_engine.py to load.

Requires: ANTHROPIC_API_KEY in config/siteminder.env
"""

import json
import os
import pathlib
import re
import sys
from datetime import date, timedelta

BASE_DIR = pathlib.Path(__file__).parent
DATA_DIR = BASE_DIR / "data"


def _load_env() -> None:
    env_file = BASE_DIR / "config" / "siteminder.env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())


def _ddg_search(query: str, max_results: int = 6) -> str:
    """Run a DuckDuckGo search and return a compact snippet string."""
    try:
        from ddgs import DDGS
        results = list(DDGS().text(query, max_results=max_results))
        lines = []
        for r in results:
            title = r.get("title", "")
            body  = r.get("body", "")[:250]
            lines.append(f"- {title}: {body}")
        return "\n".join(lines) if lines else "[no results]"
    except Exception as exc:
        return f"[search error: {exc}]"


def run_scraper(days_ahead: int = 180, log=print) -> list:
    """
    Search the web for Bangkok demand events and save to data/events_YYYY-MM-DD.json.
    Returns list of event dicts (empty list on failure).
    """
    _load_env()

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key or api_key.startswith("sk-ant-..."):
        log("[scraper] ANTHROPIC_API_KEY not set — skipping web search")
        return []

    try:
        import anthropic
    except ImportError:
        log("[scraper] anthropic package not installed — run: pip install anthropic")
        return []

    client   = anthropic.Anthropic(api_key=api_key)
    today    = date.today()
    end_date = today + timedelta(days=days_ahead)
    m1 = today.strftime("%B %Y")
    m2 = (today + timedelta(days=90)).strftime("%B %Y")

    log(f"[scraper] Searching web for Bangkok events {today} -> {end_date} ...")

    # ── Phase 1: DuckDuckGo searches (snippets only, no token cost) ───────────
    queries = [
        f"Bangkok events concerts festivals {m1} {m2}",
        f"Bangkok BITEC IMPACT QSNCC conference exhibition {today.year}",
        f"Thailand teacher licensing exam krusapa {today.year}",
        f"Bangkok marathon sports tournament {today.year}",
        f"Bangkok hotel demand tourism {m1}",
    ]

    all_snippets = []
    for q in queries:
        log(f"[scraper]   Searching: {q}")
        snippets = _ddg_search(q, max_results=5)
        all_snippets.append(f"Query: {q}\n{snippets}")

    raw_text = "\n\n".join(all_snippets)
    log(f"[scraper] Search complete. Asking Claude to extract events ...")

    # ── Phase 2: Claude Haiku extracts structured events from snippets ─────────
    prompt = f"""You are a hotel revenue analyst. Extract upcoming events from these web search snippets
that would increase hotel demand in Bangkok between {today} and {end_date}.

SEARCH RESULTS:
{raw_text[:5000]}

Return ONLY a valid JSON object (no markdown, no explanation):
{{
  "scraped_date": "{today}",
  "source_summary": "1-2 sentences summarising the demand outlook for Bangkok hotels",
  "events": [
    {{
      "name": "Event name",
      "date_start": "YYYY-MM-DD",
      "date_end": "YYYY-MM-DD",
      "type": "concert|festival|conference|exam|sports|cultural|other",
      "segment": "thai|chinese|asian|european|all",
      "boost": 18,
      "note": "Why this drives overnight hotel stays"
    }}
  ]
}}

Boost scoring:
- Teacher licensing exam (krusapa) — upcountry teachers stay overnight: 25, segment "thai"
- Major concert / music festival (10k+ attendance): 20, segment varies
- International conference at BITEC / IMPACT / QSNCC: 16, segment "all"
- Sports event / marathon: 12, segment varies
- Cultural / local festival: 14, segment "thai"
- Tourism campaign / new airline route: 8, segment varies

Only include events that fall between {today} and {end_date}.
If a date is approximate, use your best estimate.
Return an empty events list if nothing relevant found — do not invent events."""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        json_text = response.content[0].text.strip()
        json_text = re.sub(r"^```[a-z]*\n?", "", json_text)
        json_text = re.sub(r"\n?```$", "", json_text.strip())
        events_data = json.loads(json_text)
    except Exception as exc:
        log(f"[scraper] Claude extraction failed: {exc}")
        events_data = {"scraped_date": str(today), "events": []}

    # ── Save ──────────────────────────────────────────────────────────────────
    DATA_DIR.mkdir(exist_ok=True)
    out_path = DATA_DIR / f"events_{today}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(events_data, f, indent=2, ensure_ascii=False)

    n = len(events_data.get("events", []))
    log(f"[scraper] Saved {n} events -> {out_path}")

    if summary := events_data.get("source_summary"):
        log(f"[scraper] Outlook: {summary}")

    return events_data.get("events", [])


if __name__ == "__main__":
    from config import HOTEL
    events = run_scraper(days_ahead=HOTEL["days_ahead"])
    if events:
        print(f"\nFound {len(events)} events:")
        for ev in events:
            print(f"  {ev['date_start']} -> {ev['date_end']}  "
                  f"[boost +{ev.get('boost','?'):>2}]  {ev['name']}")
    else:
        print("No events found.")
        sys.exit(1)
