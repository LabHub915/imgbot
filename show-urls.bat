@echo off
chcp 65001 >nul
echo.
echo ==============================
echo   LINE 梗圖機器人 URL 查詢
echo ==============================
echo.

for /f "delims=" %%i in ('powershell -Command "(Invoke-WebRequest -Uri http://localhost:4040/api/tunnels -UseBasicParsing | ConvertFrom-Json).tunnels[0].public_url"') do set NGROK_URL=%%i

if "%NGROK_URL%"=="" (
    echo [錯誤] 無法取得 ngrok URL，請確認容器是否正在運行
    echo.
    echo 執行 docker-compose ps 檢查狀態
    pause
    exit /b 1
)

echo [Webhook URL]
echo %NGROK_URL%/callback
echo.
echo [管理介面 URL]
echo %NGROK_URL%/admin
echo.
echo ==============================
pause
