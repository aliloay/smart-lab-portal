# Robot 3D models (used by the robot twins)

| Folder | Source | Licence |
|---|---|---|
| `ur5e/` | Universal Robots, `Universal_Robots_ROS2_Description` (meshes/ur5e/visual), https://github.com/UniversalRobots/Universal_Robots_ROS2_Description | BSD-3-Clause (`LICENSE-BSD3.txt`; UR's stricter graphical-documentation terms apply only to the UR8LONG/15/18/20/30 meshes) |
| `fanuc_lrmate200id/` | ROS-Industrial `fanuc` (fanuc_lrmate200id_support, meshes/lrmate200id/visual), https://github.com/ros-industrial/fanuc | BSD (`LICENSE-BSD3.txt`) |

The joint chains (positions, axes, mesh offsets) are copied from the same
packages' `ur_macro.xacro` + `config/ur5e/*.yaml` and
`lrmate200id_macro.xacro` (frontend/src/components/robot/robotModels.ts).

The FANUC arm in the lab is shown as an LR Mate 200iD: the model is NOT yet
confirmed from the robot's plate - replace the folder and chain if it differs.
