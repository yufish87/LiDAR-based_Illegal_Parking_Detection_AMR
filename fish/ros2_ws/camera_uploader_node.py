#!/usr/bin/env python3
"""
camera_uploader_node.py
ROS 2 Python 節點：
1. 訂閱 /violation/camera_trigger
2. 呼叫 OpenCV (自動偵測 Logitech C270 / 視訊鏡頭) 拍照並轉 Base64
3. 仿射變換計算 Lat/Lon 與 Google Maps 連結
4. OSM Nominatim 逆向地理編碼取得地址
5. 打包 JSON 上傳至 Google Apps Script (Drive + Sheets)
"""

import os
import sys
import time
import json
import base64
import uuid
import logging
from datetime import datetime

import cv2
import numpy as np
import requests

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

# 設定日誌
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# 預設 Google Apps Script Web App URL
GAS_URL = os.environ.get("AMR_GAS_URL", "")

# SLAM 地圖基準點 (Source Points, Pixel [X, Y])
SRC_PTS = np.float32([
    [2854, 4415],
    [3128, 2086],
    [990, 1581]
])

# 對應真實世界基準點 (Destination Points, GPS [Lon, Lat])
DST_PTS = np.float32([
    [121.543250, 25.014694],
    [121.540611, 25.013750],
    [121.541333, 25.011472]
])

# 計算 2x3 仿射變換矩陣 M (Pixel -> GPS)
AFFINE_MAT = cv2.getAffineTransform(SRC_PTS, DST_PTS)


def get_gps_and_url(pixel_x: float, pixel_y: float):
    """將像素座標透過仿射變換轉換為 GPS (Lat, Lon) 並產生 Google Maps URL"""
    pt_pixel = np.array([pixel_x, pixel_y, 1.0], dtype=np.float32)
    pt_gps = AFFINE_MAT.dot(pt_pixel)
    lon, lat = float(pt_gps[0]), float(pt_gps[1])
    maps_url = f"https://www.google.com/maps/search/?api=1&query={lat:.6f},{lon:.6f}"
    return lat, lon, maps_url


def get_osm_address(lat: float, lon: float, timeout_sec: float = 3.0) -> str:
    """呼叫 OpenStreetMap Nominatim API 進行反向地理編碼，取得門牌街道地址"""
    url = f"https://nominatim.openstreetmap.org/reverse?lat={lat:.6f}&lon={lon:.6f}&format=json&zoom=18&addressdetails=1"
    headers = {
        "User-Agent": "NTUST_Violation_Bot/1.0"
    }

    try:
        response = requests.get(url, headers=headers, timeout=timeout_sec)
        if response.status_code == 200:
            data = response.json()
            display_name = data.get("display_name", "")
            return display_name if display_name else "地址解析失敗"
        else:
            return "地址解析失敗"
    except Exception as e:
        logging.error(f"OSM Reverse Geocoding error: {e}")
        return "地址解析失敗"


def capture_image_base64(preferred_camera_id: int = 2, compress_image: bool = False) -> tuple:
    """
    開啟 USB 相機 (Logitech C270) 拍照並轉為 Base64 字串。
    1. 自動偵測 /dev/v4l/by-id/ 中包含 C270 / USB 相機的裝置。
    2. 增加 20 幀熱身，確保自動曝光 (Auto Exposure) 與白平衡穩定收斂，避免過曝。
    3. 不進行畫面 Resize 縮放，保持原生解析度與比例尺，品質設為 95 (高畫質)。
    """
    # 優先自動尋找系統中真正的 Logitech C270 外接相機裝置路徑
    c270_path = None
    by_id_dir = "/dev/v4l/by-id"
    if os.path.exists(by_id_dir):
        for f in os.listdir(by_id_dir):
            if ("C270" in f or "WEBCAM" in f or "usb-" in f) and "HP_True_Vision" not in f:
                if "video-index0" in f:
                    c270_path = os.path.join(by_id_dir, f)
                    logging.info(f"Detected USB camera device via by-id: {f} -> {c270_path}")
                    break

    candidate_sources = []
    if c270_path:
        candidate_sources.append(c270_path)
    
    # 備用索引 (針對本機環境 C270 為 video2)
    candidate_sources += [preferred_camera_id] + [i for i in range(5) if i != preferred_camera_id]
    
    for cam_src in candidate_sources:
        try:
            # 優先使用 V4L2 驅動開啟相機
            cap = cv2.VideoCapture(cam_src, cv2.CAP_V4L2) if isinstance(cam_src, str) else cv2.VideoCapture(cam_src, cv2.CAP_V4L2)
            if not cap.isOpened():
                cap = cv2.VideoCapture(cam_src)
            
            if not cap.isOpened():
                continue

            # 讓感光元件與 Auto Exposure 完全收斂 (20 幀熱身)
            time.sleep(0.5)
            for _ in range(20):
                cap.read()
            
            ret, frame = cap.read()
            cap.release()

            if not ret or frame is None or frame.size == 0:
                logging.warning(f"Camera source '{cam_src}' opened but returned invalid frame. Trying next...")
                continue

            # 成功取得有效畫面
            h, w = frame.shape[:2]
            logging.info(f"Successfully captured FULL RES frame from camera '{cam_src}' (Native Resolution: {w}x{h})")

            # 不壓縮比例尺，保持全解析度；JPEG 品質設為 95 (高清)
            success, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
            if not success:
                return "encode_failed.jpg", ""

            base64_str = base64.b64encode(buffer).decode("utf-8")
            filename = f"photo_{int(time.time())}.jpg"
            return filename, base64_str

        except Exception as e:
            logging.warning(f"Error accessing camera source '{cam_src}': {e}")
            continue

    logging.error("All camera sources failed to capture a valid frame. Sending record without image.")
    return "camera_unavailable.jpg", ""


