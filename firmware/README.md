# Arduino Mega 2560 韌體

使用者指定的韌體為 [final_copy_20260923083515.ino](mega2560/final_copy_20260923083515/final_copy_20260923083515.ino)，已原樣複製，放入與 sketch 同名的資料夾。通訊、腳位、回授和待確認參數見 [硬體與韌體](../docs/硬體與韌體.md)。

## 建置準備

1. 使用 Arduino IDE，準備 Arduino AVR Boards 套件及 Mega 2560 開發板設定。
2. 安裝 [AccelStepper](https://www.airspayce.com/mikem/arduino/AccelStepper/) 函式庫；目前只知道使用此 API，實車編譯版本尚待補記。它是外部依賴，未將未確認版本的函式庫複製進本專案。
3. 開啟上述 sketch，選擇對應 Mega 2560 開發板，先執行編譯驗證。燒錄前應先核對現有韌體備份、接線、編碼器倍率和驅動板設定。
4. 完成後記錄 IDE、AVR Boards、AccelStepper 版本與編譯／測試結果，以便他人重建。

本次僅閱讀與複製 `.ino`，未在此 Windows 環境編譯、燒錄或驅動馬達。Jetson 端仍使用 115200 bps 的 `Vv,w`／`P左計數,右計數` 協定。
