import os
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    # 你的地圖路徑
    map_yaml_file = '/home/saitama/ros2_ws/mymap.yaml' 

    return LaunchDescription([
        # 1. 啟動地圖伺服器，直接載入你的 mymap.yaml
        Node(
            package='nav2_map_server',
            executable='map_server',
            name='map_server',
            output='screen',
            parameters=[{
                'yaml_filename': map_yaml_file,
                'use_sim_time': False
            }]
        ),
        # 2. 啟動一個專屬的大總管，只負責強行把 map_server 給活化（Activate）
        Node(
            package='nav2_lifecycle_manager',
            executable='lifecycle_manager',
            name='lifecycle_manager_map',
            output='screen',
            parameters=[{
                'autostart': True,
                'bond_timeout': 4.0,
                'node_names': ['map_server']
            }]
        )
    ])
