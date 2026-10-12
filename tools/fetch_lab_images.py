"""
Real equipment photographs for the lab pages, from Wikimedia Commons only
(free licences that allow use in a public repo). For each item the first
search hit with an acceptable licence is downloaded as a 640 px thumbnail and
its source, author and licence are written to
frontend/public/equipment/ATTRIBUTION.json (shown under each photo).

    py tools/fetch_lab_images.py            (needs internet)

Nothing here claims a photo shows OUR lab: these are model / category photos,
labelled "product photo" in the portal. Own lab photos replace them later.
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

OUT = os.path.join(os.path.dirname(__file__), "..", "frontend", "public", "equipment")
API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "SmartLab-thesis/1.0 (GIU BSc project; equipment photos)"}
OK_LICENCES = ("cc0", "public domain", "pd", "cc by", "cc-by", "cc by-sa", "cc-by-sa")

# key, label, Commons search
ITEMS = [
    ("ur5e", "Universal Robots UR5e (cobot)", "Universal Robots UR5"),
    ("fanuc", "FANUC industrial robot", "Fanuc M-410 robot"),
    ("conveyor", "Conveyor belt", "conveyor belt factory"),
    ("workstation", "Lab PCs / workstations", "computer lab workstations"),
    ("s7-1200", "Siemens SIMATIC S7-1200 PLC", "Siemens S7-1200"),
    ("drill-press", "Drilling machine", "drill press machine"),
    ("sheet-metal", "Sheet-metal tools", "sheet metal shear"),
    ("tensile", "Tensile testing machine", "universal testing machine tensile"),
    ("bending", "Bending test machine", "three point bending test"),
    ("bmw-i3", "BMW i3 (electric hatchback)", "BMW i3 hatchback"),
    ("gearbox", "Gears and transmission", "gearbox cutaway"),
    ("steering", "Steering system", "steering rack car part"),
    ("pcb-mill", "PCB prototyping machine", "PCB milling machine"),
    ("soldering", "Soldering station", "soldering station"),
    ("atmega", "ATmega microcontroller boards", "Arduino Uno ATmega328"),
    ("esp32", "ESP32 boards", "ESP32 development board"),
    ("water-tank", "Process water tanks", "Siemens WinCC SCADA screen"),
    ("hmi", "SCADA / HMI panel", "human machine interface touch panel"),
    ("sewing", "Sewing machine", "Singer sewing machine electric"),
    ("mannequin", "Mannequins / dress forms", "dress form mannequin"),
    ("matlab", "MATLAB (licence USB keys)", "MATLAB software screenshot"),
    ("proteus", "Proteus simulation on lab PCs", "Proteus Design Suite"),
    ("thread", "Threads and fabrics", "sewing thread spools"),
    ("laser-cutter", "Laser cutter", "laser cutter machine"),
    ("woodcut", "Wood-cutting equipment", "table saw woodworking"),
    ("jewelry", "Jewelry-making tools", "jewellery making tools bench"),
]


def get(params):
    q = API + "?" + urllib.parse.urlencode({**params, "format": "json"})
    for wait in (5, 15, 45):
        try:
            with urllib.request.urlopen(urllib.request.Request(q, headers=UA), timeout=20) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
            time.sleep(wait)                 # rate-limited: back off and retry
    raise RuntimeError("Commons keeps rate-limiting - run again later")


def strip(html):
    return re.sub(r"<[^>]+>", "", html or "").strip()


def main():
    os.makedirs(OUT, exist_ok=True)
    meta_path = os.path.join(OUT, "ATTRIBUTION.json")
    meta = json.load(open(meta_path, encoding="utf-8")) if os.path.isfile(meta_path) else {}
    for key, label, query in ITEMS:
        if key in meta and os.path.isfile(os.path.join(OUT, meta[key]["file"])):
            continue
        res = get({"action": "query", "generator": "search", "gsrsearch": f"filetype:bitmap {query}",
                   "gsrnamespace": 6, "gsrlimit": 30, "prop": "imageinfo",
                   "iiprop": "url|extmetadata|mime", "iiurlwidth": 640})
        pages = sorted((res.get("query") or {}).get("pages", {}).values(), key=lambda p: p.get("index", 99))
        chosen = None
        for p in pages:
            ii = (p.get("imageinfo") or [{}])[0]
            em = ii.get("extmetadata", {})
            lic = strip(em.get("LicenseShortName", {}).get("value", "")).lower()
            if ii.get("mime") not in ("image/jpeg", "image/png") or not any(l in lic for l in OK_LICENCES):
                continue
            chosen = (p, ii, em)
            break
        if not chosen:
            print(f"{key}: no free-licence photo found for '{query}'")
            continue
        p, ii, em = chosen
        ext = ".png" if ii["mime"] == "image/png" else ".jpg"
        fn = f"{key}{ext}"
        with urllib.request.urlopen(urllib.request.Request(ii["thumburl"], headers=UA), timeout=30) as r:
            open(os.path.join(OUT, fn), "wb").write(r.read())
        meta[key] = {"file": fn, "label": label, "title": p["title"],
                     "source": ii.get("descriptionurl"),
                     "author": strip(em.get("Artist", {}).get("value", ""))[:120] or "unknown",
                     "licence": strip(em.get("LicenseShortName", {}).get("value", "")),
                     "kind": "product photo (Wikimedia Commons), not our lab"}
        print(f"{key}: {p['title']}  [{meta[key]['licence']}]", flush=True)
        json.dump(meta, open(meta_path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        time.sleep(4.0)                      # polite to the Commons API
    json.dump(meta, open(meta_path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    sys.exit(main())
