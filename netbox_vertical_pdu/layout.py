"""Framework-independent physical geometry. Offsets are always measured from the bottom."""
from decimal import Decimal

UNIT = 22
LANE_WIDTH = 150
RACK_WIDTH = 220
TOP = 40


def validate_dimensions(rack_height, offset, height, lane):
    values = tuple(Decimal(str(v)) for v in (rack_height, offset, height))
    if not all(v.is_finite() for v in values):
        raise ValueError("Dimensions must be finite.")
    rack_height, offset, height = values
    if offset < 0 or height <= 0 or offset + height > rack_height:
        raise ValueError("The device must fit inside the rack: offset >= 0, height > 0, offset + height <= rack height.")
    if not isinstance(lane, int) or not 1 <= lane <= 16:
        raise ValueError("Lane must be between 1 and 16.")


def overlaps(offset, height, other_offset, other_height):
    return offset < other_offset + other_height and other_offset < offset + height


def vertical_rect(rack_height, offset, height, unit_height=UNIT):
    return {"y": round(TOP + float(rack_height - offset - height) * unit_height, 4),
            "height": round(float(height) * unit_height, 4)}


def occupied(outlet):
    return bool(outlet.cable_id or outlet.mark_connected)


def build_scene(rack, placements, outlets, *, unit_height=UNIT, unit_width=RACK_WIDTH,
                legend_width=30, margin_width=15, border_width=2):
    """Accept only permission-filtered input; never query relations for extra objects."""
    left = max((p.lane for p in placements if p.side == "left"), default=0)
    right = max((p.lane for p in placements if p.side == "right"), default=0)
    # The native SVG includes its own unit legend, border and reservation margin.
    native_x = left * LANE_WIDTH + 10
    rack_x = native_x + legend_width + border_width
    native_width = unit_width + legend_width + margin_width + 2 * border_width
    right_x = native_x + native_width + 10
    scene = {"width": right_x + right * LANE_WIDTH + 10,
             "height": TOP + rack.u_height * unit_height + border_width + 30,
             "native_x": native_x, "native_y": TOP - border_width,
             "native_width": native_width, "unit_height": unit_height, "unit_width": unit_width,
             "rack_label_x": rack_x + unit_width / 2,
             "pdus": [], "side_labels": []}
    for side, count in (("left", left), ("right", right)):
        for lane in range(1, count + 1):
            x = native_x - lane * LANE_WIDTH if side == "left" else right_x + (lane - 1) * LANE_WIDTH
            label = side.title() if count == 1 else f"{side.title()} · lane {lane}"
            scene["side_labels"].append({"x": x + 65, "text": label})
    for p in placements:
        rect = vertical_rect(rack.u_height, p.offset_u, p.height_u, unit_height)
        x = native_x - p.lane * LANE_WIDTH if p.side == "left" else right_x + (p.lane - 1) * LANE_WIDTH
        visible_outlets = outlets.get(p.device_id, [])
        # A single vertical strip of readable socket symbols. Do not squeeze a
        # large outlet count into unreadable glyphs; disclose overflow below.
        available_height = max(0, rect["height"] - 64)
        shown = min(len(visible_outlets), int(available_height // 32))
        spacing = available_height / shown if shown else 0
        points = []
        for i, outlet in enumerate(visible_outlets[:shown]):
            kind = {"iec-60320-c13": "C13", "iec-60320-c19": "C19"}.get(getattr(outlet, "type", ""), "Outlet")
            points.append({"name": outlet.name, "short_name": outlet.name if len(outlet.name) <= 11 else outlet.name[:10] + "…",
                           "occupied": occupied(outlet), "kind": kind, "iec": kind in ("C13", "C19"),
                           "x": x + 14, "y": round(rect["y"] + 44 + (i + 0.5) * spacing - 12, 4)})
        scene["pdus"].append({"placement": p, "device": p.device, "x": x,
                              "text_x": x + 6, "text_y": rect["y"] + 18,
                              "total": len(visible_outlets), "used": sum(occupied(o) for o in visible_outlets),
                              "overflow": len(visible_outlets) - shown, "footer_y": rect["height"] - 9,
                              **rect, "outlets": points})
    return scene
