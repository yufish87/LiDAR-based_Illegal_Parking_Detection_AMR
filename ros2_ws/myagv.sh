ros2 run robot_state_publisher robot_state_publisher \
  --ros-args \
  -p robot_description:="$(cat myagv.urdf)" \
  -p use_sim_time:=false
