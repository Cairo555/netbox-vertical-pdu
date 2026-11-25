from django import forms
from dcim.models import Device
from .models import VerticalPlacement


class PlacementForm(forms.ModelForm):
    class Meta:
        model = VerticalPlacement
        fields = ("device", "face", "side", "lane", "offset_u", "height_u")
        labels = {"offset_u": "Offset from rack bottom (U)", "height_u": "Physical height (U)"}
        help_texts = {"lane": "Lane 1 is closest to the rack. Left/right are as viewed from the selected face.",
                      "height_u": "Physical length: 1 U = 44.45 mm. Does not consume rack units."}

    def __init__(self, *args, user, rack, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.rack = rack
        self.fields["device"].queryset = Device.objects.restrict(user, "view").filter(
            rack=rack, device_type__u_height=0, position__isnull=True)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-select" if isinstance(field.widget, forms.Select) else "form-control"
