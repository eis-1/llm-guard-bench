@echo off
TITLE LLM Guard Bench - Security Framework Orchestrator
cls

echo =======================================================================
echo   LLM Guard Bench - Adversarial Attack Benchmark Suite
echo =======================================================================

echo.
echo Step 1: Configuring Absolute Paths
echo -----------------------------------------------------------------------

set "INNER_DIR=C:\projects\Best\llm-guard-bench\llm-guard-bench"
set "VENV_PYTHON=%INNER_DIR%\.venv\Scripts\python.exe"
set "VENV_PIP=%INNER_DIR%\.venv\Scripts\pip.exe"

echo Inner Directory: %INNER_DIR%
echo Python Executable: %VENV_PYTHON%

if not exist "%VENV_PYTHON%" (
    echo ERROR: Python executable not found at %VENV_PYTHON%
    echo Please verify the virtual environment is installed correctly
    pause
    exit /b 1
)

echo.
echo Step 2: Installing or Verifying Dependencies
echo -----------------------------------------------------------------------

call "%VENV_PIP%" install -q python-dotenv pydantic aiohttp aiosqlite groq matplotlib 2>nul

if errorlevel 1 (
    echo Warning: Some dependencies may not have installed, continuing anyway
)

echo.
echo Step 3: Executing LLM Guard Bench Orchestrator
echo -----------------------------------------------------------------------

cd /d "%INNER_DIR%"

if not exist "main.py" (
    echo ERROR: main.py not found in %INNER_DIR%
    pause
    exit /b 1
)

echo Launching benchmark with target model: llama3:8b
echo Concurrency level: 1
echo.

"%VENV_PYTHON%" main.py --target llama3:8b --concurrency 1

echo.
echo =======================================================================
echo   Benchmark Execution Finished
echo =======================================================================

pause
