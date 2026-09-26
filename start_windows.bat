@echo off
REM Windows helper: double-click or run from Command Prompt.
cd /d "%~dp0"
python -m pip install -r requirements.txt
python -m pip install -e .
python run.py
pause
