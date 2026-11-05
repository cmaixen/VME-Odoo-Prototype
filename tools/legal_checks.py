#!/usr/bin/env python3
"""Collect every `# LEGAL-CHECK:` comment in the code into docs/dev/legal-checks.md.

Usage (from the repository root):
    python3 tools/legal_checks.py           # write docs/dev/legal-checks.md
    python3 tools/legal_checks.py --check   # exit 1 if the file is out of date

A marker looks like `# LEGAL-CHECK: <source> - <text>`; comment lines right below it
continue the text until a sentence ends with a period. Without " - " the whole first
line is taken as the source.
"""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "docs" / "dev" / "legal-checks.md"
SCAN_DIRS = ["addons", "ai"]
SUFFIXES = {".py", ".xml", ".js", ".csv"}
MARKER = re.compile(r"(?:^|\s)(?:#|<!--)\s*LEGAL-CHECK:\s*(?P<rest>.*?)\s*(?:-->)?\s*$")
CONTINUATION = re.compile(r"^\s*#\s?(?P<text>.*)$")


def scan_file(path):
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    checks = []
    for index, line in enumerate(lines):
        match = MARKER.search(line)
        if not match:
            continue
        rest = match.group("rest")
        source, _sep, text = rest.partition(" - ")
        text = text.strip()
        for next_line in lines[index + 1:]:
            cont = CONTINUATION.match(next_line)
            # Stop at the end of the sentence: the comment may go on about something else.
            if not cont or "LEGAL-CHECK" in next_line or text.endswith("."):
                break
            text = f"{text} {cont.group('text').strip()}".strip()
        checks.append({
            "file": path.relative_to(ROOT).as_posix(),
            "line": index + 1,
            "source": source.strip().rstrip("."),
            "text": text,
        })
    return checks


def collect():
    checks = []
    for directory in SCAN_DIRS:
        base = ROOT / directory
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.suffix in SUFFIXES and path.is_file() and "__pycache__" not in path.parts:
                checks.extend(scan_file(path))
    return checks


def cell(value):
    return value.replace("|", "\\|") or "-"


def render(checks):
    out = [
        "# LEGAL-CHECK-punten",
        "",
        "Automatisch gemaakt door `python3 tools/legal_checks.py`; niet met de hand bewerken.",
        "Elke rij is een wettelijke regel in de code die nog juridisch gevalideerd moet worden.",
        "",
        f"Aantal punten: {len(checks)}.",
        "",
        "## Per bron",
        "",
    ]
    by_source = {}
    for check in checks:
        by_source.setdefault(check["source"], []).append(check)
    for source in sorted(by_source):
        refs = ", ".join(f"[{c['file'].split('/')[-1]}:{c['line']}](../../{c['file']}#L{c['line']})" for c in by_source[source])
        out.append(f"- **{source}**: {refs}")
    out += ["", "## Alle punten", "", "| Bestand | Regel | Bron | Tekst |", "| --- | --- | --- | --- |"]
    for check in checks:
        link = f"[{check['file']}](../../{check['file']}#L{check['line']})"
        out.append(f"| {link} | {check['line']} | {cell(check['source'])} | {cell(check['text'])} |")
    return "\n".join(out) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if docs/dev/legal-checks.md is out of date")
    args = parser.parse_args()
    content = render(collect())
    if args.check:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if current != content:
            print(f"{OUTPUT.relative_to(ROOT)} is niet up-to-date: draai python3 tools/legal_checks.py")
            return 1
        return 0
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(content, encoding="utf-8")
    print(f"{OUTPUT.relative_to(ROOT)}: {content.count(chr(10) + '| [')} punten")
    return 0


if __name__ == "__main__":
    sys.exit(main())
