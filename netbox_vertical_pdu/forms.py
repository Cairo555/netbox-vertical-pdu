from django import forms
from dcim.models import Device
from .models import VerticalPlacement


class PlacementForm(forms.ModelForm):
    class Meta:
        model = VerticalPlacement
        fields = ("device", "face", "side", "lane", "offset_u", "height_u")
        labels = {"offset_u": "Offset from rack bottom (U)", "height_u": "Physical height (U)"}
        help_texts = {"lane": "Use the same lane with different bottom offsets to stack devices. Different lanes place them side by side. Lane 1 is closest to the rack; left/right are as viewed from the selected face.",
                      "height_u": "Physical length: 1 U = 44.45 mm. Does not consume rack units."}

    def __init__(self, *args, user, rack, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.rack = rack
        self.fields["device"].queryset = Device.objects.restrict(user, "view").filter(
            rack=rack, device_type__u_height=0, position__isnull=True)
        placed = VerticalPlacement.objects.exclude(pk=self.instance.pk).values("device_id")
        self.fields["device"].queryset = self.fields["device"].queryset.exclude(pk__in=placed).order_by("name", "pk")
        self.has_eligible_devices = self.fields["device"].queryset.exists()
        self.fields["device"].help_text = (
            "Choose an existing 0U device assigned to this rack, with no rack-unit position. "
            "Devices already placed are available through Edit on the elevation page."
        )
        self.fields["device"].empty_label = "Select a device" if self.has_eligible_devices else "No available 0U devices in this rack"
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-select" if isinstance(field.widget, forms.Select) else "form-control"
