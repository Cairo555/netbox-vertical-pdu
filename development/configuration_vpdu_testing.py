"""Disposable CI/test configuration. Never use with a production database."""
from .configuration_testing import *  # noqa: F403

PLUGINS = ["netbox_vertical_pdu"]
