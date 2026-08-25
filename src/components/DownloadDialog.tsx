import { useState } from "react";
import { Modal, MultiSelect, Checkbox, Button, Stack, Text, Alert, Group, Progress, Anchor } from "@mantine/core";
import { IconDownload, IconAlertCircle } from "@tabler/icons-react";
import JSZip from "jszip";
import { regionGeojsonlUrl } from "../config/regions";
import type { RegionConfig, TileVariant } from "../config/regions";

interface Props {
  opened: boolean;
  onClose: () => void;
  regions: RegionConfig[];
  defaultSlug: string | null;
  defaultVariant: TileVariant;
}

interface Job {
  slug: string;
  variant: TileVariant;
}

function filenameFor({ slug, variant }: Job): string {
  return `${slug}_${variant === "tiles_nochm" ? "nochm" : "chm"}_buildings.geojsonl`;
}

async function fetchBlob(url: string): Promise<Blob> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url.split("/").pop()} -> HTTP ${res.status}`);
  return res.blob();
}

function triggerBlobDownload(blob: Blob, filename: string) {
  const objectUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = objectUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(objectUrl);
}

export default function DownloadDialog({ opened, onClose, regions, defaultSlug, defaultVariant }: Props) {
  const [slugs, setSlugs] = useState<string[]>(defaultSlug ? [defaultSlug] : []);
  const [includeChm, setIncludeChm] = useState(defaultVariant !== "tiles_nochm");
  const [includeNoChm, setIncludeNoChm] = useState(defaultVariant === "tiles_nochm");
  const [status, setStatus] = useState<"idle" | "working" | "error">("idle");
  const [progress, setProgress] = useState({ done: 0, total: 0 });
  const [error, setError] = useState<string | null>(null);

  const variants: TileVariant[] = [
    ...(includeChm ? (["tiles"] as const) : []),
    ...(includeNoChm ? (["tiles_nochm"] as const) : []),
  ];
  const jobs: Job[] = slugs.flatMap(slug => variants.map(variant => ({ slug, variant })));
  const totalBuildings = slugs.reduce((sum, slug) => sum + (regions.find(r => r.slug === slug)?.nBuildings ?? 0), 0)
    * Math.max(variants.length, 1);

  const handleDownload = async () => {
    if (jobs.length === 0) return;
    setStatus("working");
    setError(null);
    setProgress({ done: 0, total: jobs.length });
    try {
      if (jobs.length === 1) {
        const blob = await fetchBlob(regionGeojsonlUrl(jobs[0].slug, jobs[0].variant));
        triggerBlobDownload(blob, filenameFor(jobs[0]));
        setProgress({ done: 1, total: 1 });
      } else {
        const zip = new JSZip();
        for (let i = 0; i < jobs.length; i++) {
          const blob = await fetchBlob(regionGeojsonlUrl(jobs[i].slug, jobs[i].variant));
          zip.file(filenameFor(jobs[i]), blob);
          setProgress({ done: i + 1, total: jobs.length });
        }
        const zipBlob = await zip.generateAsync({ type: "blob" });
        const stamp = new Date().toISOString().slice(0, 10);
        triggerBlobDownload(zipBlob, `urban_taxonomy_${jobs.length}_files_${stamp}.zip`);
      }
      setStatus("idle");
    } catch (e) {
      setStatus("error");
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <Modal opened={opened} onClose={onClose} title="Download building data" size="sm">
      <Stack gap="sm">
        <div>
          <Group justify="space-between" mb={2}>
            <Text component="label" size="xs" fw={600}>Regions</Text>
            <Group gap={8}>
              <Anchor size="xs" onClick={() => setSlugs(regions.map(r => r.slug))}>Select all</Anchor>
              <Anchor size="xs" c="dimmed" onClick={() => setSlugs([])}>Clear</Anchor>
            </Group>
          </Group>
          <MultiSelect
            placeholder="Choose one or more regions"
            searchable
            value={slugs}
            onChange={setSlugs}
            data={regions.map(r => ({ value: r.slug, label: `${r.name}, ${r.province}` }))}
            maxDropdownHeight={250}
            size="xs"
          />
        </div>

        <div>
          <Text size="xs" fw={600} mb={4}>Dataset</Text>
          <Group gap="lg">
            <Checkbox size="xs" label="CHM" checked={includeChm}
              onChange={(e) => setIncludeChm(e.currentTarget.checked)} />
            <Checkbox size="xs" label="No CHM" checked={includeNoChm}
              onChange={(e) => setIncludeNoChm(e.currentTarget.checked)} />
          </Group>
        </div>

        {jobs.length > 0 && (
          <Text size="xs" c="dimmed">
            {jobs.length} file{jobs.length > 1 ? "s" : ""} ({slugs.length} region{slugs.length > 1 ? "s" : ""} × {variants.length} dataset{variants.length > 1 ? "s" : ""})
            {totalBuildings > 0 && ` — ~${totalBuildings.toLocaleString()} buildings total`}
            {jobs.length > 1 && " — bundled into one .zip"}
          </Text>
        )}

        {status === "working" && (
          <Stack gap={4}>
            <Progress value={(progress.done / Math.max(1, progress.total)) * 100} size="sm" animated />
            <Text size="xs" c="dimmed">
              {jobs.length > 1 ? `Fetching ${progress.done}/${progress.total}…` : "Downloading…"}
            </Text>
          </Stack>
        )}

        {status === "error" && (
          <Alert color="red" icon={<IconAlertCircle size={14} />} title="Download failed">
            {error}
          </Alert>
        )}

        <Button
          leftSection={<IconDownload size={16} />}
          onClick={handleDownload}
          loading={status === "working"}
          disabled={jobs.length === 0}
        >
          {jobs.length > 1 ? `Download ${jobs.length} files as .zip` : "Download .geojsonl"}
        </Button>
      </Stack>
    </Modal>
  );
}
