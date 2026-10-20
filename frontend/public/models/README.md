# Robot 3D models (used by the robot twins)

| Folder | Source | Licence |
|---|---|---|
| `ur5e/` | Universal Robots, `Universal_Robots_ROS2_Description` (meshes/ur5e/visual), https://github.com/UniversalRobots/Universal_Robots_ROS2_Description | BSD-3-Clause (`LICENSE-BSD3.txt`; UR's stricter graphical-documentation terms apply only to the UR8LONG/15/18/20/30 meshes) |
| `fanuc_lrmate200id/` | ROS-Industrial `fanuc` (fanuc_lrmate200id_support, meshes/lrmate200id/visual), https://github.com/ros-industrial/fanuc | BSD (`LICENSE-BSD3.txt`) |

The joint chains (positions, axes, mesh offsets) are copied from the same
packages' `ur_macro.xacro` + `config/ur5e/*.yaml` and
`lrmate200id_macro.xacro` (frontend/src/components/robot/robotModels.ts).

The FANUC arm in the lab is an ER-4iA (lettering on the arm, owner's photos 2026-10-19); it is drawn with
the LR Mate 200iD meshes and chain as a stand-in (not its exact link lengths).

What the browser loads: one compact binary `.glb` per mesh, same triangles and frame as the source file -
`scripts/dae_to_glb.mjs` then `scripts/compact_glb.mjs` for the Collada meshes (UR5e, Robotiq: welded,
quantized; the flat-shaded UR5e meshes store no normals) and `scripts/stl_to_glb.mjs` for the FANUC STLs.
2026-10-20: UR5e + Robotiq 10.4 MB -> 1.9 MB, FANUC 1.26 MB -> 0.26 MB. The source `.dae` / `.stl` stay here.

| `robotiq_2f85/` | PickNik `ros2_robotiq_gripper` (robotiq_description/meshes/visual/2f_85), https://github.com/PickNikRobotics/ros2_robotiq_gripper - the Robotiq 2F-85 gripper on the lab's UR5e, mounted with the UR-to-Robotiq adapter; drawn open | BSD-3-Clause |
| `abb_irb2400/`, `kuka_kr6r900/` | ROS-Industrial `abb` (abb_irb2400_support) and `kuka_experimental` (kuka_kr6_support), generated into src/components/welcome/industrial.ts - welcome page finale only | Apache-2.0 |
| `kinova_gen3_6dof/` | Kinova `ros_kortex` (kortex_description, gen3 6dof), generated into src/components/welcome/kinova.ts - welcome finale only | BSD-3-Clause |
