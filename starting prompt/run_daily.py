#!/usr/bin/env python3
"""
BuPlace Revenue Management Agent — Daily Runner
Run this script via cron every morning at 6AM.

Cron entry (runs at 6:00 AM daily):
  0 6 * * * /usr/bin/python3 /path/to/buplace-agent/run_daily.py >> /path/to/buplace-agent/logs/cron.log 2>&1

Requirements:
  pip install anthropic python-dotenv
"""

import os
import json
import subprocess
from datetime import datetime
from dotenv import load_dotenv

load_dotenv("config/siteminder.env")

# ── CONFIG ─────────────────────────────────────────────────────────────────────

HOTEL_NAME     = "BuPlace Hotel"
HOTEL_LOCATION = os.getenv("HOTEL_LOCATION", "FILL_IN_CITY_COUNTRY")
STAR_RATING    = os.getenv("STAR_RATING", "4-star boutique")
OWNER_EMAIL    = os.getenv("OWNER_EMAIL", "FILL_IN_EMAIL")
APPROVAL_MODE  = os.getenv("APPROVAL_MODE", "approval")  # "auto" or "approval"

COMPETITORS    = os.getenv("COMPETITORS", "").split(",")
AIRPORTS       = os.getenv("AIRPORTS", "").split(",")

BASE_PRICES    = {
    "standard": float(os.getenv("BASE_STANDARD", "120")),
    "deluxe":   float(os.getenv("BASE_DELUXE",   "162")),
    "suite":    float(os.getenv("BASE_SUITE",     "252")),
}
FLOOR_PRICES   = {
    "standard": float(os.getenv("FLOOR_STANDARD", "80")),
    "deluxe":   float(os.getenv("FLOOR_DELUXE",   "108")),
    "suite":    float(os.getenv("FLOOR_SUITE",     "170")),
}
CEILING_PRICES = {
    "standard": float(os.getenv("CEIL_STANDARD", "280")),
    "deluxe":   float(os.getenv("CEIL_DELUXE",   "380")),
    "suite":    float(os.getenv("CEIL_SUITE",     "600")),
}

SITEMINDER_URL  = os.getenv("SITEMINDER_URL", "https://app.siteminder.com")
SITEMINDER_USER = os.getenv("SITEMINDER_USER", "")
SITEMINDER_PASS = os.getenv("SITEMINDER_PASS", "")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

TODAY = datetime.now().strftime("%Y-%m-%d")

# ── DIRECTORIES ────────────────────────────────────────────────────────────────

os.makedirs("logs", exist_ok=True)
os.makedirs("data/screenshots", exist_ok=True)

LOG_FILE = f"logs/{TODAY}.log"

