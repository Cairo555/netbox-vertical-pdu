"""Run through manage.py shell, only in the empty disposable smoke-test stack."""
import json
import os
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.urls import reverse
from dcim.models import (
    Cable, Device, DeviceRole, DeviceType, Manufacturer, PowerOutlet, PowerPort, Rack, Site,
)
from users.models import ObjectPermission
from netbox_vertical_pdu.models import VerticalPlacement

if os.environ.get("VPDU_SMOKE_TEST") != "1" or Site.objects.exists():
    raise RuntimeError("Seed requires VPDU_SMOKE_TEST=1 and an empty disposable database.")

with transaction.atomic():
    site = Site.objects.create(name="Plugin test lab", slug="plugin-test-lab")
    rack = Rack.objects.create(name="D07-R01", site=site, u_height=42)
    descending = Rack.objects.create(name="Descending rack", site=site, u_height=18, starting_unit=11, desc_units=True)
    manufacturer = Manufacturer.objects.create(name="Test lab", slug="test-lab")
    role = DeviceRole.objects.create(name="Lab equipment", slug="lab-equipment", color="008080")
    vertical_type = DeviceType.objects.create(manufacturer=manufacturer, model="Vertical PDU", slug="vertical-pdu", u_height=0)
    server_type = DeviceType.objects.create(manufacturer=manufacturer, model="Server", slug="server", u_height=2, is_full_depth=True)
    half_type = DeviceType.objects.create(manufacturer=manufacturer, model="Half-U", slug="half-u", u_height=Decimal("0.5"), is_full_depth=False)

    def device(name, dtype=vertical_type, target=rack, **kwargs):
        return Device.objects.create(name=name, device_type=dtype, site=site, rack=target, role=role, **kwargs)

    compute = device("Server-019", server_type, position=25, face="front")
    device("Compute-02", server_type, position=10, face="front")
    device("Edge-switch", server_type, position=36, face="rear")
    device("Half-U-shelf", half_type, position=Decimal("20.5"), face="rear")
    pdus = []
    placements = []
    first_outlets = []
    for name, side, lane, height, offset in (
        ("PDU-L1", "left", 1, 20, 22),
        ("PDU-L2", "left", 1, 20, 0),
        ("PDU-R1", "right", 1, 20, 22),
        ("PDU-R2", "right", 1, 20, 0),
    ):
        pdu = device(name)
        pdus.append(pdu)
        p = VerticalPlacement(device=pdu, rack=rack, side=side, lane=lane, height_u=height, offset_u=offset)
        p.full_clean()
        p.save()
        placements.append(p)
        outlets = [PowerOutlet.objects.create(device=pdu, name=f"Outlet-{i:02}", type="iec-60320-c13", mark_connected=i in ((4,) if name == "PDU-L1" else (2, 4))) for i in range(1, 13)]
        if name == "PDU-R1":
            right_outlets = outlets
        if name == "PDU-L1":
            first_outlets = outlets
            port = PowerPort.objects.create(device=compute, name="PSU-1", type="iec-60320-c14")
            cable = Cable(a_terminations=[outlets[0]], b_terminations=[port], status="connected")
            cable.full_clean()
            cable.save()
            outlets[0].refresh_from_db()
            assert outlets[0].cable_id == cable.pk
    PowerOutlet.objects.create(device=pdus[0], name="Outlet-13", type="iec-60320-c13")
    second_server = device("Server-018", server_type, position=22, face="front")
    second_port = PowerPort.objects.create(device=second_server, name="PSU-1", type="iec-60320-c14")
    second_cable = Cable(a_terminations=[first_outlets[1]], b_terminations=[second_port], status="connected")
    second_cable.full_clean()
    second_cable.save()
    redundant_port = PowerPort.objects.create(device=compute, name="PSU-2", type="iec-60320-c14")
    redundant_cable = Cable(a_terminations=[right_outlets[0]], b_terminations=[redundant_port], status="connected")
    redundant_cable.full_clean()
    redundant_cable.save()
    front = device("PDU-F1")
    VerticalPlacement.objects.create(device=front, rack=rack, face="front", side="right", height_u=4, offset_u=18)
    front_outlets = [PowerOutlet.objects.create(device=front, name=str(i), type="iec-60320-c13") for i in range(7)]
    spare = device("PDU-spare")
    device("Top-server", server_type, target=descending, position=11, face="front")
    device("Bottom-server", server_type, target=descending, position=27, face="front")
    desc_pdu = device("PDU-descending", target=descending)
    VerticalPlacement.objects.create(device=desc_pdu, rack=descending, face="front", height_u=16, offset_u=1)

    get_user_model().objects.create_superuser(username="smoke-admin", password="Disposable-admin-42!")
    reader = get_user_model().objects.create_user(username="smoke-reader", password="Disposable-reader-42!")
    for model, constraints in (
        (Rack, {"pk": rack.pk}), (Device, {"pk": pdus[0].pk}),
        (VerticalPlacement, {"pk": placements[0].pk}),
        (PowerOutlet, {"pk__in": [first_outlets[0].pk, first_outlets[1].pk]}),
    ):
        permission = ObjectPermission.objects.create(name=f"smoke-{model.__name__}", actions=["view"], constraints=constraints)
        permission.object_types.add(ContentType.objects.get_for_model(model))
        permission.users.add(reader)

manifest = {
    "rack": rack.get_absolute_url(),
    "elevation": reverse("dcim:rack_vertical_pdu", args=[rack.pk]),
    "descending": reverse("dcim:rack_vertical_pdu", args=[descending.pk]) + "?face=front",
    "spare_id": spare.pk,
    "spare_url": spare.get_absolute_url(),
    "pdu_url": pdus[0].get_absolute_url(),
    "front_outlet_url": front_outlets[0].get_absolute_url(),
    "cable_url": cable.get_absolute_url(),
    "outlet1_id": first_outlets[0].pk,
    "outlet2_id": first_outlets[1].pk,
    "right_outlet_id": right_outlets[0].pk,
}
Path("/tmp/vpdu-smoke.json").write_text(json.dumps(manifest), encoding="utf-8")
print("Created isolated rack/browser fixtures.")
