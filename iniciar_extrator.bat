@echo off
chcp 65001 > nul
title Extrator de Guias Prisionais - SERES / CEASA

echo ======================================================================
echo    EXTRATOR INTELIGENTE DE GUIAS PRISIONAIS (SERES-PE / CEASA)
echo ======================================================================
echo.
echo [1/4] Verificando instalacao do Python...
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERRO] Python nao encontrado no PATH do sistema.
    echo Por favor, instale o Python 3.10+ marcando a opcao "Add Python to PATH".
    pause
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
    echo 2. Instale mantendo a pasta padrao (C:\Program Files\Tesseract-OCR).
    echo.
    echo Continuando inicializacao...
    echo.
)

echo [3/4] Verificando dependencias necessarias...
python -m pip install -q -r requirements.txt

echo [4/4] Iniciando o servidor web local na sua maquina...
cd /d "%~dp0"

echo.
echo ======================================================================
echo  Servidor ativo! Abrindo o navegador em: http://127.0.0.1:5000
echo  Para encerrar o extrator, basta fechar esta janela do terminal.
echo ======================================================================
echo.

python app.py

pause
