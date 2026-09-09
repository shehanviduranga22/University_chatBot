@echo off
cd backend
call venv\Scripts\activate
python ingest.py
pause
