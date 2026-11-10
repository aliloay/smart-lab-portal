# Smart Lab architecture image: sources

`smart-lab-architecture.png` (2400 x 1350) is composed from existing project assets. Nothing in it was produced by an image generator, and all text is set by the HTML/CSS source.

## How it is built

- Composition source: `src/architecture.html` (fixed 2400 x 1350 layout, system font Segoe UI).
- Renderer: `frontend/e2e/render_architecture.mjs` (playwright-core driving the installed Google Chrome, one screenshot at scale 1). Rebuild with `cd frontend && node e2e/render_architecture.mjs`.

## Assets

| Panel | File | What it is |
|---|---|---|
| Master (door) node | `nodes/door-node-render.png` | Blender render of the real enclosure CAD (`tools/cad/release_2026-10-25`); copy of `docs/media/hardware/master_node_render.png` |
| Environment node | `nodes/environment-node-render.png` | Blender render of the enclosure CAD; copy of `docs/media/hardware/environment_node_render.png` |
| Consumables node | `nodes/consumables-node-render.png` | Blender render of the enclosure CAD, LCD layout from the firmware with an example reading |
| Reusables node | `nodes/reusables-node-render.png` | Blender render of the dock CAD and the bin outline from its design |
| Portal | `docs/media/portal/operations_overview.png` | Real portal screenshot (System Administrator account) |
| Cameras | `docs/media/computer-vision/camera_pc10_in_use_blurred.jpg` | Real camera footage of 7 Oct 2026, faces blurred |
| Robots | `frontend/public/equipment/our-ur5e.jpg`, `our-fanuc.jpg` | Photos of the lab's UR5e cell and FANUC ER-4iA cell |
| Lab PCs | `frontend/public/equipment/our-pcs.jpg`, `docs/media/portal/lab_pcs_screen_wall.png` | Photo of the lab PCs; real screen-wall capture with names masked |
| Assistants | `docs/media/portal/ask_the_lab_answer.png` | Real portal screenshot |
| Knowledge | `docs/media/obsidian/vault_graph_and_agent.png` | Visualisation of the real vault graph and a real agent answer |
| Automation | `docs/media/n8n/workflows_16_and_06.png` | Drawn from the exported workflow JSON and the real reports page |

The four node renders were not re-rendered for this image; the existing renders of the real CAD were reused and cropped by the layout.

## Statements in the image and where they come from

- 329 API operations, 42 tables: backend OpenAPI schema and database dictionary.
- 23 n8n workflows: `automation/n8n/json`. 322 notes: the published vault copy.
- YOLO26s, two cameras sharing one identity: `docs/computer-vision/`. Camera 2 still needs its floor calibration for name sharing.
- Robots are read-only: UR5e over RTDE receive, FANUC over the controller web page (`GET` only).
- Reusables node is marked "prototype".

## Not shown, on purpose

No PLC, Raspberry Pi gateway, MQTT broker or robot motion control (none is implemented). No "100% offline" claim (the formal offline run is still open). The router and cabling are not drawn. No separate university logo was added; the one visible is part of the portal screenshot.
