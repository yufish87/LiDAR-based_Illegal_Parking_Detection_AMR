# IMU 旁支查核參考

更新：2026-09-24。以下為備份中找到、但未列於主要 `fish/ros2_ws/run.md` 啟動紀錄的檔案，保持原始位元組內容，僅供查核，不視為已啟用的部署流程。

| 此目錄複本 | 原備份相對路徑 | 行為與限制 |
|---|---|---|
| [navga_imu.py](navga_imu.py) | `navga/imu.py` | 訂閱 `/ouster/imu`，依首次 ROS／訊息時間差修正 stamp 後發布 `/fixed/imu`；本檔不錄製 bag，註解不能作為錄包證據。 |
| [ekf_run.sh](ekf_run.sh) | `ros2_ws/ekf_run.sh` | 執行 robot_localization 的 ekf_node，指向固定路徑的 EKF YAML；不能由此推定兩個 EKF 節點均被正確啟動。 |
| [ekf.yaml](ekf.yaml) | `ros2_ws/src/config/ekf.yaml` | 包含 local／global 兩個節點 mapping，輸入為 `/odom` 及 NDT pose，未設定 IMU 輸入。 |

來源與複本 SHA-256 列於 [複製清單](../../docs/copied_files_manifest.json)。主要結論見 [里程計、IMU 與控制架構答覆](../../docs/AMR里程計_IMU與控制架構答覆.md)。
