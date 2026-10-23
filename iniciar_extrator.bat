@echo off
chcp 65001 > nul
title Extrator de Guias Prisionais - SERES / CEASA

cd /d "%~dp0"

echo ======================================================================
echo    EXTRATOR INTELIGENTE DE GUIAS PRISIONAIS (SERES-PE / CEASA)
echo ======================================================================
echo.
echo [1/4] Verificando instalacao do Python...
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERRO] Python nao encontrado no PATH do sistema.
    echo Por favor, instale o Python 3.10+ marcando a opcao "Add Python to PATH".
    echo.
    echo Pressione qualquer tecla para sair...
    pause > nul
    exit /b 1
)

echo [2/4] Verificando motor de OCR (Tesseract)...
set TESS_FOUND=0
if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" set TESS_FOUND=1
if exist "C:\Program Files (x86)\Tesseract-OCR\tesseract.exe" set TESS_FOUND=1
where tesseract >nul 2>nul
if %errorlevel% equ 0 set TESS_FOUND=1

if %TESS_FOUND% neq 1 (
    echo.
    echo [AVISO IMPORTANTE] Motor Tesseract OCR nao detectado na maquina!
    echo Para conseguir extrair PDFs digitalizados/escaneados:
    echo 1. Baixe o instalador oficial do Tesseract para Windows em:
    echo    https://github.com/UB-Mannheim/tesseract/wiki
    echo 2. Instale mantendo a pasta padrao ^(C:\Program Files\Tesseract-OCR^).
    echo.
    echo Continuando inicializacao...
    echo.
)

echo [3/4] Verificando dependencias necessarias...
python -m pip install -q -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo [AVISO] Nao foi possivel instalar/atualizar as dependencias via pip.
    echo Verifique a conexao com a internet ou o proxy da rede.
    echo Tentando iniciar mesmo assim com as bibliotecas ja instaladas...
    echo.
)

echo [4/4] Liberando conexoes antigas na porta 5000...
REM O padrao ":5000 .*LISTENING" exige um espaco apos a porta, evitando
REM derrubar por engano processos nas portas 50001, 50002, etc.
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr /R /C:":5000 .*LISTENING"') do (
    taskkill /F /PID %%a >nul 2>nul
)

echo.
echo ======================================================================
echo  🚀 INICIANDO EXTRATOR PRISIONAL...
echo  📍 Endereço local: http://127.0.0.1:5000
echo.
echo  ⚠️  ATENÇÃO: Mantenha esta janela aberta enquanto utiliza o sistema.
echo  🛑 Para encerrar a execução, basta fechar esta janela ou teclar CTRL+C.
echo ======================================================================
echo.

python app.py

echo.
echo ======================================================================
echo  🛑 Servidor encerrado. A janela ficara aberta ate voce fechar.
echo ======================================================================
pause

