# NetBox Vertical PDU

Native, independent NetBox plugin adding an **Enhanced Rack Elevation** tab to racks. No NetBox core modifications or other visualization plugins required.

Version 0.1.0 targets **NetBox Community 4.7.5**, including **NetBox Docker 5.1.2**. Only 4.7.5 is accepted until other versions have been tested. See [actual test status](docs/testing.md).

## Features

- Clickable regular rack devices and vertical 0U devices in an SVG elevation.
- Separate front/rear views; up to 16 lanes per side, with multiple non-overlapping devices per lane.
- Physical height and bottom offset in U, to two decimal places (1 U = 44.45 mm). These do not consume rack units.
- Existing NetBox Power Outlets: cabled or marked-connected = occupied; otherwise free. This is connection occupancy, not measured power.
- Theme-aware light/dark colors, keyboard links, text outlet status and a scrollable wide elevation.
- Object permissions for racks, devices, placements and outlets, including constrained add/change permissions.
- Own migration-backed placement model; existing devices, outlets and cables remain authoritative.

## Use

1. Create a device type with **Height = 0 U** and outlet templates if applicable.
2. Assign a device of that type to a rack. Leave its ordinary rack position empty.
3. Open the rack's **Enhanced Rack Elevation** tab and select **Add vertical device**.
4. Select face, side, lane, bottom offset and physical height. A full-height device in a 42U rack uses offset 0 and height 42.
5. For four PDUs use left lanes 1/2 and right lanes 1/2. Lane 1 is closest to the rack.

Left/right are **as viewed from the selected face**. A placement appears on its selected face only; it is not mirrored onto the opposite face. Physical offsets always start at the rack bottom regardless of numbering direction or starting unit. Regular full-depth equipment appears on both faces.

Each device has one placement. Overlaps in a face/side/lane are rejected. Short devices retain their physical height; all visible outlets remain in the details table even if they do not fit in the drawing. Counts are explicitly counts of **visible** outlets only.

If a device moves or its type/rack dimensions change in NetBox, stale placements are omitted from the drawing and flagged in their original rack's table. Removing a placement never removes the device or cabling. Deleting a device/rack cascades to its placement.

## Permissions

Grant through NetBox's object-permission UI (constraints are supported):

| Purpose | Permissions |
| --- | --- |
| Read elevation | `dcim.view_rack`, `dcim.view_device`, `netbox_vertical_pdu.view_verticalplacement` |
| See outlet status | `dcim.view_poweroutlet` |
| Add placements | Above read permissions plus `netbox_vertical_pdu.add_verticalplacement` |
| Edit/remove placements | Above read permissions plus `change_verticalplacement` / `delete_verticalplacement` on the plugin model |

Placement permissions authorize plugin metadata changes, not changes to the underlying device. Device choices are limited to visible 0U devices in the same visible rack. Hidden conflicting placements produce a generic collision error. Writes are CSRF-protected, rack-serialized transactions, with permission constraints rechecked on the saved result. This release provides UI editing only, no REST write API or bulk import.

## Installation and development

- [NetBox Docker installation](docs/docker.md)
- [Tests and validation status](docs/testing.md)

The existing rack tab remains available. This is a schematic drawing; device images, rack reservations, cable routes, power measurements and redundancy analysis are outside this release.

License: Apache-2.0.
