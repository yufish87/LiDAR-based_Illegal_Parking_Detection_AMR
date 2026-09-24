#!/bin/bash

MAP_YAML="/home/ntust/ros2_ws/mymap.yaml"

echo "=========================================="
echo " 正在啟動 nav2_map_server 與 Lifecycle Manager..."
echo "=========================================="

# 1. 啟動 map_server
ros2 run nav2_map_server map_server --ros-args -p yaml_filename:=${MAP_YAML} -r __node:=map_server &
MAP_SERVER_PID=$!

# 2. 使用官方 lifecycle_manager 自動完成 configure & activate
ros2 run nav2_lifecycle_manager lifecycle_manager --ros-args \
  -p autostart:=true \
  -p node_names:="['map_server']" &
MANAGER_PID=$!

echo "=========================================="
echo " 地圖伺服器已由 Lifecycle Manager 託管啟動！"
echo "=========================================="

wait $MAP_SERVER_PID
