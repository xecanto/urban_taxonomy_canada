# all map layouts
import arcpy
import os
import re

MAP_NAME = "Map7"
LAYOUT_NAME = "City Export"
MAP_FRAME_NAME = "City Map Frame"

BUILDING_LAYER_NAME = "main.morphotopes"
BOUNDARY_LAYER_NAME = "main.boundary_unbuffered"
BUFFERED_BOUNDARY_LAYER_NAME = "main.boundary_buffered"
INCLUDE_BOUNDARY = False

CLASS_FIELD = "level_3"

OUTPUT_DIR = r"C:\urban-form\outputs\maps"

# Choose: "PNG" or "PDF"
EXPORT_FORMAT = "PNG"

DPI = 400
EXTENT_PADDING = 1.05

PAGE_LONG_SIDE_MM = 500.0
MIN_SHORT_SIDE_MM = 150.0
MAX_SHORT_SIDE_MM = 500.0

PAGE_MARGIN_MM = 0.0

# Buffered boundary appearance
BOUNDARY_OUTLINE_COLOR = [80, 80, 80, 100]
BOUNDARY_OUTLINE_WIDTH = 1.5
BOUNDARY_FILL_COLOR = [255, 255, 255, 0]

PALETTE = {
    1: [244, 166, 166, 100],
    2: [157, 219, 229, 100],
    3: [233, 163, 209, 100],
    4: [245, 194, 139, 100],
    5: [243, 223, 162, 100],
    6: [168, 230, 176, 100],
    7: [201, 181, 232, 100],
    8: [169, 190, 234, 100],
}


def safe_filename(value):
    value = re.sub(r'[<>:"/\\|?*]', "_", value)
    value = value.strip().strip(".")
    return value or "map"


def find_child_layer(group_layer, layer_name):
    for layer in group_layer.listLayers():
        if layer.name == layer_name:
            return layer

    return None


def set_layer_visibility(group_layers, active_group):
    for group_layer in group_layers:
        group_layer.visible = group_layer == active_group

        for layer in group_layer.listLayers():
            layer.visible = False

        if group_layer != active_group:
            continue

        building_layer = find_child_layer(
            group_layer,
            BUILDING_LAYER_NAME,
        )

        buffered_boundary_layer = find_child_layer(
            group_layer,
            BUFFERED_BOUNDARY_LAYER_NAME,
        )

        if building_layer:
            building_layer.visible = True

        if INCLUDE_BOUNDARY and buffered_boundary_layer:
            buffered_boundary_layer.visible = True


def remove_all_polygon_outlines(layer):
    cim_layer = layer.getDefinition("V3")
    renderer = cim_layer.renderer

    if not hasattr(renderer, "groups"):
        return

    for group in renderer.groups:
        for cim_class in group.classes:
            if not cim_class.symbol:
                continue

            if not cim_class.symbol.symbol:
                continue

            symbol_layers = cim_class.symbol.symbol.symbolLayers

            if not symbol_layers:
                continue

            cim_class.symbol.symbol.symbolLayers = [
                symbol_layer
                for symbol_layer in symbol_layers
                if symbol_layer.__class__.__name__ != "CIMSolidStroke"
            ]

    layer.setDefinition(cim_layer)


def apply_building_symbology(layer):
    sym = layer.symbology

    if not hasattr(sym, "renderer"):
        raise RuntimeError(
            f"Layer does not support symbology: {layer.longName}"
        )

    sym.updateRenderer("UniqueValueRenderer")
    sym.renderer.fields = [CLASS_FIELD]
    sym.renderer.useDefaultSymbol = False

    for group in sym.renderer.groups:
        for item in group.items:
            if not item.values:
                continue

            raw_value = item.values[0][0]

            try:
                class_value = int(raw_value)
            except (TypeError, ValueError):
                continue

            if class_value not in PALETTE:
                continue

            item.symbol.color = {
                "RGB": PALETTE[class_value],
            }

            item.label = str(class_value)

    layer.symbology = sym
    remove_all_polygon_outlines(layer)


