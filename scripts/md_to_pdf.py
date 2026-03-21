#!/usr/bin/env python3
"""
Convert Markdown to styled HTML, and optionally to PDF if a local backend exists.

Supported PDF backends:
- pandoc
- wkhtmltopdf

This script intentionally has no third-party Python dependencies.
"""

from __future__ import annotations

import argparse
import html
import re
import shutil
import subprocess
import sys
from pathlib import Path


CSS = """
@page {
  size: A4;
  margin: 22mm 16mm;
}

:root {
  --text: #1f2937;
  --muted: #6b7280;
  --border: #d1d5db;
  --soft: #f8fafc;
  --code-bg: #f3f4f6;
  --accent: #0f766e;
}

html, body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  color: var(--text);
  font-size: 12px;
  line-height: 1.55;
}

body {
  max-width: 900px;
  margin: 0 auto;
}

h1, h2, h3, h4 {
  color: #0f172a;
  margin-top: 1.5em;
  margin-bottom: 0.5em;
  line-height: 1.25;
}

h1 {
  font-size: 26px;
  border-bottom: 2px solid var(--border);
  padding-bottom: 0.3em;
}

h2 { font-size: 20px; }
h3 { font-size: 16px; }
h4 { font-size: 14px; }

p, ul, ol, table, pre, blockquote {
  margin-top: 0.7em;
  margin-bottom: 0.7em;
}

ul, ol {
  padding-left: 1.5em;
}

li + li {
  margin-top: 0.2em;
}

code {
  background: var(--code-bg);
  border-radius: 4px;
  padding: 0.08em 0.35em;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.95em;
}

pre {
  background: var(--code-bg);
  padding: 12px;
  border-radius: 8px;
  overflow-x: auto;
}

pre code {
  background: transparent;
  padding: 0;
}

blockquote {
  border-left: 4px solid var(--accent);
  margin-left: 0;
  padding-left: 12px;
  color: var(--muted);
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 11.5px;
}

th, td {
  border: 1px solid var(--border);
  padding: 7px 8px;
  vertical-align: top;
  text-align: left;
}

th {
  background: var(--soft);
}

hr {
  border: 0;
  border-top: 1px solid var(--border);
  margin: 1.2em 0;
}
"""


def inline_markup(text: str) -> str:
    escaped = html.escape(text, quote=False)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", escaped)
    escaped = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', escaped)
    return escaped


def split_table_row(line: str) -> list[str]:
    inner = line.strip().strip("|")
    return [cell.strip() for cell in inner.split("|")]


