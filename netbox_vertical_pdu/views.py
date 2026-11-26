from collections import defaultdict

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from dcim.models import Cable, Device, PowerOutlet, PowerPort, Rack
from netbox.views import generic
from netbox.config import get_config
from dcim.constants import RACK_ELEVATION_DEFAULT_LEGEND_WIDTH, RACK_ELEVATION_DEFAULT_MARGIN_WIDTH, RACK_ELEVATION_BORDER_WIDTH
from utilities.views import ViewTab, register_model_view

from .forms import PlacementForm
from .layout import build_scene, occupied, outlet_sort_key, validate_dimensions
from .models import VerticalPlacement


def visible_placements(user, rack):
    return VerticalPlacement.objects.restrict(user, "view").filter(
        rack=rack, device_id__in=Device.objects.restrict(user, "view").values("pk")
    ).select_related("device__device_type", "rack")


def visible_connections(user, outlets):
    """Direct outlet-to-power-port links, with independent object permissions.

    NetBox's peer resolver also handles profiled cables; never infer a link
    merely because two terminations share a cable or an outlet is marked used.
    """
    cabled = [o for group in outlets.values() for o in group if o.cable_id]
    cables = Cable.objects.restrict(user, "view").filter(pk__in=[o.cable_id for o in cabled]).in_bulk()
    devices = Device.objects.restrict(user, "view")
    ports = PowerPort.objects.restrict(user, "view").filter(
        cable_id__in=cables, device_id__in=devices.values("pk"),
    ).select_related("device__device_type").in_bulk()
    result = defaultdict(list)
    for outlet in cabled:
        if outlet.cable_id not in cables:
            continue
        cable = cables[outlet.cable_id]
        for peer in outlet.link_peers:
            if not isinstance(peer, PowerPort) or peer.pk not in ports:
                continue
            port = ports[peer.pk]
            result[outlet.pk].append({
                "device": port.device, "url": cable.get_absolute_url(),
                "device_url": port.device.get_absolute_url(),
                "port": port, "port_url": port.get_absolute_url(),
                "label": f"{outlet.device} / {outlet.name} → {port.device} / {port.name} ({cable.get_status_display()})",
                "planned": cable.status != "connected",
            })
    return result


@register_model_view(Rack, "vertical_pdu", path="enhanced-elevation")
class EnhancedRackView(generic.ObjectView):
    queryset = Rack.objects.all()
    template_name = "netbox_vertical_pdu/elevation.html"
    tab = ViewTab(label="Enhanced Rack Elevation", permission="dcim.view_rack", weight=1500)

    def get_extra_context(self, request, instance):
        face = request.GET.get("face", "rear")
        if face not in ("front", "rear"):
            face = "rear"
        placements = list(visible_placements(request.user, instance).filter(face=face))
        valid, invalid = [], []
        for p in placements:
            try:
                validate_dimensions(instance.u_height, p.offset_u, p.height_u, p.lane)
                if p.device.rack_id != instance.pk or p.device.device_type.u_height != 0 or p.device.position is not None:
                    raise ValueError("Device is no longer a 0U device in this rack.")
                valid.append(p)
            except ValueError:
                invalid.append(p)
        outlets = defaultdict(list)
        for outlet in PowerOutlet.objects.restrict(request.user, "view").filter(device_id__in=[p.device_id for p in placements]).select_related("device", "cable").order_by("name", "pk"):
            outlets[outlet.device_id].append(outlet)
        change_ids = set(VerticalPlacement.objects.restrict(request.user, "change").filter(rack=instance).values_list("pk", flat=True))
        delete_ids = set(VerticalPlacement.objects.restrict(request.user, "delete").filter(rack=instance).values_list("pk", flat=True))
        connections = visible_connections(request.user, outlets)
        drawn_connections = {
            outlet_id: [link for link in links if
                        link["device"].rack_id == instance.pk and
                        link["device"].position is not None and
                        link["device"].position > 0 and
                        link["device"].device_type.u_height > 0 and
                        (link["device"].face == face or link["device"].device_type.is_full_depth)]
            for outlet_id, links in connections.items()
        }
        rows = []
        for p in placements:
            visible = sorted(outlets[p.device_id], key=outlet_sort_key)
            used = sum(occupied(o) for o in visible)
            rows.append({"placement": p, "used": used, "free": len(visible) - used,
                         "outlets": [{"name": o.name, "occupied": occupied(o), "url": o.get_absolute_url(),
                                      "connections": connections.get(o.pk, [])} for o in visible],
                         "can_change": p.pk in change_ids, "can_delete": p.pk in delete_ids,
                         "invalid": p in invalid})
        config = get_config()
        scene = build_scene(instance, valid, outlets,
                            connections=drawn_connections,
                            unit_height=config.RACK_ELEVATION_DEFAULT_UNIT_HEIGHT,
                            unit_width=config.RACK_ELEVATION_DEFAULT_UNIT_WIDTH,
                            legend_width=RACK_ELEVATION_DEFAULT_LEGEND_WIDTH,
                            margin_width=RACK_ELEVATION_DEFAULT_MARGIN_WIDTH,
                            border_width=RACK_ELEVATION_BORDER_WIDTH)
        return {"face": face, "scene": scene, "rows": rows,
                "can_add": request.user.has_perm("netbox_vertical_pdu.add_verticalplacement")}


