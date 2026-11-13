@echo off
cd /d "%~dp0"
python -m pip install -r requirements.txt
pyinstaller --onefile --windowed --name jarvis-consulenti --distpath dist --workpath build server.py
