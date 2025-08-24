
#!/usr/bin/env python3
"""
prepare_valo_icons.py  (Downloader + Normalizer + Generator)
------------------------------------------------------------
Lädt automatisch ein Icon-Pack (voreingestellt: emoji.gg Valorant-Rank-Emote-Pack),
oder generiert minimalistische Platzhalter-Icons lokal. Danach normalisiert/konvertiert
das Skript die Dateien in die von der App erwarteten Namen.

Quick start (auto-download → normalize → PNG 128px):
  python tools/prepare_valo_icons.py --download emoji_gg --dest app/resources/valo_tracker_icons --size 128 --force-png --overwrite

Alternativ ohne Internet (lokal generieren):
  python tools/prepare_valo_icons.py --generate minimal --dest app/resources/valo_tracker_icons --size 128 --force-png --overwrite

Eigene ZIP-URL:
  python tools/prepare_valo_icons.py --download-url https://.../valorant_ranks.zip --dest app/resources/valo_tracker_icons --size 128 --force-png

Hinweis zur Nutzung Dritter-Packs:
  Prüfe die Lizenz deiner Quelle (emoji.gg, Fandom, Shops, GitHub, ...). Dieses Skript legt optional eine ATTRIBUTION.txt ab.
"""

import argparse, re, sys, shutil, os, io, tempfile, zipfile, urllib.parse, json
from typing import Optional, Tuple, List

# Optional: Pillow für Generierung/Skalierung/PNG
try:
    from PIL import Image, ImageDraw, ImageFont
    _HAS_PIL = True
except Exception:
    _HAS_PIL = False

VALID_EXT = {".png", ".jpg", ".jpeg", ".webp", ".svg"}

BASE_MAP = {
    "iron": "iron",
    "bronze": "bronze",
    "silver": "silver",
    "gold": "gold",
    "platinum": "plat",
    "plat": "plat",
    "diamond": "dia",
    "dia": "dia",
    "ascendant": "asc",
    "asc": "asc",
    "immortal": "imm",
    "imm": "imm",
    "radiant": "rad",
    "rad": "rad",
}

ROMAN_MAP = {"i": "1", "ii": "2", "iii": "3"}

PAT = re.compile(r"""
    (?P<base>iron|bronze|silver|gold|platinum|plat|diamond|dia|ascendant|asc|immortal|imm|radiant|rad)
    [\s_\-]*
    (?P<div>(iii|ii|i|3|2|1))?
""", re.IGNORECASE | re.VERBOSE)

DIV_TARGETS = ["1", "2", "3"]
RANKS_LINEAR = [
    ("iron", DIV_TARGETS), ("bronze", DIV_TARGETS), ("silver", DIV_TARGETS),
    ("gold", DIV_TARGETS), ("plat", DIV_TARGETS), ("dia", DIV_TARGETS),
    ("asc", DIV_TARGETS), ("imm", DIV_TARGETS), ("rad", []),
]
COLOR_MAP = {
    "iron": (130, 130, 130), "bronze": (155, 120, 75), "silver": (170, 190, 200),
    "gold": (210, 175, 55), "plat": (60, 185, 175), "dia": (70, 150, 245),
    "asc": (120, 200, 110), "imm": (220, 60, 120), "rad": (255, 160, 30),
}

def normalize_name(name: str) -> Optional[str]:
    stem = os.path.splitext(os.path.basename(name))[0]
    m = PAT.search(stem)
    if not m: return None
    base_raw = m.group("base").lower()
    div_raw = (m.group("div") or "").lower()
    base = BASE_MAP.get(base_raw)
    if base is None: return None
    if base == "rad": return "rad"
    div = ROMAN_MAP.get(div_raw, div_raw) if div_raw else ""
    if div not in {"", "1", "2", "3"}: return None
    if base in {"iron","bronze","silver","gold","plat","dia","asc","imm"} and div == "":
        div = "1"
    return f"{base}{div}" if base != "rad" else "rad"

def ensure_dir(path: str): os.makedirs(path, exist_ok=True)

