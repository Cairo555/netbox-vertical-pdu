"""Disposable CI/test configuration. Never use with a production database."""
from .configuration_testing import *  # noqa: F403

PLUGINS = ["netbox_vertical_pdu"]

# The workflow first migrates this disposable database from scratch. Clone that
# verified schema for tests rather than replaying all core migrations twice.
DATABASES["default"]["TEST"] = {"TEMPLATE": "netbox"}  # noqa: F405
