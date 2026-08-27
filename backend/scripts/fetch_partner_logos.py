"""Fetch REAL Ukrainian company logos from Wikimedia (via Wikidata P154) and
normalise them all to uniform transparent PNGs stored in
backend/static/partners/. Prints a JSON map {slug: url} for seeding.

Companies are real Ukrainian brands from sectors that plausibly use a
hazardous / medical / chemical / plastic-waste utilisation operator:
  • Pharma / medical:  Darnitsa, Farmak, Arterium
  • Agro-holdings:     MHP, Kernel, Astarta, Nibulon
  • Retail / industrial: Epicentr
  • Plastic / hygiene: Biosphere
  • Beverage / packaging: Obolon, Roshen
"""
import io
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import cairosvg
from PIL import Image

OUT = Path(__file__).resolve().parent.parent / "static" / "partners"
OUT.mkdir(parents=True, exist_ok=True)

UA = {"User-Agent": "ECO.NOVA-deploy/1.0 (logo fetch; contact info@eco-utyl.ua)"}

# (slug, search terms tried in order, keyword hints to disambiguate the entity)
COMPANIES = [
    ("darnitsa",  ["Дарниця (фармацевтична компанія)", "Darnitsa"], ["pharma", "фарма", "ukrain"]),
    ("farmak",    ["Farmak", "Фармак"], ["pharma", "фарма", "ukrain"]),
    ("arterium",  ["Arterium", "Артеріум"], ["pharma", "фарма", "ukrain"]),
    ("mhp",       ["Myronivsky Hliboprodukt", "МХП", "MHP (company)"], ["agro", "poultry", "ukrain", "food"]),
    ("kernel",    ["Kernel Holding", "Kernel (company)", "Кернел"], ["agro", "ukrain", "oil", "sunflower"]),
    ("astarta",   ["Astarta Holding", "Астарта-Київ", "Astarta"], ["agro", "sugar", "ukrain"]),
    ("nibulon",   ["Nibulon", "Нібулон"], ["agro", "grain", "ukrain"]),
    ("epicentr",  ["Epicentr K", "Епіцентр К", "Epicentr"], ["retail", "ukrain", "construction"]),
    ("obolon",    ["Obolon (company)", "Оболонь (компанія)", "Obolon"], ["beer", "beverage", "ukrain"]),
    ("roshen",    ["Roshen", "Рошен"], ["confection", "candy", "ukrain"]),
    ("biosphere", ["Biosphere Corporation", "Біосфера (корпорація)"], ["hygiene", "plastic", "ukrain"]),
]


def _get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read()


def _get_json(url):
    return json.loads(_get(url).decode("utf-8"))


def search_entity(term, hints):
    url = ("https://www.wikidata.org/w/api.php?action=wbsearchentities"
           f"&search={urllib.parse.quote(term)}&language=en&uselang=en&format=json&limit=6")
    try:
        d = _get_json(url)
    except Exception:
        return []
    out = []
    for x in d.get("search", []):
        desc = (x.get("description") or "").lower()
        score = sum(1 for h in hints if h in desc)
        out.append((score, x["id"]))
    out.sort(reverse=True)
    return [qid for _, qid in out]


def logo_filename(qid):
    url = (f"https://www.wikidata.org/w/api.php?action=wbgetclaims"
           f"&entity={qid}&property=P154&format=json")
    try:
        d = _get_json(url)
    except Exception:
        return None
    claims = d.get("claims", {}).get("P154", [])
    for c in claims:
        try:
            return c["mainsnak"]["datavalue"]["value"]
        except Exception:
            continue
    return None


def download_commons(filename):
    url = "https://commons.wikimedia.org/wiki/Special:FilePath/" + urllib.parse.quote(filename)
    return _get(url), filename.lower()


def to_transparent_png(raw, name_lower, target_h=220):
    """Return PNG bytes on a transparent canvas, height-normalised."""
    if name_lower.endswith(".svg"):
        png = cairosvg.svg2png(bytestring=raw, output_height=target_h)
        img = Image.open(io.BytesIO(png)).convert("RGBA")
    else:
        img = Image.open(io.BytesIO(raw)).convert("RGBA")
        # Knock out near-white background → transparent (helps JPG logos).
        px = img.getdata()
        new = []
        for r, g, b, a in px:
            if r > 238 and g > 238 and b > 238:
                new.append((r, g, b, 0))
            else:
                new.append((r, g, b, a))
        img.putdata(new)
        # trim fully-transparent borders
        bbox = img.getbbox()
        if bbox:
            img = img.crop(bbox)
        # scale to target height
        if img.height != target_h:
            w = max(1, int(img.width * target_h / img.height))
            img = img.resize((w, target_h), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def main():
    result = {}
    for slug, terms, hints in COMPANIES:
        fn = None
        for term in terms:
            for qid in search_entity(term, hints):
                fn = logo_filename(qid)
                if fn:
                    break
            if fn:
                break
            time.sleep(0.2)
        if not fn:
            print(f"[MISS] {slug}: no logo found", file=sys.stderr)
            continue
        try:
            raw, name_lower = download_commons(fn)
            png = to_transparent_png(raw, name_lower)
            dest = OUT / f"{slug}.png"
            dest.write_bytes(png)
            result[slug] = f"/api/static/partners/{slug}.png"
            print(f"[OK]  {slug}: {fn} -> {dest} ({len(png)} bytes)", file=sys.stderr)
        except Exception as e:
            print(f"[ERR] {slug}: {e}", file=sys.stderr)
        time.sleep(0.2)

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
