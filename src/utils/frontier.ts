import type { LegendRow, GlobalClusterSummary, TreeNode } from "./types";

export function clusterKey(level: string, cluster: number): string {
  return `${level}:${cluster}`;
}

export function parseClusterKey(key: string): { level: string; cluster: number } {
  const i = key.lastIndexOf(":");
  return { level: key.slice(0, i), cluster: Number(key.slice(i + 1)) };
}

// The legend, as a flat (but indentation-ordered) list mirroring an outline:
// every cluster at `baseLevel` gets a row labeled with its own id ("5"); if
// the user has drilled into it (its key is in `expanded`), that row STAYS
// visible as a group header (isExpanded: true, offers collapse) and its
// children at the next level follow immediately after, indented one level
// deeper and labeled "5.1", "5.2", ... — recursively, so a child can itself
// become a header. Only non-expanded rows are actual map paint categories
// (a header's own buildings are now split across its children); callers
// filter for `!isExpanded` to get that paint-relevant subset.
// Runs off the small region-independent global summary, not any per-region
// data.
export function buildLegendRows(
  baseLevel: string,
  expanded: Set<string>,
  summary: GlobalClusterSummary | null,
): LegendRow[] {
  if (!summary) return [];
  const levels = summary.levels;
  if (levels.indexOf(baseLevel) < 0) return [];

  const countAt = (level: string, cluster: number): number =>
    summary.cluster_summary[level]?.find(s => s.cluster === cluster)?.morphotopes ?? 0;

  const childrenOf = (level: string, cluster: number): number[] | null => {
    const li = levels.indexOf(level);
    const nextLevel = levels[li + 1];
    if (!nextLevel) return null;
    return summary.children_map[level]?.[String(cluster)] ?? null;
  };

  const rows: LegendRow[] = [];

  function visit(level: string, cluster: number, depth: number, label: string) {
    const key = clusterKey(level, cluster);
    const children = childrenOf(level, cluster);
    const expandable = !!children && children.length > 0;
    // A drilled node keeps its own row (as a group header showing "-") and
    // gains child rows right after it — offered even when there's exactly
    // one child (it won't visibly split yet), so someone can still step
    // level_3 -> level_4 -> level_5 -> ... one hop at a time until the
    // branch they're following actually does split.
    const isExpanded = expandable && expanded.has(key);
    rows.push({ key, level, cluster, label, morphotopes: countAt(level, cluster), depth, isExpanded, expandable });
    if (isExpanded) {
      const li = levels.indexOf(level);
      const nextLevel = levels[li + 1];
      children!.forEach((child, i) => visit(nextLevel, child, depth + 1, `${label}.${i + 1}`));
    }
  }

  const baseClusters = (summary.cluster_summary[baseLevel] ?? []).map(s => s.cluster).sort((a, b) => a - b);
  for (const c of baseClusters) visit(baseLevel, c, 0, String(c));
  return rows;
}

// The Hierarchy Tree panel's data source. Built straight from the same
// region-independent children_map used for drill-down, not from the scipy
// linkage dendrogram (hierarchy_tree.json) — that file only ever exists for
// one legacy region (Winnipeg), so a tree built from it is blank everywhere
// else. This tree has no missing-data gap: every level_1..level_7 cluster
// came from the one global clustering pass, so it's identical (and always
// available) for every region. It's also small (max ~254 nodes across all
// 7 levels, vs. tens of thousands of morphotope leaves in the real
// dendrogram), so unlike that one, this doesn't need a depth/pruning option.
//
// Every node carries every ancestor level's cluster id (not just its own),
// e.g. a level_5 node also has level_1..level_4 set — HierarchyView colors
// by whichever level_N is currently selected regardless of node depth, the
// same way the original per-morphotope leaves did.
export function buildTaxonomyTree(summary: GlobalClusterSummary): TreeNode {
  const levels = summary.levels;

  function buildNode(level: string, cluster: number, ancestors: Record<string, number>): TreeNode {
    const li = levels.indexOf(level);
    const nextLevel = levels[li + 1];
    const here = { ...ancestors, [level]: cluster };
    const childIds = nextLevel ? (summary.children_map[level]?.[String(cluster)] ?? []) : [];
    const node: TreeNode = {
      id: `${level}_${cluster}`,
      leaf: childIds.length === 0,
      distance: 0,
      count: summary.cluster_summary[level]?.find(s => s.cluster === cluster)?.morphotopes ?? 0,
      ...here,
    };
    if (childIds.length > 0) node.children = childIds.map(c => buildNode(nextLevel, c, here));
    return node;
  }

  const baseLevel = levels[0];
  const baseClusters = (summary.cluster_summary[baseLevel] ?? []).map(s => s.cluster).sort((a, b) => a - b);
  return {
    id: "root", leaf: false, distance: 0, count: summary.total_morphotopes,
    children: baseClusters.map(c => buildNode(baseLevel, c, {})),
  };
}
