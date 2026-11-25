"""Framework-independent physical geometry. Offsets are always measured from the bottom."""
from decimal import Decimal
import re

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


def outlet_sort_key(outlet):
    return tuple((1, int(part)) if part.isdigit() else (0, part.casefold())
                 for part in re.split(r"(\d+)", outlet.name))


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
    next_y = {}
    for p in sorted(placements, key=lambda p: (p.side, p.lane, -p.offset_u - p.height_u)):
        rect = vertical_rect(rack.u_height, p.offset_u, p.height_u, unit_height)
        x = native_x - p.lane * LANE_WIDTH if p.side == "left" else right_x + (p.lane - 1) * LANE_WIDTH
        visible_outlets = sorted(outlets.get(p.device_id, []), key=outlet_sort_key)
        # Keep the native rack scale. Expand only the adjacent outlet card,
        # and mark the actual mounting span separately when it differs.
        expanded = bool(visible_outlets) and rect["height"] < 64 + len(visible_outlets) * 32
        display_height = 80 + len(visible_outlets) * 32 if expanded else rect["height"]
        display_y = max(rect["y"], next_y.get((p.side, p.lane), TOP))
        next_y[p.side, p.lane] = display_y + display_height + 16
        scene["height"] = max(scene["height"], display_y + display_height + 30)
        header = 60 if expanded else 44
        available_height = max(0, display_height - header - 20)
        spacing = available_height / len(visible_outlets) if visible_outlets else 0
        points = []
        for i, outlet in enumerate(visible_outlets):
            kind = {"iec-60320-c13": "C13", "iec-60320-c19": "C19"}.get(getattr(outlet, "type", ""), "Outlet")
            points.append({"name": outlet.name, "short_name": outlet.name if len(outlet.name) <= 11 else outlet.name[:10] + "…",
                           "occupied": occupied(outlet), "kind": kind, "iec": kind in ("C13", "C19"),
                           "url": outlet.get_absolute_url(),
                           "x": x + 14, "y": round(display_y + header + (i + 0.5) * spacing - 12, 4)})
        marker = ""
        if expanded or display_y != rect["y"]:
            mx = x + 138 if p.side == "left" else x - 8
            edge = x + 130 if p.side == "left" else x
            top, bottom = rect["y"], rect["y"] + rect["height"]
            marker = (f"M{mx - 3} {top}h6 M{mx} {top}V{bottom} M{mx - 3} {bottom}h6 "
                      f"M{mx} {(top + bottom) / 2}L{edge} {display_y + display_height / 2}")
        scene["pdus"].append({"placement": p, "device": p.device, "x": x,
                              "total": len(visible_outlets), "used": sum(occupied(o) for o in visible_outlets),
                              "expanded": expanded, "marker": marker,
                              "physical_y": rect["y"], "physical_height": rect["height"],
                              "y": display_y, "height": display_height, "outlets": points})
    return scene
