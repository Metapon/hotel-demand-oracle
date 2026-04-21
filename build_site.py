"""
BuPlace Hotel — GitHub Pages Site Builder
Generates docs/index.html and archives today's chart.

docs/
  index.html          <- rebuilt daily (main landing page)
  demand_today.html   <- copy of today's chart (iframe source)
  archive/
    demand_YYYY-MM-DD.html   <- one per day, keeps history
"""

import json
import pathlib
import shutil
from datetime import date, timedelta

import pandas as pd

BASE_DIR  = pathlib.Path(__file__).parent
DOCS_DIR  = BASE_DIR / "docs"
ARC_DIR   = DOCS_DIR / "archive"
OUT_DIR   = BASE_DIR / "output"
DATA_DIR  = BASE_DIR / "data"


def _read_latest_events_summary() -> str:
    files = sorted(DATA_DIR.glob("events_*.json"), reverse=True) if DATA_DIR.exists() else []
    if not files:
        return ""
    try:
        with open(files[0], encoding="utf-8") as f:
            data = json.load(f)
        return data.get("source_summary", "")
    except Exception:
        return ""


def _peak_days_html(df: pd.DataFrame, n: int = 8) -> str:
    top = df[df["score"] >= 65].head(n)
    if top.empty:
        return "<p style='color:#888;font-size:0.85rem;'>No high-demand days in range.</p>"

    rows = ""
    for _, row in top.iterrows():
        score = int(row["score"])
        if score >= 80:
            badge_cls = "badge-peak"
        elif score >= 65:
            badge_cls = "badge-high"
        else:
            badge_cls = "badge-normal"

        event_text = str(row["events"]).replace("[web] ", "").strip()
        event_text = event_text if event_text not in ("", "-", "nan") else ""

        rows += f"""
        <div class="peak-row">
          <div>
            <div class="peak-date">{row['date'].strftime('%b %d')} &nbsp;<span class="peak-dow">{row['day']}</span></div>
            {'<div class="peak-event">' + event_text + '</div>' if event_text else ''}
          </div>
          <span class="badge {badge_cls}">{score}</span>
        </div>"""
    return rows


def _archive_links_html() -> str:
    files = sorted(ARC_DIR.glob("demand_*.html"), reverse=True) if ARC_DIR.exists() else []
    if not files:
        return "<p style='color:#888;font-size:0.85rem;'>No snapshots yet.</p>"
    items = ""
    today_str = f"demand_{date.today()}.html"
    for f in files[:60]:  # show last 60 snapshots
        label = f.stem.replace("demand_", "")
        is_today = f.name == today_str
        cls = "arc-link arc-today" if is_today else "arc-link"
        items += f'<a href="archive/{f.name}" class="{cls}">{label}{"  (today)" if is_today else ""}</a>\n'
    return items


