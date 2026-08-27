#!/usr/bin/env python3
"""
Build /app/data/national_waste_list.json from the official waste list DOCX.

Source of truth: «Перелік відходів для сайта» (Національний перелік відходів).
Each non-empty paragraph is one of:
  * Chapter (level 1):   "NN <name>"            e.g. "02 Відходи ..."
  * Group   (level 2):   "NN NN <name>"         e.g. "02 01 Відходи ..."
  * Code    (level 3):   "NN NN NN[*] <name>"   e.g. "02 01 08* ..."

A trailing '*' on a leaf code marks an ABSOLUTE hazardous entry.

Usage:
    python build_national_waste_list.py /path/to/source.docx
Writes: /app/data/national_waste_list.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import docx  # python-docx

OUT_FILE = Path("/app/data/national_waste_list.json")

RE_CODE = re.compile(r"^(\d{2} \d{2} \d{2})(\*?)\s+(.+)$")   # level 3 (leaf)
RE_GROUP = re.compile(r"^(\d{2} \d{2})\s+(.+)$")             # level 2
RE_CHAPTER = re.compile(r"^(\d{2})\s+(.+)$")                 # level 1

# Non-hazardous "mirror" twins usually phrase: "... інші, ніж зазначені за кодом ..."
RE_MIRROR = re.compile(r"ніж зазначен", re.IGNORECASE)


def build(source_docx: str) -> list[dict]:
    doc = docx.Document(source_docx)
    rows: list[dict] = []
    for p in doc.paragraphs:
        text = " ".join(p.text.split()).strip()  # collapse whitespace
        if not text:
            continue

        m = RE_CODE.match(text)
        if m:
            base, star, name = m.group(1), m.group(2), m.group(3).strip()
            code = f"{base}{star}"
            hazardous = star == "*"
            chapter = base[:2]
            group = base[:5]
            rows.append({
                "level": 3,
                "code": code,
                "name": name,
                "chapter": chapter,
                "group": group,
                "parent_code": group,
                "absolute_hazardous": hazardous,
                "mirror_hazardous": (not hazardous) and bool(RE_MIRROR.search(name)),
            })
            continue

        m = RE_GROUP.match(text)
        if m:
            code, name = m.group(1), m.group(2).strip()
            rows.append({
                "level": 2,
                "code": code,
                "name": name,
                "chapter": code[:2],
                "group": None,
                "parent_code": code[:2],
                "absolute_hazardous": False,
                "mirror_hazardous": False,
            })
            continue

        m = RE_CHAPTER.match(text)
        if m:
            code, name = m.group(1), m.group(2).strip()
            rows.append({
                "level": 1,
                "code": code,
                "name": name,
                "chapter": code,
                "group": None,
                "parent_code": None,
                "absolute_hazardous": False,
                "mirror_hazardous": False,
            })
            continue

        # Anything else = continuation of previous entry's name (wrapped line).
        if rows:
            rows[-1]["name"] = (rows[-1]["name"] + " " + text).strip()

    return rows


def main() -> None:
    src = sys.argv[1] if len(sys.argv) > 1 else "/tmp/waste.docx"
    rows = build(src)

    # De-duplicate leaf codes (keep first occurrence) to satisfy unique index.
    seen: set[str] = set()
    deduped: list[dict] = []
    dups: list[str] = []
    for r in rows:
        if r["level"] == 3:
            if r["code"] in seen:
                dups.append(r["code"])
                continue
            seen.add(r["code"])
        deduped.append(r)

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(deduped, ensure_ascii=False, indent=1), encoding="utf-8")

    lv = {1: 0, 2: 0, 3: 0}
    haz = 0
    for r in deduped:
        lv[r["level"]] += 1
        if r["level"] == 3 and r["absolute_hazardous"]:
            haz += 1
    print(f"Wrote {OUT_FILE}")
    print(f"  chapters(level1)={lv[1]}  groups(level2)={lv[2]}  codes(level3)={lv[3]}  hazardous={haz}")
    if dups:
        print(f"  removed {len(dups)} duplicate leaf codes: {dups}")


if __name__ == "__main__":
    main()
