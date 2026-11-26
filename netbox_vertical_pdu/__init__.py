from netbox.plugins import PluginConfig


class VerticalPDUConfig(PluginConfig):
    name = "netbox_vertical_pdu"
    verbose_name = "Vertical PDU"
    description = "Enhanced rack elevations with vertical 0U devices"
    version = "0.3.1"
    base_url = "vertical-pdu"
    min_version = "4.7.5"
    max_version = "4.7.5"
    default_auto_field = "django.db.models.BigAutoField"


config = VerticalPDUConfig
