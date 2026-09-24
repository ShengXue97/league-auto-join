@echo off
title Stop League Remote
cd /d "%~dp0"
python league_remote.py --stop
pause
