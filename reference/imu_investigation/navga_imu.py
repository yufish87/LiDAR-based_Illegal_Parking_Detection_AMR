#!/usr/bin/env python3
import sys
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Imu
from rclpy.qos import qos_profile_sensor_data

class ImuTimeFixer(Node):
    def __init__(self):
        super().__init__('imu_time_fixer', allow_undeclared_parameters=True, automatically_declare_parameters_from_overrides=True)
        self.sub = self.create_subscription(Imu, '/ouster/imu', self.callback, qos_profile_sensor_data)
        self.pub = self.create_publisher(Imu, '/fixed/imu', 10)
        self.offset_ns = None
        self.get_logger().info('IMU 完美時間修正 (保持原廠 dt) 已啟動，等待 Bag 資料中...')

    def callback(self, msg):
        current_ros_time = self.get_clock().now()
        
        # 擋下時間為 0 的幽靈資料 (等待與 Bag 的 /clock 同步)
        if current_ros_time.nanoseconds == 0:
            return

        # 取得 IMU 原本的硬體時間 (奈秒)
        imu_time_ns = msg.header.stamp.sec * 1000000000 + msg.header.stamp.nanosec

        # 第一次收到資料時：鎖定 ROS 時間與硬體時間的「固定時差」
        if self.offset_ns is None:
            self.offset_ns = current_ros_time.nanoseconds - imu_time_ns
            self.get_logger().info(f'已鎖定時間差: {self.offset_ns / 1e9:.3f} 秒')

        # 把原本的 IMU 時間加上固定時差 (完美保留硬體級的資料間隔)
        fixed_time_ns = imu_time_ns + self.offset_ns
        
        if fixed_time_ns < 0:
            fixed_time_ns = 0

        # 將修正好的時間塞回訊息中
        msg.header.stamp.sec = int(fixed_time_ns // 1000000000)
        msg.header.stamp.nanosec = int(fixed_time_ns % 1000000000)

        self.pub.publish(msg)

def main(args=None):
    # 這裡必須傳入 sys.argv，節點才會乖乖聽話吃進 use_sim_time:=true
    rclpy.init(args=sys.argv)
    node = ImuTimeFixer()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
