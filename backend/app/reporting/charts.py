"""Static inline-SVG charts for the HTML/PDF report (no JS, print-friendly).

Colors come from the validated reference categorical palette (fixed slot order;
color follows the entity, e.g. a platform always has the same hue). Marks follow the
data-viz spec: 2px lines, rounded bar ends anchored to the baseline, recessive
grid, text in ink colors (never the series color), direct labels kept selective.
"""

from html import escape

SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
PLATFORM_COLORS = {"instagram": SERIES[0], "facebook": SERIES[1], "tiktok": SERIES[2], "linkedin": SERIES[3]}
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e4e3df"
SURFACE = "#fcfcfb"


def _fmt(v: float) -> str:
    if abs(v) >= 1_000_000:
        return f"{v / 1_000_000:.1f}M"
    if abs(v) >= 1_000:
        return f"{v / 1_000:.1f}k"
    if abs(v) >= 10:
        return f"{v:.0f}"
    return f"{v:.2f}".rstrip("0").rstrip(".")


def _nice_max(v: float) -> float:
    if v <= 0:
        return 1.0
    mag = 10 ** (len(str(int(v))) - 1)
    for step in (1, 2, 2.5, 5, 10):
        if step * mag >= v:
            return step * mag
    return 10 * mag


def line_chart(points: list[tuple[str, float | None]], color: str, title: str, y_label: str,
               width: int = 340, height: int = 170) -> str:  # fmt: skip
    """Single-series line (small multiple). Gaps (None) break the line."""
    pad_l, pad_r, pad_t, pad_b = 40, 12, 28, 26
    vals = [v for _, v in points if v is not None]
    if len(vals) < 2:
        return f'<div class="chart-empty">{escape(title)}: not enough weekly data</div>'
    y_max = _nice_max(max(vals))
    w, h = width - pad_l - pad_r, height - pad_t - pad_b
    n = len(points)

    def x(i: int) -> float:
        return pad_l + (w * i / (n - 1) if n > 1 else 0)

    def y(v: float) -> float:
        return pad_t + h - h * v / y_max

    grid = "".join(
        f'<line x1="{pad_l}" x2="{pad_l + w}" y1="{y(y_max * f):.1f}" y2="{y(y_max * f):.1f}" stroke="{GRID}" stroke-width="1"/>'
        f'<text x="{pad_l - 6}" y="{y(y_max * f) + 3:.1f}" text-anchor="end" font-size="9" fill="{INK_2}">{_fmt(y_max * f)}</text>'
        for f in (0, 0.5, 1)
    )
    segs, cur = [], []
    for i, (_, v) in enumerate(points):
        if v is None:
            if len(cur) > 1:
                segs.append(cur)
            cur = []
        else:
            cur.append(f"{x(i):.1f},{y(v):.1f}")
    if len(cur) > 1:
        segs.append(cur)
    paths = "".join(
        f'<polyline points="{" ".join(s)}" fill="none" stroke="{color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>'
        for s in segs
    )
    last_i = max(i for i, (_, v) in enumerate(points) if v is not None)
    last_v = points[last_i][1] or 0
    end = (f'<circle cx="{x(last_i):.1f}" cy="{y(last_v):.1f}" r="4" fill="{color}" stroke="{SURFACE}" stroke-width="2"/>'
           f'<text x="{x(last_i) - 6:.1f}" y="{y(last_v) - 8:.1f}" text-anchor="end" font-size="9" fill="{INK}">{_fmt(last_v)}</text>')  # fmt: skip
    xlabels = (f'<text x="{pad_l}" y="{height - 8}" font-size="9" fill="{INK_2}">{escape(points[0][0])}</text>'
               f'<text x="{pad_l + w}" y="{height - 8}" text-anchor="end" font-size="9" fill="{INK_2}">{escape(points[-1][0])}</text>')  # fmt: skip
    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" role="img" aria-label="{escape(title)}" class="chart">'
        f'<text x="{pad_l}" y="14" font-size="11" font-weight="600" fill="{INK}">{escape(title)}</text>'
        f'<text x="{pad_l + w}" y="14" text-anchor="end" font-size="9" fill="{INK_2}">{escape(y_label)}</text>'
        f"{grid}{paths}{end}{xlabels}</svg>"
    )


