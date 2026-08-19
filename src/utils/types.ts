export interface LayerSymbology {
  level: string;      // level_1..level_7 — drives map color, legend, and the hierarchy panel
  ramp: string;
  opacity: number;
  visible: boolean;
}

// One legend row — either a leaf (an actual map paint category, label like
// "5.2") or a group header (a drilled cluster, kept visible with its
// children nested underneath instead of being replaced by them).
export interface LegendRow {
  key: string;           // "level:cluster" — see clusterKey/parseClusterKey in frontier.ts
  level: string;
  cluster: number;
  label: string;        // "5", "5.2", "5.2.1", ... — position among siblings, not the raw cluster id
  morphotopes: number;
  depth: number;         // hops below the base level (0 = undrilled), drives legend indentation
  isExpanded: boolean;   // true = group header (already drilled) — show collapse ("-"), no color swatch
  expandable: boolean;   // true = has children to drill into (offer "+" when not already expanded)
}

export interface TreeNode {
  id: string;
  leaf: boolean;
  distance: number;
  count: number;
  children?: TreeNode[];
  [key: string]: any;
}

// Region-independent: level_N cluster ids mean the same taxonomy class
// everywhere (one global clustering pass covers every region), so this
// loads once and powers the legend, symbology, and hierarchy tree (see
// buildTaxonomyTree in frontier.ts) regardless of which region is selected.
export interface GlobalClusterSummary {
  levels: string[];
  cluster_summary: Record<string, { cluster: number; morphotopes: number }[]>;
  children_map: Record<string, Record<string, number[]>>;
  total_morphotopes: number;
}
