@echo off
set PYTHONPATH=
echo ============================================
echo  Meeting Recorder - Setup Inicial
echo ============================================
echo.

echo [1/4] Criando ambiente virtual...
python -m venv venv
if errorlevel 1 (
    echo ERRO: Python nao encontrado. Instale o Python 3.11+
    pause
    exit /b 1
)

echo [2/4] Instalando dependencias...
call venv\Scripts\activate.bat
pip install --upgrade pip
pip install PyQt6 sounddevice jinja2 numpy pywin32 groq anthropic pyaudiowpatch python-dotenv json-repair httpx

echo Configurando pywin32 (DLLs do Windows)...
python venv\Scripts\pywin32_postinstall.py -install >nul 2>&1

echo [3/4] Configurando chaves de API...
if not exist .env (
    copy .env.example .env
    echo.
    echo  IMPORTANTE: Abra o arquivo .env e preencha suas chaves de API antes de rodar o app.
    echo  Veja .env.example para instrucoes.
    echo.
) else (
    echo  Arquivo .env ja existe, pulando.
)

echo [4/4] Criando pastas necessarias...
mkdir data\audio 2>nul
mkdir data\transcriptions 2>nul
mkdir "%USERPROFILE%\Documents\Notes" 2>nul

echo Gerando icone do app...
python generate_icon.py

echo Criando atalho no Desktop...
python create_shortcut.py

echo.
echo ============================================
echo  Setup concluido!
echo  1. Edite o arquivo .env com suas chaves de API
echo  2. Para iniciar: run.bat ou pelo atalho no Desktop
echo  3. Clique direito no atalho > Fixar na barra de tarefas
echo ============================================
pause