def apply_boundary_symbology(layer):
    sym = layer.symbology

    if not hasattr(sym, "renderer"):
        raise RuntimeError(
            f"Boundary layer does not support symbology: {layer.longName}"
        )

    sym.updateRenderer("SimpleRenderer")

    symbol = sym.renderer.symbol

    symbol.color = {
        "RGB": BOUNDARY_FILL_COLOR,
    }

    symbol.outlineColor = {
        "RGB": BOUNDARY_OUTLINE_COLOR,
    }

    symbol.outlineWidth = BOUNDARY_OUTLINE_WIDTH

    layer.symbology = sym


def get_padded_extent(map_frame, boundary_layer):
    extent = map_frame.getLayerExtent(
        boundary_layer,
        False,
        False,
    )

    width = extent.XMax - extent.XMin
    height = extent.YMax - extent.YMin

    if width <= 0 or height <= 0:
        raise RuntimeError(
            f"Invalid boundary extent for {boundary_layer.longName}"
        )

    center_x = (extent.XMin + extent.XMax) / 2.0
    center_y = (extent.YMin + extent.YMax) / 2.0

    padded_width = width * EXTENT_PADDING
    padded_height = height * EXTENT_PADDING

    return arcpy.Extent(
        center_x - padded_width / 2.0,
        center_y - padded_height / 2.0,
        center_x + padded_width / 2.0,
        center_y + padded_height / 2.0,
    )


def calculate_page_size(extent):
    width = extent.XMax - extent.XMin
    height = extent.YMax - extent.YMin

    aspect_ratio = width / height

    if aspect_ratio >= 1.0:
        page_width = PAGE_LONG_SIDE_MM
        page_height = PAGE_LONG_SIDE_MM / aspect_ratio

        if page_height < MIN_SHORT_SIDE_MM:
            page_height = MIN_SHORT_SIDE_MM

        if page_height > MAX_SHORT_SIDE_MM:
            page_height = MAX_SHORT_SIDE_MM
    else:
        page_height = PAGE_LONG_SIDE_MM
        page_width = PAGE_LONG_SIDE_MM * aspect_ratio

        if page_width < MIN_SHORT_SIDE_MM:
            page_width = MIN_SHORT_SIDE_MM

        if page_width > MAX_SHORT_SIDE_MM:
            page_width = MAX_SHORT_SIDE_MM

    return page_width, page_height


def resize_layout(layout, map_frame, page_width_mm, page_height_mm):
    layout.changePageSize(
        page_width_mm,
        page_height_mm,
        False,
    )

    margin = PAGE_MARGIN_MM

    map_frame.elementPositionX = margin
    map_frame.elementPositionY = margin

    map_frame.elementWidth = page_width_mm - (margin * 2)
    map_frame.elementHeight = page_height_mm - (margin * 2)


def configure_pdf(output_path):
    export_format = arcpy.mp.CreateExportFormat(
        "PDF",
        output_path,
    )

    export_format.resolution = DPI
    export_format.outputAsImage = False
    export_format.embedFonts = True
    export_format.georefInfo = True
    export_format.compressVectorGraphics = True

    try:
        export_format.imageCompression = "ADAPTIVE"
    except Exception:
        pass

    try:
        export_format.jpegCompressionQuality = 100
    except Exception:
        pass

    try:
        export_format.layersAttributes = "LAYERS_ONLY"
    except Exception:
        pass

    return export_format


def configure_png(output_path):
    export_format = arcpy.mp.CreateExportFormat(
        "PNG",
        output_path,
    )

    export_format.resolution = DPI

    try:
        export_format.colorMode = "32-BIT_WITH_ALPHA"
    except Exception:
        pass

    return export_format


def configure_export(output_path):
    export_type = EXPORT_FORMAT.upper()

    if export_type == "PDF":
        return configure_pdf(output_path)

    if export_type == "PNG":
        return configure_png(output_path)

    raise ValueError(
        f'Unsupported EXPORT_FORMAT "{EXPORT_FORMAT}". '
        'Use "PDF" or "PNG".'
    )


