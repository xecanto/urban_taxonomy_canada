import { useEffect, useRef, useState } from "react";
import { SegmentedControl, Stack, Group, Text, Slider, Select } from "@mantine/core";
import * as d3 from "d3";
import gsap from "gsap";
import type { TreeNode } from "../utils/types";
import { generateColors } from "../utils/colors";
import type { RampName } from "../utils/colors";

interface Props {
  trees: Record<string, TreeNode> | null;
  fullTree: TreeNode | null;
  level: string;
  ramp: RampName;
  clusterIds: number[];
  activeClusters: Set<number>;
  centroids: Record<string, [number, number]>;
  onClusterClick: (id: number) => void;
  onBranchClick?: (ids: number[]) => void;
  onClusterDoubleClick?: (id: number) => void;
}

function fisheyePoint(
  px: number, py: number, fx: number, fy: number,
  radius: number, distortion: number,
): [number, number] {
  const dx = px - fx, dy = py - fy;
  const dd = Math.sqrt(dx * dx + dy * dy);
  if (dd === 0 || dd >= radius) return [px, py];
  const norm = dd / radius;
  const warp = norm * (distortion + 1) / (norm * distortion + 1);
  const scale = warp / norm;
  return [fx + dx * scale, fy + dy * scale];
}

function pruneToLevel(node: TreeNode, level: string): TreeNode {
  if (node.leaf || !node.children || node.children.length === 0) return node;
  const clusters = new Set<number>();
  let leafCount = 0;
  (function collect(n: TreeNode) {
    if (n.leaf || !n.children) {
      const cid = (n as any)[level] as number ?? -1;
      if (cid >= 0) clusters.add(cid);
      leafCount++;
      return;
    }
    n.children.forEach(collect);
  })(node);
  if (clusters.size <= 1) {
    const cid = clusters.size === 1 ? Array.from(clusters)[0] : -1;
    const collapsed: any = {
      id: node.id + "_c", leaf: true, distance: node.distance,
      count: leafCount, _collapsed: true, _morphCount: leafCount,
    };
    collapsed[level] = cid;
    return collapsed as TreeNode;
  }
  return { ...node, children: node.children.map(c => pruneToLevel(c, level)) };
}

const DEPTH_OPTIONS = [
  { value: "depth_3", label: "3 levels (15 nodes)" },
  { value: "depth_5", label: "5 levels (57 nodes)" },
  { value: "depth_7", label: "7 levels (143 nodes)" },
  { value: "depth_10", label: "10 levels (635 nodes)" },
  { value: "full", label: "All levels (full tree)" },
  { value: "by_level", label: "Simplified by clusters" },
];

type LayoutMode = "radial" | "vertical" | "geographic";