def is_table_separator(line: str) -> bool:
    cells = split_table_row(line)
    if not cells:
        return False
    return all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def parse_markdown(md: str) -> str:
    lines = md.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    parts: list[str] = []
    paragraph: list[str] = []
    i = 0

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            text = " ".join(s.strip() for s in paragraph)
            parts.append(f"<p>{inline_markup(text)}</p>")
            paragraph = []

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            flush_paragraph()
            i += 1
            continue

        if stripped.startswith("```"):
            flush_paragraph()
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            code = html.escape("\n".join(code_lines))
            parts.append(f"<pre><code>{code}</code></pre>")
            i += 1
            continue

        if stripped == "---":
            flush_paragraph()
            parts.append("<hr />")
            i += 1
            continue

        heading = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if heading:
            flush_paragraph()
            level = len(heading.group(1))
            parts.append(f"<h{level}>{inline_markup(heading.group(2))}</h{level}>")
            i += 1
            continue

        if stripped.startswith("> "):
            flush_paragraph()
            quote_lines = []
            while i < len(lines) and lines[i].strip().startswith("> "):
                quote_lines.append(lines[i].strip()[2:])
                i += 1
            parts.append(f"<blockquote>{inline_markup(' '.join(quote_lines))}</blockquote>")
            continue

        if (
            "|" in stripped
            and i + 1 < len(lines)
            and "|" in lines[i + 1]
            and is_table_separator(lines[i + 1])
        ):
            flush_paragraph()
            header = split_table_row(lines[i])
            i += 2
            rows = []
            while i < len(lines) and "|" in lines[i]:
                row = split_table_row(lines[i])
                if len(row) != len(header):
                    break
                rows.append(row)
                i += 1

            table_html = ["<table>", "<thead><tr>"]
            table_html.extend(f"<th>{inline_markup(cell)}</th>" for cell in header)
            table_html.append("</tr></thead><tbody>")
            for row in rows:
                table_html.append("<tr>")
                table_html.extend(f"<td>{inline_markup(cell)}</td>" for cell in row)
                table_html.append("</tr>")
            table_html.append("</tbody></table>")
            parts.append("".join(table_html))
            continue

        if re.match(r"^[-*]\s+", stripped):
            flush_paragraph()
            items = []
            while i < len(lines) and re.match(r"^[-*]\s+", lines[i].strip()):
                item = re.sub(r"^[-*]\s+", "", lines[i].strip())
                items.append(f"<li>{inline_markup(item)}</li>")
                i += 1
            parts.append("<ul>" + "".join(items) + "</ul>")
            continue

        if re.match(r"^\d+\.\s+", stripped):
            flush_paragraph()
            items = []
            while i < len(lines) and re.match(r"^\d+\.\s+", lines[i].strip()):
                item = re.sub(r"^\d+\.\s+", "", lines[i].strip())
                items.append(f"<li>{inline_markup(item)}</li>")
                i += 1
            parts.append("<ol>" + "".join(items) + "</ol>")
            continue

        paragraph.append(line)
        i += 1

    flush_paragraph()
    return "\n".join(parts)


def build_html_document(title: str, body_html: str) -> str:
    safe_title = html.escape(title)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{safe_title}</title>
  <style>{CSS}</style>
</head>
<body>
{body_html}
</body>
</html>
"""


def convert_with_pandoc(src: Path, out_pdf: Path) -> bool:
    if not shutil.which("pandoc"):
        return False
    subprocess.run(
        ["pandoc", str(src), "-o", str(out_pdf)],
        check=True,
    )
    return True


def convert_with_wkhtmltopdf(html_path: Path, out_pdf: Path) -> bool:
    if not shutil.which("wkhtmltopdf"):
        return False
    subprocess.run(
        ["wkhtmltopdf", str(html_path), str(out_pdf)],
        check=True,
    )
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert Markdown to HTML and PDF.")
    parser.add_argument("input", help="Markdown input file")
    parser.add_argument(
        "--html-out",
        help="Optional HTML output path. Defaults to the input filename with .html",
    )
    parser.add_argument(
        "--pdf-out",
        help="Optional PDF output path. Defaults to the input filename with .pdf",
    )
    parser.add_argument(
        "--title",
        help="Override document title",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    src = Path(args.input).expanduser().resolve()
    if not src.exists():
        print(f"Input file not found: {src}", file=sys.stderr)
        return 1

    html_out = Path(args.html_out).expanduser().resolve() if args.html_out else src.with_suffix(".html")
    pdf_out = Path(args.pdf_out).expanduser().resolve() if args.pdf_out else src.with_suffix(".pdf")

    md = src.read_text(encoding="utf-8")
    title = args.title or src.stem.replace("_", " ").replace("-", " ").title()
    body_html = parse_markdown(md)
    full_html = build_html_document(title, body_html)

    html_out.write_text(full_html, encoding="utf-8")
    print(f"Wrote HTML: {html_out}")

    try:
        if convert_with_pandoc(src, pdf_out):
            print(f"Wrote PDF with pandoc: {pdf_out}")
            return 0

        if convert_with_wkhtmltopdf(html_out, pdf_out):
            print(f"Wrote PDF with wkhtmltopdf: {pdf_out}")
            return 0
    except subprocess.CalledProcessError as exc:
        print(f"PDF backend failed: {exc}", file=sys.stderr)
        return 1

    print(
        "No PDF backend found. Install `pandoc` or `wkhtmltopdf` to generate PDF, "
        "or print the generated HTML to PDF from a browser.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
