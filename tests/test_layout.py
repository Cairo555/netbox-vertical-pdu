import importlib.util
from decimal import Decimal as D
from pathlib import Path
from types import SimpleNamespace as NS
import unittest

spec = importlib.util.spec_from_file_location("layout", Path(__file__).resolve().parents[1] / "netbox_vertical_pdu/layout.py")
layout = importlib.util.module_from_spec(spec)
spec.loader.exec_module(layout)


class LayoutTests(unittest.TestCase):
    def test_full_height(self):
        layout.validate_dimensions(42, 0, 42, 1)
        self.assertEqual(layout.vertical_rect(42, 0, 42), {"y": 40, "height": 924})

    def test_fractional_offset(self):
        self.assertEqual(layout.vertical_rect(D(42), D("1.5"), D("20.25")), {"y": 485.5, "height": 445.5})

    def test_invalid_dimensions(self):
        for args in [(42, -1, 20, 1), (42, 0, 0, 1), (42, 10, 33, 1), (42, 0, 20, 0), (42, 0, 20, 17), (42, 0, "NaN", 1), (42, 0, "Infinity", 1)]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                layout.validate_dimensions(*args)

    def test_adjacent_not_overlapping(self):
        self.assertFalse(layout.overlaps(D(0), D(20), D(20), D(22)))

    def test_overlap_and_containment(self):
        self.assertTrue(layout.overlaps(D(0), D(20), D(19), D(22)))
        self.assertTrue(layout.overlaps(D(0), D(42), D(10), D(2)))

    def test_outlet_states(self):
        for cable, marked, expected in [(None, False, False), (12, False, True), (None, True, True)]:
            self.assertEqual(layout.occupied(NS(cable_id=cable, mark_connected=marked)), expected)

    def scene(self, descending=False, placements=(), outlets=None, **kwargs):
        return layout.build_scene(NS(u_height=42, starting_unit=5, desc_units=descending), placements, outlets or {}, **kwargs)

    def test_empty_scene(self):
        scene = self.scene()
        self.assertEqual(scene["pdus"], [])
        self.assertEqual(scene["native_width"], 269)

    def test_native_geometry_respects_configured_dimensions(self):
        scene = self.scene(unit_height=35, unit_width=300)
        self.assertEqual(scene["native_width"], 349)
        self.assertEqual(scene["height"], 1542)

    def test_pdu_aligns_to_native_interior_in_both_numbering_directions(self):
        p = NS(side="left", lane=1, offset_u=D(0), height_u=D(42), device_id=1, device=NS(name="PDU"))
        for descending in (False, True):
            scene = self.scene(descending, placements=[p], unit_height=35)
            self.assertEqual(scene["pdus"][0]["y"], scene["native_y"] + 2)
            self.assertEqual(scene["pdus"][0]["height"], 42 * 35)

    def test_multiple_lanes_and_sides(self):
        ps = [NS(side=side, lane=lane, offset_u=D(0), height_u=D(42), device_id=i, device=NS(name=str(i)))
              for i, (side, lane) in enumerate([("left", 1), ("left", 2), ("right", 1), ("right", 2)])]
        scene = self.scene(placements=ps)
        self.assertEqual(len({p["x"] for p in scene["pdus"]}), 4)
        self.assertLess(scene["pdus"][1]["x"], scene["pdus"][0]["x"])
        self.assertGreater(scene["pdus"][3]["x"], scene["pdus"][2]["x"])

    def test_short_device_outlets_stay_inside(self):
        p = NS(side="left", lane=1, offset_u=D(0), height_u=D(1), device_id=1, device=NS(name="PDU"))
        scene = self.scene(placements=[p], outlets={1: [NS(name="1", cable_id=None, mark_connected=False)]})
        self.assertEqual(scene["pdus"][0]["outlets"], [])

    def test_stacked_pdus_share_x_and_do_not_overlap(self):
        ps = [NS(side="left", lane=1, offset_u=D(offset), height_u=D(20), device_id=i, device=NS(name=str(i)))
              for i, offset in enumerate((22, 0))]
        top, bottom = self.scene(placements=ps)["pdus"]
        self.assertEqual(top["x"], bottom["x"])
        self.assertLess(top["y"] + top["height"], bottom["y"])

    def test_outlets_follow_single_column_with_names_and_type(self):
        p = NS(side="left", lane=1, offset_u=D(0), height_u=D(24), device_id=1, device=NS(name="PDU"))
        outlets = [NS(name=f"Outlet-{i:02}", type="iec-60320-c13", cable_id=None, mark_connected=i == 2) for i in range(1, 13)]
        row = self.scene(placements=[p], outlets={1: outlets})["pdus"][0]
        points = row["outlets"]
        self.assertEqual(len(points), 12)
        self.assertEqual(len({point["x"] for point in points}), 1)
        self.assertTrue(all(a["y"] + 24 < b["y"] for a, b in zip(points, points[1:])))
        self.assertEqual(points[0]["name"], "Outlet-01")
        self.assertEqual(points[0]["kind"], "C13")
        self.assertEqual(row["used"], 1)

    def test_dense_outlets_are_disclosed_not_overlapped(self):
        p = NS(side="right", lane=1, offset_u=D(0), height_u=D(4), device_id=1, device=NS(name="short"))
        outlets = [NS(name=str(i), cable_id=None, mark_connected=False) for i in range(20)]
        row = self.scene(placements=[p], outlets={1: outlets})["pdus"][0]
        self.assertEqual(row["total"], len(row["outlets"]) + row["overflow"])
        self.assertGreater(row["overflow"], 0)
        self.assertTrue(all(point["y"] + 24 < row["y"] + row["height"] - 16 for point in row["outlets"]))


if __name__ == "__main__":
    unittest.main()
