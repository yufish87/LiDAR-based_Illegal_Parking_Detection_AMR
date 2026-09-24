import sys
import threading
import numpy as np

from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, 
                             QHBoxLayout, QVBoxLayout, QLabel, QPushButton)
from PySide6.QtCore import Signal, QObject, QRectF
import pyqtgraph as pg

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped
from nav_msgs.msg import OccupancyGrid

# ==========================================
# 1. Qt 與 ROS 2 跨線程 Signal
# ==========================================
class CommSignals(QObject):
    pose_updated = Signal(float, float)
    map_updated = Signal(object, float, float, float)

# ==========================================
# 2. 容錯型 ROS 2 背景節點
# ==========================================
class NavGuiNode(Node):
    def __init__(self, signals):
        super().__init__('nav_gui_node')
        self.signals = signals

        # 高相容性 QoS 設定
        sensor_qos = QoSProfile(
            depth=10,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE
        )
        map_qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL
        )

        # [1] 訂閱位置 (同時支援兩種數據結構)
        self.sub_pose1 = self.create_subscription(
            PoseWithCovarianceStamped,
            '/localization/pose_with_covariance',
            self.pose_callback,
            sensor_qos
        )
        self.sub_pose2 = self.create_subscription(
            PoseStamped,
            '/pcl_pose',
            self.pose_callback,
            sensor_qos
        )

        # [2] 訂閱地圖 (優先 /map，備用 /global_costmap/costmap)
        self.sub_map = self.create_subscription(
            OccupancyGrid,
            '/map',
            self.map_callback,
            map_qos
        )
        self.sub_costmap = self.create_subscription(
            OccupancyGrid,
            '/global_costmap/costmap',
            self.map_callback,
            sensor_qos
        )

        # [3] 發送導航目標點
        self.pub_goal = self.create_publisher(
            PoseStamped,
            '/goal_pose',
            10
        )

    def pose_callback(self, msg):
        try:
            # 自動判斷訊息格式
            if hasattr(msg, 'pose') and hasattr(msg.pose, 'pose'):
                x = msg.pose.pose.position.x
                y = msg.pose.pose.position.y
            elif hasattr(msg, 'pose') and hasattr(msg.pose, 'position'):
                x = msg.pose.position.x
                y = msg.pose.position.y
            else:
                return

            print(f"✅ [Debug] 成功接收車輛位置: X={x:.2f}, Y={y:.2f}")
            self.signals.pose_updated.emit(x, y)
        except Exception as e:
            print(f"❌ [Error] 位置解析失敗: {e}")

    def map_callback(self, msg):
        try:
            width = msg.info.width
            height = msg.info.height
            resolution = msg.info.resolution
            origin_x = msg.info.origin.position.x
            origin_y = msg.info.origin.position.y

            map_data = np.array(msg.data, dtype=np.int8).reshape((height, width))

            img_data = np.zeros((height, width), dtype=np.uint8)
            img_data[map_data == 0] = 255     # 可通行區域：白色
            img_data[map_data > 0] = 0        # 障礙物/牆壁：黑色
            img_data[map_data == -1] = 180    # 未知區域：灰色

            print(f"🗺️ [Debug] 成功接收地圖: {width}x{height} (解析度: {resolution})")
            self.signals.map_updated.emit(img_data, resolution, origin_x, origin_y)
        except Exception as e:
            print(f"❌ [Error] 地圖解析失敗: {e}")

    def send_goal(self, x, y):
        msg = PoseStamped()
        msg.header.frame_id = 'map'
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.pose.position.x = float(x)
        msg.pose.position.y = float(y)
        msg.pose.orientation.w = 1.0

        self.pub_goal.publish(msg)
        print(f"🚀 已發送導航目標至: X={x:.2f}, Y={y:.2f}")

