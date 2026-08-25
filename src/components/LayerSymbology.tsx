import { Select, Stack, Group, Text, Switch, ActionIcon, Tooltip, CopyButton } from "@mantine/core";
import { IconCopy, IconCheck } from "@tabler/icons-react";
import { RAMP_NAMES, generateColors } from "../utils/colors";
import type { RampName } from "../utils/colors";
import type { LayerSymbology as LS } from "../utils/types";

interface Props {
  label: string;
  symbology: LS;
  onChange: (s: LS) => void;
  layerType: "buildings";
  levelOptions: { value: string; label: string }[];
}

function buildStyleJSON(symbology: LS, layerType: string) {
  return JSON.stringify({
    layer: layerType,
    colorBy: symbology.level,
    colorRamp: symbology.ramp,
    opacity: symbology.opacity,
    visible: symbology.visible,
  }, null, 2);
}

export default function LayerSymbologyPanel({ label, symbology, onChange, layerType, levelOptions }: Props) {
  const styleJSON = buildStyleJSON(symbology, layerType);

  return (
    <Stack gap={4}>
      <Group justify="space-between">
        <Switch
          label={label}
          checked={symbology.visible}
          onChange={(e) => onChange({ ...symbology, visible: e.currentTarget.checked })}
          size="xs"
          fw={600}
        />
        <CopyButton value={styleJSON} timeout={2000}>
          {({ copied, copy }) => (
            <Tooltip label={copied ? "Copied!" : "Copy style JSON"} withArrow>
              <ActionIcon size="xs" variant="subtle" color={copied ? "teal" : "gray"} onClick={copy}>
                {copied ? <IconCheck size={12} /> : <IconCopy size={12} />}
              </ActionIcon>
            </Tooltip>
          )}
        </CopyButton>
      </Group>

      <Select
        label="Color by"
        data={levelOptions}
        value={symbology.level}
        onChange={(v) => v && onChange({ ...symbology, level: v })}
        size="xs"
        allowDeselect={false}
      />

      <Select
        label="Color ramp"
        data={RAMP_NAMES.map((r) => ({ value: r, label: r }))}
        value={symbology.ramp}
        onChange={(v) => v && onChange({ ...symbology, ramp: v })}
        size="xs"
        leftSection={
          <div style={{ display: "flex", gap: 0 }}>
            {generateColors(4, symbology.ramp as RampName).map((c, i) => (
              <div key={i} style={{ width: 5, height: 14, background: c }} />
            ))}
          </div>
        }
        renderOption={({ option }) => {
          const cols = generateColors(8, option.value as RampName);
          return (
            <Group gap={4}>
              <div style={{ display: "flex", gap: 0 }}>
                {cols.map((c, i) => (
                  <div key={i} style={{ width: 10, height: 14, background: c }} />
                ))}
              </div>
              <Text size="xs">{option.label}</Text>
            </Group>
          );
        }}
      />

      <Group gap="xs">
        <Text size="xs">Opacity:</Text>
        <input
          type="range" min={0} max={1} step={0.05}
          value={symbology.opacity}
          onChange={(e) => onChange({ ...symbology, opacity: Number(e.target.value) })}
          style={{ flex: 1 }}
        />
        <Text size="xs" w={30}>{Math.round(symbology.opacity * 100)}%</Text>
      </Group>
    </Stack>
  );
}
