# 資源與 Git LFS

新增的底部尺寸圖位於 [images/chassis_bottom_dimensions.png](images/chassis_bottom_dimensions.png)，以一般 Git 保存；既有 PDF 為前次版本，本次資訊以 Markdown 為準。

本地 `github/` 已包含以下主要資源，不需再向原資料夾取得。大小以 MiB（1,048,576 bytes）計算；完整清單與 SHA-256 見 [assets_manifest.json](assets_manifest.json)。清單也保留第三方套件的測試資源，不能把測試用的空檔或故意損壞範例當成下載遺失。

| 資源 | 大小（MiB） | 用途 | 儲存方式 |
|---|---:|---|---|
| `ros2_ws/cloudGlobal.pcd` | 129.33 | 定位 launch 指向的三維地圖 | Git LFS |
| `ros2_ws/final_map_V1_9_8_F_FLATTENED.pcd` | 7.46 | 另一份三維地圖，保留供核對 | Git LFS |
| `ros2_ws/mymap.pgm` | 23.71 | map.sh 指向的二維地圖影像 | Git LFS |
| `ros2_ws/my_map.pgm` | 0.35 | nav1.sh 提及的另一份二維地圖影像 | Git LFS |
| `agv.stl` | 76.78 | URDF 使用的車體模型 | Git LFS |
| `fish/ros2_ws/weights/pointpillar_nuscenes_50e.pth` | 23.30 | PointPillars 預訓練權重 | Git LFS |
| `output/pdf/114-2專題報告_控制章節更新版.pdf` | 6.24 | 已更新控制章節的報告 | 一般 Git |

PGM 的原點、解析度與影像檔名另存於同目錄 YAML，須成對保留。上述兩種二維地圖不可只更換檔名就視為相同場域；PCD、PGM 及禁停區座標的對齊仍待原機確認。模型權重的取得來源、版本與再散布條件尚待補記，不提供未確認的下載連結。

## 首次提交前

GitHub 一般 Git 會拒絕超過 100 MiB 的單檔；`cloudGlobal.pcd` 已超過此限制。50 MiB 以上的一般 Git 檔案也會收到警告，因此一併以 LFS 管理 STL、地圖及權重。[GitHub 官方限制](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)

根目錄 [.gitattributes](../.gitattributes) 已設定 `*.pcd`、`*.ply`、`*.pgm`、`*.stl`、`*.pth` 的 LFS 規則。以下是未來建立 repository 時的操作說明，**本次尚未執行 git init、add、commit 或 push**：

```bash
# 先確認所在目錄是整理好的 github/，並已安裝 git-lfs。
git init
git lfs install --local
# 在首次 git add 之前，確認現有 .gitattributes 已保留。
git add .
git lfs ls-files
git status --short
```

啟用 LFS 必須在首次加入大型檔案前完成，事後只新增規則不會自動移除已提交歷史中的大型內容。實際提交與公開前仍需完成 [授權確認](../LICENSE_STATUS.md) 及 [完整性清單](開源專案完整性清單.md)。不要先以 GitHub 網頁逐檔上傳大型地圖。

## 從正式 repository 取得後

```bash
git lfs install --local
git lfs pull
python3 tools/check_project.py --verify-assets
```

目前沒有正式 repository URL。未來公開後，應從全新的 clone 驗證能下載 LFS 實體檔案，再核對 checksum；LFS pointer 只是小型文字描述，不能拿來載入地圖或模型。上述檢查也會回報已知原始碼問題，資源校驗通過不代表整體檢查或模型載入通過。

若未來改以 Release 或外部儲存提供大型資源，需同步更新真實下載網址、版本、SHA-256、授權條件與路徑說明；不可僅刪除檔案而留下不可重現的安裝流程。