def log(msg, level="INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] [{level}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

# ── CLAUDE CODE INVOCATION ─────────────────────────────────────────────────────

def run_claude_agent():
    """
    Invokes Claude Code with the full agent prompt.
    Claude Code handles web search, computer use, and Gmail automatically.
    """

    log("Starting BuPlace Revenue Agent")
    log(f"Hotel: {HOTEL_NAME} | Location: {HOTEL_LOCATION} | Mode: {APPROVAL_MODE}")

    # Build the task prompt that goes to Claude Code
    task_prompt = build_task_prompt()

    # Save it so Claude Code can read it
    with open(f"data/task_{TODAY}.md", "w") as f:
        f.write(task_prompt)

    log("Task prompt written. Invoking Claude Code...")

    # Run Claude Code with the agent prompt
    # Claude Code reads AGENT_PROMPT.md as system context + task as the user message
    result = subprocess.run(
        [
            "claude",
            "--print",                          # non-interactive mode
            "--model", "claude-opus-4-5",       # use most capable model for agentic tasks
            "--system-prompt", open("AGENT_PROMPT.md").read(),
            task_prompt
        ],
        capture_output=True,
        text=True,
        timeout=1800  # 30 min max
    )

    if result.returncode == 0:
        log("Claude Code completed successfully")
        log(f"Output preview: {result.stdout[:300]}...")
    else:
        log(f"Claude Code exited with error: {result.stderr[:300]}", "ERROR")

    # Log to history CSV
    append_history(result.returncode == 0)

    return result.returncode == 0


def build_task_prompt():
    """Builds today's specific task message for the agent."""

    from datetime import timedelta
    dates_60 = []
    for i in range(1, 61):
        d = datetime.now() + timedelta(days=i)
        dates_60.append(d.strftime("%Y-%m-%d"))

    competitor_list = ", ".join([c.strip() for c in COMPETITORS if c.strip()]) or "comparable hotels in area"
    airport_list = ", ".join([a.strip() for a in AIRPORTS if a.strip()]) or "nearby airports"

    return f"""
# TODAY'S TASK — {TODAY}

Run the full 5-step revenue management sequence for BuPlace Hotel.

## Context
- Date: {TODAY}
- Hotel: {HOTEL_NAME}
- Location: {HOTEL_LOCATION} ({STAR_RATING})
- Approval mode: {APPROVAL_MODE}
- Owner email: {OWNER_EMAIL}

## Pricing bounds
- Standard: floor ${FLOOR_PRICES['standard']} | base ${BASE_PRICES['standard']} | ceiling ${CEILING_PRICES['standard']}
- Deluxe:   floor ${FLOOR_PRICES['deluxe']}   | base ${BASE_PRICES['deluxe']}   | ceiling ${CEILING_PRICES['deluxe']}
- Suite:    floor ${FLOOR_PRICES['suite']}     | base ${BASE_PRICES['suite']}    | ceiling ${CEILING_PRICES['suite']}

## Competitors to research
{competitor_list}

## Airports to monitor
{airport_list}

## Dates to price
{chr(10).join(dates_60)}

## SiteMinder credentials
- URL: {SITEMINDER_URL}
- User: {SITEMINDER_USER}
- Pass: (load from config/siteminder.env — variable SITEMINDER_PASS)

## Instructions
Follow all 5 steps in AGENT_PROMPT.md exactly.
- Save market data to: data/market_{TODAY}.json
- Save pricing to: data/pricing_{TODAY}.json
- Log everything to: logs/{TODAY}.log
- Send email to: {OWNER_EMAIL}
- SiteMinder action: {"APPLY rates directly, then screenshot confirmation" if APPROVAL_MODE == "auto" else "DO NOT apply yet — screenshot proposed grid, include in email, await APPROVE reply"}

Begin now.
"""


def append_history(success: bool):
    """Append a summary row to the history log."""
    pricing_file = f"data/pricing_{TODAY}.json"
    avg_std = "N/A"
    high_days = "N/A"

    if os.path.exists(pricing_file):
        try:
            with open(pricing_file) as f:
                data = json.load(f)
            prices = [d["standard"] for d in data.get("pricing", [])]
            avg_std = round(sum(prices) / len(prices), 2) if prices else "N/A"
            high_days = sum(1 for d in data.get("pricing", []) if d.get("demand_level") == "HIGH")
        except:
            pass

    sm_status = "applied" if APPROVAL_MODE == "auto" else "pending_approval"
    if not success:
        sm_status = "error"

    row = f"{TODAY},{avg_std},{high_days},{sm_status},{'yes' if success else 'no'}\n"
    with open("logs/history.csv", "a") as f:
        f.write(row)

    log(f"History logged: avg_std={avg_std}, high_days={high_days}, sm={sm_status}")


# ── ENTRY POINT ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    log("=" * 60)
    log(f"BuPlace Revenue Agent — {TODAY}")
    log("=" * 60)

    if not ANTHROPIC_API_KEY:
        log("ANTHROPIC_API_KEY not set in environment", "ERROR")
        exit(1)

    if HOTEL_LOCATION == "FILL_IN_CITY_COUNTRY":
        log("HOTEL_LOCATION not configured in siteminder.env", "ERROR")
        exit(1)

    success = run_claude_agent()
    log(f"Run complete. Success: {success}")
    log("=" * 60)
    exit(0 if success else 1)
