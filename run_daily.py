"""
BuPlace Hotel — Daily Demand Runner
Run this every morning (Task Scheduler / cron).

What it does:
  1. Scrapes the web for Bangkok events (requires ANTHROPIC_API_KEY)
  2. Generates the 180-day demand chart
  3. Builds the GitHub Pages site (docs/)
  4. Commits and pushes to GitHub

Schedule (Windows Task Scheduler):
  Program: C:\\path\\to\\python.exe
  Arguments: C:\\...\\Hotel Demand Oracle\\run_daily.py
  Start in: C:\\...\\Hotel Demand Oracle
"""

import pathlib
import subprocess
import sys
from datetime import date, datetime

BASE_DIR = pathlib.Path(__file__).parent
LOG_DIR  = BASE_DIR / "logs"


def log(msg: str, level: str = "INFO") -> None:
    ts   = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] [{level}] {msg}"
    print(line)
    LOG_DIR.mkdir(exist_ok=True)
    with open(LOG_DIR / f"{date.today()}.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def git(*args) -> bool:
    result = subprocess.run(
        ["git", *args],
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        log(f"git {' '.join(args)} failed: {result.stderr.strip()}", "WARN")
    return result.returncode == 0


def main() -> int:
    today = date.today()
    log("=" * 56)
    log(f"BuPlace Demand Run — {today}")
    log("=" * 56)

    # ── Step 1: Web scrape for Bangkok events ─────────────────────────────────
    log("Step 1/4 — Web scraping Bangkok events ...")
    try:
        from scraper import run_scraper
        from config import HOTEL
        events = run_scraper(days_ahead=HOTEL["days_ahead"], log=log)
        log(f"Step 1 done — {len(events)} events found")
    except Exception as exc:
        log(f"Step 1 error (non-fatal): {exc}", "WARN")

    # ── Step 2: Reload dynamic events and regenerate chart ───────────────────
    log("Step 2/4 — Generating demand chart ...")
    try:
        # Force reload of dynamic events after scraper wrote new file
        import demand_engine
        demand_engine.reload_dynamic_events()

        import pandas as pd
        from datetime import timedelta
        from demand_engine import get_demand_score
        from demand_predictor import score_to_price, bar_color, demand_label
        from config import HOTEL

        rooms = HOTEL["rooms"]
        records = []
        for i in range(HOTEL["days_ahead"]):
            d = today + timedelta(days=i)
            score, event_labels = get_demand_score(d)
            row = {
                "date":   d,
                "day":    d.strftime("%a"),
                "score":  score,
                "level":  demand_label(score),
                "events": " | ".join(event_labels) if event_labels else "-",
                "color":  bar_color(score),
            }
            for rname, rc in rooms.items():
                row[f"price_{rname}"] = score_to_price(
                    score, rc["floor"], rc["base"], rc["ceiling"]
                )
            records.append(row)
        df = pd.DataFrame(records)

        # Build and save the plotly chart
        import plotly.graph_objects as go
        import os

        room_names = list(rooms.keys())
        price_cols = [f"price_{r}" for r in room_names]
        cur = HOTEL["currency"]

        price_hover = "".join(
            f"{r}: ~%{{customdata[{i+2}]:,}} {cur}<br>"
            for i, r in enumerate(room_names)
        )
        custom = df[["events", "day"] + price_cols + ["level"]].values

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df["date"], y=df["score"],
            marker_color=df["color"], marker_line_width=0,
            customdata=custom,
            hovertemplate=(
                "<b>%{x|%A, %d %b %Y}</b><br>"
                "Demand: <b>%{y}/100</b> (%{customdata[4]})<br>"
                + price_hover +
                "<i>%{customdata[0]}</i><extra></extra>"
            ),
            showlegend=False,
        ))
        for y_val, label_text in [(33, "Low / Normal"), (66, "Normal / High")]:
            fig.add_hline(y=y_val, line_dash="dot", line_color="#cccccc", line_width=1.5,
                          annotation_text=label_text, annotation_position="top left",
                          annotation_font_size=10, annotation_font_color="#aaaaaa")

        annotated = df[(df["score"] >= 72) & (df["events"] != "-")]
        for _, row in annotated.iterrows():
            first = str(row["events"]).split(" | ")[0].replace("[web] ", "")
            fig.add_annotation(x=row["date"], y=row["score"] + 3, text=first,
                               showarrow=False, font=dict(size=9, color="#444"),
                               textangle=-50, xanchor="left", yanchor="bottom")

        for color, label in [
            ("#c1121f", "Peak (80-100)"),
            ("#e76f51", "High (65-79)"),
            ("#2a9d8f", "Normal (48-64)"),
            ("#457b9d", "Low (<48)"),
        ]:
            fig.add_trace(go.Bar(x=[None], y=[None], marker_color=color,
                                 name=label, showlegend=True))

        price_range_note = "  |  ".join(
            f"{r}: {rooms[r]['floor']:,}-{rooms[r]['ceiling']:,} {cur}"
            for r in room_names
        )
        fig.update_layout(
            title=dict(
                text=(f"<b>{HOTEL['name']} - Demand Index - Next {HOTEL['days_ahead']} Days</b><br>"
                      f"<sup>From {today.strftime('%A %d %B %Y')}  |  Price bands: {price_range_note}</sup>"),
                font=dict(size=17), x=0.0, xanchor="left",
            ),
            xaxis=dict(tickformat="%b %d", tickangle=-45, tickmode="linear",
                       dtick=86400000 * 5, showgrid=False),
            yaxis=dict(title="Demand Score (0 = lowest | 100 = peak event)",
                       range=[0, 118], gridcolor="#f0f0f0", zeroline=False),
            plot_bgcolor="#ffffff", paper_bgcolor="#f8f9fa",
            bargap=0.15, height=640,
            margin=dict(t=120, b=140, l=80, r=30),
            legend=dict(orientation="h", yanchor="bottom", y=-0.30,
                        xanchor="center", x=0.5, font=dict(size=11)),
            hoverlabel=dict(bgcolor="white", font_size=13, font_family="monospace"),
        )

        out_dir = BASE_DIR / "output"
        out_dir.mkdir(exist_ok=True)
        date_str  = today.strftime("%Y-%m-%d")
        html_path = out_dir / f"demand_{date_str}.html"
        csv_path  = out_dir / f"demand_{date_str}.csv"
        fig.write_html(str(html_path))
        df.to_csv(str(csv_path), index=False)
        log(f"Step 2 done — chart saved to {html_path}")

    except Exception as exc:
        log(f"Step 2 error: {exc}", "ERROR")
        import traceback; traceback.print_exc()
        return 1

    # ── Step 3: Build GitHub Pages site ──────────────────────────────────────
    log("Step 3/4 — Building site ...")
    try:
        from build_site import build_site
        build_site(df, log=log)
        log("Step 3 done")
    except Exception as exc:
        log(f"Step 3 error: {exc}", "ERROR")

    # ── Step 4: Git commit and push ───────────────────────────────────────────
    log("Step 4/4 — Committing and pushing to GitHub ...")
    try:
        git("add", "docs/")
        git("add", "data/", "output/", "logs/")
        commit_ok = git("commit", "-m", f"Daily demand update {today}")
        if commit_ok:
            push_ok = git("push")
            if push_ok:
                log("Step 4 done — pushed to GitHub")
            else:
                log("Push failed — check remote and credentials", "WARN")
        else:
            log("Nothing to commit (already up to date)", "INFO")
    except Exception as exc:
        log(f"Step 4 error: {exc}", "WARN")

    log("=" * 56)
    log(f"Run complete.")
    log("=" * 56)
    return 0


if __name__ == "__main__":
    sys.exit(main())
