import { useEffect, useRef, useState } from "react";
import { Paper, ActionIcon, Tooltip } from "@mantine/core";
import { IconCircle, IconSitemap } from "@tabler/icons-react";
import * as d3 from "d3";
import type { TreeNode } from "../utils/types";
import { generateColors } from "../utils/colors";
import type { RampName } from "../utils/colors";

export type LayoutMode = "radial" | "vertical";

interface Props {
  fullTree: TreeNode | null;
  level: string;
  ramp: RampName;
  clusterIds: number[];
  activeClusters: Set<number>;
  mode: LayoutMode;
  onModeChange: (mode: LayoutMode) => void;
  onClusterClick: (id: number) => void;
  onBranchClick?: (ids: number[]) => void;
  onClusterDoubleClick?: (id: number) => void;
}

// Depth-to-radius/y easing: d3.cluster() normally spaces levels linearly
// (equal ring/row spacing per level). Reference dendrograms (e.g. the
// arcpy circular one this mirrors) instead give early splits near the
// root much more room and compress the fine branching near the leaves.
// Applying this power-ease to the normalized [0,1] depth position
// reproduces that look for any tree shape, radial or vertical, without
// needing a fixed per-level radius table.
const LEVEL_SPACING_GAMMA = 2.2;
function easeOutPow(t: number, gamma: number): number {
  return 1 - Math.pow(1 - t, gamma);
}

// Shortest signed angular delta a -> b, in (-π, π]. Picks the SVG arc sweep
// direction for radial links' circumferential segment.
function angleDelta(a: number, b: number): number {
  let d = (b - a) % (2 * Math.PI);
  if (d > Math.PI) d -= 2 * Math.PI;
  if (d < -Math.PI) d += 2 * Math.PI;
  return d;
}

