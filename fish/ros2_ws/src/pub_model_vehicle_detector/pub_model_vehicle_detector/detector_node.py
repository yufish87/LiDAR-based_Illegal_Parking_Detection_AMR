#!/usr/bin/env python3

import os
import sys

# 強制限制所有底層 C++ / OpenMP 函式庫的 CPU 使用率，防止 VoxelGenerator / spconv 吃光所有 CPU
os.environ["OMP_NUM_THREADS"] = "2"
os.environ["MKL_NUM_THREADS"] = "2"
os.environ["OPENBLAS_NUM_THREADS"] = "2"
os.environ["VECLIB_MAXIMUM_THREADS"] = "2"
os.environ["NUMEXPR_NUM_THREADS"] = "2"

import numpy as np
import torch
import warnings

# 限制 PyTorch 的 CPU 執行緒數量，避免吃光 CPU 導致 Localizer 被 starvation
torch.set_num_threads(2)
# 抑制 PyTorch 相關的 FutureWarning，避免干擾 log
warnings.filterwarnings("ignore", category=FutureWarning)
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import PointCloud2
from vision_msgs.msg import Detection3DArray, Detection3D, BoundingBox3D
from geometry_msgs.msg import Pose, Point, Quaternion, PoseStamped
from visualization_msgs.msg import MarkerArray, Marker
from std_msgs.msg import Header
import tf2_ros
import tf2_geometry_msgs  # noqa: registers PoseStamped transform support
from tf2_geometry_msgs import do_transform_pose

# 新增 OpenPCDet 的路徑至 Python 搜尋路徑中 (動態支援主機與 Docker)
pcdet_path = '/home/ntust/fish/ros2_ws/OpenPCDet' if os.path.exists('/home/ntust/fish/ros2_ws/OpenPCDet') else '/opt/OpenPCDet'
sys.path.append(pcdet_path)

from pcdet.config import cfg as pcdet_cfg, cfg_from_yaml_file
from pcdet.models import build_network, load_data_to_gpu
from pcdet.utils import common_utils
from pcdet.datasets import DatasetTemplate


class ROSDemoDataset(DatasetTemplate):
    """
    自訂一個簡單的 Dataset 類別繼承 OpenPCDet 的 DatasetTemplate，
    以便直接利用 OpenPCDet 內建的點雲前處理與 Voxel 劃分管道。
    """
    def __init__(self, dataset_cfg, class_names, training=False, logger=None):
        super().__init__(
            dataset_cfg=dataset_cfg, class_names=class_names, training=training, logger=logger
        )

    def prepare_point_cloud(self, points):
        """
        將輸入的點雲轉換為 OpenPCDet 預處理後的字典格式
        points: [N, 4] (X, Y, Z, Intensity)
        """
        input_dict = {
            'points': points,
            'frame_id': 'base_link',
        }
        data_dict = self.prepare_data(data_dict=input_dict)
        return data_dict


