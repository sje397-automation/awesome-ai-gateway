#!/usr/bin/env python3
"""Render the coding capability-vs-cost chart to assets/coding-value.png.

This is the *coding* counterpart to make_cost_chart.py. Instead of a single
scenario's price, it plots each model's **agentic-coding capability**
(SWE-bench Verified) against the **cost of one coding-agent session**, so the
"value frontier" is visible at a glance: open-weight models reach ~80% at a
fraction of flagship cost.

Both axes are reproducible. The cost axis reuses the unit-tested cost engine
(``cost_calc.compute_cost`` on the shared ``coding`` scenario) so the chart can
never drift from BENCHMARKS.md Part 3.3; the capability axis is the
``swe_bench_verified`` figure dated in data/models.json. Any model that has
*both* a published SWE-bench Verified score and a price is plotted — nothing is
hand-placed.

PIL is imported lazily inside ``render()`` so the pure data function
(``build_coding_data``) stays importable — and unit-testable — on machines
without Pillow (e.g. the CI runner).
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from cost_calc import MODELS_FILE, SCENARIOS, compute_cost, format_cost

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "coding-value.png"


def build_coding_data(models: list[dict]) -> list[dict]:
    """Rows for every model with both a SWE-bench Verified score and a price.

    Cost is the shared ``coding`` agent-session scenario, computed by the same
    engine that drives the published cost tables (reasoning models bill their
    thinking tokens as output). Returns rows sorted cheapest-first; the single
    highest-capability row is flagged ``flagship`` so the renderer can mark the
    price ceiling.
    """
    coding = next(s for s in SCENARIOS if s.id == "coding")
    rows = []
    for m in models:
        swe = (m.get("benchmarks") or {}).get("swe_bench_verified")
        pricing = m.get("pricing_usd_per_mtok")
        if swe is None or not pricing:
            continue
        rows.append(
            {
                "name": m["name"],
                "provider": m["provider"],
                "open": bool(m.get("open")),
                "swe": float(swe),  # fraction 0–1
                "cost": compute_cost(pricing, coding, m.get("reasoning", False)),
                "flagship": False,
            }
        )
    rows.sort(key=lambda r: r["cost"])
    if rows:
        max(rows, key=lambda r: r["swe"])["flagship"] = True
    return rows


PEER_TOLERANCE = 0.02  # ±2 SWE-bench points counts as "ties / rivals"


def value_headline(rows: list[dict]) -> dict | None:
    """The one-line "value" story: best open model vs. the closed peer it rivals.

    Picks the strongest open-weight model, then the most capable *closed* model
    it still matches on SWE-bench (within ±2 points) while costing less, and
    reports the cost multiple it undercuts that peer by. This is the honest
    framing — open weights don't reach the 95% ceiling, but they tie a pricier
    flagship-tier closed model for a fraction of the cost. ``None`` when there
    is no open model that rivals a pricier closed one.
    """
    open_rows = [r for r in rows if r["open"]]
    closed_rows = [r for r in rows if not r["open"]]
    if not open_rows or not closed_rows:
        return None
    best_open = max(open_rows, key=lambda r: (r["swe"], -r["cost"]))
    peers = [
        c for c in closed_rows
        if c["cost"] > best_open["cost"] and abs(c["swe"] - best_open["swe"]) <= PEER_TOLERANCE
    ]
    if not peers:
        return None
    peer = max(peers, key=lambda r: r["swe"])
    top_swe = max(r["swe"] for r in rows)
    return {
        "name": best_open["name"],
        "peer": peer["name"],
        "swe": best_open["swe"],
        "cost": best_open["cost"],
        "cheaper_x": peer["cost"] / best_open["cost"] if best_open["cost"] else 0.0,
        "gap_pts": (top_swe - best_open["swe"]) * 100,
    }


# ── Rendering (PIL only; not exercised by unit tests) ────────────────────────

W, H = 1200, 675
BG = "#0d1117"
WHITE = "#f0f6fc"
GRAY = "#8b949e"
BLUE = "#58a6ff"
GREEN = "#3fb950"
GOLD = "#e3b341"
TRACK = "#161b22"
GRID = "#21262d"

# x-axis (cost, log scale) and y-axis (SWE-bench %) ranges
X_MIN, X_MAX = 0.05, 3.6
Y_MIN, Y_MAX = 70.0, 96.0
X_TICKS = [0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 3.0]
Y_TICKS = [70, 75, 80, 85, 90, 95]

# Per-model label placement (anchor, dx, dy) to keep the 7 labels legible.
# anchor: "l" left-aligned right of the dot, "r" right-aligned left of it.
LABELS = {
    "Claude Fable 5": ("r", -16, -8),
    "GPT-5.5": ("l", 16, -8),
    "Claude Opus 4.8": ("r", -16, -8),
    "Gemini 3.1 Pro": ("c", 0, -34),
    "DeepSeek V4 Pro": ("l", 14, -32),
    "Kimi K2.6": ("l", 14, 16),
    "Claude Haiku 4.5": ("l", 16, -8),
}

PLOT_L, PLOT_R, PLOT_T, PLOT_B = 132, 1140, 185, 560


def _x(cost: float) -> float:
    lo, hi = math.log10(X_MIN), math.log10(X_MAX)
    return PLOT_L + (math.log10(cost) - lo) / (hi - lo) * (PLOT_R - PLOT_L)


def _y(swe_pct: float) -> float:
    return PLOT_B - (swe_pct - Y_MIN) / (Y_MAX - Y_MIN) * (PLOT_B - PLOT_T)


def render(rows: list[dict], out: Path = OUT) -> Path:
    from PIL import Image, ImageDraw, ImageFont

    fdir = "/System/Library/Fonts/Supplemental/"
    bold = lambda s: ImageFont.truetype(fdir + "Arial Bold.ttf", s)
    reg = lambda s: ImageFont.truetype(fdir + "Arial.ttf", s)

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 6], fill=BLUE)

    d.text((48, 36), "Coding: capability vs. cost", font=bold(38), fill=WHITE)
    d.text(
        (48, 88),
        "SWE-bench Verified (higher = better) against the cost of one coding-agent session.",
        font=reg(21),
        fill=GRAY,
    )
    d.text(
        (48, 116),
        "Same unit-tested engine as the cost tables — open-weight models in green.",
        font=reg(21),
        fill=GRAY,
    )

    # grid + y ticks
    for t in Y_TICKS:
        y = _y(t)
        d.line([(PLOT_L, y), (PLOT_R, y)], fill=GRID, width=1)
        d.text((PLOT_L - 46, y - 11), f"{t}%", font=bold(17), fill=GRAY)
    # x ticks
    for t in X_TICKS:
        x = _x(t)
        d.line([(x, PLOT_T), (x, PLOT_B)], fill=GRID, width=1)
        lab = f"${t:g}" if t >= 0.1 else f"${t:.2f}"
        bb = d.textbbox((0, 0), lab, font=bold(16))
        d.text((x - (bb[2] - bb[0]) / 2, PLOT_B + 10), lab, font=bold(16), fill=GRAY)

    # axis captions (no arrow glyphs — Arial lacks them)
    d.text((PLOT_L - 52, PLOT_T - 28), "SWE-bench Verified (higher = better)", font=bold(16), fill=GRAY)
    cap = "cost per coding-agent session  (log scale, USD)"
    bb = d.textbbox((0, 0), cap, font=bold(16))
    d.text(((PLOT_L + PLOT_R) / 2 - (bb[2] - bb[0]) / 2, PLOT_B + 34), cap, font=bold(16), fill=GRAY)

    # points + labels
    for r in rows:
        x, y = _x(r["cost"]), _y(r["swe"] * 100)
        color = GOLD if r["flagship"] else GREEN if r["open"] else BLUE
        d.ellipse([x - 9, y - 9, x + 9, y + 9], fill=color, outline=BG, width=2)
        d.ellipse([x - 3, y - 3, x + 3, y + 3], fill=BG)

        text = f"{r['name']}  {r['swe'] * 100:.1f}% · {format_cost(r['cost'])}"
        anchor, dx, dy = LABELS.get(r["name"], ("l", 14, -8))
        tx, ty = x + dx, y + dy
        bb = d.textbbox((0, 0), text, font=bold(18))
        tw = bb[2] - bb[0]
        if anchor == "r":
            tx -= tw
        elif anchor == "c":
            tx -= tw / 2
        d.text((tx, ty), text, font=bold(18), fill=WHITE)

    # value callout in the empty top-left zone, with a drawn arrow (not a glyph)
    # pointing down to the open-weight cluster.
    hd = value_headline(rows)
    if hd:
        d.text((PLOT_L + 24, PLOT_T + 30), "Open-weight value zone", font=bold(20), fill=GREEN)
        d.text(
            (PLOT_L + 24, PLOT_T + 58),
            "~80% SWE-bench Verified at a fraction of the flagship cost",
            font=bold(15),
            fill=GREEN,
        )
        # arrow: from below the callout down to the cheapest open dot
        target = min((r for r in rows if r["open"]), key=lambda r: r["cost"])
        ax, ay = _x(target["cost"]) + 6, _y(target["swe"] * 100) - 14
        sx, sy = PLOT_L + 60, PLOT_T + 92
        d.line([(sx, sy), (ax, ay)], fill=GREEN, width=2)
        ang = math.atan2(ay - sy, ax - sx)
        for da in (2.5, -2.5):
            d.line(
                [(ax, ay), (ax - 12 * math.cos(ang + da), ay - 12 * math.sin(ang + da))],
                fill=GREEN,
                width=2,
            )

    # footer
    note = "github.com/cuihuan/awesome-ai-gateway"
    if hd:
        note = (
            f"{hd['name']} ties {hd['peer']} on SWE-bench at ~{hd['cheaper_x']:.0f}× less   ·   "
            + note
        )
    d.text((48, H - 30), note, font=bold(19), fill=BLUE)

    out.parent.mkdir(exist_ok=True)
    img.save(out, "PNG")
    return out


def main() -> int:
    models = json.loads(MODELS_FILE.read_text(encoding="utf-8"))["models"]
    rows = build_coding_data(models)
    out = render(rows)
    hd = value_headline(rows)
    extra = f" — {hd['name']} {hd['cheaper_x']:.0f}× cheaper" if hd else ""
    print(f"wrote {out} ({out.stat().st_size // 1024} KB) — {len(rows)} models{extra}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
