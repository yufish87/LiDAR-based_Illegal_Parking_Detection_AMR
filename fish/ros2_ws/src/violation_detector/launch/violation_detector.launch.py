import os
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    zones_yaml = '/home/ntust/fish/ros2_ws/violation_area/zones.yaml'

    return LaunchDescription([
        Node(
            package='violation_detector',
            executable='violation_detector_node',
            name='violation_detector',
            output='screen',
            parameters=[{
                'zones_yaml_path':      zones_yaml,
                'vehicles_topic':       '/detected_vehicles',
                'map_frame':            'map',
                # 車輛停留超過幾秒才確認為違停
                'confirm_duration_sec': 3.0,
                # RViz marker 高度參數
                'marker_z':             0.05,
                'marker_height':        1.8,
                # 違停區域邊框線寬 (m)
                'zone_line_width':      0.15,
            }]
        ),
    ])
