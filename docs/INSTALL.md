# 安裝與建置指引

本文件以已確認的 Ubuntu 20.04／ROS 2 Foxy 整理依賴與建置順序，不是已驗證的安裝紀錄。備份來源的 Foxy 相容性、NDT 匯出與辨識 launch 問題見 [缺漏清單](檔案缺漏與待確認事項.md)。

原車已拆除；以下是依現存程式整理的重建參考，不代表目前仍可在原車重跑。原機版本紀錄若已無法取得，應明列未知；未來建立的新環境與測試結果另行記錄，不回填為當時環境。

## 1. 先固定環境

使用者已確認主機為 Jetson AGX Xavier、Ubuntu 20.04 與 ROS 2 Foxy。JetPack、L4T、CUDA 與套件精確版本仍需補記。Mega 韌體已收錄，另需 Arduino AVR Boards 與 AccelStepper，準備方式見 [firmware/README](../firmware/README.md)。

在原 Jetson 執行 `bash tools/collect_environment.sh > environment.txt`，記錄 Ubuntu、L4T、JetPack、ROS、Python、CUDA、PyTorch、torchvision、spconv、NumPy。Windows 資料夾不能提供原機的實際執行版本；備份中的 Python 3.8 ARM64 `.so` 也不能拿到不同 Python／CPU 架構使用。

