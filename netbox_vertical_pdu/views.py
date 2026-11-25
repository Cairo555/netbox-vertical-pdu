from collections import defaultdict

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from dcim.models import Device, PowerOutlet, Rack
from netbox.views import generic
from netbox.config import get_config
from dcim.constants import RACK_ELEVATION_DEFAULT_LEGEND_WIDTH, RACK_ELEVATION_DEFAULT_MARGIN_WIDTH, RACK_ELEVATION_BORDER_WIDTH
from utilities.views import ViewTab, register_model_view

from .forms import PlacementForm
from .layout import build_scene, occupied, validate_dimensions
from .models import VerticalPlacement


def visible_placements(user, rack):
    return VerticalPlacement.objects.restrict(user, "view").filter(
        rack=rack, device_id__in=Device.objects.restrict(user, "view").values("pk")
    ).select_related("device__device_type", "rack")


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
        for outlet in PowerOutlet.objects.restrict(request.user, "view").filter(device_id__in=[p.device_id for p in placements]).order_by("name", "pk"):
            outlets[outlet.device_id].append(outlet)
        change_ids = set(VerticalPlacement.objects.restrict(request.user, "change").filter(rack=instance).values_list("pk", flat=True))
        delete_ids = set(VerticalPlacement.objects.restrict(request.user, "delete").filter(rack=instance).values_list("pk", flat=True))
        rows = []
        for p in placements:
            visible = outlets[p.device_id]
            used = sum(occupied(o) for o in visible)
            rows.append({"placement": p, "used": used, "free": len(visible) - used,
                         "outlets": [{"name": o.name, "occupied": occupied(o)} for o in visible],
                         "can_change": p.pk in change_ids, "can_delete": p.pk in delete_ids,
                         "invalid": p in invalid})
        config = get_config()
        scene = build_scene(instance, valid, outlets,
                            unit_height=config.RACK_ELEVATION_DEFAULT_UNIT_HEIGHT,
                            unit_width=config.RACK_ELEVATION_DEFAULT_UNIT_WIDTH,
                            legend_width=RACK_ELEVATION_DEFAULT_LEGEND_WIDTH,
                            margin_width=config.RACK_ELEVATION_DEFAULT_MARGIN_WIDTH,
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
        return render(request, "netbox_vertical_pdu/edit.html", {"object": rack, "form": form})

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
        return render(request, "netbox_vertical_pdu/edit.html", {"object": rack, "form": form})


class PlacementDeleteView(PlacementAccessMixin, View):
    def get(self, request, rack_pk, pk):
        rack = self.get_rack(request, rack_pk)
        placement = self.get_placement(request, rack, pk, "delete")
        return render(request, "netbox_vertical_pdu/delete.html", {"object": rack, "placement": placement})

    def post(self, request, rack_pk, pk):
        with transaction.atomic():
            rack = self.get_rack(request, rack_pk, lock=True)
            placement = self.get_placement(request, rack, pk, "delete")
            url = placement.get_absolute_url()
            placement.delete()
        messages.success(request, "Vertical placement removed. The device and its outlets have been kept.")
        return redirect(url)
