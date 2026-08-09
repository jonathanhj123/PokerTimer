# Poker night: activates the backend venv and starts the server.
# Run from anywhere: .\start.ps1  (or with a full path)
Set-Location "$PSScriptRoot\backend"
& .\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 0.0.0.0 --port 8000
