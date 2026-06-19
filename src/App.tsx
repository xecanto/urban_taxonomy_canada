import { useState, useEffect, useCallback, useRef } from "react";
import maplibregl from "maplibre-gl";
import gsap from "gsap";
import {
  SegmentedControl, Stack, Text, Paper, ScrollArea,
  ActionIcon, useMantineColorScheme, Badge, Table,
  Divider, Group, Accordion, Switch, Tooltip,
} from "@mantine/core";
import {
  IconSun, IconMoon, IconX, IconChevronUp, IconChevronDown,
  IconChevronLeft, IconChevronRight,
  IconLink, IconLinkOff, IconTree, IconEye, IconEyeOff,
} from "@tabler/icons-react";
import * as flatgeobuf from "flatgeobuf/lib/mjs/geojson.js";
import LayerSymbologyPanel from "./components/LayerSymbology";
import HierarchyView from "./components/HierarchyView";
import {
  generateColors, buildMatchExpression, buildInterpolateExpression,
} from "./utils/colors";
import type { RampName } from "./utils/colors";
import type { LayerSymbology, HierarchyData } from "./utils/types";

const BASEMAPS: Record<string, { name: string; url: string }> = {
  osm: { name: "OSM", url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png" },
  light: { name: "Light", url: "https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png" },
  dark: { name: "Dark", url: "https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png" },
  satellite: { name: "Satellite", url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}" },
};

async function loadFGB(url: string): Promise<GeoJSON.FeatureCollection> {
  const resp = await fetch(url);
  const buf = await resp.arrayBuffer();
  const features: GeoJSON.Feature[] = [];
  for await (const f of flatgeobuf.deserialize(new Uint8Array(buf))) {
    features.push(f as GeoJSON.Feature);
  }
  return { type: "FeatureCollection", features };
}

function extractClusterIds(datasets: GeoJSON.FeatureCollection[], prop: string): number[] {
  const set = new Set<number>();
  for (const data of datasets) {
    for (const f of data.features) {
      const v = f.properties?.[prop];
      if (v != null && v >= 0) set.add(v);
    }
  }
  return Array.from(set).sort((a, b) => a - b);
}

// ── Resize hook ──────────────────────────────────────────
function useResize(
  initial: number, min: number, max: number, side: "left" | "right",
) {
  const [width, setWidth] = useState(initial);
  const onMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    const startX = e.clientX;
    const startW = width;
    const onMove = (ev: MouseEvent) => {
      const delta = side === "left" ? ev.clientX - startX : startX - ev.clientX;
      setWidth(Math.max(min, Math.min(max, startW + delta)));
    };
    const onUp = () => {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  }, [width, min, max, side]);
  return { width, onMouseDown };
}