class PlacementAccessMixin(LoginRequiredMixin):
    def get_rack(self, request, rack_pk, lock=False):
        qs = Rack.objects.restrict(request.user, "view")
        if lock:
            qs = qs.select_for_update()
        return get_object_or_404(qs, pk=rack_pk)

    def get_placement(self, request, rack, pk, action):
        if not request.user.has_perm(f"netbox_vertical_pdu.{action}_verticalplacement"):
            raise PermissionDenied
        if pk is None:
            return VerticalPlacement(rack=rack)
        return get_object_or_404(visible_placements(request.user, rack).restrict(request.user, action), pk=pk)


class PlacementEditView(PlacementAccessMixin, View):
    def get(self, request, rack_pk, pk=None):
        rack = self.get_rack(request, rack_pk)
        placement = self.get_placement(request, rack, pk, "change" if pk else "add")
        form = PlacementForm(instance=placement, user=request.user, rack=rack)
        return render(request, "netbox_vertical_pdu/edit.html", {"object": rack, "form": form, "tab": EnhancedRackView.tab})

    def post(self, request, rack_pk, pk=None):
        action = "change" if pk else "add"
        try:
            with transaction.atomic():
                # Serialize writes per rack so two requests cannot validate overlapping free space.
                rack = self.get_rack(request, rack_pk, lock=True)
                placement = self.get_placement(request, rack, pk, action)
                if pk:
                    placement.snapshot()
                form = PlacementForm(request.POST, instance=placement, user=request.user, rack=rack)
                if form.is_valid():
                    placement = form.save(commit=False)
                    placement.device = Device.objects.select_for_update().get(pk=placement.device_id)
                    placement.full_clean()
                    placement.save()
                    # Recheck constraints against the saved state, rolling back unauthorized changes.
                    if not VerticalPlacement.objects.restrict(request.user, action).filter(pk=placement.pk).exists():
                        raise PermissionDenied
                    messages.success(request, "Vertical placement saved.")
                    return redirect(placement.get_absolute_url())
        except ValidationError as error:
            form.add_error(None, "; ".join(error.messages))
        except IntegrityError:
            form.add_error(None, "The placement conflicted with another update. Reload and try again.")
        return render(request, "netbox_vertical_pdu/edit.html", {"object": rack, "form": form, "tab": EnhancedRackView.tab})


class PlacementDeleteView(PlacementAccessMixin, View):
    def get(self, request, rack_pk, pk):
        rack = self.get_rack(request, rack_pk)
        placement = self.get_placement(request, rack, pk, "delete")
        return render(request, "netbox_vertical_pdu/delete.html", {"object": rack, "placement": placement, "tab": EnhancedRackView.tab})

    def post(self, request, rack_pk, pk):
        with transaction.atomic():
            rack = self.get_rack(request, rack_pk, lock=True)
            placement = self.get_placement(request, rack, pk, "delete")
            url = placement.get_absolute_url()
            placement.delete()
        messages.success(request, "Vertical placement removed. The device and its outlets have been kept.")
        return redirect(url)
