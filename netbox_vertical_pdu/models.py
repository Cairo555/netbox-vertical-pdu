from decimal import Decimal
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.urls import reverse
from netbox.models import ChangeLoggedModel

from .layout import validate_dimensions, overlaps


class VerticalPlacement(ChangeLoggedModel):
    device = models.OneToOneField("dcim.Device", on_delete=models.CASCADE, related_name="vertical_placement")
    rack = models.ForeignKey("dcim.Rack", on_delete=models.CASCADE, related_name="vertical_placements")
    face = models.CharField(max_length=5, choices=(("front", "Front"), ("rear", "Rear")), default="rear")
    side = models.CharField(max_length=5, choices=(("left", "Left"), ("right", "Right")), default="left")
    lane = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(16)])
    offset_u = models.DecimalField(max_digits=7, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    height_u = models.DecimalField(max_digits=7, decimal_places=2, default=42, validators=[MinValueValidator(Decimal("0.01"))])

    class Meta:
        ordering = ("rack", "face", "side", "lane", "offset_u")
        constraints = [
            models.CheckConstraint(condition=models.Q(offset_u__gte=0), name="vpdu_nonnegative_offset"),
            models.CheckConstraint(condition=models.Q(height_u__gt=0), name="vpdu_positive_height"),
            models.CheckConstraint(condition=models.Q(lane__gte=1, lane__lte=16), name="vpdu_valid_lane"),
        ]

    def __str__(self):
        return f"{self.device}: {self.face} {self.side} lane {self.lane}"

    def get_absolute_url(self):
        return reverse("dcim:rack_vertical_pdu", args=[self.rack_id]) + f"?face={self.face}"

    def clean(self):
        super().clean()
        if not self.device_id or not self.rack_id:
            return
        if self.device.rack_id != self.rack_id or self.device.device_type.u_height != 0:
            raise ValidationError({"device": "Choose a 0U device assigned to this rack."})
        if self.device.position is not None:
            raise ValidationError({"device": "A vertical device must have no rack-unit position."})
        if None in (self.offset_u, self.height_u, self.lane):
            return  # Field validation reports missing/invalid values.
        try:
            validate_dimensions(self.rack.u_height, self.offset_u, self.height_u, self.lane)
        except ValueError as error:
            raise ValidationError(str(error)) from error
        others = type(self).objects.filter(rack=self.rack, face=self.face, side=self.side, lane=self.lane).exclude(pk=self.pk)
        if any(overlaps(self.offset_u, self.height_u, p.offset_u, p.height_u) for p in others):
            # Do not reveal details of a conflicting placement the editor may not be allowed to view.
            raise ValidationError("This space is already occupied in the selected lane.")
