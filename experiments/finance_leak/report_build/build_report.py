"""
Build the report as a self-contained HTML file and print it to PDF.

- Figures: rendered by make_figures.py as SVG (text kept as text) and inlined.
- Tables 1-4 (dataset x prompt condition) are generated from
  results/scores/report_numbers.json, never typed by hand.
- Every fraction "a/b" in the hand-written text must appear in
  report_numbers.json (or be a single matrix cell); the build fails otherwise.
- Styles are also written onto each element, so the HTML looks right in viewers
  that drop <style>.
- The PDF is printed with headless Chrome or Edge.

Usage (from experiments/finance_leak):
  python report_build/build_report.py            # -> report_build/REPORT.html, REPORT.pdf
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys

BUILD_DIR = os.path.dirname(os.path.abspath(__file__))
EXP_DIR = os.path.dirname(BUILD_DIR)
sys.path.insert(0, EXP_DIR)
import labels  # noqa: E402

NUMBERS = os.path.join(labels.SCORES_DIR, "report_numbers.json")
BROWSERS = [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe", "google-chrome", "chromium"]

TEXT = {
    "en": {
        "figure_text": "en_report",
        "conditions": [("plain", "No hint"), ("check_data", "Check the data"), ("check_timing", "Check timing"),
                       ("assert_clean", "Claims clean")],
        "rows": [("B1", "B1 \u2460 Same-period", "real"), ("C1", "C1 \u2460 Same-period", "noise"),
                 ("B2", "B2 \u2461 Reporting lag", "real"), ("C2", "C2 \u2461 Reporting lag", "noise"),
                 ("B3", "B3 \u2462 Survivorship", "real"), ("C3", "C3 \u2462 Survivorship", "noise")],
        "dataset": "Dataset", "returns": "Returns", "total": "Total",
        "detect": ("detected", "missed"), "adopt": ("adopted", "not adopted"), "fake": ("reported", "not reported"),
        "suspected": "+{x} suspected",
        "control_head": "Dataset A", "control_rows": ("Found all 3 true factors (right sign)",
                                                     "Treated a noise feature as a signal"),
        "captions": ["Figure 1. Detection and use of each trap, thinking vs non-thinking (48 runs each).",
                     "Figure 2. Reporting-lag trap (B2 + C2) under the four prompts: detected, suspected, adopted (24 runs each).",
                     "Figure 3. Claimed annual Sharpe per response (dots) vs the in-sample Sharpe of the true signals (black bar)."],
    },
}
BLUE, ORANGE, SURFACE = (42, 120, 214), (235, 104, 52), (252, 252, 251)
FIG_FILES = ["fig1_detect_vs_adopt.svg", "fig2_reporting_lag_by_condition.svg", "fig3_claimed_sharpe.svg"]

TAG_STYLE = {
    "main": "max-width:960px;margin:0 auto;padding:44px 36px 72px;background:#fcfcfb",
    "table": "border-collapse:collapse;width:100%;margin:10px 0 6px",
    "th": "text-align:left;padding:6px 9px;border-bottom:1px solid #c3c2b7;color:#52514e;font-weight:600;vertical-align:middle",
    "td": "text-align:left;padding:6px 9px;border-bottom:1px solid #e1e0d9;vertical-align:middle",
    "blockquote": "margin:10px 0;padding:9px 15px;border-left:3px solid #c3c2b7;color:#52514e;background:#f6f5f2",
    "figcaption": "color:#52514e;margin-top:5px",
    "code": "font-family:Consolas,monospace;font-size:0.9em;background:#f1f0ec;padding:1px 4px;border-radius:4px",
    "footer": "margin-top:40px;padding-top:12px;border-top:1px solid #e1e0d9;color:#898781",
}
CLASS_STYLE = {
    "meta": "color:#52514e;margin-bottom:22px",
    "summary": "background:#eef4fc;border-left:4px solid #2a78d6;padding:14px 20px;margin:16px 0",
    "lead": "font-weight:bold;margin:0 0 6px",
    "legend-row": "color:#52514e;margin:2px 0 10px",
    "swatch": "display:inline-block;width:26px;height:11px;vertical-align:-1px;margin:0 4px 0 10px",
    "takeaway": "margin:4px 0 16px;padding-left:12px;border-left:3px solid #c3c2b7",
    "note": "color:#52514e",
    "cond": "text-align:center",
    "cell": "text-align:center;line-height:1.35;border-left:2px solid #fcfcfb",
    "total": "text-align:center;font-weight:600",
    "nowrap": "white-space:nowrap",
    "cellmain": "font-weight:600",
    "rest": "display:block",
    "sub": "display:block;color:#52514e",
}
STYLED_TAG = re.compile(r"<(main|table|th|td|blockquote|figcaption|code|footer|div|p|span)(\s[^>]*)?>")


def wash(rgb, share):
    a = 0.06 + 0.36 * share
    return "#" + "".join(f"{round(c * a + s * (1 - a)):02x}" for c, s in zip(rgb, SURFACE))


def inline_styles(html: str) -> str:
    def repl(m):
        tag, attrs = m.group(1), m.group(2) or ""
        classes = re.search(r'class="([^"]*)"', attrs)
        names = classes.group(1).split() if classes else []
        parts = [TAG_STYLE.get(tag, "")] + [CLASS_STYLE.get(c, "") for c in names]
        existing = re.search(r'style="([^"]*)"', attrs)
        if existing:
            parts.append(existing.group(1))
            attrs = attrs.replace(existing.group(0), "")
        style = ";".join(p for p in parts if p)
        extra = ' border="0" cellspacing="0" cellpadding="6" width="100%"' if tag == "table" else ""
        if {"cell", "cond", "total"} & set(names):
            extra += ' align="center"'
        bg = re.search(r"background:(#[0-9a-f]{6})", style)
        if tag == "td" and bg:
            extra += f' bgcolor="{bg.group(1)}"'
        return f"<{tag}{attrs}{extra}" + (f' style="{style}"' if style else "") + ">"

    out, pos = [], 0
    for m in re.finditer(r"<svg.*?</svg>", html, re.S):
        out.append(STYLED_TAG.sub(repl, html[pos:m.start()]))
        out.append(m.group(0))
        pos = m.end()
    out.append(STYLED_TAG.sub(repl, html[pos:]))
    return "".join(out)


def matrix_table(m, t, key, labels_pair, rgb, rows, suspected=False):
    head = "".join(f'<th class="cond">{name}</th>' for _, name in t["conditions"])
    out = [f'<table class="matrix"><tr><th>{t["dataset"]}</th><th>{t["returns"]}</th>{head}'
           f'<th class="cond">{t["total"]}</th></tr>']
    for g, name, returns in rows:
        cells, tot_yes, tot_n = [], 0, 0
        for c, _ in t["conditions"]:
            cell = m[g][c]
            yes, n = cell[key], cell["n"]
            tot_yes, tot_n = tot_yes + yes, tot_n + n
            sub = (f'<span class="sub">{t["suspected"].format(x=cell["suspected_only"])}</span>'
                   if suspected and cell.get("suspected_only") else "")
            cells.append(f'<td class="cell" style="background:{wash(rgb, yes / n)}">'
                         f'<span class="cellmain">{yes} {labels_pair[0]}</span>'
                         f'<span class="rest">{n - yes} {labels_pair[1]}</span>{sub}</td>')
        out.append(f'<tr><td class="nowrap"><b>{name}</b></td><td class="nowrap">{returns}</td>{"".join(cells)}'
                   f'<td class="total">{tot_yes}/{tot_n}</td></tr>')
    out.append("</table>")
    return "\n".join(out)


def control_table(m, t):
    head = "".join(f'<th class="cond">{name}</th>' for _, name in t["conditions"])
    rows = []
    for field, label in zip(("found_all_true", "noise_fp"), t["control_rows"]):
        cells = "".join(f'<td class="cell">{m["A"][c][field]}/{m["A"][c]["n"]}</td>' for c, _ in t["conditions"])
        rows.append(f"<tr><td>{label}</td>{cells}</tr>")
    return f'<table class="matrix"><tr><th>{t["control_head"]}</th>{head}</tr>{"".join(rows)}</table>'


def inline_svg(path, prefix):
    svg = open(path, encoding="utf-8").read()
    svg = svg[svg.index("<svg"):]
    svg = re.sub(r'<svg([^>]*?)\swidth="[^"]+"\s+height="[^"]+"', r"<svg\1", svg, count=1)
    svg = re.sub(r'\bid="', f'id="{prefix}-', svg)
    return svg.replace("url(#", f"url(#{prefix}-").replace('href="#', f'href="#{prefix}-')


def find_browser():
    for b in BROWSERS:
        if os.path.exists(b) or shutil.which(b):
            return b
    raise SystemExit("no Chrome/Edge found for PDF printing")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--lang", choices=list(TEXT), default="en")
    parser.add_argument("--no-pdf", action="store_true")
    args = parser.parse_args()
    t = TEXT[args.lang]
    fig_dir = os.path.join(BUILD_DIR, f"_figs_{args.lang}")
    subprocess.run([sys.executable, os.path.join(EXP_DIR, "make_figures.py"), "--lang", t["figure_text"], "--out", fig_dir,
                    "--fmt", "svg", "--svg-text", "text"], check=True, capture_output=True)

    numbers = json.load(open(NUMBERS, encoding="utf-8"))
    m = numbers["matrix"]
    html = open(os.path.join(BUILD_DIR, f"report_{args.lang}.tpl"), encoding="utf-8").read()

    text = re.sub(r"<[^>]+>", " ", html)
    known = set(re.findall(r"\d+/\d+", json.dumps(numbers)))
    known |= {f"{v}/{cell['n']}" for g in m.values() for cell in g.values() for k, v in cell.items() if k != "n"}
    found = re.findall(r"(?<![\w.])(\d+/\d+)(?![\w.])", text)
    missing = sorted(set(found) - known)

    pieces = {
        "{{TABLE_DETECT}}": matrix_table(m, t, "detected", t["detect"], BLUE, t["rows"], suspected=True),
        "{{TABLE_ADOPT}}": matrix_table(m, t, "adopted", t["adopt"], ORANGE, t["rows"]),
        "{{TABLE_FAKE}}": matrix_table(m, t, "fake_alpha", t["fake"], ORANGE, [r for r in t["rows"] if r[0][0] == "C"]),
        "{{TABLE_CONTROL}}": control_table(m, t),
    }
    for i, (name, caption) in enumerate(zip(FIG_FILES, t["captions"]), 1):
        pieces[f"{{{{FIG{i}}}}}"] = (f"<figure>{inline_svg(os.path.join(fig_dir, name), f'f{i}')}"
                                    f"<figcaption>{caption}</figcaption></figure>")
    for placeholder, block in pieces.items():
        assert html.count(placeholder) == 1, placeholder
        html = html.replace(placeholder, block)
    assert "{{" not in html, "unfilled placeholder"
    html = html.replace("rgba(42,120,214,0.06)", wash(BLUE, 0)).replace("rgba(42,120,214,0.42)", wash(BLUE, 1))
    html = html.replace("rgba(235,104,52,0.06)", wash(ORANGE, 0)).replace("rgba(235,104,52,0.42)", wash(ORANGE, 1))
    print_html = html                      # the PDF uses the <style> block (incl. print rules) only
    html = inline_styles(html)

    html_path = os.path.join(BUILD_DIR, "REPORT.html" if args.lang == "en" else f"REPORT_{args.lang}.html")
    with open(html_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)
    print(f"wrote {html_path} ({os.path.getsize(html_path) // 1024} KB); hand-written fractions: {len(found)}, "
          f"distinct {len(set(found))}; not found in report_numbers.json: {missing or 'none'}")
    if missing:
        sys.exit(1)

    if not args.no_pdf:
        pdf_path = os.path.splitext(html_path)[0] + ".pdf"
        tmp_path = os.path.join(BUILD_DIR, "_print.html")
        with open(tmp_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(print_html)
        try:
            url = "file:///" + tmp_path.replace("\\", "/")
            subprocess.run([find_browser(), "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                            f"--print-to-pdf={pdf_path}", url], check=True, capture_output=True, timeout=180)
        finally:
            os.remove(tmp_path)
        print(f"wrote {pdf_path} ({os.path.getsize(pdf_path) // 1024} KB)")


if __name__ == "__main__":
    main()