export default function HierarchyView({
  trees, fullTree, level, ramp, clusterIds, activeClusters, centroids,
  onClusterClick, onBranchClick, onClusterDoubleClick,
}: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [mode, setMode] = useState<LayoutMode>("radial");
  const [depthKey, setDepthKey] = useState("depth_10");
  const [fishRadius, setFishRadius] = useState(200);
  const [fishDistortion, setFishDistortion] = useState(1);
  const [containerSize, setContainerSize] = useState({ w: 500, h: 500 });

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

  const displayTree = (() => {
    const ft = trees?.full ?? fullTree;
    if (depthKey === "full") return ft;
    if (depthKey === "by_level") return ft ? pruneToLevel(ft, level) : null;
    return trees?.[depthKey] ?? ft;
  })();

  useEffect(() => {
    if (!displayTree || !svgRef.current) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const width = containerSize.w;
    const height = containerSize.h;
    if (width < 50 || height < 50) return;

    const colors = generateColors(clusterIds.length, ramp);
    const cx = width / 2, cy = height / 2;
    const mg = { top: 30, right: 30, bottom: 30, left: 30 };
    const isGeo = mode === "geographic";

    function getLeafCluster(node: any): number {
      if (node.data?.leaf || !node.children) return node.data?.[level] ?? -1;
      return getLeafCluster(node.children[0]);
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

    const root = d3.hierarchy(displayTree, (d: any) => d.children);
    svg.attr("viewBox", `0 0 ${width} ${height}`);

    // ── Layout ───────────────────────────────────────────
    if (mode === "radial") {
      const r = Math.min(width, height) / 2 - 40;
      d3.cluster<TreeNode>().size([2 * Math.PI, r]).separation(() => 1)(root as any);
    } else if (mode === "vertical") {
      d3.cluster<TreeNode>()
        .size([width - mg.left - mg.right, height - mg.top - mg.bottom])(root as any);
    }
    // geographic: positions set below from centroids

    // ── Assign Cartesian positions ───────────────────────
    if (isGeo) {
      // Compute geographic bounds from centroids of leaves in this tree
      let lngMin = Infinity, lngMax = -Infinity, latMin = Infinity, latMax = -Infinity;
      let found = 0;
      root.leaves().forEach((d: any) => {
        const key = String(d.data.id).replace(/_c$/, "");
        const c = centroids[key];
        if (c) {
          lngMin = Math.min(lngMin, c[0]); lngMax = Math.max(lngMax, c[0]);
          latMin = Math.min(latMin, c[1]); latMax = Math.max(latMax, c[1]);
          found++;
        }
      });

      if (found < 2) {
        // Fallback: not enough centroids, use vertical layout
        d3.cluster<TreeNode>()
          .size([width - mg.left - mg.right, height - mg.top - mg.bottom])(root as any);
        root.each((d: any) => { d._ox = d.x + mg.left; d._oy = d.y + mg.top; });
      } else {
        const pad = 35;
        const aspect = (lngMax - lngMin) / (latMax - latMin);
        const panelAspect = (width - 2 * pad) / (height - 2 * pad);
        let scaleW = width - 2 * pad, scaleH = height - 2 * pad;
        let offX = pad, offY = pad;
        if (aspect > panelAspect) {
          scaleH = scaleW / aspect;
          offY = (height - scaleH) / 2;
        } else {
          scaleW = scaleH * aspect;
          offX = (width - scaleW) / 2;
        }
        const sx = (lng: number) => offX + ((lng - lngMin) / (lngMax - lngMin)) * scaleW;
        const sy = (lat: number) => offY + ((latMax - lat) / (latMax - latMin)) * scaleH;

        // Leaves: place at centroid
        root.leaves().forEach((d: any) => {
          const key = String(d.data.id).replace(/_c$/, "");
          const c = centroids[key];
          if (c) {
            d._ox = sx(c[0]); d._oy = sy(c[1]);
          }
        });

        // Branch nodes: weighted average of children (bottom-up)
        root.eachAfter((d: any) => {
          if (d.children && d.children.length > 0) {
            let sumX = 0, sumY = 0, n = 0;
            for (const child of d.children) {
              if (child._ox != null) { sumX += child._ox; sumY += child._oy; n++; }
            }
            if (n > 0) { d._ox = sumX / n; d._oy = sumY / n; }
            else { d._ox = cx; d._oy = cy; }
          }
          // Leaves without centroids: place near parent later
          if (!d.children && d._ox == null) {
            d._ox = cx; d._oy = cy;
          }
        });
      }
    } else {
      root.each((d: any) => {
        if (mode === "radial") {
          const [px, py] = d3.pointRadial(d.x, d.y) as [number, number];
          d._ox = cx + px; d._oy = cy + py;
        } else {
          d._ox = d.x + mg.left; d._oy = d.y + mg.top;
        }
      });
    }

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
      if (isGeo) {
        // Smooth curve: control point at parent x, child y
        link._bx = s._ox;
        link._by = t._oy;
      } else if (mode === "radial") {
        const [bx, by] = d3.pointRadial(t.x, s.y) as [number, number];
        link._bx = cx + bx; link._by = cy + by;
      } else {
        link._bx = t._ox; link._by = s._oy;
      }
    });

    // ── Draw ─────────────────────────────────────────────
    const g = svg.append("g");

    const linkEls: SVGPathElement[] = [];
    g.selectAll(".link").data(allLinks).join("path")
      .attr("class", "link").attr("fill", "none")
      .attr("stroke", (d: any) => getNodeColor(d.target))
      .attr("stroke-width", (d: any) =>
        Math.max(isGeo ? 0.4 : 0.8, Math.log2(d.target.data?.count || 1) * (isGeo ? 0.3 : 0.7)))
      .attr("stroke-opacity", (d: any) =>
        (d.target as any)._active ? (isGeo ? 0.5 : 0.7) : 0.04)
      .attr("d", (d: any) => {
        const t = d.target as any, s = d.source as any;
        if (isGeo) {
          return `M${t._ox},${t._oy}Q${(d as any)._bx},${(d as any)._by} ${s._ox},${s._oy}`;
        }
        return `M${t._ox},${t._oy}L${(d as any)._bx},${(d as any)._by}L${s._ox},${s._oy}`;
      })
      .each(function () { linkEls.push(this as SVGPathElement); });

    const nodeEls: SVGCircleElement[] = [];
    g.selectAll(".node").data(allNodes).join("circle")
      .attr("class", "node")
      .attr("cx", (d: any) => d._ox).attr("cy", (d: any) => d._oy)
      .attr("r", (d: any) => {
        if (d.data?._collapsed) return Math.max(4, Math.min(12, Math.sqrt(d.data._morphCount) * 1.2));
        return d.children ? (isGeo ? 1.5 : 2.5) : (isGeo ? 2 : 3.5);
      })
      .attr("fill", (d: any) => getNodeColor(d))
      .attr("stroke", (d: any) => {
        if (d.data?._collapsed) return getNodeColor(d);
        return d.children ? "rgba(255,255,255,0.5)" : "#fff";
      })
      .attr("stroke-width", (d: any) => d.data?._collapsed ? 2 : 0.5)
      .attr("opacity", (d: any) => {
        if (!d._active) return 0.04;
        if (d.data?._collapsed) return 0.9;
        return d.children ? (isGeo ? 0.25 : 0.45) : 0.95;
      })
      .style("cursor", "pointer")
      .on("click", (_e: any, d: any) => {
        if (d.children) onBranchClick?.(getSubtreeClusters(d));
        else onClusterClick(getLeafCluster(d));
      })
      .on("dblclick", (_e: any, d: any) => {
        if (!d.children) onClusterDoubleClick?.(getLeafCluster(d));
      })
      .each(function () { nodeEls.push(this as SVGCircleElement); });

    const labelEls: SVGTextElement[] = [];
    g.selectAll(".node-label").data(allNodes).join("text")
      .attr("class", "node-label")
      .attr("x", (d: any) => d._ox)
      .attr("y", (d: any) => {
        const r = d.data?._collapsed
          ? Math.max(4, Math.min(12, Math.sqrt(d.data._morphCount) * 1.2))
          : d.children ? 3 : 4;
        return d._oy - r - 2;
      })
      .attr("text-anchor", "middle")
      .attr("font-size", (d: any) => d.data?._collapsed ? 5 : (isGeo ? 2.5 : 3.5))
      .attr("font-weight", (d: any) => d.data?._collapsed ? "600" : "400")
      .attr("fill", (d: any) => d._active ? "#555" : "transparent")
      .attr("pointer-events", "none")
      .text((d: any) => {
        if (d.data?._collapsed) return `#${getLeafCluster(d)} (${d.data._morphCount})`;
        if (d.children) return `[${d.leaves().length}]`;
        return getLeafCluster(d);
      })
      .style("opacity", (d: any) =>
        d.data?._collapsed && depthKey === "by_level" ? "1" : "0")
      .each(function () { labelEls.push(this as SVGTextElement); });

    const radiusRing = g.append("circle")
      .attr("fill", "none").attr("stroke", "rgba(100,100,100,0.15)")
      .attr("stroke-width", 1).attr("stroke-dasharray", "4,3")
      .style("pointer-events", "none").style("opacity", "0");

    // ── GSAP fisheye ─────────────────────────────────────
    const lens = { fx: cx, fy: cy, blend: 0 };

    function render() {
      const { fx, fy, blend } = lens;
      radiusRing.attr("cx", fx).attr("cy", fy).attr("r", fishRadius)
        .style("opacity", String(blend * 0.4));

      for (let i = 0; i < allNodes.length; i++) {
        const d = allNodes[i] as any;
        const isCollapsed = !!d.data?._collapsed;
        const isLeaf = !d.children;
        const baseR = isCollapsed
          ? Math.max(4, Math.min(12, Math.sqrt(d.data._morphCount) * 1.2))
          : isLeaf ? (isGeo ? 2 : 3.5) : (isGeo ? 1.5 : 2.5);
        const maxGrow = isCollapsed ? 8 : isLeaf ? 6 : 4;

        const [nx, ny] = fisheyePoint(d._ox, d._oy, fx, fy, fishRadius, fishDistortion);
        const x = d._ox + (nx - d._ox) * blend;
        const y = d._oy + (ny - d._oy) * blend;
        const dist = Math.sqrt((d._ox - fx) ** 2 + (d._oy - fy) ** 2);
        const near = dist < fishRadius ? 1 - dist / fishRadius : 0;
        const r = baseR + near * maxGrow * blend;

        nodeEls[i].setAttribute("cx", String(x));
        nodeEls[i].setAttribute("cy", String(y));
        nodeEls[i].setAttribute("r", String(r));

        if (!isLeaf && d._active)
          nodeEls[i].setAttribute("opacity", String((isGeo ? 0.25 : 0.45) + near * 0.55 * blend));

        const el = labelEls[i];
        if (el) {
          el.setAttribute("x", String(x));
          el.setAttribute("y", String(y - r - 2));
          const fs = (isCollapsed ? 5 : isGeo ? 2.5 : 3.5) + near * 7 * blend;
          el.setAttribute("font-size", String(fs));
          const alwaysShow = isCollapsed && depthKey === "by_level";
          const threshold = isLeaf ? 0.25 : 0.4;
          el.style.opacity = alwaysShow
            ? String(Math.max(0.8, near * 2 * blend))
            : (near > threshold && blend > 0.3 ? String(Math.min(1, near * 2.5 * blend)) : "0");
        }
      }

      for (let i = 0; i < allLinks.length; i++) {
        const link = allLinks[i] as any;
        const t = link.target as any, s = link.source as any;
        const [ntx, nty] = fisheyePoint(t._ox, t._oy, fx, fy, fishRadius, fishDistortion);
        const [nsx, nsy] = fisheyePoint(s._ox, s._oy, fx, fy, fishRadius, fishDistortion);
        const [nbx, nby] = fisheyePoint(link._bx, link._by, fx, fy, fishRadius, fishDistortion);
        const tx = t._ox + (ntx - t._ox) * blend, ty = t._oy + (nty - t._oy) * blend;
        const sx = s._ox + (nsx - s._ox) * blend, sy = s._oy + (nsy - s._oy) * blend;
        const bx = link._bx + (nbx - link._bx) * blend, by = link._by + (nby - link._by) * blend;
        if (isGeo) {
          linkEls[i]?.setAttribute("d", `M${tx},${ty}Q${bx},${by} ${sx},${sy}`);
        } else {
          linkEls[i]?.setAttribute("d", `M${tx},${ty}L${bx},${by}L${sx},${sy}`);
        }
      }
    }

    svg.on("mousemove.fisheye", function (event: MouseEvent) {
      const [mx, my] = d3.pointer(event, this);
      gsap.to(lens, { fx: mx, fy: my, blend: 1, duration: 0.2,
        ease: "power2.out", overwrite: true, onUpdate: render });
    });
    svg.on("mouseleave.fisheye", () => {
      gsap.to(lens, { blend: 0, duration: 0.5,
        ease: "power3.out", overwrite: true, onUpdate: render });
    });

    return () => {
      gsap.killTweensOf(lens);
      svg.on("mousemove.fisheye", null);
      svg.on("mouseleave.fisheye", null);
    };
  }, [displayTree, mode, level, ramp, clusterIds, activeClusters, centroids,
      onClusterClick, onBranchClick, onClusterDoubleClick,
      fishRadius, fishDistortion, containerSize, depthKey]);

  return (
    <Stack gap={6} style={{ height: "100%", minHeight: 0 }}>
      <Group gap={4} grow>
        <SegmentedControl size="xs"
          data={[
            { value: "radial", label: "Circular" },
            { value: "vertical", label: "Vertical" },
            { value: "geographic", label: "Geographic" },
          ]}
          value={mode}
          onChange={v => setMode(v as LayoutMode)} />
      </Group>
      <Group gap={4} grow>
        <Select size="xs" data={DEPTH_OPTIONS} value={depthKey}
          onChange={v => v && setDepthKey(v)} allowDeselect={false} />
      </Group>
      <Group gap="xs" grow>
        <Stack gap={2}>
          <Text size="xs" c="dimmed">Radius {fishRadius}</Text>
          <Slider size="xs" min={60} max={200} value={fishRadius}
            onChange={setFishRadius} label={null} />
        </Stack>
        <Stack gap={2}>
          <Text size="xs" c="dimmed">Distortion {fishDistortion}</Text>
          <Slider size="xs" min={1} max={8} step={0.5} value={fishDistortion}
            onChange={setFishDistortion} label={null} />
        </Stack>
      </Group>
      <Text size="xs" c="dimmed" ta="center">
        Hover to distort · Click any node to filter · Dbl-click to zoom
      </Text>
      <div ref={containerRef}
        style={{ width: "100%", flex: 1, overflow: "hidden", minHeight: 0 }}>
        <svg ref={svgRef} width="100%" height="100%" style={{ display: "block" }} />
      </div>
    </Stack>
  );
}