class CameraUploaderNode(Node):
    def __init__(self):
        super().__init__('camera_uploader_node')

        self.declare_parameter('gas_url', GAS_URL)
        self.declare_parameter('camera_id', 0)

        self.gas_url = self.get_parameter('gas_url').get_parameter_value().string_value
        self.camera_id = self.get_parameter('camera_id').get_parameter_value().integer_value

        self.sub_trigger = self.create_subscription(
            String,
            '/violation/camera_trigger',
            self.cb_trigger,
            10
        )

        self.get_logger().info(f"CameraUploaderNode started. Subscribed to /violation/camera_trigger. GAS endpoint configured: {bool(self.gas_url)}")

    def cb_trigger(self, msg: String):
        self.get_logger().info(f"Received camera trigger: {msg.data}")

        try:
            data = json.loads(msg.data)
        except Exception as e:
            self.get_logger().error(f"Failed to parse JSON trigger payload: {e}")
            return

        vehicle_id = data.get("vehicle_id", "v_unknown")
        zone_name  = data.get("zone_name", "unknown_zone")
        pixel_x    = float(data.get("px", 0.0))
        pixel_y    = float(data.get("py", 0.0))

        # 1. 拍照並轉 Base64
        filename, img_b64 = capture_image_base64(self.camera_id)
        self.get_logger().info(f"Photo captured ({filename}). Base64 payload size: {len(img_b64)} chars.")

        # 2. 座標轉換
        lat, lon, maps_url = get_gps_and_url(pixel_x, pixel_y)

        # 3. 反向地理編碼
        address = get_osm_address(lat, lon)

        # 4. 構建事件與 Payload
        time_prefix = datetime.now().strftime("%Y%m%d%H%M%S")
        short_uuid = uuid.uuid4().hex[:6]
        event_id = f"EVT-{time_prefix}-{short_uuid}"
        timestamp_str = datetime.now().strftime("%Y/%m/%d %H:%M:%S")

        payload = {
            "event_id": event_id,
            "timestamp": timestamp_str,
            "zone_name": zone_name,
            "maps_url": maps_url,
            "address": address,
            "image_filename": filename,
            "image_base64": img_b64
        }

        # 5. 上傳至 GAS
        self.upload_to_gas(payload)

    def upload_to_gas(self, payload: dict, timeout_sec: float = 15.0):
        try:
            self.get_logger().info(f"Sending POST request to GAS for event {payload['event_id']}...")
            response = requests.post(
                self.gas_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=timeout_sec,
                allow_redirects=True
            )
            self.get_logger().info(f"GAS Response Status Code: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    res_json = response.json()
                    if res_json.get("status") == "success":
                        self.get_logger().info(f"Successfully uploaded event: {payload['event_id']} | Photo URL: {res_json.get('photo_url')}")
                    else:
                        self.get_logger().error(f"GAS returned error status: {res_json.get('message')}")
                except Exception:
                    self.get_logger().info(f"GAS Upload Completed. Raw response text: {response.text[:200]}")
            elif response.status_code == 401:
                self.get_logger().error("HTTP 401 Unauthorized! 請確認 GAS 部署權限設定為「所有人 (Anyone)」。")
            else:
                self.get_logger().error(f"HTTP Request failed with status code: {response.status_code}")
        except requests.exceptions.Timeout:
            self.get_logger().error(f"Request to GAS timed out after {timeout_sec}s")
        except Exception as e:
            self.get_logger().error(f"Failed to upload to GAS: {e}")


def main(args=None):
    rclpy.init(args=args)
    node = CameraUploaderNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
