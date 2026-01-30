#!/bin/bash

echo ""
echo "=============================="
echo "  LINE 梗圖機器人 URL 查詢"
echo "=============================="
echo ""

URL=$(curl -s http://localhost:4040/api/tunnels | grep -o '"public_url":"[^"]*' | head -1 | cut -d'"' -f4)

if [ -z "$URL" ]; then
    echo "[錯誤] 無法取得 ngrok URL，請確認容器是否正在運行"
    echo ""
    echo "執行 docker compose ps 檢查狀態"
    exit 1
fi

echo "[Webhook URL]"
echo "${URL}/callback"
echo ""
echo "[管理介面 URL]"
echo "${URL}/admin"
echo ""
echo "=============================="
