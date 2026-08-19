// Base URL for the static tiles/ directory (buildings.pmtiles per region +
// regions_manifest.json). Local dev is served by ../app.py (Flask). In
// production this is the ONLY thing that needs to change: point it at
// wherever tiles/ gets uploaded (S3, a CDN, any static host) and everything
// else keeps working, since every fetch/pmtiles URL is built from it.
export const TILES_BASE_URL = import.meta.env.VITE_TILES_BASE_URL || "http://localhost:5000";

interface RegionManifestEntry {
  slug: string;
  region_id: string;
  name: string;
  cma_type: string | null;
  pruid: string | null;
  n_buildings: number;
  bbox_wgs84: [number, number, number, number] | null;
}

const PROVINCE_NAMES: Record<string, string> = {
  "10": "Newfoundland and Labrador",
  "11": "Prince Edward Island",
  "12": "Nova Scotia",
  "13": "New Brunswick",
  "24": "Quebec",
  "35": "Ontario",
  "46": "Manitoba",
  "47": "Saskatchewan",
  "48": "Alberta",
  "59": "British Columbia",
  "60": "Yukon",
  "61": "Northwest Territories",
  "62": "Nunavut",
};

export interface RegionConfig {
  slug: string;
  name: string;
  province: string;
  center: [number, number];
  bbox: [number, number, number, number] | null;
  nBuildings: number;
}

export async function fetchRegions(): Promise<RegionConfig[]> {
  const res = await fetch(`${TILES_BASE_URL}/tiles/regions_manifest.json`);
  if (!res.ok) throw new Error(`Failed to load regions_manifest.json (${res.status})`);
  const manifest: RegionManifestEntry[] = await res.json();
  return manifest
    .map((r): RegionConfig => {
      const bbox = r.bbox_wgs84;
      const center: [number, number] = bbox
        ? [(bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2]
        : [-96, 62]; // fallback: roughly the geographic middle of Canada
      return {
        slug: r.slug,
        name: r.name,
        province: PROVINCE_NAMES[r.pruid ?? ""] ?? "Canada",
        center,
        bbox,
        nBuildings: r.n_buildings,
      };
    })
    .sort((a, b) => a.name.localeCompare(b.name));
}

export function pmtilesUrl(slug: string): string {
  return `pmtiles://${TILES_BASE_URL}/tiles/${slug}/buildings.pmtiles`;
}
