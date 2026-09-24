cd ros2_ws
source fix.sh
python3 odem_bridge.py

source myagv.sh

cd ous
source lidar.sh

cd ros2_ws
source laser.sh

source local.sh

source nav1.sh

python3 nav_gui.py

source map.sh

source /opt/ros/foxy/setup.bash && source /home/ntust/fish/ros2_ws/install/setup.bash
ros2 launch pub_model_vehicle_detector pub_model_detector.launch.py

source /opt/ros/foxy/setup.bash && source /home/ntust/fish/ros2_ws/install/setup.bash
ros2 run violation_detector violation_detector_node

cd /home/ntust/fish/ros2_ws
source /opt/ros/foxy/setup.bash && source /home/ntust/fish/ros2_ws/install/setup.bash
python3 camera_uploader_node.py
