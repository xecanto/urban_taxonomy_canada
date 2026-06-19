/// <reference types="vite/client" />

declare module "flatgeobuf/lib/mjs/geojson.js" {
  export function deserialize(
    input: Uint8Array | string,
    rect?: { minX: number; minY: number; maxX: number; maxY: number }
  ): AsyncGenerator<GeoJSON.Feature>;
}
