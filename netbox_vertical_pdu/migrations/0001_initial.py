from decimal import Decimal
import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [("dcim", "0001_squashed")]
    operations = [
        migrations.CreateModel(
            name="VerticalPlacement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created", models.DateTimeField(auto_now_add=True, blank=True, null=True, verbose_name="created")),
                ("last_updated", models.DateTimeField(auto_now=True, blank=True, null=True, verbose_name="last updated")),
                ("face", models.CharField(choices=[("front", "Front"), ("rear", "Rear")], default="rear", max_length=5)),
                ("side", models.CharField(choices=[("left", "Left"), ("right", "Right")], default="left", max_length=5)),
                ("lane", models.PositiveSmallIntegerField(default=1, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(16)])),
                ("offset_u", models.DecimalField(decimal_places=2, default=0, max_digits=7, validators=[django.core.validators.MinValueValidator(0)])),
                ("height_u", models.DecimalField(decimal_places=2, default=42, max_digits=7, validators=[django.core.validators.MinValueValidator(Decimal("0.01"))])),
                ("device", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="vertical_placement", to="dcim.device")),
                ("rack", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="vertical_placements", to="dcim.rack")),
            ],
            options={"ordering": ("rack", "face", "side", "lane", "offset_u"), "constraints": [
                models.CheckConstraint(condition=models.Q(offset_u__gte=0), name="vpdu_nonnegative_offset"),
                models.CheckConstraint(condition=models.Q(height_u__gt=0), name="vpdu_positive_height"),
                models.CheckConstraint(condition=models.Q(lane__gte=1, lane__lte=16), name="vpdu_valid_lane"),
            ]},
        ),
    ]
