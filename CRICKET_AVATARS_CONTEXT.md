# Cricket Avatars — Project Context for Copilot & AI Agents

> Feed this file at the start of any session working on `cricket-avatars`:
> In Chat type: `#file:CRICKET_AVATARS_CONTEXT.md` then your prompt.

---

## 1. What This Repository Is

An independent, standardized player avatar and headshot asset library for cricket analytics applications. Built directly from ESPNcricinfo's media catalog and delivery-level match participants, outputting high-resolution **600×600 transparent WebP images** at **Quality 95**.

- **Primary Identifier**: Keyed strictly by **`espn_id`** (e.g. `253802.webp` for Virat Kohli).
- **Format**: High-resolution square WebP with transparent alpha channel (native resolution up to 600×600, Quality 95, ~35–50 KB per player).
- **Public CDN Distribution**: Served globally at zero cost via **jsDelivr**:
  ```
  https://cdn.jsdelivr.net/gh/iam-Hemanth/cricket-avatars@main/avatars/{espn_id}.webp
  ```
- **Backward Compatibility**: Includes `data/cricsheet_to_espn.json` mapping 18,500+ Cricsheet hashes (`player_id`) to `espn_id`.

---

## 2. Architecture & Design Decisions

### A. Primary Keying via `espn_id`
- **100% Identification Coverage**: Every player extracted from Cricinfo possesses an immutable integer `espn_id`. Cricsheet IDs only cover ~89–92% of players.
- **Future Project Decoupling**: Natively supports modern projects built on ESPNcricinfo schemas without requiring legacy Cricsheet conventions.
- **Bidirectional Mapping**: Cricsheet-based projects (like `cricket-stats`) resolve images seamlessly:
  `cricsheet_id` $\rightarrow$ `cricsheet_to_espn.json` $\rightarrow$ `{espn_id}.webp`.

### B. Image Processing & Quality Standards
- Images are harvested from raw scorecard payloads:
  - **Tier 1 (Preferred)**: `headshotImageUrl` — crisp, transparent cut-out PNG from official team photoshoots.
  - **Tier 2 (Fallback)**: `imageUrl` — standard portrait photo.
- **High-Resolution Quality Contract**:
  - Full native 600×600 resolution (no downscaling to 320px).
  - High fidelity: **Quality 95** with maximum compression effort (`method=6`).
  - Native scaling protection: Smaller images (e.g. 160×136) are preserved at native crispness rather than artificially upscaled.
  - Razor-sharp on Apple Retina, high-DPI mobile, and 4K desktop screens.
  - Average size: ~35–50 KB (complete 10,000-player library is ~450 MB, well within GitHub's 1–2 GB repo limits).

### C. Self-Healing Incremental Watermarking
- `data/manifest.json` acts as an incremental watermark cache tracking `{espn_id, name, source_url, image_type, quality, width, height, size_bytes, updated_at}`.
- Re-runs detect new debutants, upgraded photos (transitioning from portrait to cutout), or quality upgrades automatically without re-downloading unchanged players.

---

## 3. Usage & Integration Guide

### Next.js / React Frontend Integration

#### For ESPN-based Projects:
```tsx
export function PlayerAvatar({ espnId, name }: { espnId: number; name: string }) {
  const avatarUrl = `https://cdn.jsdelivr.net/gh/iam-Hemanth/cricket-avatars@main/avatars/${espnId}.webp`;

  return (
    <img
      src={avatarUrl}
      alt={name}
      width={48}
      height={48}
      className="rounded-full bg-slate-800 object-cover"
      onError={(e) => {
        // Fallback to initials or placeholder
        e.currentTarget.style.display = 'none';
      }}
    />
  );
}
```

#### For Cricsheet-based Projects (`cricket-stats`):
```tsx
import cricsheetToEspn from "@/data/cricsheet_to_espn.json";

const espnId = cricsheetToEspn[playerId];
const avatarUrl = espnId 
  ? `https://cdn.jsdelivr.net/gh/iam-Hemanth/cricket-avatars@main/avatars/${espnId}.webp`
  : null;
```

---

## 4. Key CLI Commands

```bash
# 1. Harvest player targets from local raw scorecards
python scripts/harvest_from_lake.py --dir /path/to/raw/matches --output data/player_targets.json

# 2. Process and convert avatars with 12 parallel threads
python scripts/process_avatars.py --targets data/player_targets.json --manifest data/manifest.json --output-dir avatars --workers 12

# 3. Dry-run test with 10 players
python scripts/process_avatars.py --limit 10
```

---

## 5. Chronological Development Log

### Sat Oct 17 22:50:00 IST 2026
- **Repository Inception & Architecture Blueprint**:
  - Created remote GitHub repository `iam-Hemanth/cricket-avatars` (public for jsDelivr support).
  - Adopted `espn_id` as the primary key for all image filenames (`avatars/{espn_id}.webp`) and manifest entries.
  - Generated `data/cricsheet_to_espn.json` mapping 18,509 players from `cricket-extractor/data/people.csv`.
  - Built `scripts/harvest_from_lake.py` and `scripts/process_avatars.py` (LANCZOS 320x320 RGBA WebP conversion, 9.3 KB avg size).
  - Configured automated GitHub Actions workflow `.github/workflows/build_avatars.yml`.