export default function HierarchyView({
  fullTree, level, ramp, clusterIds, activeClusters, mode, onModeChange,
  onClusterClick, onBranchClick, onClusterDoubleClick,
}: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerSize, setContainerSize] = useState({ w: 300, h: 300 });

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    let timeout: number;
    const obs = new ResizeObserver(entries => {
      clearTimeout(timeout);
      timeout = window.setTimeout(() => {
        const { width, height } = entries[0].contentRect;
        if (width > 0 && height > 0)
          setContainerSize({ w: Math.round(width), h: Math.round(height) });
      }, 120);
    });
    obs.observe(el);
    return () => { obs.disconnect(); clearTimeout(timeout); };
  }, []);

  useEffect(() => {
    if (!svgRef.current) return;
    const svg = d3.select(svgRef.current);
    // Always clear first: switching to a region with no tree data yet
    // (fullTree null) must blank the panel, not leave the previous
    // region's tree rendered on screen.
    svg.selectAll("*").remove();
    if (!fullTree) return;

    const width = containerSize.w;
    const height = containerSize.h;
    if (width < 50 || height < 50) return;

    const colors = generateColors(clusterIds.length, ramp);
    const cx = width / 2, cy = height / 2;
    const mg = { top: 16, right: 16, bottom: 16, left: 16 };

    function getLeafCluster(node: any): number {
      // Every node (not just leaves) carries every ancestor level's cluster
      // id — see buildTaxonomyTree — so this is a direct lookup, not a walk.
      return node.data?.[level] ?? -1;
    }
    function getNodeColor(node: any): string {
      const idx = clusterIds.indexOf(getLeafCluster(node));
      return idx >= 0 ? colors[idx] : "#ccc";
    }
    function getSubtreeClusters(node: d3.HierarchyNode<any>): number[] {
      const ids = new Set<number>();
      for (const leaf of node.leaves()) {
        const cid = (leaf.data as any)?.[level] ?? -1;
        if (cid >= 0) ids.add(cid);
      }
      return Array.from(ids);
    }

    const root = d3.hierarchy(fullTree, (d: any) => d.children);
    svg.attr("viewBox", `0 0 ${width} ${height}`);
    const r = Math.min(width, height) / 2 - 20;
    // Radial mode only: keep a small open hub at the center instead of
    // letting depth 0 collapse to radius 0. Without it, every link whose
    // parent is the root (or near it) has its curve's control point land
    // exactly on the center point too, so sibling branches meet as a sharp
    // vertex there instead of a smooth curve.
    const MIN_R = 26;
    const radialR = (t: number) => MIN_R + easeOutPow(t, LEVEL_SPACING_GAMMA) * (r - MIN_R);

    // ── Layout ───────────────────────────────────────────
    // Both cluster() calls use a normalized [0,1] extent for the depth axis
    // (radius / vertical y) — the non-linear easing below maps that [0,1]
    // position to physical pixels instead of d3's linear default.
    if (mode === "radial") {
      d3.cluster<TreeNode>().size([2 * Math.PI, 1]).separation(() => 1)(root as any);
    } else {
      d3.cluster<TreeNode>().size([width - mg.left - mg.right, 1])(root as any);
    }

    // ── Assign Cartesian positions ───────────────────────
    root.each((d: any) => {
      if (mode === "radial") {
        const rad = radialR(d.y);
        const [px, py] = d3.pointRadial(d.x, rad) as [number, number];
        d._ox = cx + px; d._oy = cy + py;
      } else {
        d._ox = d.x + mg.left;
        d._oy = mg.top + easeOutPow(d.y, LEVEL_SPACING_GAMMA) * (height - mg.top - mg.bottom);
      }
    });

    // ── Active status ────────────────────────────────────
    root.eachAfter((d: any) => {
      if (!d.children)
        d._active = activeClusters.size === 0 || activeClusters.has(d.data?.[level] ?? -1);
      else
        d._active = d.children.some((c: any) => c._active);
    });

    const allNodes = root.descendants();
    const allLinks = root.links();

    // ── Link bend points ─────────────────────────────────
    allLinks.forEach((link: any) => {
      const t = link.target as any, s = link.source as any;
      if (mode === "radial") {
        // Bend point and parent are both at the parent's radius (just
        // different angles) — drawn as a true circular arc below, not a
        // straight chord, which is what made links near the center look
        // faceted/jagged rather than smooth.
        const sRad = radialR(s.y);
        const [bx, by] = d3.pointRadial(t.x, sRad) as [number, number];
        link._bx = cx + bx; link._by = cy + by;
      } else {
        link._bx = t._ox; link._by = s._oy;
      }
    });

    // ── Draw ─────────────────────────────────────────────
    const g = svg.append("g");

    g.selectAll(".link").data(allLinks).join("path")
      .attr("class", "link").attr("fill", "none")
      .attr("stroke", (d: any) => getNodeColor(d.target))
      .attr("stroke-width", 2)
      .attr("stroke-opacity", (d: any) => (d.target as any)._active ? 0.7 : 0.04)
      .attr("d", (d: any) => {
        const t = d.target as any, s = d.source as any;
        if (mode === "radial") {
          const sRad = radialR(s.y);
          const sweep = angleDelta(t.x, s.x) >= 0 ? 1 : 0;
          return `M${t._ox},${t._oy}L${d._bx},${d._by}A${sRad},${sRad} 0 0,${sweep} ${s._ox},${s._oy}`;
        }
        // Rectangular: classic dendrogram right-angle elbow through the
        // bend point, not a curve.
        return `M${t._ox},${t._oy}L${d._bx},${d._by}L${s._ox},${s._oy}`;
      });

    const branchR = 1.1, leafR = 1.4;
    g.selectAll(".node").data(allNodes).join("circle")
      .attr("class", "node")
      .attr("cx", (d: any) => d._ox).attr("cy", (d: any) => d._oy)
      .attr("r", (d: any) => d.children ? branchR : leafR)
      .attr("fill", (d: any) => getNodeColor(d))
      .attr("stroke", "none")
      .attr("opacity", (d: any) => {
        if (!d._active) return 0.04;
        return d.children ? 0.45 : 0.95;
      })
      .style("cursor", "pointer")
      .on("click", (_e: any, d: any) => {
        if (d.children) onBranchClick?.(getSubtreeClusters(d));
        else onClusterClick(getLeafCluster(d));
      })
      .on("dblclick", (_e: any, d: any) => {
        if (!d.children) onClusterDoubleClick?.(getLeafCluster(d));
      });
  }, [fullTree, mode, level, ramp, clusterIds, activeClusters,
      onClusterClick, onBranchClick, onClusterDoubleClick, containerSize]);

  return (
    <div style={{ position: "relative", width: "100%", height: "100%" }}>
      <Paper shadow="sm" radius="md" p={2} withBorder
        style={{ position: "absolute", top: 6, right: 6, zIndex: 2, display: "flex", flexDirection: "column", gap: 2 }}>
        <Tooltip label="Circular" position="left" withArrow>
          <ActionIcon size="sm" variant={mode === "radial" ? "filled" : "subtle"}
            onClick={() => onModeChange("radial")}>
            <IconCircle size={14} />
          </ActionIcon>
        </Tooltip>
        <Tooltip label="Vertical" position="left" withArrow>
          <ActionIcon size="sm" variant={mode === "vertical" ? "filled" : "subtle"}
            onClick={() => onModeChange("vertical")}>
            <IconSitemap size={14} />
          </ActionIcon>
        </Tooltip>
      </Paper>
      <div ref={containerRef} style={{ width: "100%", height: "100%", overflow: "hidden" }}>
        <svg ref={svgRef} width="100%" height="100%" style={{ display: "block" }} />
      </div>
    </div>
  );
}
