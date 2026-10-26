@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 goto python
py -3 -m tools.site.serve --port 0 --open
goto done
:python
python -m tools.site.serve --port 0 --open
:done
if errorlevel 1 pause
