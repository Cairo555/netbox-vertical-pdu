"""Event serialization for the change-logged placement model.

No API routes are exposed: placement writes use the permission-checked UI.
"""
from rest_framework import serializers

from netbox_vertical_pdu.models import VerticalPlacement


class VerticalPlacementSerializer(serializers.ModelSerializer):
    class Meta:
        model = VerticalPlacement
        fields = (
            "id", "device", "rack", "face", "side", "lane", "offset_u", "height_u",
            "created", "last_updated",
        )