# ==========================================
# 3. PySide6 主介面
# ==========================================
class MainWindow(QMainWindow):
    def __init__(self, ros_node, signals):
        super().__init__()
        self.ros_node = ros_node
        self.signals = signals

        self.setWindowTitle("AGX NAVIGATION GUI")
        self.resize(1000, 600)

        self.target_x = None
        self.target_y = None

        main_widget = QWidget()
        layout = QHBoxLayout(main_widget)
        self.setCentralWidget(main_widget)

        # 左側控制面板
        panel = QVBoxLayout()
        self.lbl_curr = QLabel("Current Position: (等待 ROS 數據...)")
        self.lbl_goal = QLabel("Set Goal: (點擊右側地圖)")

        font = self.lbl_curr.font()
        font.setPointSize(11)
        self.lbl_curr.setFont(font)
        self.lbl_goal.setFont(font)

        self.btn_send = QPushButton("Set Goal")
        self.btn_send.setFixedHeight(45)
        self.btn_send.setStyleSheet("background-color: #007ACC; color: white; font-weight: bold; font-size: 14px;")
        self.btn_send.clicked.connect(self.on_send_clicked)

        panel.addWidget(self.lbl_curr)
        panel.addWidget(self.lbl_goal)
        panel.addWidget(self.btn_send)
        panel.addStretch()

        # 右側 2D 畫布
        self.plot_widget = pg.PlotWidget(title="2D 導航地圖")
        self.plot_widget.showGrid(x=True, y=True)
        self.plot_widget.setAspectLocked(True)

        self.map_item = pg.ImageItem()
        self.map_item.setZValue(-10)
        self.plot_widget.addItem(self.map_item)

        self.car_item = self.plot_widget.plot([], [], pen=None, symbol='o', symbolBrush='r', symbolSize=14)
        self.car_item.setZValue(10)

        self.goal_item = self.plot_widget.plot([], [], pen=None, symbol='+', symbolBrush='g', symbolSize=18)
        self.goal_item.setZValue(10)

        self.plot_widget.scene().sigMouseClicked.connect(self.on_map_clicked)

        layout.addLayout(panel, stretch=1)
        layout.addWidget(self.plot_widget, stretch=3)

        self.signals.pose_updated.connect(self.update_car_pose)
        self.signals.map_updated.connect(self.update_map)

    def update_car_pose(self, x, y):
        self.lbl_curr.setText(f"當前位置: X={x:.2f}, Y={y:.2f}")
        self.car_item.setData([x], [y])

    def update_map(self, img_data, resolution, origin_x, origin_y):
        self.map_item.setImage(img_data.T)
        width_m = img_data.shape[1] * resolution
        height_m = img_data.shape[0] * resolution
        self.map_item.setRect(QRectF(origin_x, origin_y, width_m, height_m))

    def on_map_clicked(self, event):
        pos = event.scenePos()
        if self.plot_widget.plotItem.sceneBoundingRect().contains(pos):
            mouse_point = self.plot_widget.plotItem.vb.mapSceneToView(pos)
            self.target_x = mouse_point.x()
            self.target_y = mouse_point.y()

            self.lbl_goal.setText(f"設定目標: X={self.target_x:.2f}, Y={self.target_y:.2f}")
            self.goal_item.setData([self.target_x], [self.target_y])

    def on_send_clicked(self):
        if self.target_x is not None and self.target_y is not None:
            self.ros_node.send_goal(self.target_x, self.target_y)
        else:
            self.lbl_goal.setText("⚠️ 請先在地圖上點擊選取目標點！")

# ==========================================
# 4. 主程式啟動點
# ==========================================
def main():
    rclpy.init()
    signals = CommSignals()
    ros_node = NavGuiNode(signals)

    ros_thread = threading.Thread(target=rclpy.spin, args=(ros_node,), daemon=True)
    ros_thread.start()

    app = QApplication(sys.argv)
    window = MainWindow(ros_node, signals)
    window.show()

    sys.exit(app.exec())

if __name__ == '__main__':
    main()
