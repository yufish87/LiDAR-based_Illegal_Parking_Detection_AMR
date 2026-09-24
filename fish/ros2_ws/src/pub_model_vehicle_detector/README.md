# Public Model Vehicle Detector

此套件包含基於 **OpenPCDet (PointPillars)** 預訓練模型的 3D 車輛偵測節點與輕量 2D Map Server。

---

## 節點介紹

1.  **`detector_node.py` (3D 車輛偵測器)**
    *   **核心演算法**：使用 OpenPCDet 的 PointPillars 模型（基於 NuScenes 預訓練權重）。
    *   **輸入話題**：`/ouster/points_sync` (型態：`sensor_msgs/PointCloud2`)。
    *   **輸出話題**：`/detected_vehicles` (3D Bounding Box 陣列) 與 `/detected_vehicles_markers` (RViz 綠色立方體框與 ID 標籤)。
    *   **前處理優化**：包含反射強度歸一化（適應 Ouster Lidar 特性）、ROI 幾何過濾、推車高度 Z 軸修正。
    *   **後處理優化**：包含同幀 Centroid NMS（雙框抑制）與 3D 質心軌跡追蹤器 (Centroid Tracker)，確保 ID 跨幀追蹤穩定。
2.  **`map_server_node.py` (輕量 2D 地圖伺服器)**
    *   不需安裝龐大的 Nav2 軟體包，直接讀取並以 1Hz 發布 `.yaml` + `.pgm` 格式的 2D 佔據網格地圖至 `/map` 話題。

---

## 移植至 NVIDIA Jetson AGX (Ubuntu 20.04 / ROS 2 Foxy) 修改指引

由於 Jetson AGX 為 **ARM64 (aarch64)** 架構，且 OpenPCDet 包含大量 C++/CUDA 的自訂運算子（如 `spconv`、`iou3d_nms`），在 Jetson 上部署時請注意以下步驟：

### 1. 安裝 ARM64 PyTorch 與 torchvision
在 Jetson AGX 上，您**不能**直接使用 `pip install torch`。必須前往 NVIDIA 官方論壇下載專為 Jetson (L4T) 編譯的 PyTorch `wheel` 檔安裝：
*   請參考 NVIDIA 官方指引：[PyTorch for Jetson](https://forums.developer.nvidia.com/t/pytorch-for-jetson/72047) 安裝相容於您的 JetPack 版本的 PyTorch。

### 2. 在 Jetson 上重新編譯 OpenPCDet
因為 OpenPCDet 包含 CUDA C++ 核心，必須在 Jetson 上針對其 GPU 架構（例如 Xavier 為 `sm_72`，Orin 為 `sm_87`）進行本地編譯：
```bash
cd ~/ros2_ws/OpenPCDet
python3 setup.py develop
```
*(如果編譯遇到 CUDA 記憶體不足，請在編譯前加上 `export MAX_JOBS=2` 限制多核心編譯)*

### 3. 動態路徑確認
在 `detector_node.py` 中，程式已動態適應了主機與 Docker 容器中的 OpenPCDet 和 weights 權重路徑：
*   OpenPCDet 目錄：預設尋找 `/home/ntust/fish/ros2_ws/OpenPCDet` 或 `/opt/OpenPCDet`。
*   Weights 權重：預設尋找 `/home/ntust/fish/ros2_ws/weights/pointpillar_nuscenes_50e.pth`。
請確保您的 Jetson AGX 上這些檔案放置於對應路徑。

---

## 安裝依賴與編譯步驟

### 1. 安裝 Python 套件依賴
在 Jetson 上安裝模型執行所需的額外 Python 函式庫：
```bash
pip3 install scipy numpy numba
```

### 2. 編譯 ROS 2 套件
回到工作區進行編譯：
```bash
cd ~/ros2_ws
colcon build --packages-select pub_model_vehicle_detector
```
