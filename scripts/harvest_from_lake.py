#!/usr/bin/env python3
"""
Harvest Player Targets from Raw Scorecards.
Extracts unique players keyed strictly by `espn_id` with their best available headshot/image URLs.
"""

import os
import gzip
import json
import tarfile
import argparse
from pathlib import Path

def get_cricsheet_mapping():
    mapping_path = Path(__file__).resolve().parent.parent / "data" / "cricsheet_to_espn.json"
    if mapping_path.exists():
        with open(mapping_path, "r", encoding="utf-8") as f:
            cid_to_eid = json.load(f)
            # Invert: eid -> cid
            return {eid: cid for cid, eid in cid_to_eid.items()}
    return {}

def process_scorecard_dict(d, players_dict, eid_to_cid):
    content = d.get("content", {})
    team_players = (content.get("matchPlayers") or {}).get("teamPlayers") or []
    for tp in team_players:
        for p_entry in tp.get("players", []):
            p = p_entry.get("player") or {}
            oid = p.get("objectId")
            if not oid:
                continue
            try:
                espn_id = int(oid)
            except (ValueError, TypeError):
                continue

            eid_str = str(espn_id)
            headshot = p.get("headshotImageUrl")
            img = p.get("imageUrl")
            name = p.get("longName") or p.get("name") or f"Player {espn_id}"

            if eid_str not in players_dict:
                players_dict[eid_str] = {
                    "espn_id": espn_id,
                    "name": name,
                    "cricsheet_id": eid_to_cid.get(espn_id),
                    "headshot_url": headshot,
                    "image_url": img
                }
            else:
                # Upgrade if headshot was previously missing
                if not players_dict[eid_str]["headshot_url"] and headshot:
                    players_dict[eid_str]["headshot_url"] = headshot
                if not players_dict[eid_str]["image_url"] and img:
                    players_dict[eid_str]["image_url"] = img

def harvest_from_directory(root_dir, players_dict, eid_to_cid):
    root = Path(root_dir)
    print(f"Scanning directory: {root}")
    # 1. Process any tarballs in the directory
    tar_files = sorted(list(root.rglob("*.tar*")))
    if tar_files:
        print(f"Found {len(tar_files)} archive files in {root}. Processing archives...")
        for tar in tar_files:
            harvest_from_tarball(str(tar), players_dict, eid_to_cid)

    # 2. Process any loose scorecards
    count = 0
    for path in root.rglob("scorecard.json*"):
        try:
            if path.suffix == ".gz":
                with gzip.open(path, "rt", encoding="utf-8") as f:
                    d = json.load(f)
            else:
                with open(path, "r", encoding="utf-8") as f:
                    d = json.load(f)
            process_scorecard_dict(d, players_dict, eid_to_cid)
            count += 1
            if count % 500 == 0:
                print(f"Processed {count} scorecards... Unique players so far: {len(players_dict)}")
        except Exception as e:
            continue
    if count > 0:
        print(f"Completed directory scan: {count} loose scorecards processed.")

def harvest_from_tarball(tar_path, players_dict, eid_to_cid):
    print(f"Scanning tarball: {tar_path}")
    count = 0
    with tarfile.open(tar_path, "r:*") as tar:
        for member in tar:
            if member.name.endswith("scorecard.json.gz"):
                f = tar.extractfile(member)
                if f:
                    try:
                        with gzip.open(f, "rt", encoding="utf-8") as gz:
                            d = json.load(gz)
                            process_scorecard_dict(d, players_dict, eid_to_cid)
                            count += 1
                    except Exception:
                        continue
    print(f"Extracted {count} scorecards from {tar_path}. Unique players: {len(players_dict)}")

def main():
    parser = argparse.ArgumentParser(description="Harvest player image targets from raw match scorecards.")
    parser.add_argument("--dir", help="Directory containing raw scorecard files or batches.")
    parser.add_argument("--tarballs", nargs="*", help="One or more tar.gz files to inspect.")
    parser.add_argument("--output", default="data/player_targets.json", help="Output targets JSON file path.")
    args = parser.parse_args()

    eid_to_cid = get_cricsheet_mapping()
    players_dict = {}

    if args.dir:
        harvest_from_directory(args.dir, players_dict, eid_to_cid)

    if args.tarballs:
        for tar in args.tarballs:
            harvest_from_tarball(tar, players_dict, eid_to_cid)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(players_dict, f, indent=2)

    with_headshot = sum(1 for p in players_dict.values() if p.get("headshot_url"))
    with_any = sum(1 for p in players_dict.values() if p.get("headshot_url") or p.get("image_url"))
    print(f"\nDone! Harvested {len(players_dict)} unique players.")
    print(f"  - With transparent cut-out headshot: {with_headshot}")
    print(f"  - With any image URL: {with_any}")
    print(f"Saved targets to: {out_path}")

if __name__ == "__main__":
    main()
