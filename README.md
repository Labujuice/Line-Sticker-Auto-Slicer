# LINE 貼圖自動裁切與縮放工具組 (LINE Sticker Auto-Slicer & Resizer)

這是一套專為 LINE 貼圖設計的 Python 3 圖片處理工具組。提供**網格均勻切圖**、**電腦視覺自動去背識別切圖**以及**單張尺寸縮放**等功能，並支援無損 PNG 格式輸出與自動生成 LINE 標籤圖示 (96x74)。

---

## 🌟 核心功能
1. **智慧自動切圖 (`auto_slice_image.py`)**：
   - 透過 OpenCV 電腦視覺演算法自動識別非均勻排列的貼圖邊緣。
   - 內建「間距合併演算法」(`--gap`)，會自動將靠得很近的文字、特效或陰影與貼圖本體合併，避免被撕裂裁切。
   - 支援透明背景 PNG，若為一般 JPG 也會自動偵測角落背景色進行智慧去背識別。
   - **背景去除功能 (`--remove-bg`)**：能自動將偵測到的背景底色轉為完全透明（適用於 JPG 或無透明度的 PNG）。
2. **均勻網格切圖 (`slice_image.py`)**：
   - 自由指定水平欄數 (Columns) 及垂直列數 (Rows) 進行網格狀完美切割。
3. **單圖縮放工具 (`resize_image.py`)**：
   - 針對單張圖片進行快速缩放，不產生多餘的切圖編號。
4. **多種縮放填補模式 (Resize Mode)**：
   - `pad` (預設/推薦)：等比例縮放至邊框內，不足的部分以指定背景色（如透明色）填滿，確保貼圖不變形。
   - `fit`：等比例縮減至邊界內，不填補背景。
   - `stretch`：強行拉伸填滿指定尺寸（圖片可能會變形）。
5. **LINE 專用標籤圖產生器 (`--gentab`)**：
   - 自動為每張裁切下來的貼圖額外生成一張符合 LINE 貼圖規範的 `96x74` 標籤圖示 (tab image)。

---

## 📦 系統需求與安裝

請確保您的電腦已安裝 Python 3，並安裝以下第三方套件：

```bash
pip install Pillow opencv-python numpy
```

---

## 🚀 使用說明

所有腳本均支援**兩種運行模式**：
- **互動引導模式**：直接執行腳本，腳本會一步步引導您輸入設定（支援直接將圖片拖曳進終端機輸入路徑）。
- **命令列 (CLI) 模式**：適合自動化或快速處理。

---

### 1. 智慧自動切圖工具 ([auto_slice_image.py](auto_slice_image.py))
針對**排列不均勻、大小不一**的貼圖底圖進行自動識別裁切。

#### 互動引導模式：
```bash
python3 auto_slice_image.py
```

#### 命令列快速指令：
* **自動識別並切圖，產生 96x74 的 LINE 標籤圖 (`--gentab`)**：
  ```bash
  python3 auto_slice_image.py input.png -g 5 --gentab
  ```
  *(注：`-g 5` 為合併間距 5 像素，若您的貼圖排得很擠，調小此數值可以防止不同貼圖黏在一起)*

* **自動識別切圖，並將貼圖全部縮放至 LINE 規格 `240x240`（透明背景填充）**：
  ```bash
  python3 auto_slice_image.py input.png -g 5 -s 240x240 -m pad
  ```

* **自動識別切圖，並去除偵測到的底色背景（直接輸出成去背透明貼圖）**：
  ```bash
  python3 auto_slice_image.py input.png -g 5 --remove-bg
  ```

* **自動識別切圖，且同時進行去背、縮放至 `240x240`、並輸出 LINE 96x74 標籤圖**：
  ```bash
  python3 auto_slice_image.py input.png -g 5 -s 240x240 -m pad --remove-bg --gentab
  ```

* **自動識別切圖，並輸出偵測框預覽圖 (`-d`) 以便檢查結果**：
  ```bash
  python3 auto_slice_image.py input.png -g 5 -d debug_preview.png
  ```

---

### 2. 均勻網格切圖工具 ([slice_image.py](slice_image.py))
針對**排列非常整齊**的貼圖底圖進行網格切割。

#### 互動引導模式：
```bash
python3 slice_image.py
```

#### 命令列快速指令：
* **均勻切成 4 欄 x 4 列 (共 16 張貼圖)，維持原始解析度**：
  ```bash
  python3 slice_image.py input.png -c 4 -r 4
  ```

* **均勻切成 2 欄 x 3 列，並全部縮放至 `240x240` (透明填滿)**：
  ```bash
  python3 slice_image.py input.png -c 2 -r 3 -s 240x240 -m pad
  ```

---

### 3. 單張圖片縮放工具 ([resize_image.py](resize_image.py))
當您只需要縮放單張已切好的圖片時使用。

* **縮放至 `240x240`，多餘區域以透明背景填滿，輸出為 `input_resized.png`**：
  ```bash
  python3 resize_image.py input.png -s 240x240
  ```

* **一鍵生成 LINE 貼圖封面與標籤圖 (`--gencover`)**：
  直接指定一張切好的貼圖（例如 `01.png`），自動輸出封面圖 `main.png` (240x240) 與標籤圖 `tab.png` (96x74)，皆為等比例縮放且透明填充：
  ```bash
  python3 resize_image.py 01.png --gencover
  ```

---

## 🎨 常用色彩設定
當使用 `--pad-color` 參數時，支援以下設定：
- `transparent` (預設)：透明背景
- `white`：白色背景
- `black`：黑色背景
- 十六進位色碼如 `#ffffff` 或 `#ff000080` (後半部為透明度)

## 📁 預設輸出位置
- 若未指定 `-o` (輸出目錄/路徑)，裁切工具會在輸入圖片的同目錄下，自動建立一個名為 `[圖片名稱]_auto_slices` 或 `[圖片名稱]_slices` 的資料夾放置所有生成的圖片，不會弄髒您的專案目錄。
- **命名規則**：所有切割出來的貼圖皆會使用**兩位數順序編號**進行命名（例如：`01.png`, `02.png`, `03.png`...），方便您一眼看出貼圖序號，也方便後續指定特定的貼圖生成 `main/tab` 封面。
