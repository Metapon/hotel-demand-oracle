#!/usr/bin/env python3
"""
BuPlace Hotel - Demand Predictor
Run: python demand_predictor.py

Output:
  output/demand_YYYY-MM-DD.html   interactive chart (opens in browser)
  output/demand_YYYY-MM-DD.csv    raw data export
"""

import pathlib
import webbrowser
from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go

from config import HOTEL
from demand_engine import get_demand_score, MONTHLY_BASE

BASE_DIR = pathlib.Path(__file__).parent


# ── Helpers ───────────────────────────────────────────────────────────────────

def score_to_price(score: int, floor: int, base: int, ceiling: int) -> int:
    """Non-linear mapping: slow ramp below midpoint, steeper above."""
    if score <= 50:
        t = score / 50.0
        price = floor + (base - floor) * t
    else:
        t = (score - 50) / 50.0
        price = base + (ceiling - base) * (t ** 1.35)
    return round(price / 50) * 50  # round to nearest 50 THB


def bar_color(score: int) -> str:
    if score >= 80:
        return "#c1121f"   # deep red - peak / event
    elif score >= 65:
        return "#e76f51"   # orange - above average
    elif score >= 48:
        return "#2a9d8f"   # teal - normal
    else:
        return "#457b9d"   # steel blue - low / competitive


def demand_label(score: int) -> str:
    if score >= 80:
        return "Peak"
    elif score >= 65:
        return "High"
    elif score >= 48:
        return "Normal"
    else:
        return "Low"


