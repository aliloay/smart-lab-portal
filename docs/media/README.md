# Media inventory

Every image in this folder, where it comes from and what it shows. Faces are blurred and names removed wherever people appear. Renders are labelled as renders; nothing generated is presented as a photograph of our hardware.

| File | Type | Source | Shows |
|---|---|---|---|
| `hardware/master_node_render.png` | Render | Blender, real enclosure CAD (`tools/cad/release_2026-10-25`), screen text from the door firmware | Master Node granting access, with the solenoid lock on its post |
| `hardware/environment_node_render.png` | Render | Blender, enclosure CAD | Environment Node |
| `hardware/consumables_node_render.png` | Render | Blender, enclosure CAD; LCD layout from the firmware, example reading | Consumables Node with the weighing plate and LCD |
| `hardware/reusables_node_render.png` | Render | Blender, dock CAD and the bin outline from its design | Reusables dock and bin, lid open |
| `computer-vision/camera_door_crosscheck_blurred.jpg` | Real footage (processed) | Portal camera recording, 7 Oct 2026; faces blurred, name replaced by the system ID | Person with no door entry: "USER1 – not entered" |
| `computer-vision/camera_pc10_in_use_blurred.jpg` | Real footage (processed) | Same recording | The tracked person sits at PC-10 ("PC-10 in") |
| `digital-twin/ur5e_with_twin.jpg` | Photo | Lab, Oct 2026 | The real UR5e and the portal twin on a laptop |
| `ar/ur5e_cell_marker_photo.jpg` | Photo | Lab, 3 Nov 2026 | UR5e cell with its printed QR marker |
| `ar/scan_overlay_reconstruction.png` | Composite | The photo above with the Scan page's overlay reconstructed (marker, robot box, live-record card); **not a screen recording** | How Scan the lab presents a target |
| `obsidian/vault_graph_and_agent.png` | Visualisation | The real vault graph (331 notes, 1,014 links, parsed 8 Nov 2026) and the real knowledge-agent answer of 8 Nov 2026 | Knowledge → agent → answer with sources |
| `n8n/workflows_16_and_06.png` | Visualisation | Drawn from the exported workflow JSON (16 and 06) and the real reports page | Trigger → automation → action → report |
| `portal/operations_overview.png`, `lab_pcs_screen_wall.png`, `ask_the_lab_answer.png`, `reports.png` | Screenshots | Real portal (names masked on the PC wall) | Overview, PC wall, AI answer, reports |
| `portal/lab_pc_desk_shared_screen_render.png` | Render | Blender lab desk; screens are blurred real PC captures, then the shared portal view | Screen sharing to every lab PC |
| `portal/dev_captures/*.png` | Screenshots | Portal captures from the e2e probes (System Administrator account only) | Reliability, incidents and robot control pages |
| `diagrams/architecture_render_blender.png` | Render | Blender scene of the real enclosures around a local core | Local architecture illustration |

Diagrams in Mermaid (rendered by GitHub): [`docs/architecture/*.mmd`](../architecture/) and inline in the architecture pages. More real screenshots: [`docs/screenshots/`](../screenshots/), [`docs/paper_figures/portal_2026-10-19/`](../paper_figures/portal_2026-10-19/).