class PubModelVehicleDetector(Node):
    def __init__(self):
        super().__init__('pub_model_vehicle_detector')
        self.get_logger().info(f"Loaded detector_node.py from: {__file__}")

        # === 參數設定 ===
        default_config = '/home/ntust/fish/ros2_ws/OpenPCDet/tools/cfgs/nuscenes_models/cbgs_pp_multihead.yaml' \
            if os.path.exists('/home/ntust/fish/ros2_ws/OpenPCDet') else '/opt/OpenPCDet/tools/cfgs/nuscenes_models/cbgs_pp_multihead.yaml'
        default_checkpoint = '/home/ntust/fish/ros2_ws/weights/pointpillar_nuscenes_50e.pth' \
            if os.path.exists('/home/ntust/fish/ros2_ws/weights/pointpillar_nuscenes_50e.pth') else '/workspace/ros2_ws/weights/pointpillar_nuscenes_50e.pth'

        self.declare_parameter('config_path', default_config)
        self.declare_parameter('checkpoint_path', default_checkpoint)
        self.declare_parameter('score_threshold', 0.1)
        self.declare_parameter('score_threshold_car', 0.1)
        self.declare_parameter('score_threshold_truck', 0.1)
        self.declare_parameter('score_threshold_bus', 0.1)
        self.declare_parameter('point_cloud_topic', '/ouster/points')
        self.declare_parameter('output_topic', '/detected_vehicles')
        self.declare_parameter('marker_topic', '/detected_vehicles_markers')
        self.declare_parameter('target_frame', 'base_link') # 對齊 base_link
        self.declare_parameter('map_scale_factor', 3.0) # 地圖比例縮放因子
        
        # 是否強制將點雲時間戳與當下系統時間同步 (實車防止 TF Extrapolation Error)
        self.declare_parameter('sync_time_stamp', True)
        
        # ROI 動態參數 (預設參考 Training_Pipeline.m)
        self.declare_parameter('roi_x_min', -10.0)
        self.declare_parameter('roi_x_max', 15.0)
        self.declare_parameter('roi_y_min', -12.0)
        self.declare_parameter('roi_y_max', 12.0)
        self.declare_parameter('roi_z_min', -2.5)
        self.declare_parameter('roi_z_max', 3.0)
        self.declare_parameter('z_offset_correction', 0.57) # 修正光達高度偏差 (nuScenes車頂 1.84m - 當前實體光達高度 1.12m = 0.72m)

        config_path = self.get_parameter('config_path').get_parameter_value().string_value
        checkpoint_path = self.get_parameter('checkpoint_path').get_parameter_value().string_value
        self.score_threshold = self.get_parameter('score_threshold').get_parameter_value().double_value
        pc_topic = self.get_parameter('point_cloud_topic').get_parameter_value().string_value
        output_topic = self.get_parameter('output_topic').get_parameter_value().string_value
        marker_topic = self.get_parameter('marker_topic').get_parameter_value().string_value
        self.target_frame = self.get_parameter('target_frame').get_parameter_value().string_value
        self.map_scale_factor = self.get_parameter('map_scale_factor').get_parameter_value().double_value

        self.get_logger().info(f"Loading config from: {config_path}")
        self.get_logger().info(f"Loading weights from: {checkpoint_path}")

        # === 載入 OpenPCDet 模型 ===
        self.logger = common_utils.create_logger()
        cfg_from_yaml_file(config_path, pcdet_cfg)

        # 建立預處理器
        self.demo_dataset = ROSDemoDataset(
            dataset_cfg=pcdet_cfg.DATA_CONFIG,
            class_names=pcdet_cfg.CLASS_NAMES,
            training=False,
            logger=self.logger
        )

        # 建立模型並載入權重
        self.model = build_network(
            model_cfg=pcdet_cfg.MODEL,
            num_class=len(pcdet_cfg.CLASS_NAMES),
            dataset=self.demo_dataset
        )
        self.model.load_params_from_file(filename=checkpoint_path, to_cpu=False, logger=self.logger)
        self.model.cuda()
        self.model.eval()

        self.class_names = pcdet_cfg.CLASS_NAMES
        self.get_logger().info(f"Model loaded successfully. Classes: {self.class_names}")

        from rclpy.qos import qos_profile_sensor_data
        self.sub_pc = self.create_subscription(PointCloud2, pc_topic, self.cloud_callback, qos_profile_sensor_data)
        self.pub_detect = self.create_publisher(Detection3DArray, output_topic, 10)
        self.pub_marker = self.create_publisher(MarkerArray, marker_topic, 10)
        self.pub_roi = self.create_publisher(Marker, '/roi_boundary', 10)

        # === TF2 ===
        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)

        # === 3D Centroid Tracker 狀態 ===
        # 每條 track: {'id': int, 'cx': float, 'cy': float, 'cz': float,
        #              'box': np.ndarray[7], 'score': float, 'class_name': str,
        #              'hits': int, 'age': int}
        self.tracks = []
        self.next_track_id = 0
        self.TRACK_DIST_THRESH = 2.0   # BEV 距離門檻 (m)，用於關聯偵測框與軌跡
        self.TRACK_MAX_AGE = 3         # 連續幾幀未匹配即刪除軌跡
        self.TRACK_MIN_HITS = 5       # 連續幾幀命中才正式發布
        self.NMS_DIST_THRESH = 1.5     # 同幀 Centroid NMS 距離門檻 (m)
        self.confirmed_ids = set()     # 已印過 NEW VEHICLE 的 track id 集合
        self.last_stamp = None         # 用於計算前後幀時間差
        self.last_processed_stamp = 0.0# 用於限制處理頻率

        self.get_logger().info("Scenario 3 Pre-trained PointPillars Node initialized.")

    def cloud_callback(self, msg):
        # 1. 實車環境下，強制重寫時間戳避免 TF 時間不同步錯誤
        if self.get_parameter('sync_time_stamp').get_parameter_value().bool_value:
            msg.header.stamp = self.get_clock().now().to_msg()
            
        # 計算時間差
        curr_stamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9

        # 不限制偵測頻率，對每一幀點雲皆進行即時推理與檢測
        self.last_processed_stamp = curr_stamp

        # 2. 計算前後幀的時間差以動態調整 Tracker 距離門檻
        if self.last_stamp is not None:
            dt = curr_stamp - self.last_stamp
            if 0.0 < dt < 2.0:
                # 假設車與我方相對速度最大為 15.0 m/s，丟幀/降頻時動態放寬距離門檻
                # 基礎門檻放寬到 3.5 米 (解決框飄移漏檢)，最大放寬到 8.0 米
                self.TRACK_DIST_THRESH = max(3.5, min(8.0, 15.0 * dt))
            else:
                self.TRACK_DIST_THRESH = 3.5
        else:
            self.TRACK_DIST_THRESH = 3.5
        self.last_stamp = curr_stamp

        # 1. 將 PointCloud2 轉為 numpy array
        points = self.convert_pc2_to_numpy(msg)
        if points is None or len(points) == 0:
            return

        # 2. 點雲適應前處理 (Domain Adaptation)
        # Ouster 的反射率 (reflectivity) 數值通常很大 (0~255 或更高)，而 nuScenes 訓練時強度範圍是 [0, 1] 或是已進行歸一化。
        # 我們將強度欄位除以 255.0，並限制在 [0.0, 1.0] 區間
        points[:, 3] = np.clip(points[:, 3] / 255.0, 0.0, 1.0)

        # 點雲 ROI 過濾 (動態參數)
        x_min, x_max, y_min, y_max, z_min, z_max = self.get_roi_limits()
        roi_mask = (points[:, 0] >= x_min) & (points[:, 0] <= x_max) & \
                   (points[:, 1] >= y_min) & (points[:, 1] <= y_max) & \
                   (points[:, 2] >= z_min) & (points[:, 2] <= z_max)
        points = points[roi_mask]

        # 幾何高度修正 (Z-offset Correction)：
        # 手動將點雲 Z 軸壓低，模擬車頂光達，以適應 nuScenes 預訓練模型
        self.z_offset_correction = self.get_parameter('z_offset_correction').get_parameter_value().double_value
        points[:, 2] -= self.z_offset_correction

        # 發布 ROI 邊界框給 RViz 視覺化
        self.publish_roi_boundary(msg.header)

        # 補上全為 0 的第 5 維 (timestamp)，以符合 nuScenes 模型預期的 5 維輸入
        timestamps = np.zeros((points.shape[0], 1), dtype=np.float32)
        points = np.hstack((points, timestamps))

        # 3. 呼叫 OpenPCDet 預處理管道 (Voxelization 等)
        with torch.no_grad():
            data_dict = self.demo_dataset.prepare_point_cloud(points)
            # 將資料打包為 Batch = 1 並搬移到 GPU
            data_dict = self.demo_dataset.collate_batch([data_dict])
            load_data_to_gpu(data_dict)

            # 4. 執行模型推論
            pred_dicts, _ = self.model(data_dict)

        # 5. 解析與發布預測結果
        # 直接使用點雲的原始/對齊後的時間戳，不重新覆寫為系統時間，保證與定位 TF 時間戳完全同步
        self.publish_detections(msg.header, pred_dicts[0])

    def convert_pc2_to_numpy(self, msg):
        """
        高效率地將 PointCloud2 轉換為 [N, 4] (X, Y, Z, Intensity) numpy 陣列
        """
        # ROS 2 PointField 資料類型映射表
        ros_to_numpy_type = {
            1: np.int8,
            2: np.uint8,
            3: np.int16,
            4: np.uint16,
            5: np.int32,
            6: np.uint32,
            7: np.float32,
            8: np.float64
        }

        try:
            # 排序欄位確保依 offset 對齊
            sorted_fields = sorted(msg.fields, key=lambda f: f.offset)
            dtype_spec = []
            current_offset = 0
            
            for i, f in enumerate(sorted_fields):
                if f.offset > current_offset:
                    dtype_spec.append((f'pad_{i}', f'|V{f.offset - current_offset}'))
                    current_offset = f.offset
                
                num_bytes = 4
                if f.datatype in [1, 2]: num_bytes = 1
                elif f.datatype in [3, 4]: num_bytes = 2
                elif f.datatype in [5, 6, 7]: num_bytes = 4
                elif f.datatype == 8: num_bytes = 8
                
                dtype_spec.append((f.name, ros_to_numpy_type[f.datatype]))
                current_offset += num_bytes
                
            if msg.point_step > current_offset:
                dtype_spec.append(('pad_end', f'|V{msg.point_step - current_offset}'))

            pc_arr = np.frombuffer(msg.data, dtype=np.dtype(dtype_spec))
            
            x = pc_arr['x'].astype(np.float32)
            y = pc_arr['y'].astype(np.float32)
            z = pc_arr['z'].astype(np.float32)
            
            if 'intensity' in pc_arr.dtype.names:
                intensity = pc_arr['intensity'].astype(np.float32)
            elif 'reflectivity' in pc_arr.dtype.names:
                intensity = pc_arr['reflectivity'].astype(np.float32)
            else:
                intensity = np.zeros_like(x)
                
            # 過濾掉無效點 (NaN / Inf)
            valid_mask = np.isfinite(x) & np.isfinite(y) & np.isfinite(z)
            return np.stack([x[valid_mask], y[valid_mask], z[valid_mask], intensity[valid_mask]], axis=1)

        except Exception as e:
            self.get_logger().error(f"Failed to parse PointCloud2: {str(e)}")
            return None

    def _centroid_nms(self, detections):
        """
        同幀 Centroid NMS：若兩個偵測框 BEV 距離 < NMS_DIST_THRESH 且類別相同，
        保留 score 較高者。
        detections: list of (box[7], score, class_name)
        returns: 過濾後的 list
        """
        if not detections:
            return []
        # 依 score 降冪排列
        detections = sorted(detections, key=lambda d: d[1], reverse=True)
        keep = []
        suppressed = set()
        for i, (box_i, score_i, cls_i) in enumerate(detections):
            if i in suppressed:
                continue
            keep.append((box_i, score_i, cls_i))
            for j in range(i + 1, len(detections)):
                if j in suppressed:
                    continue
                box_j, score_j, cls_j = detections[j]
                if cls_j != cls_i:
                    continue
                dist = np.sqrt((box_i[0] - box_j[0])**2 + (box_i[1] - box_j[1])**2)
                if dist < self.NMS_DIST_THRESH:
                    suppressed.add(j)
        return keep

    def _update_tracks(self, detections):
        """
        以貪婪最鄰近匹配更新 Centroid Tracker。
        detections: list of (box[7], score, class_name)
        """
        # 對每個軌跡找最近的偵測框
        matched_det_idx = set()
        for track in self.tracks:
            best_dist = self.TRACK_DIST_THRESH
            best_idx = -1
            for j, (box, score, cls) in enumerate(detections):
                if j in matched_det_idx:
                    continue
                # 移除嚴格的 class_name 檢查，因為模型常常在 car / truck 之間跳動而導致軌跡中斷漏檢
                # 只需距離夠近即視為同一台車
                dist = np.sqrt((box[0] - track['cx'])**2 + (box[1] - track['cy'])**2)
                if dist < best_dist:
                    best_dist = dist
                    best_idx = j

            if best_idx >= 0:
                box, score, cls = detections[best_idx]
                track['cx'] = box[0]
                track['cy'] = box[1]
                track['cz'] = box[2]
                track['box'] = box
                track['score'] = score
                track['class_name'] = cls  # 更新為當前幀判定的類別
                track['hits'] += 1
                track['age'] = 0
                matched_det_idx.add(best_idx)
            else:
                track['age'] += 1

        # 刪除過期軌跡（印出 LOST 訊息）
        for t in self.tracks:
            if t['age'] > self.TRACK_MAX_AGE and t['id'] in self.confirmed_ids:
                self.get_logger().info(
                    f"[LOST]  #{t['id']:>3} {t['class_name']:<6}  "
                    f"x={t['cx']:+.1f} y={t['cy']:+.1f}  "
                    f"total_hits={t['hits']}"
                )
                self.confirmed_ids.discard(t['id'])
        self.tracks = [t for t in self.tracks if t['age'] <= self.TRACK_MAX_AGE]

        # 對未匹配的偵測框建立新軌跡
        for j, (box, score, cls) in enumerate(detections):
            if j not in matched_det_idx:
                self.tracks.append({
                    'id': self.next_track_id,
                    'cx': box[0],
                    'cy': box[1],
                    'cz': box[2],
                    'box': box,
                    'score': score,
                    'class_name': cls,
                    'hits': 1,
                    'age': 0,
                })
                self.next_track_id += 1

    def publish_detections(self, header, pred_dict):
        # 建立 ROS 2 發布訊息
        detection_array = Detection3DArray()
        detection_array.header = Header()
        detection_array.header.stamp = header.stamp
        detection_array.header.frame_id = header.frame_id

        marker_array = MarkerArray()

        boxes = pred_dict['pred_boxes'].cpu().numpy()     # [M, 7] (x, y, z, dx, dy, dz, heading)

        # 還原 Z 軸高度回到推車座標系中發布
        self.z_offset_correction = self.get_parameter('z_offset_correction').get_parameter_value().double_value
        boxes[:, 2] += self.z_offset_correction

        scores = pred_dict['pred_scores'].cpu().numpy()   # [M]
        labels = pred_dict['pred_labels'].cpu().numpy()   # [M]

        score_threshold = self.get_parameter('score_threshold').get_parameter_value().double_value
        score_threshold_car = self.get_parameter('score_threshold_car').get_parameter_value().double_value
        score_threshold_truck = self.get_parameter('score_threshold_truck').get_parameter_value().double_value
        score_threshold_bus = self.get_parameter('score_threshold_bus').get_parameter_value().double_value
        self.get_logger().info(
            f"Filtering detections (car: {score_threshold_car}, truck: {score_threshold_truck}, bus: {score_threshold_bus})",
            throttle_duration_sec=10.0
        )

        # ── 第一階段：幾何尺寸 & 類別過濾 ──────────────────────────────
        x_min, x_max, y_min, y_max, z_min, z_max = self.get_roi_limits()
        candidates = []  # list of (box[7], score, class_name)
        for i in range(len(boxes)):
            box = boxes[i]
            if not (x_min <= box[0] <= x_max and y_min <= box[1] <= y_max and z_min <= box[2] <= z_max):
                continue

            label = labels[i]
            class_name = self.class_names[label - 1]

            if class_name not in ['car', 'truck', 'bus']:
                continue

            score = scores[i]
            # 根據類別套用個別的 score 門檻
            if class_name == 'car' and score < score_threshold_car:
                continue
            elif class_name == 'truck' and score < score_threshold_truck:
                continue
            elif class_name == 'bus' and score < score_threshold_bus:
                continue
            elif class_name not in ['car', 'truck', 'bus'] and score < score_threshold:
                continue

            dx, dy, dz = box[3], box[4], box[5]

            # 1. 排除過矮的物體（如矮花圃，正常車輛高度通常 > 1.15m）
            if dz < 1.15:
                continue

            # 2. 排除寬度顯著大於長度的橫向狹長物體（如並排摩托車、橫向整排花圃）
            if dy > dx * 1.25:
                continue

            # 3. 排除圓形或正方形的聚類誤判（如人群、圓形花圃）。真實車輛必然是長條形。
            # 要求長度 (dx) 必須是寬度 (dy) 的 1.3 倍以上
            if dx < dy * 1.3:
                continue

            # 4. 針對個別類別的常識幾何約束
            if class_name == 'car':
                # 台灣常見轎車與 Veryca 小貨車長度皆大於 3.3m，寬度在 1.4m ~ 2.2m 之間，高度大於 1.30m
                if dy > 2.2 or dy < 1.4 or dx < 3.3 or dz < 1.30:
                    continue
            elif class_name == 'truck':
                if dy > 2.8 or dx < 4.0:
                    continue
            elif class_name == 'bus':
                if dy > 3.0 or dx < 6.0:
                    continue

            # 5. 車輛朝向與行進方向 (X軸) 的夾角約束
            # 只保留與我們行進方向平行（夾角小於 45 度）的車輛，排除橫向/打橫的誤判框
            yaw = box[6]
            angle_to_x = np.abs(yaw)
            # 正規化到 [0, pi/2] 代表與 X 軸的最小銳角
            if angle_to_x > np.pi / 2:
                angle_to_x = np.pi - angle_to_x
            
            # 夾角大於 45 度 (0.785 弧度) 則視為垂直於我方，進行過濾
            if angle_to_x > 0.785:
                continue

            candidates.append((box, score, class_name))

        # ── 第二階段：同幀 Centroid NMS（抑制雙框）──────────────────────
        candidates = self._centroid_nms(candidates)

        # ── 第三階段：3D Centroid Tracker 更新 ──────────────────────────
        self._update_tracks(candidates)

        # ── 第四階段：只發布連續命中 >= TRACK_MIN_HITS 的軌跡 ────────────
        from vision_msgs.msg import ObjectHypothesisWithPose
        active_confirmed = []
        for track in self.tracks:
            if track['hits'] < self.TRACK_MIN_HITS:
                continue

            # 第一次確認時印出 NEW VEHICLE
            if track['id'] not in self.confirmed_ids:
                self.confirmed_ids.add(track['id'])
                box = track['box']
                self.get_logger().info(
                    f"[NEW VEHICLE] #{track['id']:>3} {track['class_name']:<6}  "
                    f"x={box[0]:+.1f} y={box[1]:+.1f} z={box[2]:+.1f}  "
                    f"score={track['score']:.2f}"
                )

            active_confirmed.append(track)

        # 每幀印一次當前確認車輛摘要（throttle 1 秒）
        if active_confirmed:
            summary = "  |  ".join(
                f"#{t['id']} {t['class_name']}(x={t['cx']:+.1f},y={t['cy']:+.1f}) hits={t['hits']}"
                for t in active_confirmed
            )
            self.get_logger().info(f"[ACTIVE] {summary}", throttle_duration_sec=1.0)

        for track in active_confirmed:
            box = track['box']
            score = track['score']
            class_name = track['class_name']
            track_id = track['id']

            # 填充 Detection3D
            det = Detection3D()
            det.header = detection_array.header

            bbox = BoundingBox3D()
            bbox.center.position.x = float(box[0])
            bbox.center.position.y = float(box[1])
            bbox.center.position.z = float(box[2])

            q = yaw_to_quaternion(box[6])
            bbox.center.orientation.x = q[0]
            bbox.center.orientation.y = q[1]
            bbox.center.orientation.z = q[2]
            bbox.center.orientation.w = q[3]

            bbox.size.x = float(box[3])
            bbox.size.y = float(box[4])
            bbox.size.z = float(box[5])
            det.bbox = bbox

            # 嘗試將 base_link 座標轉換到 map 座標系，產生穩定的 v_gx_gy ID
            # 使用 Time(0) 查詢最新可用的 TF，避免點雲時間戳與 TF buffer 不同步導致失敗
            veh_id = f"#{track_id}"
            try:
                ps = PoseStamped()
                ps.header.frame_id = detection_array.header.frame_id
                ps.header.stamp = rclpy.time.Time().to_msg()  # Time(0) = 最新可用
                ps.pose = bbox.center
                ps_map = self.tf_buffer.transform(ps, 'map', timeout=rclpy.duration.Duration(seconds=0.05))
                mx = ps_map.pose.position.x
                my = ps_map.pose.position.y
                gx = int(round(mx))
                gy = int(round(my))
                veh_id = f"v_{gx}_{gy}"
            except Exception as e:
                self.get_logger().warn(
                    f"TF transform failed: {e}",
                    throttle_duration_sec=3.0)

            if hasattr(det, 'id'):
                det.id = veh_id

            hyp = ObjectHypothesisWithPose()
            if hasattr(hyp, 'hypothesis'):
                hyp.hypothesis.class_id = class_name
                hyp.hypothesis.score = float(score)
            else:
                if hasattr(hyp, 'id'):
                    try:
                        hyp.id = class_name
                    except Exception:
                        hyp.id = int(label)
                if hasattr(hyp, 'score'):
                    hyp.score = float(score)
            det.results.append(hyp)
            detection_array.detections.append(det)

            # 立方體 Marker（ID = track_id * 2，跨幀覆蓋舊框）
            marker = Marker()
            marker.header = detection_array.header
            marker.ns = "detected_vehicles"
            marker.id = track_id * 2
            marker.type = Marker.CUBE
            marker.action = Marker.ADD
            
            marker.pose.position.x = bbox.center.position.x
            marker.pose.position.y = bbox.center.position.y
            marker.pose.position.z = bbox.center.position.z
            marker.pose.orientation = bbox.center.orientation

            marker.scale.x = bbox.size.x
            marker.scale.y = bbox.size.y
            marker.scale.z = bbox.size.z
            marker.color.r = 0.0
            marker.color.g = 1.0
            marker.color.b = 0.0
            marker.color.a = 0.4
            marker.lifetime = rclpy.duration.Duration(seconds=0.5).to_msg()
            marker_array.markers.append(marker)

            # 文字 Marker（ID = track_id * 2 + 1）
            text_marker = Marker()
            text_marker.header = detection_array.header
            text_marker.ns = "detected_labels"
            text_marker.id = track_id * 2 + 1
            text_marker.type = Marker.TEXT_VIEW_FACING
            text_marker.action = Marker.ADD
            
            text_marker.pose.position.x = bbox.center.position.x
            text_marker.pose.position.y = bbox.center.position.y
            text_marker.pose.position.z = bbox.center.position.z + (bbox.size.z / 2.0) + 0.5
            text_marker.pose.orientation = bbox.center.orientation

            text_marker.scale.z = 0.5
            text_marker.color.r = 1.0
            text_marker.color.g = 1.0
            text_marker.color.b = 1.0
            text_marker.color.a = 1.0
            text_marker.text = f"{veh_id} {class_name} ({score:.2f})"
            text_marker.lifetime = rclpy.duration.Duration(seconds=0.5).to_msg()
            marker_array.markers.append(text_marker)

        self.pub_detect.publish(detection_array)
        self.pub_marker.publish(marker_array)

    def get_roi_limits(self):
        """取得當前參數設定的 ROI 限制"""
        return (
            self.get_parameter('roi_x_min').get_parameter_value().double_value,
            self.get_parameter('roi_x_max').get_parameter_value().double_value,
            self.get_parameter('roi_y_min').get_parameter_value().double_value,
            self.get_parameter('roi_y_max').get_parameter_value().double_value,
            self.get_parameter('roi_z_min').get_parameter_value().double_value,
            self.get_parameter('roi_z_max').get_parameter_value().double_value
        )

    def publish_roi_boundary(self, header):
        """在 RViz 中繪製半透明的 ROI 立方體邊界"""
        x_min, x_max, y_min, y_max, z_min, z_max = self.get_roi_limits()
        marker = Marker()
        marker.header = header
        marker.ns = "roi_boundary"
        marker.id = 9999
        marker.type = Marker.CUBE
        marker.action = Marker.ADD
        
        marker.pose.position.x = (x_max + x_min) / 2.0
        marker.pose.position.y = (y_max + y_min) / 2.0
        marker.pose.position.z = (z_max + z_min) / 2.0
        marker.pose.orientation.w = 1.0

        marker.scale.x = float(x_max - x_min)
        marker.scale.y = float(y_max - y_min)
        marker.scale.z = float(z_max - z_min)

        # 半透明的青藍色
        marker.color.r = 0.0
        marker.color.g = 0.6
        marker.color.b = 1.0
        marker.color.a = 0.12  # 低透明度避免遮蔽點雲

        marker.lifetime = rclpy.duration.Duration(seconds=1.0).to_msg()
        self.pub_roi.publish(marker)


# === 幾何輔助工具函數 ===




def yaw_to_quaternion(yaw):
    """
    將 yaw 偏航角轉為四元數 [x, y, z, w]
    """
    half_yaw = yaw * 0.5
    sin_y = np.sin(half_yaw)
    cos_y = np.cos(half_yaw)
    return [0.0, 0.0, sin_y, cos_y]


def main(args=None):
    rclpy.init(args=args)
    node = PubModelVehicleDetector()
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