def bar_chart(rows: list[tuple[str, float, bool]], color: str, title: str, unit: str = "",
              width: int = 340, bar_h: int = 16) -> str:  # fmt: skip
    """Horizontal bars. rows = (label, value, low_sample). Low-sample bars are hatched-lighter."""
    rows = [r for r in rows if r[1] is not None]
    if not rows:
        return f'<div class="chart-empty">{escape(title)}: no data</div>'
    pad_l, pad_r, pad_t, gap = 96, 44, 24, 6
    w = width - pad_l - pad_r
    height = pad_t + len(rows) * (bar_h + gap) + 6
    v_max = max(v for _, v, _ in rows) or 1
    bars = []
    for i, (lbl, v, low) in enumerate(rows):
        y0 = pad_t + i * (bar_h + gap)
        bw = max(2.0, w * v / v_max)
        opacity = "0.45" if low else "1"
        bars.append(
            f'<text x="{pad_l - 8}" y="{y0 + bar_h / 2 + 3:.1f}" text-anchor="end" font-size="10" fill="{INK}">{escape(lbl)}</text>'
            f'<path d="M{pad_l},{y0} h{bw - 4:.1f} a4,4 0 0 1 4,4 v{bar_h - 8} a4,4 0 0 1 -4,4 h{-(bw - 4):.1f} z" '
            f'fill="{color}" fill-opacity="{opacity}"/>'
            f'<text x="{pad_l + bw + 5:.1f}" y="{y0 + bar_h / 2 + 3:.1f}" font-size="10" fill="{INK_2}">{_fmt(v)}{escape(unit)}{" *" if low else ""}</text>'
        )
    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" role="img" aria-label="{escape(title)}" class="chart">'
        f'<text x="{pad_l}" y="14" font-size="11" font-weight="600" fill="{INK}">{escape(title)}</text>'
        f'<line x1="{pad_l}" x2="{pad_l}" y1="{pad_t - 2}" y2="{height - 4}" stroke="{GRID}"/>'
        + "".join(bars)
        + "</svg>"
    )


def mix_bars(mixes: list[tuple[str, dict[str, float]]], order: list[str], title: str, width: int = 700) -> str:
    """100% stacked bars (one per platform) for content-pillar mix, with a shared legend."""
    pad_l, pad_t, bar_h, gap = 90, 24, 18, 10
    w = width - pad_l - 16
    colors = {k: SERIES[i % len(SERIES)] for i, k in enumerate(order)}
    height = pad_t + len(mixes) * (bar_h + gap) + 30
    parts = []
    for i, (lbl, mix) in enumerate(mixes):
        y0 = pad_t + i * (bar_h + gap)
        x0 = float(pad_l)
        parts.append(
            f'<text x="{pad_l - 8}" y="{y0 + 13}" text-anchor="end" font-size="10" fill="{INK}">{escape(lbl)}</text>'
        )
        total = sum(mix.values()) or 1
        for k in order:
            v = mix.get(k, 0) or 0
            if v <= 0:
                continue
            seg = w * v / total
            parts.append(
                f'<rect x="{x0:.1f}" y="{y0}" width="{max(seg - 2, 1):.1f}" height="{bar_h}" rx="2" fill="{colors[k]}"><title>{escape(k)}: {v:.0f}%</title></rect>'
            )
            if seg > 34:
                parts.append(f'<text x="{x0 + 4:.1f}" y="{y0 + 13}" font-size="9" fill="#ffffff">{v:.0f}%</text>')
            x0 += seg
    ly = height - 12
    lx = float(pad_l)
    for k in order:
        parts.append(f'<rect x="{lx:.1f}" y="{ly - 8}" width="10" height="10" rx="2" fill="{colors[k]}"/>'
                     f'<text x="{lx + 14:.1f}" y="{ly + 1}" font-size="9" fill="{INK_2}">{escape(k.replace("_", " "))}</text>')  # fmt: skip
        lx += 14 + 6.2 * len(k) + 14
    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" role="img" aria-label="{escape(title)}" class="chart">'
        f'<text x="{pad_l}" y="14" font-size="11" font-weight="600" fill="{INK}">{escape(title)}</text>'
        + "".join(parts)
        + "</svg>"
    )