def main():
    os.makedirs(
        OUTPUT_DIR,
        exist_ok=True,
    )

    export_type = EXPORT_FORMAT.upper()

    if export_type not in {"PDF", "PNG"}:
        raise ValueError(
            f'Unsupported EXPORT_FORMAT "{EXPORT_FORMAT}". '
            'Use "PDF" or "PNG".'
        )

    file_extension = export_type.lower()

    aprx = arcpy.mp.ArcGISProject("CURRENT")

    maps = aprx.listMaps(MAP_NAME)

    if not maps:
        raise RuntimeError(
            f'Map "{MAP_NAME}" was not found.'
        )

    map_obj = maps[0]

    layouts = aprx.listLayouts(LAYOUT_NAME)

    if not layouts:
        raise RuntimeError(
            f'Layout "{LAYOUT_NAME}" was not found.'
        )

    layout = layouts[0]

    map_frames = layout.listElements(
        "MAPFRAME_ELEMENT",
        MAP_FRAME_NAME,
    )

    if not map_frames:
        raise RuntimeError(
            f'Map frame "{MAP_FRAME_NAME}" was not found.'
        )

    map_frame = map_frames[0]

    group_layers = [
        layer
        for layer in map_obj.listLayers()
        if layer.isGroupLayer
    ]

    if not group_layers:
        raise RuntimeError(
            "No city group layers were found."
        )

    print("=" * 70)
    print(f"CITY MAP {export_type} EXPORT")
    print("=" * 70)
    print(f"Cities found: {len(group_layers)}")
    print(f"Format: {export_type}")
    print(f"Resolution: {DPI} DPI")

    exported = []
    skipped = []

    for index, group_layer in enumerate(
        group_layers,
        start=1,
    ):
        city_name = group_layer.name

        print()
        print(
            f"[{index}/{len(group_layers)}] "
            f"{city_name}"
        )

        building_layer = find_child_layer(
            group_layer,
            BUILDING_LAYER_NAME,
        )

        boundary_layer = find_child_layer(
            group_layer,
            BOUNDARY_LAYER_NAME,
        )

        buffered_boundary_layer = find_child_layer(
            group_layer,
            BUFFERED_BOUNDARY_LAYER_NAME,
        )

        if building_layer is None:
            print(
                f"  SKIPPED: "
                f"{BUILDING_LAYER_NAME} not found."
            )
            skipped.append(city_name)
            continue

        if boundary_layer is None:
            print(
                f"  SKIPPED: "
                f"{BOUNDARY_LAYER_NAME} not found."
            )
            skipped.append(city_name)
            continue

        if INCLUDE_BOUNDARY and buffered_boundary_layer is None:
            print(
                f"  WARNING: "
                f"{BUFFERED_BOUNDARY_LAYER_NAME} not found. "
                "Exporting without boundary."
            )

        print("  Applying building symbology...")

        apply_building_symbology(
            building_layer,
        )
        if INCLUDE_BOUNDARY and buffered_boundary_layer:
            print("  Applying boundary outline...")

            apply_boundary_symbology(
                buffered_boundary_layer,
            )
        else:
            print("  Boundary outline disabled.")

        apply_boundary_symbology(
            buffered_boundary_layer,
        )

        print("  Setting layer visibility...")

        set_layer_visibility(
            group_layers,
            group_layer,
        )

        print("  Calculating boundary extent...")

        extent = get_padded_extent(
            map_frame,
            boundary_layer,
        )

        page_width, page_height = calculate_page_size(
            extent,
        )

        print(
            f"  Page: "
            f"{page_width:.1f} x "
            f"{page_height:.1f} mm"
        )

        resize_layout(
            layout,
            map_frame,
            page_width,
            page_height,
        )

        map_frame.camera.setExtent(
            extent,
        )

        output_name = (
            f"{safe_filename(city_name)}."
            f"{file_extension}"
        )

        output_path = os.path.join(
            OUTPUT_DIR,
            output_name,
        )

        print(
            f"  Exporting {export_type} "
            f"at {DPI} DPI..."
        )

        export_format = configure_export(
            output_path,
        )

        layout.export(
            export_format,
        )

        exported.append(
            output_path,
        )

        print(
            f"  DONE: {output_path}"
        )

    aprx.save()

    print()
    print("=" * 70)
    print("EXPORT FINISHED")
    print("=" * 70)

    print(f"Format: {export_type}")
    print(f"Exported: {len(exported)}")
    print(f"Skipped: {len(skipped)}")

    if skipped:
        print()
        print("Skipped cities:")

        for city_name in skipped:
            print(
                f"  - {city_name}"
            )

    print()
    print(
        f"Output folder: {OUTPUT_DIR}"
    )


main()