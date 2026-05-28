"""Render a Genesis Engine paper Markdown file to print-ready, self-contained HTML.

Used only to produce the PDF artifacts (via headless Chrome --print-to-pdf).
Pure stdlib + the `markdown` package; no network, no binary deps.
"""
from __future__ import annotations

import sys
from pathlib import Path

import markdown

CSS = """
@page { size: A4; margin: 20mm 18mm; }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body {
  font-family: "Georgia", "Cambria", "Times New Roman", serif;
  font-size: 10.5pt; line-height: 1.5; color: #1a1a1a;
  max-width: 720px; margin: 0 auto;
}
h1 { font-size: 19pt; line-height: 1.25; margin: 0 0 .4em; color: #111; }
h2 { font-size: 14pt; margin: 1.4em 0 .4em; border-bottom: 1px solid #ccc;
     padding-bottom: .15em; color: #111; page-break-after: avoid; }
h3 { font-size: 11.5pt; margin: 1.1em 0 .3em; color: #222; page-break-after: avoid; }
p { margin: .5em 0; text-align: justify; }
code { font-family: "Consolas", "DejaVu Sans Mono", monospace; font-size: 9pt;
       background: #f4f4f4; padding: .5px 4px; border-radius: 3px; }
pre { background: #f6f8fa; border: 1px solid #e1e4e8; border-radius: 5px;
      padding: 10px 12px; overflow-x: auto; font-size: 8.5pt; line-height: 1.4;
      page-break-inside: avoid; }
pre code { background: none; padding: 0; font-size: 8.5pt; }
table { border-collapse: collapse; width: 100%; margin: .8em 0; font-size: 9pt;
        page-break-inside: avoid; }
th, td { border: 1px solid #ccc; padding: 5px 8px; text-align: left;
         vertical-align: top; }
th { background: #f0f0f0; font-weight: bold; }
blockquote { border-left: 3px solid #888; margin: .8em 0; padding: .2em 0 .2em 14px;
             color: #444; font-style: italic; }
hr { border: none; border-top: 1px solid #ddd; margin: 1.6em 0; }
a { color: #0b5fa4; text-decoration: none; }
strong { color: #000; }
em { color: #333; }
"""

HTML_TMPL = """<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>{css}</style>
</head>
<body>
{body}
</body>
</html>
"""


def main() -> int:
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2])
    lang = sys.argv[3] if len(sys.argv) > 3 else "en"
    text = src.read_text(encoding="utf-8")
    body = markdown.markdown(
        text,
        extensions=["tables", "fenced_code", "toc", "sane_lists", "smarty"],
        output_format="html5",
    )
    title = next(
        (ln.lstrip("# ").strip() for ln in text.splitlines() if ln.startswith("# ")),
        "Genesis Engine",
    )
    dst.write_text(
        HTML_TMPL.format(lang=lang, title=title, css=CSS, body=body),
        encoding="utf-8",
    )
    print(f"wrote {dst} ({dst.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
