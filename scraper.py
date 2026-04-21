"""
BuPlace Hotel — Web Event Scraper
Uses Claude's web search to find Bangkok events that affect hotel demand.
Writes results to data/events_YYYY-MM-DD.json for demand_engine.py to load.

Requires: ANTHROPIC_API_KEY in environment or config/siteminder.env
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

    client = anthropic.Anthropic(api_key=api_key)
    today    = date.today()
    end_date = today + timedelta(days=days_ahead)

    log(f"[scraper] Searching for Bangkok events {today} -> {end_date} ...")

    # ── Phase 1: web search ───────────────────────────────────────────────────
    search_queries = [
        f"Bangkok concerts festivals events {today.strftime('%B %Y')} {(today + timedelta(days=60)).strftime('%B %Y')}",
        f"Bangkok international conference exhibition BITEC IMPACT QSNCC {today.year}",
        f"Bangkok sports events marathon tournament {today.year}",
        f"Thailand teacher licensing exam krusapa teachers council exam {today.year}",
        f"Bangkok large events Salaya Nakhon Pathom nearby hotel demand {today.year}",
        f"new airline routes Bangkok BKK DMK {today.year} tourism",
    ]

    search_prompt = f"""Search the web using these queries one at a time and compile all findings:

Queries:
{chr(10).join(f'- {q}' for q in search_queries)}

For each event or demand signal found, note:
1. Event name (exact)
2. Date(s) — specific dates if available
3. Venue / location in Bangkok or nearby
4. Expected attendance scale (small <1k, medium 1k-10k, large >10k)
5. Which visitor segment it attracts: Thai domestic, Chinese tourists, \
Asian tourists (JP/KR/SG), European/Western, or mixed
6. How strongly it would affect overnight hotel demand (high/medium/low)

Pay special attention to:
- Teacher certification exams (krusapa): thousands of upcountry Thai teachers \
travel to Bangkok and need overnight accommodation
- Chinese group tours and FIT demand signals
- Large conventions that fill Bangkok hotels
- Any events near Phutthamonthon / Salaya / Nakhon Pathom area

Date range of interest: {today} to {end_date}
"""

    try:
        search_response = client.beta.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": search_prompt}],
            betas=["web-search-2025-03-05"],
        )
        raw_findings = "\n".join(
            block.text for block in search_response.content
            if hasattr(block, "text")
        )
        log(f"[scraper] Web search complete. Extracting structured events ...")
    except Exception as exc:
        log(f"[scraper] Web search failed: {exc}")
        return []

    # ── Phase 2: structure the findings into JSON ─────────────────────────────
    structure_prompt = f"""Based on these Bangkok event findings:

{raw_findings}

Convert to JSON. Return ONLY the raw JSON object — no markdown, no explanation.

Schema:
{{
  "scraped_date": "{today}",
  "source_summary": "2-3 sentence summary of demand outlook based on what you found",
  "events": [
    {{
      "name": "Event name",
      "date_start": "YYYY-MM-DD",
      "date_end": "YYYY-MM-DD",
      "venue": "Venue name or area",
      "type": "concert|festival|conference|exam|sports|cultural|tourism|other",
      "segment": "thai|chinese|asian|european|all",
      "boost": 20,
      "impact": "high|medium|low",
      "note": "One sentence on why this drives hotel demand"
    }}
  ]
}}

Boost scoring guide:
- Teacher exam (krusapa, upcountry teachers overnight): 25, segment "thai"
- Major concert / music festival (10k+ crowd): 20-25, varies
- International trade show / conference (BITEC/IMPACT): 15-20, segment "all"
- Sports event / marathon: 12-15, varies
- Cultural festival (domestic): 14-18, segment "thai"
- New airline route / tourism campaign: 8-12, segment varies
- Small local event (<1k): 5-8

Only include events from {today} to {end_date}.
If date is uncertain, use your best estimate and note it.
If no events found for a category, simply omit it.
"""

    try:
        struct_response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=3000,
            messages=[{"role": "user", "content": structure_prompt}],
        )
        json_text = struct_response.content[0].text.strip()

        # Strip markdown code fences if present
        json_text = re.sub(r"^```[a-z]*\n?", "", json_text)
        json_text = re.sub(r"\n?```$", "", json_text)

        events_data = json.loads(json_text)
    except (json.JSONDecodeError, IndexError, Exception) as exc:
        log(f"[scraper] JSON parsing failed: {exc}")
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
            print(f"  {ev['date_start']} - {ev['date_end']}  [{ev['boost']:>2}]  {ev['name']}")
    else:
        print("No events found (check API key or network).")
        sys.exit(1)