def copy_or_convert(src: str, dest: str, size: Optional[int], force_png: bool, overwrite: bool):
    ext = os.path.splitext(src)[1].lower()
    if (_HAS_PIL and force_png) or (_HAS_PIL and size and ext != ".svg"):
        if ext == ".svg":
            if not force_png:
                if overwrite or not os.path.exists(dest):
                    shutil.copy2(src, dest)
                return os.path.basename(dest)
            else:
                raise RuntimeError("SVG → PNG Konvertierung benötigt `cairosvg`. Entferne --force-png oder liefere PNG/WebP.")
        if not _HAS_PIL:
            raise RuntimeError("Pillow (PIL) ist nicht installiert. Installiere Pillow oder entferne --size/--force-png.")
        with Image.open(src) as im:
            im = im.convert("RGBA")
            if size: im = im.resize((size, size), Image.LANCZOS)
            dest_png = os.path.splitext(dest)[0] + ".png"
            ensure_dir(os.path.dirname(dest_png))
            if overwrite or not os.path.exists(dest_png):
                im.save(dest_png, format="PNG")
            return os.path.basename(dest_png)
    else:
        ensure_dir(os.path.dirname(dest))
        if overwrite or not os.path.exists(dest):
            shutil.copy2(src, dest)
        return os.path.basename(dest)

# -------------------- Downloader --------------------

