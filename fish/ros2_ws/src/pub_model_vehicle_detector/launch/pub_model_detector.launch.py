import os
from launch import LaunchDescription
from launch_ros.actions import Node

from launch.substitutions import LaunchConfiguration

def generate_launch_description():
    pcdet_dir = '/home/ntust/fish/ros2_ws/OpenPCDet' if os.path.exists('/home/ntust/fish/ros2_ws/OpenPCDet') else '/opt/OpenPCDet'
    weights_dir = '/home/ntust/fish/ros2_ws/weights' if os.path.exists('/home/ntust/fish/ros2_ws/weights') else '/workspace/ros2_ws/weights'
    
    config_path = os.path.join(pcdet_dir, 'tools/cfgs/nuscenes_models/cbgs_pp_multihead.yaml')
    checkpoint_path = os.path.join(weights_dir, 'pointpillar_nuscenes_50e.pth')
    map_yaml_path = '/home/ntust/ros2_ws/mymap.yaml'

    use_sim_time = LaunchConfiguration('use_sim_time', default='false')

    return LaunchDescription([
        # === 3D 車輛偵測節點 ===
        Node(
            package='pub_model_vehicle_detector',
            executable='detector_node',
            name='pub_model_vehicle_detector',
            output='screen',
                        parameters=[{
                'config_path': config_path,
                'checkpoint_path': checkpoint_path,
                'score_threshold': 0.1,
                'score_threshold_car': 0.1,
                'score_threshold_truck': 0.1,
                'score_threshold_bus': 0.1,
                'roi_x_min': -10.0,
                'roi_x_max': 15.0,
                'roi_y_min': -12.0,
                'roi_y_max': 12.0,
                'roi_z_min': -2.5,
                'roi_z_max': 3.0,
                'z_offset_correction': 0.57,
                'point_cloud_topic': '/ouster/points',
                'output_topic': '/detected_vehicles',
                'marker_topic': '/detected_vehicles_markers',
                'target_frame': 'base_link',
                'use_sim_time': use_sim_time
            }]
        ),

        # === 2D 地圖發布節點 (供違停判斷使用) ===
        # 因為 AGX 原有系統已經會發布 2D 地圖，所以這裡將其註解避免衝突
        # Node(
        #     package='pub_model_vehicle_detector',
        #     executable='map_server_node',
        #     name='map_server',
        #     output='screen',
        #                 parameters=[{
                'config_path': config_path,
                'checkpoint_path': checkpoint_path,
                'score_threshold': 0.1,
                'score_threshold_car': 0.1,
                'score_threshold_truck': 0.1,
                'score_threshold_bus': 0.1,
                'roi_x_min': -10.0,
                'roi_x_max': 15.0,
                'roi_y_min': -12.0,
                'roi_y_max': 12.0,
                'roi_z_min': -2.5,
                'roi_z_max': 3.0,
                'z_offset_correction': 0.57,
                'point_cloud_topic': '/ouster/points',
                'output_topic': '/detected_vehicles',
                'marker_topic': '/detected_vehicles_markers',
                'target_frame': 'base_link',
                'use_sim_time': use_sim_time
            }]
        # ),

        # === 靜態 TF 發布 ===
        # 因為 AGX 原有的啟動檔已發布 base_link → os_lidar，這裡將其註解避免衝突
        # Node(
        #     package='tf2_ros',
        #     executable='static_transform_publisher',
        #     name='static_tf_pub_base_to_lidar',
        #     arguments=[
        #         '--x', '0',
        #         '--y', '0',
        #         '--z', '1.12',
        #         '--yaw', '3.14159265',
        #         '--pitch', '0',
        #         '--roll', '0',
        #         '--frame-id', 'base_link',
        #         '--child-frame-id', 'os_lidar',
        #     ],
        #                 parameters=[{
                'config_path': config_path,
                'checkpoint_path': checkpoint_path,
                'score_threshold': 0.1,
                'score_threshold_car': 0.1,
                'score_threshold_truck': 0.1,
                'score_threshold_bus': 0.1,
                'roi_x_min': -10.0,
                'roi_x_max': 15.0,
                'roi_y_min': -12.0,
                'roi_y_max': 12.0,
                'roi_z_min': -2.5,
                'roi_z_max': 3.0,
                'z_offset_correction': 0.57,
                'point_cloud_topic': '/ouster/points',
                'output_topic': '/detected_vehicles',
                'marker_topic': '/detected_vehicles_markers',
                'target_frame': 'base_link',
                'use_sim_time': use_sim_time
            }]
        # ),

        # === 3D 定位節點 (使用 PCD 地圖) ===
        # 因為 AGX 有自己原生的 NDT 會負責定位並發佈 map -> odom -> base_link，必須把這個舊版的 ICP 定位註解掉避免 TF 打架
        # Node(
        #     package='pub_model_vehicle_detector',
        #     executable='localizer_node',
        #     name='localizer_node',
        #     output='screen',
        #                 parameters=[{
                'config_path': config_path,
                'checkpoint_path': checkpoint_path,
                'score_threshold': 0.1,
                'score_threshold_car': 0.1,
                'score_threshold_truck': 0.1,
                'score_threshold_bus': 0.1,
                'roi_x_min': -10.0,
                'roi_x_max': 15.0,
                'roi_y_min': -12.0,
                'roi_y_max': 12.0,
                'roi_z_min': -2.5,
                'roi_z_max': 3.0,
                'z_offset_correction': 0.57,
                'point_cloud_topic': '/ouster/points',
                'output_topic': '/detected_vehicles',
                'marker_topic': '/detected_vehicles_markers',
                'target_frame': 'base_link',
                'use_sim_time': use_sim_time
            }]
        # ),
    ])
