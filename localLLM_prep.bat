@echo off

:: --- 1. Docker Desktop 起動 ---
echo [1/3] Docker Desktop を起動しています...
start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
:wait_docker
docker stats --no-stream >nul 2>&1
if %errorlevel% neq 0 (
    timeout /t 5 >nul
    goto wait_docker
)

:: --- 2. LM Studio 起動 ---
echo [2/3] LM Studio を起動しています...
set LMS="C:\Users\cammy\.lmstudio\bin\lms.exe"

:: モデルをロード (ロードが終わるまで次の行へ進みません)
call %LMS% load google/gemma-4-e4b --gpu=max
call %LMS% server start


:: --- 3. Dify 起動 ---
echo [3/3] Dify コンテナを起動しています...
cd /d "C:\Users\cammy\Documents\localAI_GatherUpdates\dify\docker"
docker compose up -d

echo Dify サービスがオンラインになるのを待機中...
:wait_dify
curl -s http://localhost/ >nul 2>&1
if %errorlevel% neq 0 (
    timeout /t 5 >nul
    goto wait_dify
)

:: --- 4. 完了 ---
echo ==========================================
echo すべてのローカルAI環境が整いました！
echo ==========================================
start http://localhost/install
pause
