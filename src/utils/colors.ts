import chroma from "chroma-js";

export const RAMP_NAMES = [
  "Spectral", "Viridis", "Plasma", "Inferno", "Magma",
  "YlOrRd", "YlGnBu", "RdYlGn", "PuOr", "BrBG",
  "Set1", "Set2", "Set3", "Paired", "Dark2", "Accent",
  "Bold", "Pastel",
] as const;

export type RampName = (typeof RAMP_NAMES)[number];
export const RampNameValues = RAMP_NAMES;

const CUSTOM_RAMPS: Record<string, string[]> = {
  Bold: [
    "#e6194b","#3cb44b","#ffe119","#4363d8","#f58231",
    "#911eb4","#42d4f4","#f032e6","#bfef45","#fabed4",
    "#469990","#dcbeff","#9a6324","#fffac8","#800000",
    "#aaffc3","#808000","#ffd8b1","#000075","#a9a9a9",
  ],
  Pastel: [
    "#fbb4ae","#b3cde3","#ccebc5","#decbe4","#fed9a6",
    "#ffffcc","#e5d8bd","#fddaec","#f2f2f2","#b3e2cd",
    "#fdcdac","#cbd5e8","#f4cae4","#e6f5c9","#fff2ae",
    "#f1e2cc","#cccccc","#d9d9d9","#bc80bd","#fb8072",
  ],
};

export function generateColors(n: number, rampName: RampName): string[] {
  if (CUSTOM_RAMPS[rampName]) {
    const base = CUSTOM_RAMPS[rampName];
    return Array.from({ length: n }, (_, i) => base[i % base.length]);
  }
  try {
    return chroma.scale(rampName.toLowerCase() as any).mode("lch").colors(n);
  } catch {
    return chroma.scale("Spectral" as any).mode("lch").colors(n);
  }
}

export function getColor(
  id: number,
  clusterIds: number[],
  colors: string[]
): string {
  const idx = clusterIds.indexOf(id);
  if (idx < 0) return "#888";
  return colors[idx % colors.length];
}
