# BuPlace Revenue Management Agent
## Setup & Run Guide

---

## What this does

Every morning at 6AM this agent:
1. Searches the web for market conditions, events, competitor rates, airline demand
2. Calculates optimal room prices for the next 60 days
3. Logs into SiteMinder via Computer Use and updates rates (or emails you for approval)
4. Sends you a daily pricing brief by email

---

## Requirements

- Python 3.9+
- Claude Code installed (`npm install -g @anthropic-ai/claude-code`)
- Anthropic API key with Computer Use enabled

```bash
pip install anthropic python-dotenv
```

---

## Setup (5 minutes)

### 1. Fill in your config
Edit `config/siteminder.env` — fill in every value:
- Your hotel location
- Your room prices (base, floor, ceiling)
- Your SiteMinder login credentials
- Your email address
- Set `APPROVAL_MODE=approval` to start safe (you approve before anything goes live)

### 2. Add .gitignore
```
config/siteminder.env
data/
logs/
```

### 3. Test a manual run
```bash
python run_daily.py
```
Watch the terminal. It will:
- Search the web (takes ~2 min)
- Generate pricing JSON
- Open SiteMinder in a browser (you'll see it happen)
- Send you an email

### 4. Schedule daily runs (Windows Task Scheduler)
- Open Task Scheduler
- Create Basic Task → Daily → 6:00 AM
- Action: `python C:\path\to\buplace-agent\run_daily.py`

### 4. Schedule daily runs (Mac/Linux cron)
```bash
crontab -e
# Add this line:
0 6 * * * /usr/bin/python3 /path/to/buplace-agent/run_daily.py
```

---

## File structure

```
buplace-agent/
├── AGENT_PROMPT.md          ← The full Claude agent instructions
├── run_daily.py             ← Daily runner script (cron this)
├── config/
│   └── siteminder.env       ← Your credentials & config (KEEP PRIVATE)
├── data/
│   ├── market_YYYY-MM-DD.json      ← Raw market research
│   ├── pricing_YYYY-MM-DD.json     ← Generated pricing decisions
│   └── screenshots/               ← SiteMinder confirmation screenshots
└── logs/
    ├── YYYY-MM-DD.log       ← Daily run log
    ├── history.csv          ← Summary of every run
    └── cron.log             ← Cron output
```

---

## Approval flow (recommended to start)

With `APPROVAL_MODE=approval`:

1. Agent runs at 6AM
2. You get an email: "BuPlace Pricing Brief — Thursday Apr 10 — Action Required"
3. Email shows proposed rates for all 60 days with reasons
4. You reply **APPROVE** → agent applies all rates to SiteMinder
5. Or reply **APPROVE 2025-04-11 to 2025-04-20** → applies only that range

Switch to `APPROVAL_MODE=auto` once you trust the agent's decisions.

---

## Troubleshooting

**"SiteMinder login failed"**
→ Check credentials in siteminder.env
→ SiteMinder may have 2FA — disable it or use an app password

**"UI_CHANGED warning"**
→ SiteMinder updated their interface
→ The agent will email you a screenshot
→ Reply with updated navigation instructions

**Agent times out**
→ Increase timeout in run_daily.py (default 30 min)
→ Check internet connection

**No email received**
→ Check Claude Code has Gmail MCP connected
→ Check spam folder

---

## Costs

- Claude API: ~$0.50–2.00 per daily run (Computer Use tokens are higher)
- Everything else: free
- No SaaS subscriptions needed
