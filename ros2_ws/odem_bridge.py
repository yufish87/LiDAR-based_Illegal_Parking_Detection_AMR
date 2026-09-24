import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from nav_msgs.msg import Odometry
from geometry_msgs.msg import TransformStamped, Quaternion, Twist
import tf2_ros
import serial
import math
import numpy as np

class OdomBridge(Node):
    def __init__(self):
        super().__init__('odom_bridge')
        self.group = ReentrantCallbackGroup()
        
        # --- 參數設定 ---
        self.declare_parameter('wheel_diameter', 0.26)
        self.declare_parameter('wheel_base', 0.85)
        self.declare_parameter('ppr', 1600)
        
        self.D = self.get_parameter('wheel_diameter').value
        self.L = self.get_parameter('wheel_base').value
        self.PPR = self.get_parameter('ppr').value
        self.dist_per_pulse = (math.pi * self.D) / self.PPR

        # --- Serial (設定為完全非阻塞) ---
        try:
            self.ser = serial.Serial('/dev/ttyUSB0', 115200, timeout=0)
        except Exception as e:
            self.get_logger().error(f"Serial Error: {e}")

        # --- ROS 2 發佈器 ---
        self.odom_pub = self.create_publisher(Odometry, 'odom', 10)
        self.tf_broadcaster = tf2_ros.TransformBroadcaster(self)
        self.cmd_sub = self.create_subscription(Twist, 'cmd_vel', self.cmd_callback, 10)

        # 狀態變數 (由讀取 Thread 更新)
        self.x, self.y, self.th = 0.0, 0.0, 0.0
        self.vx, self.vth = 0.0, 0.0
        self.last_l_pulse, self.last_r_pulse = 0, 0
        self.last_time = self.get_clock().now()

        # --- 雙定時器架構 ---
        # 1. 專門讀資料 (50Hz)
        self.read_timer = self.create_timer(0.02, self.read_serial_callback, callback_group=self.group)
        # 2. 專門發布 TF (50Hz) - 這保證 tf2_echo 頻率
        self.pub_timer = self.create_timer(0.02, self.publish_callback, callback_group=self.group)

    def cmd_callback(self, msg):
        cmd_str = f"V{msg.linear.x:.2f},{msg.angular.z:.2f}\n"
        self.ser.write(cmd_str.encode('utf-8')) 

    def read_serial_callback(self):
        """ 專責讀取 Serial，更新座標變數 """
        while self.ser.in_waiting > 0:
            try:
                line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                if line.startswith('P'):
                    parts = line[1:].split(',')
                    if len(parts) >= 2:
                        l_pulse, r_pulse = int(parts[0]), int(parts[1])
                        
                        dl = (l_pulse - self.last_l_pulse) * self.dist_per_pulse
                        dr = (r_pulse - self.last_r_pulse) * self.dist_per_pulse
                        self.last_l_pulse, self.last_r_pulse = l_pulse, r_pulse

                        d_center = (dr + dl) / 2.0
                        # 4.5 倍率視情況調整
                        d_th = (dr - dl) / self.L

                        curr_time = self.get_clock().now()
                        dt = (curr_time - self.last_time).nanoseconds / 1e9
                        
                        if dt > 0:
                            avg_th = self.th + (d_th / 2.0)
                            self.x += d_center * math.cos(avg_th)
                            self.y += d_center * math.sin(avg_th)
                            self.th += d_th
                            self.vx, self.vth = d_center/dt, d_th/dt
                            self.last_time = curr_time
            except:
                pass

    def publish_callback(self):
        """ 專責發布，不准做任何可能卡住的事 """
        now = self.get_clock().now()
        q = self.euler_to_quaternion(0, 0, self.th)

        # 發佈 TF
        t = TransformStamped()
        t.header.stamp = now.to_msg()
        t.header.frame_id = 'odom'
        t.child_frame_id = 'base_link'
        t.transform.translation.x, t.transform.translation.y = self.x, self.y
        t.transform.rotation = q
        self.tf_broadcaster.sendTransform(t)

        # 發佈 Odom Topic
        odom = Odometry()
        odom.header.stamp = now.to_msg()
        odom.header.frame_id, odom.child_frame_id = 'odom', 'base_link'
        odom.pose.pose.position.x, odom.pose.pose.position.y = self.x, self.y
        odom.pose.pose.orientation = q
        odom.twist.twist.linear.x = self.vx
        odom.twist.twist.angular.z = self.vth
        self.odom_pub.publish(odom)

    def euler_to_quaternion(self, roll, pitch, yaw):
        qx = np.sin(roll/2) * np.cos(pitch/2) * np.cos(yaw/2) - np.cos(roll/2) * np.sin(pitch/2) * np.sin(yaw/2)
        qy = np.cos(roll/2) * np.sin(pitch/2) * np.cos(yaw/2) + np.sin(roll/2) * np.cos(pitch/2) * np.sin(yaw/2)
        qz = np.cos(roll/2) * np.cos(pitch/2) * np.sin(yaw/2) - np.sin(roll/2) * np.sin(pitch/2) * np.cos(yaw/2)
        qw = np.cos(roll/2) * np.cos(pitch/2) * np.cos(yaw/2) + np.sin(roll/2) * np.sin(pitch/2) * np.sin(yaw/2)
        return Quaternion(x=qx, y=qy, z=qz, w=qw)

def main():
    rclpy.init()
    node = OdomBridge()
    # 使用多執行緒 Executor，讓兩個 Timer 並行
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
