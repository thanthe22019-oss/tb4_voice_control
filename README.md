# tb4_voice_control

ROS 2 Humble package for TurtleBot 4 Standard in Ignition Gazebo's warehouse
world. This initial baseline provides SLAM, AMCL localization, Nav2 navigation,
and named goal recording. Voice features are planned in the design under
`docs/superpowers/`; they are not implemented in this baseline.

## Provenance

Copied from the clean `/home/alex/Interaction/tb4_nav2` checkout at commit
`3625002e8059ae84ce604ee4039ae7b0cb3c22bd`. The original repository remains
unchanged. The map and recorded goals are preserved byte for byte, including
the warehouse map's `0.05 m/pixel` resolution and `[-19.7, -27.5, 0]` origin.
The upstream Apache-2.0 license is retained in `LICENSE`.

The independent repository has a documentation bootstrap commit and an
implementation worktree on `feature/implementation`. Package metadata, imports,
package-share lookups, and node names use `tb4_voice_control`. YOLO models,
notebooks, scripts, dependencies, and tests are excluded.

## Build and test

Requirements: Ubuntu 22.04, ROS 2 Humble, Ignition Gazebo Fortress, TurtleBot 4
simulator/navigation packages, Nav2, SLAM Toolbox, PyYAML, pytest, and colcon.

From this checkout:

```bash
source /opt/ros/humble/setup.bash
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"
pytest -q
colcon build --base-paths . --packages-select tb4_voice_control --symlink-install
source install/setup.bash
ros2 pkg prefix tb4_voice_control
```

The prefix must be this checkout's `install/tb4_voice_control` directory. For a
checkout at `/home/alex/Interaction/tb4_voice_control`, it is
`/home/alex/Interaction/tb4_voice_control/install/tb4_voice_control`. In the
implementation worktree it is
`/home/alex/Interaction/tb4_voice_control/.worktrees/implementation/install/tb4_voice_control`.
Source ROS Humble and this checkout's `install/setup.bash` in every terminal.
Use the same `ROS_DOMAIN_ID` and `RMW_IMPLEMENTATION` across terminals.

## Navigate with the saved map

```bash
ros2 launch tb4_voice_control tb4_nav2.launch.py
```

This starts Gazebo, AMCL, Nav2, and RViz. Optional arguments are `rviz:=false`,
`world:=warehouse`, and `map:=/absolute/path/map.yaml`. The world must match
the map. Run one simulator session at a time.

Undock using the TurtleBot 4 HMI or a second sourced terminal:

```bash
ros2 action send_goal /undock irobot_create_msgs/action/Undock '{}' --feedback
```

Wait for undocking to finish. In RViz set **Fixed Frame** to `map`, then use
**2D Pose Estimate** at the robot's actual position and heading. Wait for AMCL
and active navigation nodes before sending a **Nav2 Goal**. Check localization
with `ros2 run tf2_ros tf2_echo map base_link` if needed. Do not teleoperate
while a navigation goal is active.

Execute the three recorded goals in YAML order:

```bash
ros2 run tb4_voice_control navigate_goals \
  --goal-timeout 180 --feedback-period 3 \
  --ros-args -p use_sim_time:=true
```

Select a different order by repeating `--goal`, for example `--goal goal_3
--goal goal_1`. Use `--goals-file /absolute/path/goals.yaml` to select another
file. The node waits for a real AMCL pose and Nav2 readiness, stops on a failed
or timed-out goal, and cancels an active goal on Ctrl+C.

Record a named goal from the current real AMCL pose:

```bash
ros2 run tb4_voice_control record_goal \
  --name goal_1 --output "$PWD/config/goals.yaml"
```

This updates the named entry atomically. Rebuild after editing packaged assets.

## Map with SLAM Toolbox

Stop the navigation launch and close its simulator before starting SLAM:

```bash
ros2 launch tb4_voice_control tb4_slam.launch.py
```

Undock, then run `ros2 run teleop_twist_keyboard teleop_twist_keyboard` in a
second sourced terminal. Move slowly through the warehouse, using `k` to stop.
RViz should show `/map` and `/scan` in the `map` frame. Save from a third
sourced terminal while SLAM remains active:

```bash
ros2 run nav2_map_server map_saver_cli \
  -f "$PWD/maps/map" \
  --ros-args -p use_sim_time:=true -p save_map_timeout:=10.0
```

This replaces the map in this checkout. Keep `map.yaml` and `map.pgm` together.
Stop SLAM, rebuild, restart the navigation launch, and set the initial pose
again before navigating.

## Milestone 0 prerequisites audit

Recorded on 2026-11-02 before copying the baseline. `git status --short` in
the source repository produced no output, and `git rev-parse HEAD` returned:

```text
3625002e8059ae84ce604ee4039ae7b0cb3c22bd
```

`nvidia-smi` exited 9 with this output:

```text
NVIDIA-SMI has failed because it couldn't communicate with the NVIDIA driver. Make sure that the latest NVIDIA driver is installed and running.

```

`gh auth status -h github.com` exited 1 with this output:

```text
* Request at 2026-11-02 09:18:22.215763966 +0700 +07 m=+0.008894107
* Request to https://api.github.com/
* dial tcp: lookup api.github.com: Temporary failure in name resolution
* Request took 531.715µs
github.com
  X github.com: authentication failed
  - The github.com token in /home/alex/.config/gh/hosts.yml is no longer valid.
  - To re-authenticate, run: gh auth login -h github.com
  - To forget about this host, run: gh auth logout -h github.com

```

GPU readiness remains unresolved. Public repository creation and pushing are
deferred to final delivery until GitHub authentication and connectivity work.
No authentication or publishing is performed by this task.
