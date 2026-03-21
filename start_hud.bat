@echo off
setlocal EnableExtensions
title Armada HUD - Servidor

cd /d "%~dp0"

REM Nil via Azure OpenAI
set "NIL_PROVIDER=azure"
set "AZURE_OPENAI_ENDPOINT=https://nel.openai.azure.com/"
set "AZURE_OPENAI_API_VERSION=2025-12-01"
set "AZURE_OPENAI_DEPLOYMENT=NIL"

REM Abre a página
start "" "http://localhost:8000"

REM Inicia o servidor
py -m uvicorn src.api_server:app --host 127.0.0.1 --port 8000 --log-level info

echo.
echo Servidor encerrado. Pressione qualquer tecla para fechar...
pause >nul
endlocal