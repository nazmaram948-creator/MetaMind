@echo off
rem SkillShift MY, Windows: double-click this file, or type "run" in a terminal in this folder.
rem It calls run.ps1 without changing any PowerShell policy on your machine.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run.ps1" %*
if errorlevel 1 pause
