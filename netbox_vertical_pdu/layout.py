"""Framework-independent physical geometry. Offsets are always measured from the bottom."""
from decimal import Decimal

UNIT = 28
LANE_WIDTH = 150
RACK_WIDTH = 430
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


def vertical_rect(rack_height, offset, height):
    return {"y": round(TOP + float(rack_height - offset - height) * UNIT, 4),
            "height": round(float(height) * UNIT, 4)}


def occupied(outlet):
    return bool(outlet.cable_id or outlet.mark_connected)


def build_scene(rack, placements, devices, outlets):
    """Accept only permission-filtered input; never query relations for extra objects."""
    left = max((p.lane for p in placements if p.side == "left"), default=0)
    right = max((p.lane for p in placements if p.side == "right"), default=0)
    rack_x = left * LANE_WIDTH + 30
    scene = {"width": rack_x + RACK_WIDTH + right * LANE_WIDTH + 30,
             "height": TOP + rack.u_height * UNIT + 30, "rack_x": rack_x,
             "rack_width": RACK_WIDTH, "rack_height": rack.u_height * UNIT,
             "rack_label_x": rack_x + RACK_WIDTH / 2,
             "pdus": [], "devices": [], "units": [], "side_labels": []}
    for side, count in (("left", left), ("right", right)):
        for lane in range(1, count + 1):
            x = rack_x - lane * LANE_WIDTH if side == "left" else rack_x + RACK_WIDTH + (lane - 1) * LANE_WIDTH + 10
            label = side.title() if count == 1 else f"{side.title()} · lane {lane}"
            scene["side_labels"].append({"x": x + 65, "text": label})
    for i in range(rack.u_height):
        label = rack.starting_unit + (i if rack.desc_units else rack.u_height - i - 1)
        scene["units"].append({"label": label, "y": TOP + i * UNIT, "text_y": TOP + i * UNIT + 20})
    for device in devices:
        h = device.device_type.u_height
        offset = device.position - rack.starting_unit
        # NetBox positions identify the lowest-numbered occupied unit, including descending racks.
        if rack.desc_units:
            offset = rack.u_height - offset - h
        rect = vertical_rect(rack.u_height, offset, h)
        scene["devices"].append({"device": device, "x": rack_x + 40,
                                 "y": rect["y"], "height": rect["height"],
                                 "text_y": rect["y"] + min(20, rect["height"] - 2)})
    for p in placements:
        rect = vertical_rect(rack.u_height, p.offset_u, p.height_u)
        x = rack_x - p.lane * LANE_WIDTH if p.side == "left" else rack_x + RACK_WIDTH + (p.lane - 1) * LANE_WIDTH + 10
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
