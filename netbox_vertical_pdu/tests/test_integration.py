from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from dcim.models import Cable, Device, DeviceRole, DeviceType, Manufacturer, PowerOutlet, PowerPort, Rack, Site
from users.models import ObjectPermission

from netbox_vertical_pdu.models import VerticalPlacement


@override_settings(LOGIN_REQUIRED=True)
class IntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.site = Site.objects.create(name="Test", slug="vpdu-test")
        cls.rack = Rack.objects.create(name="Rack", site=cls.site, u_height=42)
        cls.other_rack = Rack.objects.create(name="Other", site=cls.site, u_height=42)
        m = Manufacturer.objects.create(name="Test", slug="vpdu-test")
        cls.dtype = DeviceType.objects.create(manufacturer=m, model="PDU", slug="vpdu-pdu", u_height=0)
        cls.role = DeviceRole.objects.create(name="PDU", slug="vpdu-pdu", color="ff0000")
        cls.device = cls.make_device("PDU-visible")
        cls.hidden_device = cls.make_device("PDU-secret")
        cls.placement = VerticalPlacement.objects.create(device=cls.device, rack=cls.rack, height_u=42)
        cls.hidden_placement = VerticalPlacement.objects.create(device=cls.hidden_device, rack=cls.rack, lane=2, height_u=42)
        cls.free = PowerOutlet.objects.create(device=cls.device, name="Outlet-free", type="iec-60320-c13")
        cls.used = PowerOutlet.objects.create(device=cls.device, name="Outlet-used", type="iec-60320-c13", mark_connected=True)
        cls.secret = PowerOutlet.objects.create(device=cls.device, name="Outlet-secret", type="iec-60320-c13")
        cls.admin = get_user_model().objects.create_superuser(username="vpdu-admin", password="test-only-password")
        cls.user = get_user_model().objects.create_user(username="vpdu-user", password="test-only-password")

    @classmethod
    def make_device(cls, name):
        return Device.objects.create(name=name, site=cls.site, rack=cls.rack, device_type=cls.dtype, role=cls.role)

    def grant(self, model, actions, constraints=None):
        perm = ObjectPermission.objects.create(name=f"test-{model.__name__}", actions=actions, constraints=constraints)
        perm.object_types.add(ContentType.objects.get_for_model(model))
        perm.users.add(self.user)

    def viewer(self):
        self.grant(Rack, ["view"], {"pk": self.rack.pk})
        self.grant(Device, ["view"], {"pk": self.device.pk})
        self.grant(VerticalPlacement, ["view"], {"pk": self.placement.pk})
        self.grant(PowerOutlet, ["view"], {"pk__in": [self.free.pk, self.used.pk]})
        self.client.force_login(self.user)

    def url(self, action="view", pk=None, rack=None):
        rack = rack or self.rack
        if action == "view":
            return reverse("dcim:rack_vertical_pdu", args=[rack.pk])
        kwargs = {"rack_pk": rack.pk}
        if pk is not None:
            kwargs["pk"] = pk
        return reverse(f"plugins:netbox_vertical_pdu:verticalplacement_{action}", kwargs=kwargs)

    def payload(self, **kwargs):
        return {"device": self.device.pk, "face": "rear", "side": "left", "lane": 1, "offset_u": "0", "height_u": "42", **kwargs}

    def test_render_with_admin_and_tab(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.url())
        self.assertContains(response, "Enhanced Rack Elevation")
        self.assertContains(response, "PDU-visible")
        self.assertContains(response, self.device.get_absolute_url())

    def test_event_serialization(self):
        from extras.events import serialize_for_event
        data = serialize_for_event(self.placement)
        self.assertEqual(data["device"], self.device.pk)
        self.assertEqual(data["rack"], self.rack.pk)
        self.assertEqual(data["height_u"], Decimal("42.00"))

    def test_permissions_hide_devices_and_outlets(self):
        self.viewer()
        response = self.client.get(self.url())
        self.assertContains(response, "Outlet-free")
        self.assertContains(response, "Outlet-used")
        self.assertNotContains(response, "Outlet-secret")
        self.assertNotContains(response, "PDU-secret")
        self.assertEqual(response.context["rows"][0]["free"], 1)
        self.assertEqual(response.context["rows"][0]["used"], 1)

    def test_rack_constraint(self):
        self.viewer()
        self.assertEqual(self.client.get(self.url(rack=self.other_rack)).status_code, 404)

    def test_device_permission_independent_of_placement_permission(self):
        self.viewer()
        self.grant(VerticalPlacement, ["view"])
        self.assertNotContains(self.client.get(self.url()), "PDU-secret")

    def test_placement_permission_independent_of_device_permission(self):
        self.viewer()
        self.grant(Device, ["view"])
        self.assertNotContains(self.client.get(self.url()), "PDU-secret")

    def test_no_outlet_permission_does_not_expose_counts(self):
        self.grant(Rack, ["view"])
        self.grant(Device, ["view"])
        self.grant(VerticalPlacement, ["view"])
        self.client.force_login(self.user)
        response = self.client.get(self.url())
        self.assertNotContains(response, "Outlet-used")
        self.assertTrue(all(row["used"] == row["free"] == 0 for row in response.context["rows"]))

    def test_add_constraint_rollback(self):
        self.viewer()
        self.grant(VerticalPlacement, ["add"], {"side": "left"})
        self.placement.delete()
        response = self.client.post(self.url("add"), self.payload(side="right"))
        self.assertEqual(response.status_code, 403)
        self.assertFalse(VerticalPlacement.objects.filter(device=self.device).exists())

    def test_hidden_device_cannot_be_selected(self):
        self.viewer()
        self.grant(VerticalPlacement, ["change"])
        response = self.client.post(self.url("edit", self.placement.pk), self.payload(device=self.hidden_device.pk))
        self.assertEqual(response.status_code, 200)
        self.assertIn("device", response.context["form"].errors)
        self.placement.refresh_from_db()
        self.assertEqual(self.placement.device_id, self.device.pk)

    def test_anonymous_redirect(self):
        self.assertEqual(self.client.get(self.url()).status_code, 302)

    def test_viewer_cannot_modify(self):
        self.viewer()
        for action in ("edit", "delete"):
            self.assertEqual(self.client.post(self.url(action, self.placement.pk), self.payload()).status_code, 403)
        self.assertEqual(self.client.post(self.url("add"), self.payload()).status_code, 403)

    def test_edit_and_delete(self):
        self.client.force_login(self.admin)
        response = self.client.post(self.url("edit", self.placement.pk), self.payload(height_u="20", offset_u="1.5"))
        self.assertEqual(response.status_code, 302)
        self.placement.refresh_from_db()
        self.assertEqual(self.placement.offset_u, Decimal("1.5"))
        self.assertEqual(self.client.get(self.url("delete", self.placement.pk)).status_code, 200)
        self.assertTrue(VerticalPlacement.objects.filter(pk=self.placement.pk).exists())
        self.assertEqual(self.client.post(self.url("delete", self.placement.pk)).status_code, 302)
        self.assertTrue(Device.objects.filter(pk=self.device.pk).exists())
        self.assertTrue(PowerOutlet.objects.filter(pk=self.free.pk).exists())

    def test_create_and_face_selection(self):
        self.client.force_login(self.admin)
        device = self.make_device("new-front-pdu")
        self.assertEqual(self.client.post(self.url("add"), self.payload(device=device.pk, face="front")).status_code, 302)
        self.assertNotContains(self.client.get(self.url()), "new-front-pdu")
        self.assertContains(self.client.get(self.url() + "?face=front"), "new-front-pdu")

    def test_overlap_rejected(self):
        p = VerticalPlacement(device=self.make_device("overlap"), rack=self.rack, height_u=2, offset_u=20)
        with self.assertRaises(ValidationError):
            p.full_clean()

    def test_wrong_rack_and_nonzero_device_rejected(self):
        p = VerticalPlacement(device=self.device, rack=self.other_rack, height_u=42)
        with self.assertRaises(ValidationError):
            p.full_clean()
        self.dtype.u_height = 1
        self.dtype.save()
        self.placement.refresh_from_db()
        with self.assertRaises(ValidationError):
            self.placement.full_clean()

    def test_stale_placement_not_drawn(self):
        self.client.force_login(self.admin)
        self.device.rack = self.other_rack
        self.device.save()
        response = self.client.get(self.url())
        self.assertContains(response, "Placement no longer matches")
        self.assertNotIn(self.device.pk, [p["device"].pk for p in response.context["scene"]["pdus"]])

    def test_post_change_constraint_rollback(self):
        self.viewer()
        self.grant(VerticalPlacement, ["change"], {"side": "left"})
        response = self.client.post(self.url("edit", self.placement.pk), self.payload(side="right"))
        self.assertEqual(response.status_code, 403)
        self.placement.refresh_from_db()
        self.assertEqual(self.placement.side, "left")

    def test_csrf_required(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        self.assertEqual(client.post(self.url("delete", self.placement.pk)).status_code, 403)

    @override_settings(LANGUAGE_CODE="nl")
    def test_svg_uses_decimal_point_and_escapes_names(self):
        self.client.force_login(self.admin)
        self.device.name = '<script>alert("x")</script>'
        self.device.save()
        self.placement.height_u = Decimal("20.01")
        self.placement.save()
        response = self.client.get(self.url())
        self.assertContains(response, 'height="440.22"')
        self.assertNotContains(response, '<script>alert("x")</script>')

    def test_native_renderer_requested_on_selected_face(self):
        self.client.force_login(self.admin)
        for face in ("front", "rear"):
            response = self.client.get(self.url() + f"?face={face}")
            endpoint = reverse("dcim-api:rack-elevation", args=[self.rack.pk])
            self.assertContains(response, f'hx-get="{endpoint}?face={face}&amp;render=svg')
            self.assertContains(response, 'class="vpdu-native rack_elevation"')
            self.assertNotContains(response, 'class="vpdu-rack"')

    def test_native_endpoint_respects_device_permissions(self):
        dtype = DeviceType.objects.create(manufacturer=self.dtype.manufacturer, model="server", slug="server", u_height=2)
        Device.objects.create(name="Hidden server", site=self.site, rack=self.rack,
                              device_type=dtype, role=self.role, position=1, face="front")
        self.viewer()
        endpoint = reverse("dcim-api:rack-elevation", args=[self.rack.pk])
        response = self.client.get(endpoint + "?face=front&render=svg")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Hidden server")
        self.assertContains(response, 'class="blocked"')

    def test_short_pdu_renders_every_outlet_with_native_links(self):
        self.client.force_login(self.admin)
        device = self.make_device("Short-PDU")
        VerticalPlacement.objects.create(device=device, rack=self.rack, height_u=4, offset_u=18, lane=3)
        outlets = [PowerOutlet.objects.create(device=device, name=str(i), type="iec-60320-c13") for i in reversed(range(7))]
        response = self.client.get(self.url())
        row = next(p for p in response.context["scene"]["pdus"] if p["device"].pk == device.pk)
        self.assertEqual([o["name"] for o in row["outlets"]], [str(i) for i in range(7)])
        self.assertEqual(row["physical_height"], 88)
        self.assertGreater(row["height"], row["physical_height"])
        for outlet in outlets:
            self.assertContains(response, f'href="{outlet.get_absolute_url()}"')
        self.assertNotContains(response, "more in table")

    def connected_server(self):
        dtype = DeviceType.objects.create(manufacturer=self.dtype.manufacturer, model="Server", slug="server",
                                          u_height=2, is_full_depth=True)
        device = Device.objects.create(name="Server-019", site=self.site, rack=self.rack,
                                       device_type=dtype, role=self.role, position=25, face="front")
        port = PowerPort.objects.create(device=device, name="PSU-1")
        cable = Cable(a_terminations=[self.free], b_terminations=[port], status="connected")
        cable.full_clean()
        cable.save()
        return device, port, cable

    def test_real_connection_is_drawn_and_linked_to_cable(self):
        device, port, cable = self.connected_server()
        self.client.force_login(self.admin)
        response = self.client.get(self.url())
        lines = response.context["scene"]["connections"]
        self.assertEqual(len(lines), 1)
        self.assertIn("Server-019 / PSU-1", lines[0]["label"])
        self.assertEqual(lines[0]["url"], cable.get_absolute_url())
        self.assertEqual(lines[0]["outlet_id"], self.free.pk)
        self.assertEqual(lines[0]["device_url"], device.get_absolute_url())
        self.assertContains(response, f'data-device-url="{device.get_absolute_url()}"')
        self.assertContains(response, 'class="vpdu-connection"')

    def test_cable_permission_required_for_connection(self):
        device, port, cable = self.connected_server()
        self.viewer()
        self.grant(Device, ["view"], {"pk": device.pk})
        self.grant(PowerPort, ["view"], {"pk": port.pk})
        self.assertEqual(self.client.get(self.url()).context["scene"]["connections"], [])
        self.grant(Cable, ["view"], {"pk": cable.pk})
        self.assertEqual(len(self.client.get(self.url()).context["scene"]["connections"]), 1)

    def test_hidden_power_port_has_no_connection_line(self):
        device, port, cable = self.connected_server()
        self.viewer()
        self.grant(Device, ["view"], {"pk": device.pk})
        self.grant(Cable, ["view"], {"pk": cable.pk})
        self.assertEqual(self.client.get(self.url()).context["scene"]["connections"], [])

    def test_hidden_destination_device_has_no_connection_line(self):
        device, port, cable = self.connected_server()
        self.viewer()
        self.grant(PowerPort, ["view"], {"pk": port.pk})
        self.grant(Cable, ["view"], {"pk": cable.pk})
        self.assertEqual(self.client.get(self.url()).context["scene"]["connections"], [])

    def test_hidden_outlet_has_no_connection_line(self):
        device, port, cable = self.connected_server()
        for model in (Rack, Device, VerticalPlacement, PowerPort, Cable):
            self.grant(model, ["view"])
        self.grant(PowerOutlet, ["view"], {"pk": self.used.pk})
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.url()).context["scene"]["connections"], [])

    def test_other_rack_or_unrendered_face_has_no_line(self):
        device, port, cable = self.connected_server()
        self.client.force_login(self.admin)
        device.device_type.is_full_depth = False
        device.device_type.save()
        self.assertEqual(self.client.get(self.url()).context["scene"]["connections"], [])
        device.device_type.is_full_depth = True
        device.device_type.save()
        device.rack = self.other_rack
        device.save()
        self.assertEqual(self.client.get(self.url()).context["scene"]["connections"], [])

    def test_mark_connected_does_not_invent_cable_line(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.url()).context["scene"]["connections"], [])