def build_site(df: pd.DataFrame, log=print) -> None:
    today = date.today()

    DOCS_DIR.mkdir(exist_ok=True)
    ARC_DIR.mkdir(exist_ok=True)

    # Copy today's chart into docs/
    src_chart = OUT_DIR / f"demand_{today}.html"
    if not src_chart.exists():
        log(f"[site] Chart not found: {src_chart} — run demand_predictor.py first")
        return

    shutil.copy(src_chart, DOCS_DIR / "demand_today.html")
    shutil.copy(src_chart, ARC_DIR / f"demand_{today}.html")
    log(f"[site] Chart archived -> docs/archive/demand_{today}.html")

    # Stats from dataframe
    today_score = int(df.iloc[0]["score"]) if not df.empty else 0
    tmr_score   = int(df.iloc[1]["score"]) if len(df) > 1 else today_score
    avg_14      = int(df.head(14)["score"].mean())
    peak_row    = df.loc[df["score"].idxmax()]
    peak_date   = peak_row["date"].strftime("%b %d")
    peak_score  = int(peak_row["score"])

    def score_color(s):
        if s >= 80: return "#c1121f"
        if s >= 65: return "#e76f51"
        if s >= 48: return "#2a9d8f"
        return "#457b9d"

    def score_label(s):
        if s >= 80: return "Peak"
        if s >= 65: return "High"
        if s >= 48: return "Normal"
        return "Low"

    events_summary = _read_latest_events_summary()
    peak_days_html  = _peak_days_html(df.head(30))
    archive_html    = _archive_links_html()
    last_updated    = today.strftime("%A, %d %B %Y")
    scrape_note     = (
        f'<p class="scrape-note">{events_summary}</p>'
        if events_summary else
        '<p class="scrape-note" style="color:#aaa;">Web intelligence not yet run — add ANTHROPIC_API_KEY to enable.</p>'
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>BuPlace Hotel | Demand Intelligence</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
          background: #f0f2f5; color: #222; }}

  /* ── Header ── */
  header {{
    background: #12122a;
    color: #fff;
    padding: 18px 32px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
  }}
  .hotel-name {{ font-size: 1.25rem; font-weight: 700; letter-spacing: -0.3px; }}
  .hotel-sub  {{ font-size: 0.78rem; opacity: 0.55; margin-top: 3px; }}
  .updated    {{ font-size: 0.78rem; opacity: 0.5; text-align: right; }}

  /* ── Stats bar ── */
  .stats-bar {{
    background: #fff;
    border-bottom: 1px solid #e8e8e8;
    padding: 14px 32px;
    display: flex;
    gap: 40px;
    flex-wrap: wrap;
  }}
  .stat {{ text-align: center; min-width: 80px; }}
  .stat-val   {{ font-size: 2rem; font-weight: 800; line-height: 1; }}
  .stat-label {{ font-size: 0.7rem; color: #999; margin-top: 4px; text-transform: uppercase; letter-spacing: 0.4px; }}

  /* ── Layout ── */
  .layout {{
    display: grid;
    grid-template-columns: 1fr 300px;
    gap: 20px;
    padding: 20px 32px;
    max-width: 1600px;
    margin: 0 auto;
  }}
  @media (max-width: 960px) {{
    .layout {{ grid-template-columns: 1fr; }}
    .chart-frame {{ height: 480px; }}
  }}

  /* ── Chart card ── */
  .chart-card {{
    background: #fff;
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 2px 10px rgba(0,0,0,0.07);
  }}
  .chart-frame {{
    width: 100%;
    height: 660px;
    border: none;
    display: block;
  }}

  /* ── Sidebar ── */
  .sidebar {{ display: flex; flex-direction: column; gap: 16px; }}
  .card {{
    background: #fff;
    border-radius: 12px;
    padding: 20px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.07);
  }}
  .card-title {{
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    color: #aaa;
    margin-bottom: 14px;
  }}

  /* ── Peak days ── */
  .peak-row {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    padding: 8px 0;
    border-bottom: 1px solid #f5f5f5;
  }}
  .peak-row:last-child {{ border-bottom: none; }}
  .peak-date  {{ font-size: 0.9rem; font-weight: 700; }}
  .peak-dow   {{ font-size: 0.78rem; color: #aaa; font-weight: 400; }}
  .peak-event {{ font-size: 0.75rem; color: #888; margin-top: 2px; max-width: 180px; }}
  .badge {{
    font-size: 0.78rem;
    font-weight: 800;
    padding: 3px 10px;
    border-radius: 20px;
    flex-shrink: 0;
    margin-left: 8px;
  }}
  .badge-peak   {{ background: #fde8e8; color: #c1121f; }}
  .badge-high   {{ background: #fef0e7; color: #e76f51; }}
  .badge-normal {{ background: #e7f6f4; color: #2a9d8f; }}

  /* ── Archive ── */
  .arc-list {{
    display: flex;
    flex-direction: column;
    gap: 2px;
    max-height: 240px;
    overflow-y: auto;
  }}
  .arc-link {{
    display: block;
    padding: 5px 0;
    font-size: 0.85rem;
    color: #e76f51;
    text-decoration: none;
    border-bottom: 1px solid #f8f8f8;
  }}
  .arc-link:hover {{ color: #c1121f; }}
  .arc-today {{ font-weight: 700; }}

  /* ── Web intel ── */
  .scrape-note {{
    font-size: 0.82rem;
    color: #555;
    line-height: 1.6;
  }}

  /* ── Footer ── */
  footer {{
    text-align: center;
    padding: 20px;
    font-size: 0.75rem;
    color: #bbb;
  }}
</style>
</head>
<body>

<header>
  <div>
    <div class="hotel-name">BuPlace Hotel</div>
    <div class="hotel-sub">Demand Intelligence Dashboard &nbsp;&middot;&nbsp; buplace.com</div>
  </div>
  <div class="updated">Updated {last_updated}<br>180-day demand forecast</div>
</header>

<div class="stats-bar">
  <div class="stat">
    <div class="stat-val" style="color:{score_color(today_score)}">{today_score}</div>
    <div class="stat-label">Today's Score</div>
  </div>
  <div class="stat">
    <div class="stat-val" style="color:{score_color(tmr_score)}">{tmr_score}</div>
    <div class="stat-label">Tomorrow</div>
  </div>
  <div class="stat">
    <div class="stat-val" style="color:{score_color(avg_14)}">{avg_14}</div>
    <div class="stat-label">14-Day Avg</div>
  </div>
  <div class="stat">
    <div class="stat-val" style="color:{score_color(peak_score)}">{peak_score}</div>
    <div class="stat-label">Peak ({peak_date})</div>
  </div>
  <div class="stat">
    <div class="stat-val" style="color:#12122a;font-size:1.1rem;padding-top:6px;">
      {score_label(today_score)}
    </div>
    <div class="stat-label">Current Level</div>
  </div>
</div>

<div class="layout">
  <!-- Chart -->
  <div class="chart-card">
    <iframe src="demand_today.html" class="chart-frame" title="Demand Chart"></iframe>
  </div>

  <!-- Sidebar -->
  <div class="sidebar">

    <div class="card">
      <div class="card-title">Web Intelligence</div>
      {scrape_note}
    </div>

    <div class="card">
      <div class="card-title">High-Demand Days (Next 30)</div>
      {peak_days_html}
    </div>

    <div class="card">
      <div class="card-title">Snapshot Archive</div>
      <div class="arc-list">
        {archive_html}
      </div>
    </div>

  </div>
</div>

<footer>
  BuPlace Revenue Intelligence &nbsp;&middot;&nbsp;
  Demand score 0-100: 0 = lowest / 100 = peak event (New Year, Songkran) &nbsp;&middot;&nbsp;
  Auto-updated daily
</footer>

</body>
</html>
"""

    index_path = DOCS_DIR / "index.html"
    index_path.write_text(html, encoding="utf-8")
    log(f"[site] index.html built -> {index_path}")
    log(f"[site] Site ready in docs/ — push to GitHub and enable Pages (source: main / docs)")
