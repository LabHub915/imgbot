# LINE 梗圖機器人

當聊天室有人提到關鍵字時，機器人會自動發送對應的梗圖。

## 功能

- 🎯 **關鍵字觸發**：支援多個關鍵字對應同一張圖片
- 🖼️ **圖片回應**：使用 jsDelivr CDN 託管圖片
- 📋 **管理介面**：Web UI 管理關鍵字與圖片
- 🔐 **使用者驗證**：登入系統保護管理介面
- 👥 **多使用者**：支援多帳號，區分管理員/一般使用者
- 🔒 **安全機制**：密碼錯誤 5 次鎖定 15 分鐘
- 🐳 **Docker 部署**：一鍵啟動

## 系統需求

- Docker & Docker Compose
- 20GB 硬碟空間
- 2GB RAM
- 1 Core CPU

---

## 快速開始

### 步驟 1：取得 LINE Bot 憑證

1. 前往 [LINE Developers Console](https://developers.line.biz/console/)
2. 建立 Provider 和 Messaging API Channel
3. 記下以下資訊：
   - **Channel Secret**（在 Basic settings）
   - **Channel Access Token**（在 Messaging API → 點擊 Issue）

### 步驟 2：取得 ngrok Authtoken

1. 註冊 [ngrok](https://ngrok.com/)
2. 前往 [Your Authtoken](https://dashboard.ngrok.com/get-started/your-authtoken)
3. 複製你的 Authtoken

### 步驟 3：設定環境變數

複製範例檔案：

```powershell
copy .env.example .env
```

編輯 `.env` 檔案，填入你的憑證：

```env
# LINE Bot 憑證
LINE_CHANNEL_SECRET=你的_channel_secret
LINE_CHANNEL_ACCESS_TOKEN=你的_channel_access_token

# Ngrok
NGROK_AUTHTOKEN=你的_ngrok_authtoken

# 管理員設定（可選，預設密碼為 admin123）
ADMIN_PASSWORD=你想要的管理員密碼
SECRET_KEY=隨機字串用於session加密
```

### 步驟 4：建置並啟動

```powershell
docker compose up -d --build
```

等待約 1-2 分鐘讓所有容器啟動完成。

### 步驟 5：取得 ngrok URL

執行以下指令查詢目前的 URL：

```powershell
.\show-urls.ps1
```

或雙擊 `show-urls.bat`

輸出範例：
```
[Webhook URL]
https://xxxx.ngrok-free.app/callback

[管理介面 URL]
https://xxxx.ngrok-free.app/admin
```

### 步驟 6：設定 LINE Webhook

1. 回到 LINE Developers Console
2. 進入你的 Channel → Messaging API
3. 設定 **Webhook URL** 為：`https://xxxx.ngrok-free.app/callback`
4. 開啟 **Use webhook**
5. 關閉 **Auto-reply messages**

### 步驟 7：登入管理介面

1. 開啟瀏覽器前往管理介面 URL
2. 預設帳號密碼：
   - 帳號：`admin`
   - 密碼：`admin123`（或你在 .env 設定的 ADMIN_PASSWORD）

---

## 常用指令

| 指令 | 說明 |
|------|------|
| `docker compose up -d --build` | 建置並啟動所有容器 |
| `docker compose down` | 停止並移除所有容器 |
| `docker compose ps` | 查看容器狀態 |
| `docker compose logs -f app` | 查看 Flask 即時日誌 |
| `docker compose restart` | 重啟所有容器 |
| `.\show-urls.ps1` | 查詢目前的 ngrok URL |

---

## 圖片託管 (GitHub + jsDelivr)

1. 建立一個 GitHub 倉庫存放圖片
2. 將圖片推送到倉庫
3. 使用 jsDelivr CDN URL：

```
https://cdn.jsdelivr.net/gh/你的用戶名/倉庫名/圖片路徑.png
```

---

## API 端點

| 路徑 | 方法 | 說明 |
|------|------|------|
| `/callback` | POST | LINE Webhook |
| `/login` | GET/POST | 登入頁面 |
| `/logout` | GET | 登出 |
| `/admin` | GET | 梗圖管理介面 |
| `/admin/users` | GET | 使用者管理（僅管理員） |
| `/change-password` | GET/POST | 變更密碼 |
| `/health` | GET | 健康檢查 |

---

## 目錄結構

```
imgbot/
├── docker-compose.yml    # Docker 服務編排
├── .env                  # 環境變數（不要提交到 Git）
├── .env.example          # 環境變數範例
├── .gitignore
├── README.md
├── show-urls.bat         # 查詢 URL（Windows 批次檔）
├── show-urls.ps1         # 查詢 URL（PowerShell）
├── app/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app.py
│   └── templates/
│       ├── index.html
│       ├── login.html
│       ├── edit.html
│       ├── users.html
│       └── change_password.html
└── mongo_data/           # MongoDB 資料（自動生成）
```

---

## 注意事項

> ⚠️ **ngrok 免費版每次重啟 URL 會改變**，需要重新設定 LINE Webhook URL。

> 💡 如需固定 URL，可升級 ngrok 付費方案或使用其他隧道服務。

---

## License

MIT
