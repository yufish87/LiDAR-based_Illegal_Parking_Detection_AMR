# 驗證與排錯

## 本次整理的驗證範圍

- 檔案依主流程選取，複製清單含來源、目的地、大小、來源 SHA-256 與複本 SHA-256。
- 地圖、STL、權重及報告另有資源校驗清單。
- Python 使用 AST 解析，不匯入 ROS、GPU 模型或使用序列埠。
- 檢查 ROS package XML、URDF、console-script 指向、CMake install(PROGRAMS) 與 OpenPCDet CUDA source 的存在性。
- 未在 Windows 執行 ROS 建置、模型推論、硬體控制、相機取證或雲端上傳。

```bash
python3 tools/check_project.py
python3 tools/check_project.py --verify-assets --json artifacts/static-audit.json
```

發現問題時回傳非零 exit code，錯誤不會因已知而被忽略。本次結果見 [static_audit.json](static_audit.json)；這個快照與後續重新檢查結果可能不同。`.github/workflows/static-check.yml` 提供手動執行的 CI，暫不掛自動 push／PR，以免把未處理的原始錯誤誤認為新修改造成。

`copied_files_manifest.json` 是本次複製快照；若使用 Git 的文字行尾正規化或之後修改 source，文字 SHA 可改變。資源 checksum 適用於 LFS 的實際內容，不是 pointer 檔案。

## 新增韌體與實車資訊

Mega sketch 已原樣複製並核對 SHA-256；尺寸圖與 Markdown 已更新。靜態 Python 工具不會編譯 .ino，本次未執行 Arduino 編譯／燒錄。

原車已拆除。使用者回憶歷史點雲 topic 發布約 3.75 Hz，辨識平均更新率高於 1 Hz，精確平均與量測口徑未留存；來源與限制見 [歷史實車測試紀錄](歷史實車測試紀錄.md)。以下量測與硬體驗證步驟供未來重建參考，不列為當前文件交付的必要補件。

未來量測時應分開記錄新編碼器回報（韌體約 20 Hz 等級）、/odom 發布（計時器 50 Hz）、點雲、NDT 與辨識結果頻率；不能用重複發布舊狀態的 Hz 證明量測新鮮度。韌體時序疑點見 [硬體與韌體](硬體與韌體.md)。

## 未來重建時的部署驗證順序

| 階段 | 檢查內容 | 通過條件 |
|---|---|---|
| 環境 | collect_environment.sh、ROS distro、Python imports、CUDA 可用性 | 有明確且一致的環境紀錄。 |
| 建置 | 定位、選定驅動、感知套件分別 colcon build | 沒有遺失檔案、未解析依賴或鏈結錯誤。 |
| 感測 | `/ouster/points`、header.frame_id、header.stamp | 接收正常且時間基準與 ROS 一致。 |
| 車體 | URDF、os_lidar、輪位置資訊 | 與實車安裝一致，無錯誤固定外參。 |
| 里程計 | 架空或固定車體核對序列收發、停止方式、計數方向 | 指令格式與回授含義已由韌體確認。 |
| 定位 | `map → odom → base_link`、初始位姿、地圖對齊 | 位姿穩定且可解釋，不以固定發布頻率代替定位精度。 |
| 導航 | 低速短路徑、障礙物成本、目標容差 | 路徑追蹤、停止與異常處理符合設定。 |
| 辨識 | 模型載入、車框座標、TF、已知樣本 | 有推論與誤判分析紀錄。 |
| 巡檢 | zones.yaml、事件確認、相機／GAS | 幾何與事件流程分項驗證，不能只看有 topic 就宣稱完成。 |

常用只讀指令：

```bash
ros2 node list
ros2 topic list -t
ros2 topic info /ouster/points -v
ros2 topic hz /ouster/points
ros2 topic hz /odom
ros2 run tf2_ros tf2_echo map base_link
ros2 run tf2_ros tf2_echo base_link os_lidar
ros2 param dump /controller_server
ros2 param dump /lidar_localization
```

## 室外無法移動的離線調查

已核對官方 Foxy 的地圖引數與 QoS 覆寫，並完整解析兩張 PGM 與兩份 PCD 的範圍／點數。後續找到 [run.md](../fish/ros2_ws/run.md)，記錄 Nav2 先於地圖，故將晚加入漏收推測降為備選；原操作紀錄與複本雜湊一致。這是靜態及資源內容分析，並未重現導航故障。候選原因、有效參數查詢及依 `/map → TF → 路徑 → /cmd_vel → 序列埠` 分流的順序見 [調查報告](室外導航無法移動_調查報告.md)，機器可讀依據見 [分析結果](navigation_investigation.json)。

## 常見問題對照

| 現象 | 優先核對 |
|---|---|
| launch 無法解析 | 辨識 launch 的殘留字典、括號；不要誤判為模型下載失敗。 |
| 找不到套件或套件版本不符 | 當前 ROS_DISTRO、source 順序、套件索引中的 prefix。 |
| 找不到 PCD／STL／權重 | 固定絕對路徑、定位 launch 尾端覆寫、Git LFS 是否只取得 pointer。 |
| TF extrapolation／不存在 | frame_id、timestamp_mode、重複發布與環境混用。 |
| CUDA／spconv／torchvision 匯入錯誤 | JetPack、Python ABI、CPU 架構及 CUDA 版本；不可重用其他環境的 `.so`。 |
| 網卡失去連線 | 原 `fix.sh` 的介面名稱與速率設定；先核對硬體，不直接當通用修復。 |
| 馬達未動或方向相反 | Mega 韌體、序列設備、協定、驅動板與左右方向。 |
| 違停事件後車體不靠近 | `/violation/nav_target` 到 Nav2 action 的轉接尚未找到。 |
| GAS 上傳失敗 | AMR_GAS_URL、接收端原始碼、欄位契約、部署權限；目前沒有已驗證後端。 |
