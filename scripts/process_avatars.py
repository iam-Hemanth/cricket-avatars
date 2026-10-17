#!/usr/bin/env python3
"""
Process Avatars: Download and convert player images to uniform 320x320 WebP.
Keyed strictly by `espn_id`.
"""

import os
import io
import json
import ssl
import time
import urllib.request
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import certifi
from PIL import Image

CDN_PREFIX = "https://img1.hscicdn.com/image/upload/f_auto"
FALLBACK_CDN_PREFIX = "https://p.imgci.com"
DEFAULT_TARGET_SIZE = 600
DEFAULT_QUALITY = 95

def fetch_and_convert_image(espn_id, target_info, ctx, target_size=DEFAULT_TARGET_SIZE, quality=DEFAULT_QUALITY):
    """
    Downloads image for espn_id, converts to high-quality RGBA WebP (default 600x600, quality 95).
    Returns: (espn_id, manifest_entry, bytes_data) or (espn_id, None, error_str)
    """
    headshot_url = target_info.get("headshot_url")
    image_url = target_info.get("image_url")

    # Prefer transparent cut-out headshot, fallback to general portrait
    source_path = headshot_url or image_url
    if not source_path:
        return espn_id, None, "No image URL available"

    # Construct CDN URLs
    urls_to_try = []
    if source_path.startswith("http"):
        urls_to_try.append(source_path)
    else:
        clean_path = source_path if source_path.startswith("/") else f"/{source_path}"
        urls_to_try.append(f"{CDN_PREFIX}{clean_path}")
        urls_to_try.append(f"{FALLBACK_CDN_PREFIX}{clean_path.replace('/lsci', '')}")

    raw_bytes = None
    last_err = None
    for url in urls_to_try:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"})
            with urllib.request.urlopen(req, context=ctx, timeout=8) as resp:
                if resp.status == 200:
                    raw_bytes = resp.read()
                    break
        except Exception as e:
            last_err = str(e)
            continue

    if not raw_bytes:
        return espn_id, None, f"Failed to download from CDN: {last_err}"

    try:
        img = Image.open(io.BytesIO(raw_bytes)).convert("RGBA")
        # Resize maintaining aspect ratio only if image is larger than target_size
        if img.width > target_size or img.height > target_size:
            img.thumbnail((target_size, target_size), Image.Resampling.LANCZOS)

        # Pad into square with transparent background
        box_dim = max(img.width, img.height)
        final_dim = target_size if box_dim >= int(target_size * 0.7) else box_dim

        square = Image.new("RGBA", (final_dim, final_dim), (0, 0, 0, 0))
        paste_x = (final_dim - img.width) // 2
        paste_y = (final_dim - img.height) // 2
        square.paste(img, (paste_x, paste_y), img)

        out_buf = io.BytesIO()
        square.save(out_buf, format="WEBP", quality=quality, method=6)
        webp_bytes = out_buf.getvalue()

        entry = {
            "espn_id": int(espn_id),
            "name": target_info.get("name"),
            "cricsheet_id": target_info.get("cricsheet_id"),
            "source_url": source_path,
            "image_type": "cutout" if source_path == headshot_url else "portrait",
            "file": f"{espn_id}.webp",
            "width": final_dim,
            "height": final_dim,
            "quality": quality,
            "size_bytes": len(webp_bytes),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        return espn_id, entry, webp_bytes
    except Exception as e:
        return espn_id, None, f"Conversion error: {e}"

def main():
    parser = argparse.ArgumentParser(description="Process player avatars into high-quality WebPs.")
    parser.add_argument("--targets", default="data/player_targets.json", help="Targets JSON path.")
    parser.add_argument("--manifest", default="data/manifest.json", help="Manifest JSON path.")
    parser.add_argument("--output-dir", default="avatars", help="Output directory for WebP avatars.")
    parser.add_argument("--target-size", type=int, default=DEFAULT_TARGET_SIZE, help="Target square resolution (default 600).")
    parser.add_argument("--quality", type=int, default=DEFAULT_QUALITY, help="WebP quality 1-100 (default 95).")
    parser.add_argument("--workers", type=int, default=8, help="Number of concurrent worker threads.")
    parser.add_argument("--limit", type=int, default=0, help="Optional limit for dry runs or tests.")
    args = parser.parse_args()

    targets_path = Path(args.targets)
    manifest_path = Path(args.manifest)
    avatars_dir = Path(args.output_dir)
    avatars_dir.mkdir(parents=True, exist_ok=True)

    if not targets_path.exists():
        print(f"Error: Targets file {targets_path} not found.")
        return

    with open(targets_path, "r", encoding="utf-8") as f:
        targets = json.load(f)

    manifest = {}
    if manifest_path.exists():
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except Exception:
            manifest = {}

    # Identify work items (new players or upgrades)
    queue = {}
    for eid_str, info in targets.items():
        curr = manifest.get(eid_str)
        # Check if missing, file missing, upgraded from portrait to cutout, or quality upgrade
        file_path = avatars_dir / f"{eid_str}.webp"
        needs_work = False
        if not curr or not file_path.exists():
            needs_work = True
        elif curr.get("image_type") == "portrait" and info.get("headshot_url") and curr.get("source_url") != info.get("headshot_url"):
            needs_work = True
        elif curr.get("quality", 0) < args.quality or curr.get("width", 0) < min(args.target_size, 600):
            needs_work = True

        if needs_work and (info.get("headshot_url") or info.get("image_url")):
            queue[eid_str] = info

    if args.limit > 0:
        queue = dict(list(queue.items())[:args.limit])

    total_queue = len(queue)
    print(f"Total targets: {len(targets)} | Manifest entries: {len(manifest)} | Pending processing: {total_queue}")
    if total_queue == 0:
        print("All avatars up to date!")
        return

    ctx = ssl.create_default_context(cafile=certifi.where())
    success_count = 0
    fail_count = 0
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(fetch_and_convert_image, eid, info, ctx, args.target_size, args.quality): eid for eid, info in queue.items()}
        for i, future in enumerate(as_completed(futures), 1):
            eid, entry, result = future.result()
            if entry is not None:
                # Save webp
                out_file = avatars_dir / f"{eid}.webp"
                with open(out_file, "wb") as f:
                    f.write(result)
                manifest[str(eid)] = entry
                success_count += 1
            else:
                fail_count += 1

            if i % 25 == 0 or i == total_queue:
                elapsed = time.time() - start_time
                rate = i / max(elapsed, 0.1)
                print(f"[{i}/{total_queue}] Success: {success_count}, Failed: {fail_count} ({rate:.1f} imgs/sec)")

    # Save updated manifest
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    elapsed_total = time.time() - start_time
    print(f"\nProcessing Complete in {elapsed_total:.1f}s!")
    print(f"  - Successfully processed: {success_count}")
    print(f"  - Failed/No image: {fail_count}")
    print(f"  - Total manifest count: {len(manifest)}")
    print(f"Saved avatars to: {avatars_dir}")
    print(f"Saved manifest to: {manifest_path}")

if __name__ == "__main__":
    main()
