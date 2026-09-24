# 設定與路徑對照

原車已拆除。使用者說明大部分參數曾依實車情況調整；本次複製保留主程式的部署設定，個別校正過程未留存的部分記為歷史缺口。下列路徑調整與校正步驟供日後重建參考。`AMR_ROOT` 只用於文件中的 shell 指令；原程式沒有統一的環境變數讀取機制。

| 檔案／設定 | 現有內容 | 部署時處理 |
|---|---|---|
| `ros2_ws/odem_bridge.py` | `/dev/ttyUSB0`、115200；輪徑 0.26、輪距 0.85、PPR 1600 | 回授已確認為編碼器；核對通訊裝置、254 mm 標稱輪徑與 260 mm 設定差異、有效輪距、減速比及每輪有效計數；輪徑等為 ROS 參數，port 尚寫死。 |
| `ros2_ws/myagv.sh` | 讀目前目錄 `myagv.urdf` | 從該目錄啟動。 |
| `ros2_ws/myagv.urdf` | `file:///home/ntust/agv.stl` | 改為本專案 `agv.stl` 的實際路徑；後續可改 package URI。 |
| `ros2_ws/lidar.sh`、`ous/lidar.sh` | 感測器 IP `169.254.70.240` | 配合實機 IP 和網卡；時間戳為 ROS time，use_sim_time=false。 |
| `ros2_ws/local.sh` | `source install/setup.bash` | source 實際建置 overlay；使用 build_ws 時需同步調整。 |
| 定位 package `launch/nav2_lidar_localization.launch.py` | PCD 路徑硬編碼在 Node parameters 末項 | 此末項會覆蓋 YAML 的 map_path，兩處都要核對。 |
| `ros2_ws/nav2_lidar_localization.launch.py` | 另有 `/home/saitama/...` 版本 | 此檔不會自動取代套件索引中的同名 launch；保留做差異參考。 |
| 定位 launch `publish_lidar_tf` | package／已部署快照預設另發 os_sensor | 依實際點雲 frame 校正，避免錯誤或多餘的光達外參。 |
| `ros2_ws/map.sh` | `/home/ntust/ros2_ws/mymap.yaml` | 保留此套地圖；使用者確認兩個檔名是不同場地的地圖，室內／室外的逐檔對應未明示，見下節。 |
| `ros2_ws/nav1.sh` | my_map.yaml 與 my_nav2_params.yaml 絕對路徑 | 提及另一套場景地圖；Nav2 地圖以啟用的 Map Server 輸出為準，不僅由此引數判定。 |
| `ros2_ws/my_nav2_params.yaml` | 含 `/opt/ros/foxy/...` BT XML | 依最終 ROS／Nav2 版本核對 plugin、BT XML、恢復節點與 smoother 支援。 |
| `fish/ros2_ws/.../detector_node.py` | OpenPCDet、模型設定與權重搜尋舊絕對路徑 | `config_path`、`checkpoint_path` 可由 ROS 參數覆寫；pcdet import 搜尋路徑另須核對。 |
| `fish/ros2_ws/.../violation_detector.launch.py` | 固定 zones.yaml 路徑 | 指向 `fish/ros2_ws/violation_area/zones.yaml`。 |
| `fish/ros2_ws/violation_area/zones.yaml` | 地圖像素標註、原點與解析度 | 必須和所用地圖一致，不能沿用到其他場地。 |
| `fish/ros2_ws/camera_uploader_node.py` | GPS 仿射校正點、相機索引；GAS URL 已改為 AMR_GAS_URL | 校正點只適用原場域；雲端另需部署接收端。 |

主要介面：`/ouster/points`（PointCloud2）、`/odom`（Odometry）、`/map`（OccupancyGrid）、`/cmd_vel`（Twist）、`/detected_vehicles`（Detection3DArray）。Mega 序列格式為 Jetson 發 `V線速度,角速度\n`、接收 `P左計數,右計數\n`；Mega 韌體已確認相容解析、編碼器累積計數與 500 ms 指令逾時歸零；實際停止行為與計數倍率仍待驗證。

## 本次實車資訊補充

- Jetson AGX Xavier、Ubuntu 20.04、ROS 2 Foxy 已確認，環境入口為 /opt/ros/foxy/setup.bash；JetPack 與套件精確版本仍待補。
- 馬達為 JMC 86J18156EC-1000-LS-01 閉環步進馬達，14 mm 為輸出軸直徑；原廠資料與配套驅動器候選見 [查核文件](馬達與驅動器資料查核.md)。
- 信心門檻程式預設 0.1，實車通用及 car／truck／bus 四項皆為 0.4；已保存使用者的指令及 YAML，見下節。
- 車體及 STL 原點皆為前方驅動輪觸地連線中點 O，圖右側為前進／+x。現有 footprint 軸向與此定義不符；外框修正參考、輪距與韌體參數對照見 [硬體與韌體](硬體與韌體.md)。本次不直接更換 URDF／YAML 的幾何參數。
- 已確認馬達內建 1000 線編碼器、1600 細分。Jetson 現有 ppr=1600 保留為程式值；1000 線經目前 A 雙邊緣計數，在未分頻的假設下為 2000 次／編碼器軸圈，傳動比及實轉計數未留存，原車亦無法補測，故僅保留推算供未來重建校正參考。

## 二維地圖的兩套場景設定

使用者確認 `mymap.yaml` 與 `my_map.yaml` 確實是兩個不同場地的地圖，並說明有室內／室外場景；尚未明示哪個檔名屬室內或室外。室外測試曾無法移動、改檔名仍未排除。兩套完整 YAML／PGM 均保留，不當成同圖異名。

