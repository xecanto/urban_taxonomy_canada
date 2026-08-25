import { useState } from "react";
import { Modal, Select, SegmentedControl, Button, Stack, Text, Alert } from "@mantine/core";
import { IconDownload, IconAlertCircle } from "@tabler/icons-react";
import { regionGeojsonlUrl } from "../config/regions";
import type { RegionConfig, TileVariant } from "../config/regions";

interface Props {
  opened: boolean;
  onClose: () => void;
  regions: RegionConfig[];
  defaultSlug: string | null;
  defaultVariant: TileVariant;
}

async function downloadFile(url: string, filename: string) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Server returned ${res.status}`);
  const blob = await res.blob();
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
  const [slug, setSlug] = useState<string | null>(defaultSlug);
  const [variant, setVariant] = useState<TileVariant>(defaultVariant);
  const [status, setStatus] = useState<"idle" | "downloading" | "error">("idle");
  const [error, setError] = useState<string | null>(null);

  const region = regions.find(r => r.slug === slug) ?? null;

  const handleDownload = async () => {
    if (!slug) return;
    setStatus("downloading");
    setError(null);
    try {
      const filename = `${slug}_${variant === "tiles_nochm" ? "nochm" : "chm"}_buildings.geojsonl`;
      await downloadFile(regionGeojsonlUrl(slug, variant), filename);
      setStatus("idle");
    } catch (e) {
      setStatus("error");
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <Modal opened={opened} onClose={onClose} title="Download building data" size="sm">
      <Stack gap="sm">
        <Select
          label="Region"
          placeholder="Choose a region"
          searchable
          value={slug}
          onChange={setSlug}
          data={regions.map(r => ({ value: r.slug, label: `${r.name}, ${r.province}` }))}
        />

        <div>
          <Text size="xs" fw={600} mb={4}>Dataset</Text>
          <SegmentedControl
            fullWidth
            value={variant}
            onChange={(v) => setVariant(v as TileVariant)}
            data={[
              { value: "tiles", label: "CHM" },
              { value: "tiles_nochm", label: "No CHM" },
            ]}
          />
        </div>

        {region && (
          <Text size="xs" c="dimmed">
            {region.nBuildings.toLocaleString()} buildings — one GeoJSON Feature per line (newline-delimited),
            same attributes (level_1..level_7, HEIGHT, BLDG_POP, …) shown on the map.
          </Text>
        )}

        {status === "error" && (
          <Alert color="red" icon={<IconAlertCircle size={14} />} title="Download failed">
            {error}
          </Alert>
        )}

        <Button
          leftSection={<IconDownload size={16} />}
          onClick={handleDownload}
          loading={status === "downloading"}
          disabled={!slug}
        >
          Download .geojsonl
        </Button>
      </Stack>
    </Modal>
  );
}
