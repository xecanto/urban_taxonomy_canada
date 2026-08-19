import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import maplibregl from "maplibre-gl";
import gsap from "gsap";
import {
  SegmentedControl, Stack, Text, Paper, ScrollArea,
  ActionIcon, useMantineColorScheme, Badge, Table,
  Divider, Group, Accordion, Tooltip, Select, Checkbox,
} from "@mantine/core";
import {
  IconSun, IconMoon, IconX,
  IconChevronLeft, IconChevronRight,
  IconTree, IconEye, IconEyeOff, IconMapPin,
  IconPlus, IconMinus,
} from "@tabler/icons-react";
import { Protocol } from "pmtiles";
import LayerSymbologyPanel from "./components/LayerSymbology";
import HierarchyView from "./components/HierarchyView";
import type { LayoutMode } from "./components/HierarchyView";
import { generateColors } from "./utils/colors";
import type { RampName } from "./utils/colors";
import type { LayerSymbology, GlobalClusterSummary } from "./utils/types";
import { buildLegendRows, clusterKey, parseClusterKey, buildTaxonomyTree } from "./utils/frontier";
import { fetchRegions, pmtilesUrl } from "./config/regions";
import type { RegionConfig, TileVariant } from "./config/regions";

const BASEMAPS: Record<string, { name: string; url: string }> = {
  osm: { name: "OSM", url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png" },
  light: { name: "Light", url: "https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png" },
  dark: { name: "Dark", url: "https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png" },
  satellite: { name: "Satellite", url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}" },
};

const TAXONOMY_SOURCE = "taxonomy";
// Register the pmtiles:// protocol with MapLibre once at module load.
maplibregl.addProtocol("pmtiles", new Protocol().tile);

// Cluster ids for a level come from the global cluster summary (we can't
// iterate all tile features to discover them). Returns sorted ids, e.g.
// level_3 → [1..8]. Region-independent — see GlobalClusterSummary.
function clusterIdsForLevel(summary: GlobalClusterSummary | null, level: string): number[] {
  const entries = summary?.cluster_summary?.[level];
  if (!entries) return [];
  return entries.map(s => s.cluster).sort((a, b) => a - b);
}

function bboxToBounds(bbox: [number, number, number, number]): maplibregl.LngLatBoundsLike {
  return [[bbox[0], bbox[1]], [bbox[2], bbox[3]]];
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
  const popupRef = useRef<maplibregl.Popup | null>(null);
  const bldgSymRef = useRef<LayerSymbology>(null!);
  const initializedRef = useRef(false);
  const leftRef = useRef<HTMLDivElement>(null);
  const rightRef = useRef<HTMLDivElement>(null);
  const { colorScheme, toggleColorScheme } = useMantineColorScheme();

  const [basemap, setBasemap] = useState("dark");
  const [bldgSym, setBldgSym] = useState<LayerSymbology>({
    level: "level_3", ramp: "Bold", opacity: 0.8, visible: true,
  });
  const [clusterIds, setClusterIds] = useState<number[]>([]);
  // Drilled-down clusters at bldgSym.level — e.g. {"level_3:3"} means
  // cluster 3 has been expanded into its level_4 children in the legend/map.
  const [expandedClusters, setExpandedClusters] = useState<Set<string>>(new Set());
  // Filter selections are "level:cluster" keys (not bare numbers) because a
  // drilled-down legend mixes clusters from more than one level at once.
  const [filterClusters, setFilterClusters] = useState<Set<string>>(new Set());
  const [clickedProps, setClickedProps] = useState<Record<string, any> | null>(null);
  const [loading, setLoading] = useState(true);
  const [globalClusterSummary, setGlobalClusterSummary] = useState<GlobalClusterSummary | null>(null);
  // The no-CHM run is its own separate clustering pass — genuinely different
  // cluster counts/structure than the CHM one. See activeClusterSummary
  // below for which of the two is actually used where.
  const [nochmClusterSummary, setNochmClusterSummary] = useState<GlobalClusterSummary | null>(null);
  const [leftOpen, setLeftOpen] = useState(true);
  const [rightOpen, setRightOpen] = useState(true);
  const [featureCounts, setFeatureCounts] = useState({ buildings: 0 });
  const [regions, setRegions] = useState<RegionConfig[]>([]);
  const [regionsError, setRegionsError] = useState<string | null>(null);
  const [selectedRegion, setSelectedRegion] = useState<string | null>(null);
  const [mapReady, setMapReady] = useState(false);
  // Lifted out of HierarchyView (rather than kept internal) because the
  // floating widget's own size/shape — circle for circular, wider box for
  // vertical — depends on it, and that's App's concern, not the tree's.
  const [treeMode, setTreeMode] = useState<LayoutMode>("radial");
  // Which pipeline run's building tiles to show. Same 152 regions/slugs,
  // same taxonomy/legend/coloring either way — see config/regions.ts.
  const [tileVariant, setTileVariant] = useState<TileVariant>("tiles");

  const levelOptions = [
    { value: "level_1", label: "2 clusters (coarsest)" },
    { value: "level_2", label: "4 clusters" },
    { value: "level_3", label: "8 clusters" },
    { value: "level_4", label: "16 clusters" },
    { value: "level_5", label: "32 clusters" },
    { value: "level_6", label: "64 clusters" },
    { value: "level_7", label: "128 clusters (finest)" },
  ];

  const leftResize = useResize(300, 220, 500, "left");

  bldgSymRef.current = bldgSym;

  // CHM and no-CHM are separate clustering passes over different building
  // sets, so their real counts per cluster differ — the legend/map/tree all
  // read from whichever one matches the buildings currently on screen.
  // Colors stay consistent across both anyway: every list here is sorted by
  // cluster id, and colorForKey below assigns colors by position in that
  // sorted order, so id 5 lands on the same color regardless of which
  // dataset's (different) counts are showing next to it.
  const activeClusterSummary = tileVariant === "tiles_nochm" ? nochmClusterSummary : globalClusterSummary;

  // The legend, as an outline: every cluster at bldgSym.level, plus (for any
  // the user has drilled into) their children nested underneath as further
  // rows — see buildLegendRows.
  const legendRows = useMemo(
    () => buildLegendRows(bldgSym.level, expandedClusters, activeClusterSummary),
    [bldgSym.level, expandedClusters, activeClusterSummary],
  );
  // Only non-expanded rows are actual map paint categories — an expanded
  // (group header) row's buildings are now split across its own children.
  const paintRows = legendRows.filter(r => !r.isExpanded);
  const paintColors = generateColors(paintRows.length, bldgSym.ramp as RampName);
  const colorForKey = new Map(paintRows.map((r, i) => [r.key, paintColors[i]]));

  // The Hierarchy Tree panel's data, from that same active summary.
  const taxonomyTree = useMemo(
    () => (activeClusterSummary ? buildTaxonomyTree(activeClusterSummary) : null),
    [activeClusterSummary],
  );

  // ── Load the region list once (name, province, bbox, building count) ──
  useEffect(() => {
    fetchRegions()
      .then(setRegions)
      .catch(e => setRegionsError(String(e)));
  }, []);

  // ── Load the global cluster summary once — region-independent, powers
  // the legend/symbology regardless of which region is selected. ──
  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}data/global_cluster_summary.json`)
      .then(r => (r.ok ? r.json() : null))
      .then((summary: GlobalClusterSummary | null) => {
        setGlobalClusterSummary(summary);
        if (summary) setClusterIds(clusterIdsForLevel(summary, bldgSymRef.current.level));
      })
      .catch(() => {});
  }, []);

  // Hierarchy Tree only — see nochmClusterSummary above.
  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}data/global_cluster_summary_nochm.json`)
      .then(r => (r.ok ? r.json() : null))
      .then((summary: GlobalClusterSummary | null) => setNochmClusterSummary(summary))
      .catch(() => {});
  }, []);

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

  // ── Multi-cluster filter (keys are "level:cluster") ────
  const toggleClusterFilter = useCallback((level: string, id: number) => {
    const key = clusterKey(level, id);
    setFilterClusters(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  }, []);

  const clearFilter = useCallback(() => setFilterClusters(new Set()), []);

  // From the hierarchy tree, which is always drawn at one fixed level (no
  // drill-down there), so every id it reports belongs to bldgSym.level.
  const handleBranchClick = useCallback((ids: number[]) => {
    const keys = ids.map(id => clusterKey(bldgSymRef.current.level, id));
    setFilterClusters(prev => {
      const next = new Set(prev);
      const allSelected = keys.every(k => next.has(k));
      if (allSelected) keys.forEach(k => next.delete(k));
      else keys.forEach(k => next.add(k));
      return next;
    });
  }, []);

  // ── Drill a legend entry in (expand to its children) or out (collapse) ──
  const toggleExpand = useCallback((key: string) => {
    setExpandedClusters(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
    // The set of visible clusters is about to change shape — stale filter
    // selections referencing a cluster that just got replaced (or that just
    // reappeared) would silently do nothing, so start clean.
    setFilterClusters(new Set());
  }, []);

  // ── Zoom to cluster extent ─────────────────────────────
  // Bounds are computed from the building features in the vector tiles that
  // are currently loaded, so this only covers whatever extent is in view.
  const zoomToCluster = useCallback((level: string, clusterId: number) => {
    const map = mapRef.current;
    if (!map) return;
    const feats = map.querySourceFeatures(TAXONOMY_SOURCE, {
      sourceLayer: "buildings",
      filter: ["==", ["get", level], clusterId],
    });
    const bounds = new maplibregl.LngLatBounds();
    let found = false;
    for (const f of feats) {
      const geom = f.geometry as any;
      if (!geom) continue;
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

  // ── Buildings layer symbology ───────────────────────────
  const applyBldgSymbology = useCallback(() => {
    // Guard on mapReady, not just mapRef.current: the Map instance exists
    // synchronously from the constructor, but calling getLayer()/style
    // methods before its "load" event fires throws inside maplibre-gl
    // rather than returning undefined.
    if (!mapReady) return;
    const map = mapRef.current;
    if (!map?.getLayer("buildings-fill")) return;
    map.setLayoutProperty("buildings-fill", "visibility", bldgSym.visible ? "visible" : "none");
    map.setLayoutProperty("buildings-line", "visibility", bldgSym.visible ? "visible" : "none");
    if (!bldgSym.visible) return;

    // One ["==", ["get", level], cluster] test per paint row — rows can
    // reference different level_N properties once the user has drilled into
    // some clusters but not others.
    const cases: any[] = [];
    paintRows.forEach((r, i) => {
      cases.push(["==", ["get", r.level], r.cluster], paintColors[i]);
    });
    map.setPaintProperty("buildings-fill", "fill-color", ["case", ...cases, "rgba(180,180,180,0.35)"]);
    map.setPaintProperty("buildings-fill", "fill-opacity", bldgSym.opacity);
  }, [bldgSym, paintRows, paintColors, mapReady]);
  useEffect(() => { applyBldgSymbology(); }, [applyBldgSymbology]);

  // Also called directly after swapping the CHM/no-CHM tile source (see
  // toggleNoChm below) — that removes+re-adds the layer, which drops any
  // filter that was set on the old one, and this effect alone wouldn't
  // notice since filterClusters itself didn't change.
  const applyMapFilter = useCallback(() => {
    const map = mapRef.current;
    if (!map?.getLayer("buildings-fill")) return;
    if (filterClusters.size === 0) {
      map.setFilter("buildings-fill", null);
      map.setFilter("buildings-line", null);
      return;
    }
    const anyOf = Array.from(filterClusters).map(key => {
      const { level, cluster } = parseClusterKey(key);
      return ["==", ["get", level], cluster];
    });
    const filter = ["any", ...anyOf] as any;
    map.setFilter("buildings-fill", filter);
    map.setFilter("buildings-line", filter);
  }, [filterClusters]);

  // ── Swap the buildings source to a different region's (or variant's) PMTiles ──
  const loadRegionTiles = useCallback((map: maplibregl.Map, slug: string, variant: TileVariant) => {
    if (map.getLayer("buildings-fill")) map.removeLayer("buildings-fill");
    if (map.getLayer("buildings-line")) map.removeLayer("buildings-line");
    if (map.getSource(TAXONOMY_SOURCE)) map.removeSource(TAXONOMY_SOURCE);

    map.addSource(TAXONOMY_SOURCE, { type: "vector", url: pmtilesUrl(slug, variant) });
    map.addLayer({ id: "buildings-fill", type: "fill",
      source: TAXONOMY_SOURCE, "source-layer": "buildings",
      paint: { "fill-color": "#888", "fill-opacity": 0.8 } });
    map.addLayer({ id: "buildings-line", type: "line",
      source: TAXONOMY_SOURCE, "source-layer": "buildings",
      paint: { "line-color": "#333", "line-width": 0.4, "line-opacity": 0.5 } });
  }, []);

  // ── Region selection: swap tiles, fly to it, best-effort hierarchy fetch ──
  const selectRegion = useCallback((slug: string | null) => {
    if (!slug) return;
    const region = regions.find(r => r.slug === slug);
    if (!region) return;
    setSelectedRegion(slug);

    const map = mapRef.current;
    if (map && mapReady) {
      loadRegionTiles(map, slug, tileVariant);
      applyBldgSymbology();
      if (region.bbox) map.fitBounds(bboxToBounds(region.bbox), { padding: 40, duration: 1500 });
      else map.flyTo({ center: region.center, zoom: 11, duration: 1500 });
    }

    setFeatureCounts({ buildings: region.nBuildings });
    setFilterClusters(new Set());
    setClickedProps(null);
  }, [regions, loadRegionTiles, applyBldgSymbology, mapReady, tileVariant]);

  // ── CHM / no-CHM toggle: same region, same view — swap which pipeline
  // run's building tiles are drawn. Legend/tree/filter/drill-down all follow
  // automatically via activeClusterSummary (see above) once tileVariant
  // changes, so this only needs to touch the map layer itself. ──
  const toggleNoChm = useCallback((useNoChm: boolean) => {
    const variant: TileVariant = useNoChm ? "tiles_nochm" : "tiles";
    setTileVariant(variant);
    const map = mapRef.current;
    if (map && mapReady && selectedRegion) {
      loadRegionTiles(map, selectedRegion, variant);
      applyBldgSymbology();
    }
  }, [mapReady, selectedRegion, loadRegionTiles, applyBldgSymbology]);

  // ── Init map (once) ─────────────────────────────────────
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
      center: [-96, 62], zoom: 3,
    });
    // top-right, not bottom-right: the Hierarchy Tree overlay now floats in
    // the bottom-right corner and would otherwise sit on top of these.
    map.addControl(new maplibregl.NavigationControl(), "top-right");
    map.addControl(new maplibregl.ScaleControl(), "bottom-left");
    mapRef.current = map;

    const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, maxWidth: "240px" });
    popupRef.current = popup;

    map.on("load", () => setMapReady(true));
    return () => { map.remove(); };
  }, []); // eslint-disable-line

  // ── Once the map has loaded AND the region list has arrived: pick a
  // default region, add its tiles, and wire up the buildings interactions
  // (done once — layer ids stay stable across later region switches). ──
  useEffect(() => {
    if (!mapReady || regions.length === 0 || initializedRef.current) return;
    initializedRef.current = true;
    const map = mapRef.current!;
    const popup = popupRef.current!;
    const defaultRegion = regions.find(r => r.slug === "winnipeg") ?? regions[0];

    setSelectedRegion(defaultRegion.slug);
    loadRegionTiles(map, defaultRegion.slug, tileVariant);
    setFeatureCounts({ buildings: defaultRegion.nBuildings });
    if (defaultRegion.bbox) map.fitBounds(bboxToBounds(defaultRegion.bbox), { padding: 40, duration: 0 });
    else map.jumpTo({ center: defaultRegion.center, zoom: 11 });

    map.on("mousemove", "buildings-fill", e => {
      if (!e.features?.length) return;
      map.getCanvas().style.cursor = "pointer";
      const p = e.features[0].properties!;
      const sym = bldgSymRef.current;
      const extra = p[sym.level] != null
        ? `<div class="map-tooltip-row"><span class="tt-key">${sym.level}</span><span class="tt-val">${p[sym.level]}</span></div>` : "";
      const rows = [
        p.HEIGHT != null && p.HEIGHT > 0 ? `<div class="map-tooltip-row"><span class="tt-key">Height</span><span class="tt-val">${Number(p.HEIGHT).toFixed(1)}m</span></div>` : "",
        p.BLDG_POP != null && p.BLDG_POP > 0 ? `<div class="map-tooltip-row"><span class="tt-key">Population</span><span class="tt-val">${p.BLDG_POP}</span></div>` : "",
        extra,
      ].filter(Boolean).join("");
      if (rows) popup.setLngLat(e.lngLat).setHTML(rows).addTo(map);
    });
    map.on("mouseleave", "buildings-fill", () => { map.getCanvas().style.cursor = ""; popup.remove(); });
    map.on("click", "buildings-fill", e => {
      if (e.features?.[0]?.properties) setClickedProps(e.features[0].properties);
    });

    applyBldgSymbology();
    setLoading(false);
  }, [mapReady, regions, loadRegionTiles, applyBldgSymbology, tileVariant]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map?.getSource("basemap")) return;
    (map.getSource("basemap") as maplibregl.RasterTileSource).setTiles([BASEMAPS[basemap].url]);
  }, [basemap]);

  // Base level changed (e.g. "8 clusters" -> "16 clusters") OR the CHM/
  // no-CHM dataset was swapped (activeClusterSummary is then a different
  // object — its own children_map, so any drill-down done under the old one
  // no longer means anything): start fresh either way.
  useEffect(() => {
    if (!activeClusterSummary) return;
    setClusterIds(clusterIdsForLevel(activeClusterSummary, bldgSym.level));
    setExpandedClusters(new Set());
    setFilterClusters(new Set());
  }, [bldgSym.level, activeClusterSummary]);

  useEffect(() => { applyMapFilter(); }, [applyMapFilter]);

  // Resize map when panels change
  useEffect(() => {
    mapRef.current?.resize();
  }, [leftResize.width, leftOpen, rightOpen]);

  const currentLevel = bldgSym.level;
  // Selection stats can span multiple levels once drilled — look counts up
  // per (level, cluster) rather than assuming one shared level.
  const countFor = (level: string, cluster: number): number =>
    activeClusterSummary?.cluster_summary?.[level]?.find(s => s.cluster === cluster)?.morphotopes ?? 0;

  // The hierarchy tree only ever shows one fixed level, so its "active"
  // highlighting only understands plain cluster ids at that level — pull
  // just those out of the (possibly mixed-level) filter selection.
  const treeActiveClusters = new Set(
    Array.from(filterClusters)
      .map(parseClusterKey)
      .filter(({ level }) => level === currentLevel)
      .map(({ cluster }) => cluster),
  );

  const regionGroups = Object.entries(
    regions.reduce<Record<string, RegionConfig[]>>((acc, r) => {
      (acc[r.province] ??= []).push(r);
      return acc;
    }, {})
  )
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([province, items]) => ({
      group: province,
      items: items.map(r => ({ value: r.slug, label: r.name })),
    }));

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
                <Text fw={700} size="md">Urban Taxonomy</Text>
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

              <Select
                size="xs"
                leftSection={<IconMapPin size={13} />}
                value={selectedRegion}
                onChange={selectRegion}
                allowDeselect={false}
                searchable
                nothingFoundMessage="No matching region"
                placeholder={regionsError ? "Failed to load regions" : "Loading regions…"}
                data={regionGroups}
              />
              {regionsError && (
                <Text size="xs" c="red" fs="italic">{regionsError}</Text>
              )}

              <div className="stats-bar">
                <div className="stat-chip">
                  <span className="stat-value">{featureCounts.buildings.toLocaleString()}</span> buildings
                </div>
                <div className="stat-chip">
                  <span className="stat-value">{paintRows.length}</span> clusters
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

              <Divider label="Buildings" labelPosition="left" />
              <Group justify="space-between" px={2}>
                <Tooltip label="A separate clustering run without CHM (canopy height) attributes — same colors per cluster id, but counts/tree reflect this run's own taxonomy" withArrow>
                  <Checkbox
                    size="xs" label="No CHM"
                    checked={tileVariant === "tiles_nochm"}
                    onChange={(e) => toggleNoChm(e.currentTarget.checked)}
                  />
                </Tooltip>
                <ActionIcon size="xs" variant="subtle"
                  onClick={() => setBldgSym(s => ({ ...s, visible: !s.visible }))}>
                  {bldgSym.visible ? <IconEye size={11} /> : <IconEyeOff size={11} />}
                </ActionIcon>
              </Group>

              <Accordion variant="separated" radius="sm" defaultValue={["buildings", "legend"]} multiple>
                <Accordion.Item value="buildings">
                  <Accordion.Control><Text size="xs" fw={600}>Symbology</Text></Accordion.Control>
                  <Accordion.Panel>
                    <LayerSymbologyPanel label="Buildings" symbology={bldgSym}
                      onChange={setBldgSym} layerType="buildings"
                      levelOptions={levelOptions} />
                  </Accordion.Panel>
                </Accordion.Item>

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
                      {legendRows.map(row => {
                        const active = filterClusters.size === 0 || filterClusters.has(row.key);
                        return (
                          <div key={row.key} className={`legend-item ${active ? "" : "dimmed"}`}
                            onClick={() => toggleClusterFilter(row.level, row.cluster)}
                            onDoubleClick={() => zoomToCluster(row.level, row.cluster)}
                            title={row.isExpanded
                              ? `Click: filter · Dbl-click: zoom · − to collapse`
                              : `Click: filter · Dbl-click: zoom · ${row.morphotopes} morphotopes${row.expandable ? " · + to subdivide" : ""}`}>
                            <div className="legend-item-main" style={{ paddingLeft: row.depth * 14 }}>
                              {row.isExpanded
                                ? <div className="legend-swatch legend-swatch-group" />
                                : <div className="legend-swatch" style={{ background: colorForKey.get(row.key) }} />}
                              <span>{row.label}</span>
                              <span className="legend-count">({row.morphotopes})</span>
                            </div>
                            <div className="legend-item-actions">
                              {row.isExpanded ? (
                                <ActionIcon size="xs" variant="subtle" title="Collapse"
                                  onClick={e => { e.stopPropagation(); toggleExpand(row.key); }}>
                                  <IconMinus size={9} />
                                </ActionIcon>
                              ) : row.expandable && (
                                <ActionIcon size="xs" variant="subtle" title="Subdivide this cluster"
                                  onClick={e => { e.stopPropagation(); toggleExpand(row.key); }}>
                                  <IconPlus size={9} />
                                </ActionIcon>
                              )}
                            </div>
                          </div>
                        );
                      })}
                      {legendRows.length === 0 && (
                        <Text size="xs" c="dimmed" fs="italic">No cluster data available</Text>
                      )}
                    </div>
                  </Accordion.Panel>
                </Accordion.Item>

                {filterClusters.size > 0 && (
                  <Accordion.Item value="cluster-stats">
                    <Accordion.Control><Text size="xs" fw={600}>Selection Stats</Text></Accordion.Control>
                    <Accordion.Panel>
                      <table className="cluster-stats-table">
                        <thead><tr><th>Cluster</th><th>Morphotopes</th><th>Color</th></tr></thead>
                        <tbody>
                          {Array.from(filterClusters).map(parseClusterKey)
                            .sort((a, b) => a.level === b.level ? a.cluster - b.cluster : a.level.localeCompare(b.level))
                            .map(({ level, cluster }) => {
                              const key = clusterKey(level, cluster);
                              const count = countFor(level, cluster);
                              const color = colorForKey.get(key);
                              return (
                                <tr key={key}>
                                  <td>{level === bldgSym.level ? cluster : `${cluster} (L${level.replace("level_", "")})`}</td>
                                  <td>{count}</td>
                                  <td><div style={{ width: 14, height: 14, borderRadius: 3, background: color ?? "#ccc" }} /></td>
                                </tr>
                              );
                            })}
                          <tr style={{ fontWeight: 700, borderTop: "1px solid rgba(128,128,128,0.3)" }}>
                            <td>Total</td>
                            <td>{Array.from(filterClusters).map(parseClusterKey).reduce((s, { level, cluster }) => s + countFor(level, cluster), 0)}</td>
                            <td />
                          </tr>
                        </tbody>
                      </table>
                    </Accordion.Panel>
                  </Accordion.Item>
                )}

                {clickedProps && (
                  <Accordion.Item value="properties">
                    {/* ActionIcon renders a <button>, so it can't live inside
                        Accordion.Control (also a <button>) without invalid
                        nested-button HTML — Mantine's own pattern for this is
                        a sibling row instead. */}
                    <Group gap={0} wrap="nowrap">
                      <Accordion.Control style={{ flex: 1 }}><Text size="xs" fw={600}>Properties</Text></Accordion.Control>
                      <ActionIcon size="xs" variant="subtle" mr="xs"
                        onClick={() => setClickedProps(null)}><IconX size={10} /></ActionIcon>
                    </Group>
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

      {/* ── Hierarchy Tree: small floating overlay, bottom-right of the
          map (not a docked sidebar) — shown/hidden via the tree icon in
          the left panel's header, no chrome of its own. ── */}
      <div ref={rightRef} className="right-panel-wrapper"
        style={{ width: treeMode === "vertical" ? 520 : 320 }}
      >
        <div className={`right-panel ${treeMode === "radial" ? "right-panel-circle" : "right-panel-box"}`}>
          <HierarchyView
            fullTree={taxonomyTree}
            level={currentLevel}
            ramp={bldgSym.ramp as RampName}
            clusterIds={clusterIds}
            activeClusters={treeActiveClusters}
            mode={treeMode}
            onModeChange={setTreeMode}
            onClusterClick={(id) => toggleClusterFilter(currentLevel, id)}
            onBranchClick={handleBranchClick}
            onClusterDoubleClick={(id) => zoomToCluster(currentLevel, id)}
          />
        </div>
      </div>

      {loading && (
        <div className="loading-overlay">
          <Text size="lg" fw={600} c="white">Loading taxonomy…</Text>
        </div>
      )}
    </div>
  );
}
