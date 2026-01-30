# 查詢目前的 ngrok URL
$response = Invoke-WebRequest -Uri http://localhost:4040/api/tunnels -UseBasicParsing | ConvertFrom-Json
$url = $response.tunnels[0].public_url

Write-Host ""
Write-Host "=============================="
Write-Host "  LINE 梗圖機器人 URL 查詢"
Write-Host "=============================="
Write-Host ""
Write-Host "[Webhook URL]" -ForegroundColor Cyan
Write-Host "$url/callback"
Write-Host ""
Write-Host "[管理介面 URL]" -ForegroundColor Cyan
Write-Host "$url/admin"
Write-Host ""
Write-Host "==============================" 
