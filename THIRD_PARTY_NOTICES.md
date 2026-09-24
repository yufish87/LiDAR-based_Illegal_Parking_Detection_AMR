# 第三方來源與授權

以下 source 由現有備份複製，保留原授權，不宣稱由本專題從零撰寫。可取得的上游 commit、branch 與本地修改清單記錄於 [upstream_versions.json](docs/upstream_versions.json)；**commit 只代表上游基底，不代表本地複本未經修改**。

| 組件 | 本地位置 | 上游／授權線索 |
|---|---|---|
| LiDAR Localization ROS 2 | `ros2_ws/src/lidar_localization_ros2` | [rsasaki0109/lidar_localization_ros2](https://github.com/rsasaki0109/lidar_localization_ros2)，[BSD 2-Clause](ros2_ws/src/lidar_localization_ros2/LICENSE)。 |
| NDT OMP ROS 2 | `ros2_ws/src/ndt_omp_ros2` | [rsasaki0109/ndt_omp_ros2](https://github.com/rsasaki0109/ndt_omp_ros2)，[BSD 2-Clause](ros2_ws/src/ndt_omp_ros2/LICENSE)。 |
| Ouster ROS 2 / SDK | `ros2_ws/src/ouster-ros`、`ous/src/ouster-ros` | [ouster-lidar/ouster-ros](https://github.com/ouster-lidar/ouster-ros)，[主驅動 LICENSE](ros2_ws/src/ouster-ros/LICENSE)、[SDK LICENSE](ros2_ws/src/ouster-ros/ouster-ros/ouster-sdk/LICENSE)；SDK 另有第三方授權與 LICENSE-bin，不能只用單一標籤概括。 |
| OpenPCDet 本地修改版 | `fish/ros2_ws/OpenPCDet` | [open-mmlab/OpenPCDet](https://github.com/open-mmlab/OpenPCDet)，[Apache-2.0](fish/ros2_ws/OpenPCDet/LICENSE)，內部 KITTI 工具另有 LICENSE；本地 version.py 為 0.6.0+0000000，未找到可用的 Git commit。 |
| PCD2PGM | `ros2_ws/src/pcd2pgm-main` | [LihanChen2004/pcd2pgm](https://github.com/LihanChen2004/pcd2pgm)，[Apache-2.0](ros2_ws/src/pcd2pgm-main/LICENSE)。 |
| Arduino AVR Boards / AccelStepper | 編譯 Mega sketch 的外部依賴，未複製函式庫 | [Arduino AVR 核心](https://github.com/arduino/ArduinoCore-avr)、[AccelStepper](https://www.airspayce.com/mikem/arduino/AccelStepper/)；實車編譯版本待補，依選定版本保留其授權。 |
| ROS 2 / Nav2 / PCL 等安裝依賴 | 由系統套件提供，未複製完整套件 | 請保留各自上游授權，依 INSTALL 中的套件清單安裝。 |
| nuScenes 預訓練權重 | `fish/ros2_ws/weights/pointpillar_nuscenes_50e.pth` | 名稱與模型設定已核對；精確下載來源、權重發布條件與資料集條件待補。 |

`reference/upstream_patches/` 保存可由本地 Git 取得的修改差異，無法替代完整 release 來源證明。SDK 本體已複製，原 `.gitmodules` 僅保留來源線索；本整理目錄不是原來的巢狀 Git/submodule checkout，不在此執行 `git submodule update` 來覆蓋已複製的 source。

所有第三方子目錄中自帶的 README、測試、實驗腳本與 CI 只是原套件內容，不代表這些功能都被本 AMR 使用或驗證。