Foxy 的官方 Debian 安裝文件對應 Ubuntu Focal，並列出 ARM64 平台；此處用來還原實車基線。[Foxy 官方平台與安裝文件](https://github.com/ros2/ros2_documentation/blob/foxy/source/Installation/Ubuntu-Install-Debians.rst)

備份中另有 Humble/Jazzy 文件及不同分支原始碼，不代表實車同時使用這些環境。Nav2 插件、BT XML、vision_msgs 訊息欄位與 NDT 原始碼需按 Foxy 及原機套件版本核對；此次未進行跨版本移植。

## 2. 系統依賴

README 已列 Foxy 依賴清單。各模組另需：

| 模組 | 主要依賴 | 來源 |
|---|---|---|
| Ouster | rclcpp、sensor_msgs、ouster_sensor_msgs、TF、PCL、Eigen、jsoncpp、curl、libtins、spdlog；新版本另含 cv_bridge/libzip | 選定驅動的 package.xml 與 SDK CMake |
| NDT 定位 | rclcpp_lifecycle、lifecycle_msgs、diagnostic_msgs、TF2、PCL、Eigen、OpenMP、ndt_omp_ros2 | package.xml + CMakeLists.txt |
| Nav2 | navigation2、nav2_bringup、RPP 控制器、Map Server、robot_state_publisher | 主啟動檔及 YAML |
| 辨識節點 | rclpy、sensor_msgs、vision_msgs、geometry_msgs、visualization_msgs、tf2_ros、tf2_geometry_msgs | Python imports；現有 package.xml 尚未完整列出 |
| 禁停判定 | rclcpp、vision_msgs、nav_msgs、TF2、yaml-cpp | package.xml + CMakeLists.txt |
| Python 輔助功能 | NumPy、pyserial、requests、PyYAML；相機用 OpenCV，GUI 用 PySide6/pyqtgraph | 原始碼 imports |

`small_gicp`、pybind11 等在定位套件內屬選用功能；本次主流程為 NDT_OMP，不因套件內有其他後端就將其列為必要硬體或算法。

ROS 已安裝後，rosdep 初始化只需在尚未初始化的機器做一次：

```bash
sudo rosdep init
rosdep update --include-eol-distros
```

已有 rosdep 設定時跳過 init；更新時納入已結束支援的發行版，避免略過 Foxy 資料。此選項見 [rosdep 官方 CLI 原始碼](https://github.com/ros-infrastructure/rosdep/blob/master/src/rosdep2/main.py)。先 `source /opt/ros/foxy/setup.bash`，再對選定工作區執行 `rosdep check` 檢視；若使用原機 local-prefix，保留既有依賴來源，不自動改成系統版。一般乾淨環境的操作形式如下，需在對應 workspace 中執行：

```bash
rosdep check --from-paths src --ignore-src --rosdistro "$ROS_DISTRO"
rosdep install --from-paths src --ignore-src --rosdistro "$ROS_DISTRO" -y
```

這是 ROS 官方的 source workspace 依賴解析流程，但 package.xml 未宣告的 Python/GPU 套件仍須另外補齊。[rosdep 文件](https://github.com/ros2/ros2_documentation/blob/rolling/source/ROS-Framework/client-libraries/Working-with-Client-Libraries/Rosdep.rst)

## 3. 選一個 Ouster 驅動

- `ous/src/ouster-ros`：版本 0.12.7，Git 分支線索為 ros2-foxy。
- `ros2_ws/src/ouster-ros`：版本 0.15.0，Git 分支線索為 ros2。

兩份都保留，是因為備份存在兩種部署線索。各自已含對應 SDK 原始碼，SDK 及其他第三方授權一併保留。不要在同一次 `colcon` 掃描中混合兩個 workspace，否則會遇到同名套件；不要僅因新版存在就假設其支援舊環境。上游分支與建置說明見 [Ouster 官方 ROS 2 驅動](https://github.com/ouster-lidar/ouster-ros/tree/ros2)。

若選擇既有 Foxy 候選，在相容 ROS 環境載入後於 `ous/` 建置：

```bash
cd "$AMR_ROOT/ous"
rosdep install --from-paths src --ignore-src --rosdistro "$ROS_DISTRO" -y
colcon build --symlink-install --packages-up-to ouster_ros
source install/setup.bash
```

若選擇 `ros2_ws` 的驅動，可使用下面定位 overlay 的 build_ws，但 `--base-paths` 改為 `../src/ouster-ros`、`--packages-up-to` 改為 `ouster_ros`。兩套候選皆未在本次建置驗證。

## 4. 定位 overlay

定位套件自帶 local-prefix 工作流程。本次保留其環境腳本，以下在 `ros2_ws/build_ws` 建置，避免把生成檔放入 source tree：

```bash
export LIDAR_LOCALIZATION_WS_ROOT="$AMR_ROOT/ros2_ws"
export LIDAR_LOCALIZATION_LOCAL_PREFIX="$AMR_ROOT/ros2_ws/local_prefix"
export LIDAR_LOCALIZATION_OVERLAY="$AMR_ROOT/ros2_ws/build_ws/install/setup.bash"
source "$AMR_ROOT/ros2_ws/src/lidar_localization_ros2/scripts/setup_local_env.sh"
mkdir -p "$AMR_ROOT/ros2_ws/build_ws"
cd "$AMR_ROOT/ros2_ws/build_ws"
colcon build --symlink-install \
  --base-paths ../src/ndt_omp_ros2 ../src/lidar_localization_ros2 \
  --packages-up-to lidar_localization_ros2 \
  --cmake-args -DCMAKE_BUILD_TYPE=Release
source install/setup.bash
```

**尚待處理**：原 `ndt_omp_ros2/CMakeLists.txt` 建立 `ndt_omp` 函式庫，但安裝／匯出宣告不完整；下游定位套件卻引用該庫。此問題需修復或取回原機可建置版本後，才能把以上步驟標成通過。環境腳本亦含 x86_64 的 local-prefix 子路徑，ARM64 配置需核對。

採上述 build_ws 目錄時，舊 `local.sh` 的 `source install/setup.bash` 需指向對應的 `build_ws/install/setup.bash`，或依同一設定使用已 source 的環境直接執行該 ROS launch。不要讓舊的安裝目錄覆蓋新 overlay。

## 5. Jetson GPU 與 OpenPCDet

先以 JetPack 決定 CUDA 和 NVIDIA PyTorch，再匹配 torchvision、spconv、Python 與 NumPy。依 [NVIDIA 官方指引](https://docs.nvidia.com/deeplearning/frameworks/install-pytorch-jetson-platform/index.html) 選擇相容版本；本文件不填入未驗證的 wheel 版本。

依賴分組放在 `requirements/`；原始完整候選清單仍保留在 `fish/ros2_ws/OpenPCDet/requirements.txt`，其中泛用的 `torch>=1.1` 不是本專案的 Jetson 鎖版證據。NumPy fallback 不代表完全不需要 spconv。OpenPCDet 包含本地修改，勿直接改用最新版上游覆蓋。

確認 GPU 環境後，在 root 執行 README 的 pip 指令，以本地 source 編譯 CUDA extensions。上游建置機制可參考 [OpenPCDet 安裝說明](https://github.com/open-mmlab/OpenPCDet/blob/master/docs/INSTALL.md)。本次不複製舊 `.so`，但所需 `.cpp`、`.cu`、標頭和 setup.py 已保留。

## 6. 辨識與禁停節點

完成 GPU 環境後，再於相同 ROS／Python 組合建置：

```bash
cd "$AMR_ROOT/fish/ros2_ws"
rosdep install --from-paths src --ignore-src --rosdistro "$ROS_DISTRO" -y
colcon build --symlink-install \
  --packages-select pub_model_vehicle_detector violation_detector
source install/setup.bash
```

先修復已知 launch 語法問題，並整理使用者已說明為筆電測試殘留的舊節點，以及 `setup.py` 中已無對應模組的 `map_server_node`、`localizer_node`。定位與二維地圖已有主流程負責，不能為滿足舊入口而同時啟動另一組重複 TF。

辨識設定已收錄為 [vehicle_detector.yaml](../config/vehicle_detector.yaml)，可在完成套件建置與模型環境準備後依 [CONFIGURATION](CONFIGURATION.md) 以 `ros2 run` 明確載入；舊 launch 並未自動接入此參數檔。

## 7. 安裝後驗證

先跑 [靜態檢查](VALIDATION.md)，再依序驗證 import、ROS node/topic、TF、模型載入、架空底盤、低速移動、導航和巡檢。每一步記錄硬體／環境版本與結果；未執行的測試明確標示，不以 CI 的語法檢查取代實車驗證。
