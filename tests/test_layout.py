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
        self.assertEqual(layout.vertical_rect(42, 0, 42), {"y": 40, "height": 1176})

    def test_fractional_offset(self):
        self.assertEqual(layout.vertical_rect(D(42), D("1.5"), D("20.25")), {"y": 607, "height": 567})

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

    def scene(self, descending=False, placements=(), devices=(), outlets=None):
        return layout.build_scene(NS(u_height=42, starting_unit=5, desc_units=descending), placements, devices, outlets or {})

    def test_empty_scene(self):
        scene = self.scene()
        self.assertEqual(scene["pdus"], [])
        self.assertEqual(scene["units"][0]["label"], 46)

    def test_descending_labels(self):
        self.assertEqual(self.scene(True)["units"][0]["label"], 5)

    def test_regular_device_coordinates(self):
        device = NS(position=D(5), device_type=NS(u_height=D(2)))
        self.assertEqual(self.scene(devices=[device])["devices"][0]["y"], 1160)
        self.assertEqual(self.scene(True, devices=[device])["devices"][0]["y"], 40)

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


if __name__ == "__main__":
    unittest.main()