def demand_reason(d: date, event_labels: list) -> str:
    """Human-readable explanation shown in hover tooltip."""
    if event_labels:
        lines = []
        for e in event_labels:
            if e.startswith("[web] "):
                lines.append("* " + e[6:])   # mark web-sourced events
            else:
                lines.append(e)
        return "<br>".join(lines)

    # No events — explain via season + day of week
    parts = []
    base = MONTHLY_BASE[d.month]
    if base >= 70:
        parts.append("Peak tourist season")
    elif base >= 60:
        parts.append("High tourist season")
    elif base >= 50:
        parts.append("Mid season")
    elif base <= 42:
        parts.append("Low season (rainy period)")

    dow = d.weekday()
    if dow == 5:
        parts.append("Saturday — highest occupancy day")
    elif dow == 4:
        parts.append("Friday — strong arrival day")
    elif dow == 3:
        parts.append("Thursday — pre-weekend")
    elif dow == 6:
        parts.append("Sunday — late stays")
    elif dow == 0:
        parts.append("Monday — quiet start of week")

    return "<br>".join(parts) if parts else "Standard weekday"


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    today = date.today()
    days  = HOTEL["days_ahead"]
    cur   = HOTEL["currency"]
    rooms = HOTEL["rooms"]
    room_names = list(rooms.keys())

    # Build dataset
    records = []
    for i in range(days):
        d = today + timedelta(days=i)
        score, event_labels = get_demand_score(d)
        row = {
            "date":   d,
            "day":    d.strftime("%a"),
            "score":  score,
            "level":  demand_label(score),
            "events": " | ".join(event_labels) if event_labels else "-",
            "reason": demand_reason(d, event_labels),
            "color":  bar_color(score),
        }
        for rname, rc in rooms.items():
            row[f"price_{rname}"] = score_to_price(
                score, rc["floor"], rc["base"], rc["ceiling"]
            )
        records.append(row)

    df = pd.DataFrame(records)

    # ── Plotly chart ──────────────────────────────────────────────────────────
    price_cols = [f"price_{r}" for r in room_names]

    # customdata: [reason, day, price_Studio, price_Family, level]
    custom_cols = ["reason", "day"] + price_cols + ["level"]
    custom = df[custom_cols].values

    price_hover = "".join(
        f"  {r}: ~%{{customdata[{i+2}]:,}} {cur}<br>"
        for i, r in enumerate(room_names)
    )

    fig = go.Figure()

    # Main bars
    fig.add_trace(go.Bar(
        x=df["date"],
        y=df["score"],
        marker_color=df["color"],
        marker_line_width=0,
        customdata=custom,
        hovertemplate=(
            "<b>%{x|%A, %d %b %Y}</b><br>"
            "Score: <b>%{y} / 100</b>  —  %{customdata[4]}<br>"
            "<br>"
            "<b>Suggested prices:</b><br>"
            + price_hover +
            "<br>"
            "<b>Demand drivers:</b><br>"
            "  %{customdata[0]}"
            "<extra></extra>"
        ),
        name="Demand Score",
        showlegend=False,
    ))

    # Reference lines
    for y_val, label_text in [(33, "Low / Normal boundary"), (66, "Normal / High boundary")]:
        fig.add_hline(
            y=y_val,
            line_dash="dot",
            line_color="#bbbbbb",
            line_width=1.5,
            annotation_text=label_text,
            annotation_position="top left",
            annotation_font_size=10,
            annotation_font_color="#aaaaaa",
        )

    # Annotate significant event spikes (score ≥ 72 with an event label)
    annotated = df[(df["score"] >= 72) & (df["events"] != "-")]
    for _, row in annotated.iterrows():
        first = row["events"].split(" | ")[0].replace("[web] ", "")
        fig.add_annotation(
            x=row["date"],
            y=row["score"] + 3,
            text=first,
            showarrow=False,
            font=dict(size=9, color="#444444"),
            textangle=-50,
            xanchor="left",
            yanchor="bottom",
        )

    # Legend colour swatches (dummy traces)
    for color, label in [
        ("#c1121f", "Peak (80–100) - Premium pricing"),
        ("#e76f51", "High (65–79) - Above average"),
        ("#2a9d8f", "Normal (48–64) - Base pricing"),
        ("#457b9d", "Low (<48) - Competitive pricing"),
    ]:
        fig.add_trace(go.Bar(
            x=[None], y=[None],
            marker_color=color,
            name=label,
            showlegend=True,
        ))

    price_range_note = "  |  ".join(
        f"{r}: {rooms[r]['floor']:,}–{rooms[r]['ceiling']:,} {cur}"
        for r in room_names
    )

    fig.update_layout(
        title=dict(
            text=(
                f"<b>{HOTEL['name']} - Demand Index |Next {days} Days</b><br>"
                f"<sup>From {today.strftime('%A %d %B %Y')}  | "
                f"Price bands: {price_range_note}  | Hover bars for details</sup>"
            ),
            font=dict(size=17),
            x=0.0,
            xanchor="left",
        ),
        xaxis=dict(
            tickformat="%b %d",
            tickangle=-45,
            tickmode="linear",
            dtick=86400000 * 3,   # tick every 3 days (ms unit)
            showgrid=False,
        ),
        yaxis=dict(
            title="Demand Score  (0 = lowest |100 = New Year / peak event)",
            range=[0, 118],
            gridcolor="#f0f0f0",
            zeroline=False,
        ),
        plot_bgcolor="#ffffff",
        paper_bgcolor="#f8f9fa",
        bargap=0.18,
        height=640,
        margin=dict(t=120, b=140, l=80, r=30),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.30,
            xanchor="center",
            x=0.5,
            font=dict(size=11),
            title_text="Demand level:",
            title_font=dict(size=11),
        ),
        hoverlabel=dict(
            bgcolor="white",
            font_size=13,
            font_family="monospace",
        ),
    )

    # ── Save outputs ──────────────────────────────────────────────────────────
    out_dir = BASE_DIR / "output"
    out_dir.mkdir(exist_ok=True)

    date_str  = today.strftime("%Y-%m-%d")
    html_path = out_dir / f"demand_{date_str}.html"
    csv_path  = out_dir / f"demand_{date_str}.csv"

    fig.write_html(str(html_path))
    df.to_csv(str(csv_path), index=False)

    # ── Console summary ───────────────────────────────────────────────────────
    print(f"\n{'='*62}")
    print(f"  {HOTEL['name']} - Demand Forecast  ({days} days from {today})")
    print(f"{'='*62}")
    print(f"  Chart -> {html_path}")
    print(f"  Data  -> {csv_path}")

    print(f"\n  Next 14 days:\n")
    display = df[["date", "day", "score", "level"] + price_cols + ["events"]].head(14).copy()
    display.columns = ["Date", "Day", "Score", "Level"] + room_names + ["Events"]
    print(display.to_string(index=False))

    high = df[df["score"] >= 70]
    if not high.empty:
        print(f"\n  High-demand days (score >= 70): {len(high)}")
        for _, row in high.head(8).iterrows():
            print(f"    {row['date'].strftime('%b %d')} ({row['day']})  "
                  f"{row['score']:>3}/100  {row['events']}")

    print(f"\n{'='*62}\n")

    # Open in browser
    webbrowser.open(html_path.as_uri())


if __name__ == "__main__":
    main()
