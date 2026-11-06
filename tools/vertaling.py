#!/usr/bin/env python3
"""Help with the French translation of the VME modules (see docs/dev/vertaling.md).

    python3 tools/vertaling.py todo   <module> <out.json> [--chunk N]
        Write the untranslated or fuzzy terms of addons/<module>/i18n/fr.po (or of the .pot when
        fr.po does not exist yet) to JSON files: [{"id": 12, "msgid": "...", "where": "..."}].
    python3 tools/vertaling.py apply  <module> <translations.json> [...]
        Fill addons/<module>/i18n/fr.po with {"12": "traduction", ...} (ids from "todo").
    python3 tools/vertaling.py check  <module>
        Report empty translations, fuzzy entries and placeholders or tags that differ.

No dependencies: a small parser for the .po files that Odoo exports.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HEADER_FR = {
    "Language": "fr",
    "Plural-Forms": "nplurals=2; plural=(n > 1);",
}


def unquote(s):
    return json.loads(s) if s.startswith('"') else s


def quote(s):
    """PO quoting; long or multi-line strings are split like Odoo does."""
    out = json.dumps(s, ensure_ascii=False)
    if "\\n" not in out[1:-3] and len(out) < 78:
        return out
    parts = re.split(r"(?<=\\n)", out[1:-1])
    return '""\n' + "\n".join(f'"{p}"' for p in parts if p)


class Entry:
    def __init__(self):
        self.comments, self.msgid, self.msgstr, self.ctxt = [], "", "", None
        self.flags = set()

    @property
    def fuzzy(self):
        return "fuzzy" in self.flags

    def where(self):
        return " ".join(c[3:] for c in self.comments if c.startswith("#: "))[:300]

    def dump(self):
        lines = [c for c in self.comments if not c.startswith("#,")]
        flags = sorted(self.flags)
        if flags:
            lines.append("#, " + ", ".join(flags))
        if self.ctxt is not None:
            lines.append("msgctxt " + quote(self.ctxt))
        lines.append("msgid " + quote(self.msgid))
        lines.append("msgstr " + quote(self.msgstr))
        return "\n".join(lines)


def parse(path):
    entries, cur, field = [], Entry(), None
    for raw in Path(path).read_text(encoding="utf-8").split("\n") + [""]:
        line = raw.strip()
        if not line:
            if field:
                entries.append(cur)
            cur, field = Entry(), None
        elif line.startswith("#,"):
            cur.flags |= {f.strip() for f in line[2:].split(",")}
        elif line.startswith("#~"):
            continue  # obsolete entries from msgmerge: dropped
        elif line.startswith("#"):
            cur.comments.append(raw)
        elif line.startswith("msgctxt "):
            field, cur.ctxt = "ctxt", unquote(line[8:])
        elif line.startswith("msgid "):
            field, cur.msgid = "msgid", unquote(line[6:])
        elif line.startswith("msgstr "):
            field, cur.msgstr = "msgstr", unquote(line[7:])
        elif line.startswith('"'):
            setattr(cur, field, getattr(cur, field) + unquote(line))
    return entries


def write(path, entries):
    head = entries[0]
    if not head.msgid:
        meta = dict(l.split(": ", 1) for l in head.msgstr.split("\n") if ": " in l)
        meta.update(HEADER_FR)
        head.msgstr = "".join(f"{k}: {v}\n" for k, v in meta.items())
    Path(path).write_text("\n\n".join(e.dump() for e in entries) + "\n", encoding="utf-8")


def po_path(module):
    i18n = ROOT / "addons" / module / "i18n"
    fr = i18n / "fr.po"
    return fr, (fr if fr.exists() else i18n / f"{module}.pot")


PLACEHOLDER = re.compile(r"%\([a-z_0-9]+\)[sdf]|%[sdf]|\{\{.*?\}\}|\{[a-z_0-9]*\}|%%")
TAG = re.compile(r"</?([a-zA-Z0-9]+)|\bt-[a-z-]+=\"[^\"]*\"")


def problems(e):
    if not e.msgid:
        return []
    if not e.msgstr:
        return ["vertaling ontbreekt"]
    out = []
    if sorted(PLACEHOLDER.findall(e.msgid)) != sorted(PLACEHOLDER.findall(e.msgstr)):
        out.append("plaatshouders verschillen")
    if sorted(TAG.findall(e.msgid)) != sorted(TAG.findall(e.msgstr)):
        out.append("tags verschillen")
    if e.fuzzy:
        out.append("fuzzy")
    return out


def main(argv):
    cmd, module = argv[0], argv[1]
    fr, src = po_path(module)
    entries = parse(src)
    if cmd == "todo":
        out, chunk = Path(argv[2]), int(argv[argv.index("--chunk") + 1]) if "--chunk" in argv else 0
        todo = [{"id": i, "msgid": e.msgid, "where": e.where(), **({"old": e.msgstr} if e.fuzzy else {})}
                for i, e in enumerate(entries) if e.msgid and (not e.msgstr or e.fuzzy)]
        parts = [todo[i:i + chunk] for i in range(0, len(todo), chunk)] if chunk else [todo]
        for n, part in enumerate(parts):
            path = out if len(parts) == 1 else out.with_name(f"{out.stem}_{n:02d}{out.suffix}")
            path.write_text(json.dumps(part, ensure_ascii=False, indent=1), encoding="utf-8")
            print(path, len(part))
    elif cmd == "apply":
        for path in argv[2:]:
            for key, value in json.loads(Path(path).read_text(encoding="utf-8")).items():
                e = entries[int(key)]
                e.msgstr = value
                e.flags.discard("fuzzy")
        write(fr, entries)
        print(fr)
    elif cmd == "check":
        bad = 0
        for i, e in enumerate(entries):
            for p in problems(e):
                bad += 1
                print(f"[{i}] {p}: {e.msgid[:80]!r} -> {e.msgstr[:80]!r}")
        total = sum(1 for e in entries if e.msgid)
        print(f"{src.name}: {total} termen, {bad} problemen")
        return 1 if bad else 0
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
