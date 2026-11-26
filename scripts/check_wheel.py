"""Fail if a built wheel omits runtime assets."""
from pathlib import Path
from zipfile import ZipFile

wheel = next(Path("dist").glob("*.whl"))
with ZipFile(wheel) as archive:
    files = set(archive.namelist())
    for relative in (
        "templates/netbox_vertical_pdu/elevation.html",
        "templates/netbox_vertical_pdu/edit.html",
        "templates/netbox_vertical_pdu/delete.html",
        "static/netbox_vertical_pdu/elevation-v0.2.0.css",
        "migrations/0001_initial.py",
    ):
        assert f"netbox_vertical_pdu/{relative}" in files, relative
print("Wheel includes templates, CSS and migration.")
