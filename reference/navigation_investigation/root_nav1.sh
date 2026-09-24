# 請確保路徑指向你原本的參數檔案與地圖檔案
ros2 launch nav2_bringup navigation_launch.py \
   use_sim_time:=False \
   map:=/home/ntust/ros2_ws/mymap.yaml \
   params_file:=/home/ntust/ros2_ws/my_nav2_params.yaml 
