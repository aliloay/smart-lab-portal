# Digital twin: models and assets

3D meshes are in [`frontend/public/models/`](../../frontend/public/models/); licences and sources per robot are in [`frontend/public/models/README.md`](../../frontend/public/models/README.md) and the `LICENSE*` file in each folder.

| Folder | Robot | Licence file |
|---|---|---|
| `ur5e/` | Universal Robots UR5e | `LICENSE-BSD3.txt` |
| `fanuc_lrmate200id/` | FANUC LR Mate 200iD (used for the ER-4iA; proportions to be checked) | `LICENSE-BSD3.txt` |
| `robotiq_2f85/` | Robotiq 2F-85 gripper | `LICENSE-BSD3.txt` |
| `abb_irb2400/`, `kuka_kr6r900/`, `kinova_gen3_6dof/` | Other models used on the welcome page | `LICENSE.txt` |

Rendering: three.js 0.169 through `@react-three/fiber` 8.17. The 3D view mounts after the page is visible (deferred mount), so a slow GPU does not freeze the robot pages.
