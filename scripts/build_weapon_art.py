#!/usr/bin/env python3
"""Build the compact, transparent weapon-art set from the archived WebP sources."""
from __future__ import annotations

import json
import re
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "docs" / "weapon-art-source"
OUTPUT_DIR = ROOT / "app" / "src" / "main" / "assets" / "weapon-art"
MANIFEST_PATH = ROOT / "docs" / "weapon-art-sources.json"
CATALOG_PATH = ROOT / "app" / "src" / "main" / "assets" / "weapon_catalog.js"
MAX_SIZE = (480, 170)


def write_catalog(manifest: dict) -> None:
    lines = ["window.FF_WEAPONS = ["]
    for weapon in manifest["weapons"]:
        fields = {
            "name": weapon["name"],
            "category": weapon["category"],
            "asset": weapon["asset"],
            "action": weapon["action"],
        }
        encoded = ", ".join(
            f"{key}:{json.dumps(value, ensure_ascii=False)}"
            for key, value in fields.items()
        )
        lines.append(f"  {{{encoded}}},")
    lines.append("];\n")
    CATALOG_PATH.write_text("\n".join(lines), encoding="utf-8")


def trim_and_encode(source: Path, target: Path) -> None:
    with Image.open(source) as original:
        image = original.convert("RGBA")
        alpha = image.getchannel("A")
        bounds = alpha.getbbox()
        if not bounds:
            raise ValueError(f"No visible pixels in {source}")

        left, top, right, bottom = bounds
        subject_width = right - left
        subject_height = bottom - top
        pad_x = max(3, int(subject_width * 0.035))
        pad_y = max(3, int(subject_height * 0.10))
        crop = (
            max(0, left - pad_x),
            max(0, top - pad_y),
            min(image.width, right + pad_x),
            min(image.height, bottom + pad_y),
        )
        image = image.crop(crop)
        image.thumbnail(MAX_SIZE, Image.Resampling.LANCZOS)
        target.parent.mkdir(parents=True, exist_ok=True)
        image.save(target, "WEBP", quality=82, method=6, exact=True)


def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    write_catalog(manifest)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    missing: list[str] = []
    for asset in manifest["assets"]:
        source = SOURCE_DIR / asset["source_file"]
        target = OUTPUT_DIR / f"{asset['asset']}.webp"
        if not source.is_file():
            missing.append(str(source.relative_to(ROOT)))
            continue
        trim_and_encode(source, target)

    if missing:
        raise FileNotFoundError("Missing weapon sources:\n" + "\n".join(missing))

    result = {
        "weapons": len(manifest["weapons"]),
        "unique_images": len(manifest["assets"]),
        "output_bytes": sum(path.stat().st_size for path in OUTPUT_DIR.glob("*.webp")),
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
