#!/usr/bin/env python3
"""Render the headline cost-spread bar chart to assets/cost-spread.png.

Reuses the unit-tested cost engine (cost_calc) so the chart can never drift
from the published tables — same data, same numbers. The visual drama (a
huge bar next to a sliver) *is* the message: the cheapest path is ~100x less
than the priciest for the same task.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from cost_calc import MODELS_FILE, SCENARIOS, compute_cost, format_cost
import json

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "cost-spread.png"

W, H = 1200, 675
BG = "#0d1117"
WHITE = "#f0f6fc"
GRAY = "#8b949e"
BLUE = "#58a6ff"
GREEN = "#3fb950"
RED = "#f85149"
TRACK = "#161b22"

F = "/System/Library/Fonts/Supplemental/"
BOLD = lambda s: ImageFont.truetype(F + "Arial Bold.ttf", s)
REG = lambda s: ImageFont.truetype(F + "Arial.ttf", s)


def main() -> int:
    models = json.loads(MODELS_FILE.read_text(encoding="utf-8"))["models"]
    email = next(s for s in SCENARIOS if s.id == "email")
    rows = []
    for m in models:
        p = m.get("pricing_usd_per_mtok")
        if m.get("scenario_cost") and p:
            rows.append((m["name"], compute_cost(p, email, m.get("reasoning", False))))
    rows.sort(key=lambda r: r[1])
    cheapest, priciest = rows[0][1], rows[-1][1]
    ratio = priciest / cheapest

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 6], fill=BLUE)

    d.text((48, 40), "Cost to write one 100K-token report", font=BOLD(38), fill=WHITE)
    d.text((48, 92), "Same task, every model — computed by a unit-tested script.", font=REG(22), fill=GRAY)

    # bars
    x0 = 250
    bar_max = W - x0 - 150
    top = 150
    row_h = (H - top - 70) / len(rows)
    bh = int(row_h * 0.62)
    name_f, val_f = BOLD(21), BOLD(20)
    for i, (name, cost) in enumerate(rows):
        y = int(top + i * row_h)
        # linear scale — the sliver-vs-slab contrast is the point
        w = max(4, int(bar_max * cost / priciest))
        color = GREEN if i == 0 else RED if i == len(rows) - 1 else BLUE
        d.rectangle([x0, y, x0 + bar_max, y + bh], fill=TRACK)
        d.rectangle([x0, y, x0 + w, y + bh], fill=color)
        # model name right-aligned in the left gutter
        bb = d.textbbox((0, 0), name, font=name_f)
        d.text((x0 - 14 - (bb[2] - bb[0]), y + bh / 2 - 12), name, font=name_f, fill=WHITE)
        d.text((x0 + w + 12, y + bh / 2 - 11), format_cost(cost), font=val_f, fill=color)

    d.text(
        (48, H - 52),
        f"{ratio:.0f}x  cheapest vs most expensive   ·   github.com/cuihuan/awesome-ai-gateway",
        font=BOLD(22),
        fill=BLUE,
    )

    OUT.parent.mkdir(exist_ok=True)
    img.save(OUT, "PNG")
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB) — {ratio:.0f}x spread")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
