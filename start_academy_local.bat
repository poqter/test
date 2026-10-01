@echo off
cd /d "%~dp0"
python run_academy_local.py
if errorlevel 1 pause