def _http_get(url: str) -> bytes:
    import urllib.request
    req = urllib.request.Request(url, headers={
        "User-Agent": "RiotAccountMgr-IconFetcher/1.0",
        "Accept": "*/*",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()

def _find_zip_link_emoji_gg(pack_page_url: str) -> Optional[str]:
    # Sehr simple Heuristik: erste .zip in der Seite
    try:
        html = _http_get(pack_page_url).decode("utf-8", errors="ignore")
    except Exception:
        return None
    m = re.search(r'href="([^"]+\\.zip)"', html, re.IGNORECASE)
    if not m:
        return None
    href = m.group(1)
    return urllib.parse.urljoin(pack_page_url, href)

def download_pack_emoji_gg(dest_tmp: str, pack_page_url: str) -> Tuple[str, Optional[str]]:
    """Lädt das Emoji-Pack-ZIP von emoji.gg (per Scrape) und entpackt nach dest_tmp.
       Rückgabe: (Ordnerpfad, Attribution)"""
    zip_url = _find_zip_link_emoji_gg(pack_page_url)
    if not zip_url:
        raise RuntimeError("Konnte ZIP-Link auf emoji.gg nicht finden (Struktur evtl. geändert).")
    data = _http_get(zip_url)
    zpath = os.path.join(dest_tmp, "emoji_pack.zip")
    with open(zpath, "wb") as f: f.write(data)
    with zipfile.ZipFile(zpath, "r") as z:
        z.extractall(dest_tmp)
    attribution = f"Source: {pack_page_url}\\nDownloaded ZIP: {zip_url}\\nNote: Verify license terms on emoji.gg before distribution."
    return dest_tmp, attribution

def download_zip_url(dest_tmp: str, url: str) -> Tuple[str, Optional[str]]:
    data = _http_get(url)
    zpath = os.path.join(dest_tmp, "pack.zip")
    with open(zpath, "wb") as f: f.write(data)
    with zipfile.ZipFile(zpath, "r") as z:
        z.extractall(dest_tmp)
    return dest_tmp, f"Source ZIP: {url}"

# -------------------- Generator --------------------

def _draw_badge(size: int, color: Tuple[int,int,int], text: str) -> "Image.Image":
    if not _HAS_PIL: raise RuntimeError("Pillow (PIL) nicht installiert; Generator nicht verfügbar.")
    img = Image.new("RGBA", (size, size), (0,0,0,0))
    d = ImageDraw.Draw(img)
    # simple diamond
    cx = cy = size/2
    r = size*0.38
    poly = [(cx, cy-r), (cx+r, cy), (cx, cy+r), (cx-r, cy)]
    d.polygon(poly, fill=color+(255,), outline=(255,255,255,220), width=max(2, size//48))
    # inner diamond
    r2 = r*0.63
    poly2 = [(cx, cy-r2), (cx+r2, cy), (cx, cy+r2), (cx-r2, cy)]
    d.polygon(poly2, outline=(255,255,255,230), width=max(2, size//48))
    # text
    try:
        # Try a bold-ish font; falls back to default
        font = ImageFont.truetype("arial.ttf", size//3)
    except Exception:
        font = ImageFont.load_default()
    tw, th = d.textsize(text, font=font)
    d.text((cx - tw/2, cy - th/2), text, fill=(255,255,255,255), font=font)
    return img

def generate_minimal_pack(tmp_dir: str, size: int=128) -> Tuple[str, Optional[str]]:
    if not _HAS_PIL: raise RuntimeError("Pillow nicht installiert.")
    out_dir = os.path.join(tmp_dir, "gen")
    os.makedirs(out_dir, exist_ok=True)
    for base, divs in RANKS_LINEAR:
        if base == "rad":
            fn = os.path.join(out_dir, "rad.png")
            _draw_badge(size, COLOR_MAP[base], "R").save(fn, "PNG")
            continue
        for d in divs:
            fn = os.path.join(out_dir, f"{base}{d}.png")
            _draw_badge(size, COLOR_MAP[base], d).save(fn, "PNG")
    return out_dir, "Generated locally (minimalist placeholders)."

# -------------------- Normalize pipeline --------------------

def process_folder(src_folder: str, dest: str, size: Optional[int], force_png: bool, overwrite: bool) -> List[str]:
    created = []
    for root, _dirs, files in os.walk(src_folder):
        for fn in files:
            ext = os.path.splitext(fn)[1].lower()
            if ext not in VALID_EXT:
                continue
            canon = normalize_name(fn)
            if not canon:
                continue
            dest_name = canon + (".png" if (force_png and _HAS_PIL and ext != ".svg") else ext)
            dest_path = os.path.join(dest, dest_name)
            src_path = os.path.join(root, fn)
            try:
                out = copy_or_convert(src_path, dest_path, size, force_png, overwrite)
                created.append(out)
            except Exception as e:
                print(f"[FEHLER] {fn}: {e}", file=sys.stderr)
    return sorted(set(created))

def main():
    ap = argparse.ArgumentParser(description="Valorant Rank Icons: Download / Generate / Normalize")
    grpD = ap.add_mutually_exclusive_group()
    grpD.add_argument("--download", choices=["emoji_gg"], help="Vordefinierte Quelle automatisch laden (emoji_gg).")
    grpD.add_argument("--download-url", help="Direkte ZIP-URL eines Icon-Packs.")
    grpD.add_argument("--generate", choices=["minimal"], help="Lokal Icon-Set generieren (ohne Internet).")

    ap.add_argument("--emoji-pack-url", default="https://emoji.gg/pack/1774-every-valorant-rank", help="emoji.gg Pack-Seite (wird gescraped)")
    ap.add_argument("--dest", default="app/resources/valo_tracker_icons", help="Zielordner (Default: app/resources/valo_tracker_icons)")
    ap.add_argument("--size", type=int, default=128, help="Ausgabegröße bei Konvertierung/Generierung (Default: 128)")
    ap.add_argument("--force-png", action="store_true", help="Als PNG exportieren (empfohlen).")
    ap.add_argument("--overwrite", action="store_true", help="Existierende Dateien überschreiben.")
    ap.add_argument("--write-attribution", action="store_true", help="ATTRIBUTION.txt im Zielordner ablegen.")
    ap.add_argument("--dry-run", action="store_true", help="Nur anzeigen, was passieren würde.")
    args = ap.parse_args()

    ensure_dir(args.dest)

    with tempfile.TemporaryDirectory() as tmp:
        src_dir = None
        attribution = None

        if args.download == "emoji_gg":
            src_dir, attribution = download_pack_emoji_gg(tmp, args.emoji_pack_url)
        elif args.download_url:
            src_dir, attribution = download_zip_url(tmp, args.download_url)
        elif args.generate == "minimal":
            if not _HAS_PIL:
                print("[FEHLER] Pillow nicht installiert; 'generate' nicht verfügbar.", file=sys.stderr)
                return 2
            src_dir, attribution = generate_minimal_pack(tmp, size=args.size)
        else:
            print("[FEHLER] Bitte --download emoji_gg oder --download-url ODER --generate minimal angeben.", file=sys.stderr)
            return 2

        if args.dry_run:
            print(f"[DRY-RUN] Quelle: {src_dir}")
            print(f"[DRY-RUN] Ziel: {args.dest}")
            print("[DRY-RUN] Normalisiere & konvertiere ...")
            return 0

        created = process_folder(src_dir, args.dest, args.size, args.force_png, args.overwrite)
        print(f"[OK] {len(created)} Dateien im Zielordner")
        for n in created: print(f"  - {n}")

        if args.write_attribution and attribution:
            with open(os.path.join(args.dest, "ATTRIBUTION.txt"), "w", encoding="utf-8") as f:
                f.write(attribution + "\\n")
            print("[OK] ATTRIBUTION.txt geschrieben.")

if __name__ == "__main__":
    sys.exit(main())
