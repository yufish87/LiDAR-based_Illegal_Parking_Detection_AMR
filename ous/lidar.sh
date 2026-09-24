source install/setup.bash
ros2 launch ouster_ros sensor.launch.xml \
  sensor_hostname:=169.254.70.240 \
  timestamp_mode:=TIME_FROM_ROS_TIME \
  use_sim_time:=false \
  pub_static_tf:=false \
  viz:=false