| 地圖設定 | 影像 | 解析度（m/pixel） | 原點（x, y, yaw） | 備份中的入口 |
|---|---|---:|---|---|
| [mymap.yaml](../ros2_ws/mymap.yaml) | mymap.pgm | 0.12 | [-339, -141, 0] | map.sh 明確交給 Map Server 載入 |
| [my_map.yaml](../ros2_ws/my_map.yaml) | my_map.pgm | 0.07 | [-31.6, -10.2, 0] | nav1.sh 的 map 引數提及 |

不同場地已由使用者確認；不能只憑解析度與原點指定其中一份就是室內或室外。`nav1.sh` 啟動 `navigation_launch.py`；已核對官方 Foxy 此 launch 不使用 `map:=...`，也不啟動 Map Server，故此引數不會替換地圖。依目前保存的 `map.sh`，其啟用的 Map Server 讀取 `mymap.yaml`；過去每次部署的手動切換情況未留存。

未來重建時，應以同一場景選取二維地圖、NDT 的 PCD 及禁停區 `zones.yaml`，核對其座標基準。兩套資料保留作場景資源，歷史對應未知不列為必須向使用者補問的項目。

**啟動紀錄與 Foxy 地圖接收：**[run.md](../fish/ros2_ws/run.md) 第 15、17、19 行是 `nav1.sh → nav_gui.py → map.sh`，不支持直接假設地圖先發布、導航後加入。官方 launch 將 `map_subscribe_transient_local` 覆寫為 false 的行為仍成立，但已降為條件式備選。日後重建可明確設定 `map_subscribe_transient_local:=true`，減少訂閱延遲或重啟時的順序依賴；不是已證實的歷史故障修復。原腳本未改，詳細證據見 [室外導航調查](室外導航無法移動_調查報告.md)。

## 辨識實車參數：手動覆寫與 YAML

以下四個指令是使用者提供的實車操作；須在辨識節點已啟動時執行。三個車種分別使用獨立門檻，四項都設定才能與已記錄的部署值一致。

```bash
ros2 param set /pub_model_vehicle_detector score_threshold_car 0.4
ros2 param set /pub_model_vehicle_detector score_threshold_truck 0.4
ros2 param set /pub_model_vehicle_detector score_threshold_bus 0.4
ros2 param set /pub_model_vehicle_detector score_threshold 0.4
```

[config/vehicle_detector.yaml](../config/vehicle_detector.yaml) 原樣保存使用者提供的 12 項參數：上述四項門檻、六項 ROI 邊界、`z_offset_correction=0.57`、`sync_time_stamp=true`。程式已宣告這些參數，設定名稱與資料型別已做靜態核對；這是使用者提供的部署組態，並非本次從執行中的 Jetson 匯出。

完成 [安裝與建置](INSTALL.md)、模型依賴及路徑準備後，可在啟動辨識節點時明確載入。`AMR_ROOT` 須指向 Linux 上此專案根目錄，權重與模型設定路徑同時由參數覆寫：

```bash
source /opt/ros/foxy/setup.bash
source "$AMR_ROOT/fish/ros2_ws/install/setup.bash"
ros2 run pub_model_vehicle_detector detector_node --ros-args \
  --params-file "$AMR_ROOT/config/vehicle_detector.yaml" \
  -p config_path:="$AMR_ROOT/fish/ros2_ws/OpenPCDet/tools/cfgs/nuscenes_models/cbgs_pp_multihead.yaml" \
  -p checkpoint_path:="$AMR_ROOT/fish/ros2_ws/weights/pointpillar_nuscenes_50e.pth"
```

此命令只啟動辨識節點；需要既有點雲、TF、GPU 環境及已建置的 ROS 套件。它不經過有語法殘留的舊辨識 launch，也不會替代原來六個控制入口。現有 launch 未提供 `params_file` 引數，不能把 YAML 放入目錄後便視為自動生效。參數檔語法依 [ROS 2 命令列設計文件](https://github.com/ros2/design/blob/gh-pages/articles/160_ros_command_line_arguments.md)；本次未在 Jetson 執行命令。

啟動後可逐項核對並保存完整參數；手動 set 只改目前程序，重啟時仍須載入 YAML 或重新設定：

```bash
ros2 param get /pub_model_vehicle_detector score_threshold
ros2 param get /pub_model_vehicle_detector score_threshold_car
ros2 param get /pub_model_vehicle_detector score_threshold_truck
ros2 param get /pub_model_vehicle_detector score_threshold_bus
ros2 param get /pub_model_vehicle_detector sync_time_stamp
ros2 param dump /pub_model_vehicle_detector
```

`sync_time_stamp=true` 的實作是在點雲 callback 開始重寫 `header.stamp` 為當下節點時間；輸出 `frame_id` 仍為輸入點雲座標框架，沒有因這個參數轉為 base_link。這項設定不會消除資料排隊／推論延遲；相關性能量測須保留原始感測時間。

## 公開複本的變更

只有相機程式的原固定 GAS 部署網址改為 `os.environ.get("AMR_GAS_URL", "")`，啟動日誌改為顯示是否已設定。根目錄原始程式保留。這是公開設定處理，不代表 Apps Script 服務已部署或測試。

先複製 `.env.example` 為 `.env` 並填入自己的設定，再在可信的本機 shell 執行 `source .env`。`.env` 屬 shell 程式文字，只載入自己編輯的內容；不提交實際部署網址。ROS 的 `gas_url` 參數仍可覆寫環境預設值。