export default function App() {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const morphDataRef = useRef<GeoJSON.FeatureCollection | null>(null);
  const bldgDataRef = useRef<GeoJSON.FeatureCollection | null>(null);
  const popupRef = useRef<maplibregl.Popup | null>(null);
  const morphSymRef = useRef<LayerSymbology>(null!);
  const leftRef = useRef<HTMLDivElement>(null);
  const rightRef = useRef<HTMLDivElement>(null);
  const { colorScheme, toggleColorScheme } = useMantineColorScheme();

  const [basemap, setBasemap] = useState("dark");
  const [approach, setApproach] = useState<"fc" | "pct">("fc");
  const [morphSym, setMorphSym] = useState<LayerSymbology>({
    colorBy: "fc_level_3", ramp: "Bold", opacity: 0.65, visible: true,
  });
  const [bldgSym, setBldgSym] = useState<LayerSymbology>({
    colorBy: "fc_level_3", ramp: "Bold", opacity: 0.8, visible: true,
  });
  const [clusterIds, setClusterIds] = useState<number[]>([]);
  const [filterClusters, setFilterClusters] = useState<Set<number>>(new Set());
  const [clickedProps, setClickedProps] = useState<Record<string, any> | null>(null);
  const [loading, setLoading] = useState(true);
  const [hierarchyData, setHierarchyData] = useState<HierarchyData | null>(null);
  const [syncLevels, setSyncLevels] = useState(true);
  const [layerOrder, setLayerOrder] = useState<string[]>(["buildings", "morphotopes"]);
  const [leftOpen, setLeftOpen] = useState(true);
  const [rightOpen, setRightOpen] = useState(true);
  const [featureCounts, setFeatureCounts] = useState({ morphotopes: 0, buildings: 0 });
  const [centroids, setCentroids] = useState<Record<string, [number, number]>>({});

  const FC_LEVELS = [
    { value: "fc_level_1", label: "2 clusters (coarsest)" },
    { value: "fc_level_2", label: "4 clusters" },
    { value: "fc_level_3", label: "8 clusters" },
    { value: "fc_level_4", label: "16 clusters" },
    { value: "fc_level_5", label: "32 clusters" },
    { value: "fc_level_6", label: "64 clusters" },
    { value: "fc_level_7", label: "128 clusters (finest)" },
  ];
  const PCT_LEVELS = [
    { value: "pct_level_7", label: "~10 clusters (coarsest)" },
    { value: "pct_level_6", label: "~19 clusters" },
    { value: "pct_level_5", label: "~36 clusters" },
    { value: "pct_level_4", label: "~53 clusters" },
    { value: "pct_level_3", label: "~87 clusters" },
    { value: "pct_level_2", label: "~121 clusters" },
    { value: "pct_level_1", label: "~173 clusters (finest)" },
  ];
  const levelOptions = approach === "fc" ? FC_LEVELS : PCT_LEVELS;

  const handleApproachChange = useCallback((v: string) => {
    const a = v as "fc" | "pct";
    setApproach(a);
    const defaultLevel = a === "fc" ? "fc_level_3" : "pct_level_7";
    setMorphSym(prev => ({ ...prev, colorBy: defaultLevel }));
    setBldgSym(prev => ({ ...prev, colorBy: defaultLevel }));
    setFilterClusters(new Set());
  }, []);

  const leftResize = useResize(300, 220, 500, "left");
  const rightResize = useResize(420, 280, 700, "right");

  morphSymRef.current = morphSym;

  const morphColors = generateColors(clusterIds.length, morphSym.ramp as RampName);

  // ── Panel animations ───────────────────────────────────
  useEffect(() => {
    const el = leftRef.current;
    if (!el) return;
    if (leftOpen) {
      gsap.to(el, { x: 0, duration: 0.4, ease: "power3.out",
        onStart: () => { el.style.pointerEvents = "auto"; } });
    } else {
      gsap.to(el, { x: -(el.offsetWidth + 20), duration: 0.35, ease: "power3.inOut",
        onComplete: () => { el.style.pointerEvents = "none"; } });
    }
  }, [leftOpen]);

  useEffect(() => {
    const el = rightRef.current;
    if (!el) return;
    if (rightOpen) {
      gsap.to(el, { x: 0, duration: 0.4, ease: "power3.out",
        onStart: () => { el.style.pointerEvents = "auto"; } });
    } else {
      gsap.to(el, { x: el.offsetWidth + 20, duration: 0.35, ease: "power3.inOut",
        onComplete: () => { el.style.pointerEvents = "none"; } });
    }
  }, [rightOpen]);

  // ── Level & ramp sync handlers ─────────────────────────
  const handleMorphSymChange = useCallback((newSym: LayerSymbology) => {
    setMorphSym(newSym);
    if (syncLevels) {
      setBldgSym(prev => {
        const updates: Partial<LayerSymbology> = {};
        if (newSym.colorBy.includes("level_") && newSym.colorBy !== prev.colorBy)
          updates.colorBy = newSym.colorBy;
        if (newSym.ramp !== prev.ramp) updates.ramp = newSym.ramp;
        return Object.keys(updates).length > 0 ? { ...prev, ...updates } : prev;
      });
    }
  }, [syncLevels]);

  const handleBldgSymChange = useCallback((newSym: LayerSymbology) => {
    setBldgSym(newSym);
    if (syncLevels) {
      setMorphSym(prev => {
        const updates: Partial<LayerSymbology> = {};
        if (newSym.colorBy.includes("level_") && newSym.colorBy !== prev.colorBy)
          updates.colorBy = newSym.colorBy;
        if (newSym.ramp !== prev.ramp) updates.ramp = newSym.ramp;
        return Object.keys(updates).length > 0 ? { ...prev, ...updates } : prev;
      });
    }
  }, [syncLevels]);

  // ── Layer ordering ─────────────────────────────────────
  const moveLayer = useCallback((key: string, dir: number) => {
    setLayerOrder(prev => {
      const idx = prev.indexOf(key);
      const target = idx + dir;
      if (target < 0 || target >= prev.length) return prev;
      const next = [...prev];
      [next[idx], next[target]] = [next[target], next[idx]];
      return next;
    });
  }, []);

  // ── Multi-cluster filter ───────────────────────────────
  const toggleClusterFilter = useCallback((id: number) => {
    setFilterClusters(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }, []);

  const clearFilter = useCallback(() => setFilterClusters(new Set()), []);

  const handleBranchClick = useCallback((ids: number[]) => {
    setFilterClusters(prev => {
      const next = new Set(prev);
      const allSelected = ids.every(id => next.has(id));
      if (allSelected) ids.forEach(id => next.delete(id));
      else ids.forEach(id => next.add(id));
      return next;
    });
  }, []);

  // ── Zoom to cluster extent ─────────────────────────────
  const zoomToCluster = useCallback((clusterId: number) => {
    const map = mapRef.current;
    const data = morphDataRef.current;
    if (!map || !data) return;
    const prop = morphSymRef.current.colorBy;
    const bounds = new maplibregl.LngLatBounds();
    let found = false;
    for (const f of data.features) {
      if (f.properties?.[prop] !== clusterId || !f.geometry) continue;
      const geom = f.geometry as any;
      const rings: number[][][] =
        geom.type === "Polygon" ? geom.coordinates :
        geom.type === "MultiPolygon" ? geom.coordinates.flat() : [];
      for (const ring of rings)
        for (const coord of ring)
          if (Array.isArray(coord) && coord.length >= 2) {
            bounds.extend(coord as [number, number]);
            found = true;
          }
    }
    if (found) map.fitBounds(bounds, { padding: 60, duration: 1000 });
  }, []);

  // ── Init map ───────────────────────────────────────────
  useEffect(() => {
    if (!mapContainer.current) return;
    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: {
        version: 8,
        sources: {
          basemap: {
            type: "raster", tiles: [BASEMAPS[basemap].url],
            tileSize: 256, attribution: "&copy; OpenStreetMap contributors",
          },
        },
        layers: [{ id: "basemap", type: "raster", source: "basemap" }],
      },
      center: [-97.15, 49.85], zoom: 11,
    });
    map.addControl(new maplibregl.NavigationControl(), "bottom-right");
    map.addControl(new maplibregl.ScaleControl(), "bottom-left");
    mapRef.current = map;

    const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, maxWidth: "240px" });
    popupRef.current = popup;

    map.on("load", async () => {
      setLoading(true);
      const [morphData, bldgData, hierResp] = await Promise.all([
        loadFGB("/data/morphotopes.fgb"),
        loadFGB("/data/buildings.fgb"),
        fetch("/data/hierarchy_tree.json").then(r => r.json()),
      ]);
      morphDataRef.current = morphData;
      bldgDataRef.current = bldgData;
      setHierarchyData(hierResp);
      setFeatureCounts({ morphotopes: morphData.features.length, buildings: bldgData.features.length });

      const cents: Record<string, [number, number]> = {};
      for (const f of morphData.features) {
        const id = f.properties?.morph;
        if (!id || !f.geometry) continue;
        const coords: number[][] = [];
        (function flat(c: any) {
          if (typeof c[0] === "number") coords.push(c);
          else c.forEach(flat);
        })((f.geometry as any).coordinates);
        if (coords.length === 0) continue;
        cents[id] = [
          coords.reduce((s, c) => s + c[0], 0) / coords.length,
          coords.reduce((s, c) => s + c[1], 0) / coords.length,
        ];
      }
      setCentroids(cents);

      map.addSource("morphotopes", { type: "geojson", data: morphData });
      map.addLayer({ id: "morphotopes-fill", type: "fill", source: "morphotopes",
        paint: { "fill-color": "#888", "fill-opacity": 0.65 } });
      map.addLayer({ id: "morphotopes-line", type: "line", source: "morphotopes",
        paint: { "line-color": "#444", "line-opacity": 0.3,
          "line-width": ["interpolate", ["linear"], ["zoom"], 10, 0.1, 14, 0.8] } });

      map.addSource("buildings", { type: "geojson", data: bldgData });
      map.addLayer({ id: "buildings-fill", type: "fill", source: "buildings",
        paint: { "fill-color": "#888", "fill-opacity": 0.8 }, minzoom: 12 });
      map.addLayer({ id: "buildings-line", type: "line", source: "buildings",
        paint: { "line-color": "#333", "line-width": 0.4, "line-opacity": 0.5 }, minzoom: 12 });

      setClusterIds(extractClusterIds([morphData, bldgData], "fc_level_3"));

      map.on("mousemove", "morphotopes-fill", e => {
        if (!e.features?.length) return;
        map.getCanvas().style.cursor = "pointer";
        const p = e.features[0].properties!;
        const lvl = morphSymRef.current.colorBy;
        const rows = [
          `<div class="map-tooltip-row"><span class="tt-key">${lvl}</span><span class="tt-val">${p[lvl] ?? "—"}</span></div>`,
          p.morph != null ? `<div class="map-tooltip-row"><span class="tt-key">Morphotope</span><span class="tt-val">${p.morph}</span></div>` : "",
          p.building_count != null ? `<div class="map-tooltip-row"><span class="tt-key">Buildings</span><span class="tt-val">${p.building_count}</span></div>` : "",
        ].filter(Boolean).join("");
        popup.setLngLat(e.lngLat).setHTML(rows).addTo(map);
      });
      map.on("mouseleave", "morphotopes-fill", () => { map.getCanvas().style.cursor = ""; popup.remove(); });

      map.on("mousemove", "buildings-fill", e => {
        if (!e.features?.length) return;
        map.getCanvas().style.cursor = "pointer";
        const p = e.features[0].properties!;
        const rows = [
          p.HEIGHT != null && p.HEIGHT > 0 ? `<div class="map-tooltip-row"><span class="tt-key">Height</span><span class="tt-val">${Number(p.HEIGHT).toFixed(1)}m</span></div>` : "",
          p.BLDG_POP != null && p.BLDG_POP > 0 ? `<div class="map-tooltip-row"><span class="tt-key">Population</span><span class="tt-val">${p.BLDG_POP}</span></div>` : "",
          p[morphSymRef.current.colorBy] != null ? `<div class="map-tooltip-row"><span class="tt-key">${morphSymRef.current.colorBy}</span><span class="tt-val">${p[morphSymRef.current.colorBy]}</span></div>` : "",
        ].filter(Boolean).join("");
        if (rows) popup.setLngLat(e.lngLat).setHTML(rows).addTo(map);
      });
      map.on("mouseleave", "buildings-fill", () => { map.getCanvas().style.cursor = ""; popup.remove(); });

      for (const layerId of ["morphotopes-fill", "buildings-fill"])
        map.on("click", layerId, e => {
          if (e.features?.[0]?.properties) setClickedProps(e.features[0].properties);
        });

      setLoading(false);
    });
    return () => { map.remove(); };
  }, []); // eslint-disable-line

  useEffect(() => {
    const map = mapRef.current;
    if (!map?.getSource("basemap")) return;
    (map.getSource("basemap") as maplibregl.RasterTileSource).setTiles([BASEMAPS[basemap].url]);
  }, [basemap]);

  useEffect(() => {
    if (!morphDataRef.current) return;
    if (morphSym.colorBy.includes("level_")) {
      const datasets: GeoJSON.FeatureCollection[] = [morphDataRef.current];
      if (bldgDataRef.current) datasets.push(bldgDataRef.current);
      setClusterIds(extractClusterIds(datasets, morphSym.colorBy));
      setFilterClusters(new Set());
    }
  }, [morphSym.colorBy]);

  const applyMorphSymbology = useCallback(() => {
    const map = mapRef.current;
    if (!map?.getLayer("morphotopes-fill")) return;
    const colors = generateColors(clusterIds.length, morphSym.ramp as RampName);
    map.setPaintProperty("morphotopes-fill", "fill-color", buildMatchExpression(morphSym.colorBy, clusterIds, colors));
    map.setPaintProperty("morphotopes-fill", "fill-opacity", morphSym.opacity);
    map.setLayoutProperty("morphotopes-fill", "visibility", morphSym.visible ? "visible" : "none");
    map.setLayoutProperty("morphotopes-line", "visibility", morphSym.visible ? "visible" : "none");
  }, [morphSym, clusterIds]);
  useEffect(() => { applyMorphSymbology(); }, [applyMorphSymbology]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map?.getLayer("buildings-fill")) return;
    map.setLayoutProperty("buildings-fill", "visibility", bldgSym.visible ? "visible" : "none");
    map.setLayoutProperty("buildings-line", "visibility", bldgSym.visible ? "visible" : "none");
    if (!bldgSym.visible) return;
    const bColors = generateColors(clusterIds.length, bldgSym.ramp as RampName);
    if (bldgSym.colorBy === "HEIGHT")
      map.setPaintProperty("buildings-fill", "fill-color", buildInterpolateExpression("HEIGHT", 0, 30, bldgSym.ramp as RampName));
    else if (bldgSym.colorBy === "BLDG_POP")
      map.setPaintProperty("buildings-fill", "fill-color", buildInterpolateExpression("BLDG_POP", 0, 20, bldgSym.ramp as RampName));
    else if (bldgSym.colorBy === "solid")
      map.setPaintProperty("buildings-fill", "fill-color", bColors[0] || "#888");
    else
      map.setPaintProperty("buildings-fill", "fill-color", buildMatchExpression(bldgSym.colorBy, clusterIds, bColors, "rgba(180,180,180,0.15)"));
    map.setPaintProperty("buildings-fill", "fill-opacity", bldgSym.opacity);
  }, [bldgSym, clusterIds]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const lm: Record<string, string[]> = {
      morphotopes: ["morphotopes-fill", "morphotopes-line"],
      buildings: ["buildings-fill", "buildings-line"],
    };
    for (let i = layerOrder.length - 1; i >= 0; i--)
      for (const id of lm[layerOrder[i]])
        if (map.getLayer(id)) map.moveLayer(id);
  }, [layerOrder]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map?.getLayer("morphotopes-fill")) return;
    const filter = filterClusters.size > 0
      ? ["in", ["get", morphSym.colorBy], ["literal", Array.from(filterClusters)]] as any : null;
    map.setFilter("morphotopes-fill", filter);
    map.setFilter("morphotopes-line", filter);
    if (map.getLayer("buildings-fill")) {
      const bProp = bldgSym.colorBy.includes("level_") ? bldgSym.colorBy : morphSym.colorBy;
      const bf = filterClusters.size > 0
        ? ["in", ["get", bProp], ["literal", Array.from(filterClusters)]] as any : null;
      map.setFilter("buildings-fill", bf);
      map.setFilter("buildings-line", bf);
    }
  }, [filterClusters, morphSym.colorBy, bldgSym.colorBy]);

  // Resize map when panels change
  useEffect(() => {
    mapRef.current?.resize();
  }, [leftResize.width, rightResize.width, leftOpen, rightOpen]);

  const clusterSummary = hierarchyData?.cluster_summary?.[morphSym.colorBy] || [];
  const clusterSummaryMap = new Map(clusterSummary.map(s => [s.cluster, s.morphotopes]));

  const layerConfigs: Record<string, {
    label: string; sym: LayerSymbology;
    onChange: (s: LayerSymbology) => void; type: "morphotopes" | "buildings";
  }> = {
    morphotopes: { label: "Morphotopes", sym: morphSym, onChange: handleMorphSymChange, type: "morphotopes" },
    buildings: { label: "Buildings (zoom 12+)", sym: bldgSym, onChange: handleBldgSymChange, type: "buildings" },
  };

  const currentLevel = morphSym.colorBy.includes("level_") ? morphSym.colorBy : "fc_level_3";

  return (
    <div className="app">
      <div ref={mapContainer} className="map-container" />

      {/* ── Left panel toggle tab ─────────────────────────── */}
      <Paper
        className={`panel-tab panel-tab-left ${leftOpen ? "hidden" : ""}`}
        shadow="md" radius="sm" p={0} withBorder
        onClick={() => setLeftOpen(true)}
      >
        <IconChevronRight size={18} />
      </Paper>

      {/* ── Left Panel ─────────────────────────────────── */}
      <div ref={leftRef} className="left-panel-wrapper"
        style={{ width: leftResize.width }}
      >
        <Paper className="left-panel" shadow="lg" radius="md" p="xs" withBorder>
          <ScrollArea h="calc(100vh - 32px)" offsetScrollbars scrollbarSize={6}>
            <Stack gap={6}>
              <Group justify="space-between">
                <Text fw={700} size="md">Winnipeg Urban Taxonomy</Text>
                <Group gap={4}>
                  <Tooltip label={rightOpen ? "Hide tree" : "Show tree"}>
                    <ActionIcon variant="subtle" size="sm" onClick={() => setRightOpen(v => !v)}>
                      <IconTree size={14} />
                    </ActionIcon>
                  </Tooltip>
                  <ActionIcon variant="subtle" size="sm" onClick={() => toggleColorScheme()}>
                    {colorScheme === "dark" ? <IconSun size={14} /> : <IconMoon size={14} />}
                  </ActionIcon>
                  <Tooltip label="Collapse panel">
                    <ActionIcon variant="subtle" size="sm" onClick={() => setLeftOpen(false)}>
                      <IconChevronLeft size={14} />
                    </ActionIcon>
                  </Tooltip>
                </Group>
              </Group>

              <div className="stats-bar">
                <div className="stat-chip">
                  <span className="stat-value">{featureCounts.morphotopes.toLocaleString()}</span> morphotopes
                </div>
                <div className="stat-chip">
                  <span className="stat-value">{featureCounts.buildings.toLocaleString()}</span> buildings
                </div>
                <div className="stat-chip">
                  <span className="stat-value">{clusterIds.length}</span> clusters
                </div>
                {filterClusters.size > 0 && (
                  <div className="stat-chip" style={{ color: "#e03131" }}>
                    <span className="stat-value">{filterClusters.size}</span> filtered
                  </div>
                )}
              </div>

              <Divider label="Basemap" labelPosition="left" />
              <SegmentedControl size="xs" fullWidth
                data={Object.entries(BASEMAPS).map(([k, v]) => ({ value: k, label: v.name }))}
                value={basemap} onChange={setBasemap} />

              <Divider label="Clustering Approach" labelPosition="left" />
              <SegmentedControl size="xs" fullWidth
                data={[
                  { value: "fc", label: "Fixed Count" },
                  { value: "pct", label: "Percentile" },
                ]}
                value={approach} onChange={handleApproachChange} />
              <Text size="xs" c="dimmed">
                {approach === "fc"
                  ? "Ward linkage cut at fixed cluster counts (2→128)"
                  : "Ward linkage cut at distance percentiles (fine→coarse)"}
              </Text>

              <Divider label="Layers" labelPosition="left" />
              <Group justify="space-between" px={2}>
                <Switch label="Sync levels & ramp" checked={syncLevels}
                  onChange={e => setSyncLevels(e.currentTarget.checked)} size="xs"
                  onLabel={<IconLink size={10} />} offLabel={<IconLinkOff size={10} />} />
              </Group>

              <div className="layer-order-list">
                {layerOrder.map((key, i) => (
                  <Group key={key} className="layer-order-item" justify="space-between" wrap="nowrap">
                    <Group gap={6} wrap="nowrap">
                      <ActionIcon size="xs" variant="subtle"
                        onClick={() => { const c = layerConfigs[key]; c.onChange({ ...c.sym, visible: !c.sym.visible }); }}>
                        {layerConfigs[key].sym.visible ? <IconEye size={11} /> : <IconEyeOff size={11} />}
                      </ActionIcon>
                      <Text size="xs" fw={500} c={layerConfigs[key].sym.visible ? undefined : "dimmed"}>
                        {layerConfigs[key].label}
                      </Text>
                    </Group>
                    <Group gap={2} wrap="nowrap">
                      <Tooltip label="Move up (on top)">
                        <ActionIcon size="xs" variant="subtle" disabled={i === 0}
                          onClick={() => moveLayer(key, -1)}><IconChevronUp size={11} /></ActionIcon>
                      </Tooltip>
                      <Tooltip label="Move down (below)">
                        <ActionIcon size="xs" variant="subtle" disabled={i === layerOrder.length - 1}
                          onClick={() => moveLayer(key, 1)}><IconChevronDown size={11} /></ActionIcon>
                      </Tooltip>
                    </Group>
                  </Group>
                ))}
                <Text size="xs" c="dimmed" fs="italic" ta="right" mt={2}>
                  Top of list = top of map
                </Text>
              </div>

              <Accordion variant="separated" radius="sm" defaultValue={["morphotopes", "legend"]} multiple>
                {layerOrder.map(key => {
                  const cfg = layerConfigs[key];
                  return (
                    <Accordion.Item key={key} value={key}>
                      <Accordion.Control><Text size="xs" fw={600}>{cfg.label}</Text></Accordion.Control>
                      <Accordion.Panel>
                        <LayerSymbologyPanel label={cfg.label} symbology={cfg.sym}
                          onChange={cfg.onChange} layerType={cfg.type}
                        levelOptions={levelOptions} />
                      </Accordion.Panel>
                    </Accordion.Item>
                  );
                })}

                <Accordion.Item value="legend">
                  <Accordion.Control><Text size="xs" fw={600}>Legend</Text></Accordion.Control>
                  <Accordion.Panel>
                    {filterClusters.size > 0 && (
                      <Group gap={4} mb={4}>
                        <Badge size="sm" color="red" variant="light">{filterClusters.size} selected</Badge>
                        <ActionIcon size="xs" variant="subtle" onClick={clearFilter}><IconX size={10} /></ActionIcon>
                      </Group>
                    )}
                    <div className="legend-grid">
                      {clusterIds.map((id, i) => {
                        const active = filterClusters.size === 0 || filterClusters.has(id);
                        const count = clusterSummaryMap.get(id);
                        return (
                          <div key={id} className={`legend-item ${active ? "" : "dimmed"}`}
                            onClick={() => toggleClusterFilter(id)}
                            onDoubleClick={() => zoomToCluster(id)}
                            title={`Click: filter · Dbl-click: zoom${count != null ? ` · ${count} morphotopes` : ""}`}>
                            <div className="legend-swatch" style={{ background: morphColors[i] }} />
                            <span>{id}</span>
                            {count != null && <span className="legend-count">({count})</span>}
                          </div>
                        );
                      })}
                    </div>
                  </Accordion.Panel>
                </Accordion.Item>

                {filterClusters.size > 0 && clusterSummary.length > 0 && (
                  <Accordion.Item value="cluster-stats">
                    <Accordion.Control><Text size="xs" fw={600}>Selection Stats</Text></Accordion.Control>
                    <Accordion.Panel>
                      <table className="cluster-stats-table">
                        <thead><tr><th>Cluster</th><th>Morphotopes</th><th>Color</th></tr></thead>
                        <tbody>
                          {Array.from(filterClusters).sort((a, b) => a - b).map(id => {
                            const count = clusterSummaryMap.get(id) ?? 0;
                            const idx = clusterIds.indexOf(id);
                            return (
                              <tr key={id}>
                                <td>{id}</td><td>{count}</td>
                                <td><div style={{ width: 14, height: 14, borderRadius: 3, background: idx >= 0 ? morphColors[idx] : "#ccc" }} /></td>
                              </tr>
                            );
                          })}
                          <tr style={{ fontWeight: 700, borderTop: "1px solid rgba(128,128,128,0.3)" }}>
                            <td>Total</td>
                            <td>{Array.from(filterClusters).reduce((s, id) => s + (clusterSummaryMap.get(id) ?? 0), 0)}</td>
                            <td />
                          </tr>
                        </tbody>
                      </table>
                    </Accordion.Panel>
                  </Accordion.Item>
                )}

                {clickedProps && (
                  <Accordion.Item value="properties">
                    <Accordion.Control>
                      <Group gap={4}>
                        <Text size="xs" fw={600}>Properties</Text>
                        <ActionIcon size="xs" variant="subtle"
                          onClick={e => { e.stopPropagation(); setClickedProps(null); }}><IconX size={10} /></ActionIcon>
                      </Group>
                    </Accordion.Control>
                    <Accordion.Panel>
                      <Table striped highlightOnHover withTableBorder>
                        <Table.Tbody>
                          {Object.entries(clickedProps).filter(([k]) => k !== "geometry").map(([k, v]) => (
                            <Table.Tr key={k}>
                              <Table.Td fw={600}>{k}</Table.Td>
                              <Table.Td>{String(v)}</Table.Td>
                            </Table.Tr>
                          ))}
                        </Table.Tbody>
                      </Table>
                    </Accordion.Panel>
                  </Accordion.Item>
                )}
              </Accordion>
            </Stack>
          </ScrollArea>
        </Paper>

        {/* resize handle */}
        <div className="resize-handle resize-handle-right"
          onMouseDown={leftResize.onMouseDown} />
      </div>

      {/* ── Right panel toggle tab ────────────────────────── */}
      <Paper
        className={`panel-tab panel-tab-right ${rightOpen ? "hidden" : ""}`}
        shadow="md" radius="sm" p={0} withBorder
        onClick={() => setRightOpen(true)}
      >
        <IconChevronLeft size={18} />
      </Paper>

      {/* ── Right Panel: Hierarchy ─────────────────────── */}
      <div ref={rightRef} className="right-panel-wrapper"
        style={{ width: rightResize.width }}
      >
        {/* resize handle */}
        <div className="resize-handle resize-handle-left"
          onMouseDown={rightResize.onMouseDown} />

        <Paper className="right-panel" shadow="lg" radius="md" p="xs" withBorder>
          <Group justify="space-between" mb={4}>
            <Text fw={600} size="sm">Hierarchy Tree</Text>
            <Tooltip label="Collapse panel">
              <ActionIcon variant="subtle" size="sm" onClick={() => setRightOpen(false)}>
                <IconChevronRight size={14} />
              </ActionIcon>
            </Tooltip>
          </Group>
          <HierarchyView
            trees={hierarchyData?.trees || null}
            fullTree={hierarchyData?.tree || null}
            level={currentLevel}
            ramp={morphSym.ramp as RampName}
            clusterIds={clusterIds}
            activeClusters={filterClusters}
            centroids={centroids}
            onClusterClick={toggleClusterFilter}
            onBranchClick={handleBranchClick}
            onClusterDoubleClick={zoomToCluster}
          />
        </Paper>
      </div>

      {loading && (
        <div className="loading-overlay">
          <Text size="lg" fw={600} c="white">Loading morphotopes & buildings…</Text>
        </div>
      )}
    </div>
  );
}
