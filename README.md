# NetBox Vertical PDU

Native, independent NetBox plugin adding an **Enhanced Rack Elevation** tab to racks. No NetBox core modifications or other visualization plugins required.

Version 0.3.2 targets **NetBox Community 4.7.5**, including **NetBox Docker 5.1.2**. Only 4.7.5 is accepted until other versions have been tested. See [actual test status](docs/testing.md).

Outlet details include permission-filtered links to connected devices, power ports and cables, including destinations outside the displayed rack. The diagram shows actual cable connections without physical measurement lines.

## Features

- The actual native NetBox rack SVG, with clickable devices, role colors, device images, reservations, unit labels and theme colors; vertical 0U devices are drawn alongside it.
- Uses NetBox's configured rack unit width/height, keeping physical PDU mounting spans aligned with the native rack.
- All permitted outlets appear in a single, naturally numbered column with links to their native NetBox pages for cable management. Short PDU cards expand to fit and cards in the same lane stay apart.
- Separate front/rear views; up to 16 lanes per side, with multiple non-overlapping devices per lane.
- Physical height and bottom offset in U, to two decimal places (1 U = 44.45 mm). These do not consume rack units.
- Existing NetBox Power Outlets: cabled or marked-connected = occupied; otherwise free. This is connection occupancy, not measured power.
- Direct power cable lines from an outlet row to the edge of its connected rack-mounted server. Hover for both endpoint names; click for native cable details. Non-connected cable statuses use dashed lines.
- Hover or keyboard-focus an outlet to highlight its line and server in blue; hover/focus a server to highlight all its visible feeds and outlets. Unrelated lines dim, and highlighted lines are drawn above overlapping segments. Leaving the selection restores the normal view. Works with NetBox's asynchronously loaded rack SVG and both themes.
- Theme-aware light/dark colors, keyboard links, text outlet status and a scrollable wide elevation.
- Object permissions for racks, devices, placements and outlets, including constrained add/change permissions.
- Own migration-backed placement model; existing devices, outlets and cables remain authoritative.

## Use

1. Create a device type with **Height = 0 U** and outlet templates if applicable.
2. Assign a device of that type to a rack. Leave its ordinary rack position empty.
3. Open the rack's **Enhanced Rack Elevation** tab and select **Add vertical device**.
4. Select face, side, lane, bottom offset and physical height. A full-height device in a 42U rack uses offset 0 and height 42.
5. To stack two PDUs per side in a 42U rack, use **lane 1 for both**: e.g. height 20 / bottom offset 0 for the lower PDU and height 20 / bottom offset 22 for the upper PDU. Apply the same arrangement on the other side. These are example dimensions; enter the actual physical heights and positions.

Different lanes (1/2/…) put devices **side by side**, for racks mounted that way. Lane 1 is closest to the rack. Socket symbols form one vertical column with outlet names, connector labels and occupied/free status; their spacing is schematic, not a manufacturer drawing. All visible outlets are drawn: when necessary, the card expands. Expanded cards can extend below the rack. Clicking an outlet opens its existing NetBox page; cable creation and permissions remain managed by NetBox.

Left/right are **as viewed from the selected face**. A placement appears on its selected face only; it is not mirrored onto the opposite face. Physical offsets always start at the rack bottom regardless of numbering direction or starting unit. Regular full-depth equipment appears on both faces.

Compare the same face when checking against the standard rack page. NetBox uses role colors on a device's mounted face and its native opposite-face treatment on the other face. The plugin loads the same permission-aware SVG endpoint and uses the same theme handling as the standard page; it does not recolor or redraw rack equipment.

Each device has one placement. Physical overlaps in a face/side/lane are rejected. Short devices retain their stored physical height even when their display card expands. Counts are explicitly counts of **visible** outlets only.

If a device moves or its type/rack dimensions change in NetBox, stale placements are omitted from the drawing and flagged in their original rack's table. Removing a placement never removes the device or cabling. Deleting a device/rack cascades to its placement.

## Permissions

Grant through NetBox's object-permission UI (constraints are supported):

| Purpose | Permissions |
| --- | --- |
| Read elevation | `dcim.view_rack`, `dcim.view_device`, `netbox_vertical_pdu.view_verticalplacement` |
| See outlet status | `dcim.view_poweroutlet` |
| See cable lines | Above read permissions plus `dcim.view_cable`, `dcim.view_powerport`, and visibility of the destination device |
| Add placements | Above read permissions plus `netbox_vertical_pdu.add_verticalplacement` |
| Edit/remove placements | Above read permissions plus `change_verticalplacement` / `delete_verticalplacement` on the plugin model |

Placement permissions authorize plugin metadata changes, not changes to the underlying device. Device choices are limited to visible 0U devices in the same visible rack. Hidden conflicting placements produce a generic collision error. Writes are CSRF-protected, rack-serialized transactions, with permission constraints rechecked on the saved result. This release provides UI editing only, no REST write API or bulk import.

## Installation and development

- [NetBox Docker installation](docs/docker.md)
- [Tests and validation status](docs/testing.md)

The existing rack tab remains available. PDU sockets and cable lines are schematic, not physical routing. Lines require an actual direct cable to a visible Power Port on a server rendered on the selected rack face (including full-depth devices). Mark-connected without a cable, remote-rack devices, hidden endpoints and indirect paths through other equipment do not produce lines. Power measurements and redundancy analysis are outside this release. Native rack device images and reservations remain managed by NetBox.

License: Apache-2.0.
