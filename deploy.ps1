#requires -version 5.1
$ErrorActionPreference = 'Stop'
function Step($msg,$pct){ Write-Progress -Activity "Twin Boss Deploy" -Status $msg -PercentComplete $pct }

Step "Load env" 5
if(Test-Path ".env"){ Get-Content .env | ? {$_ -notmatch '^\s*#' -and $_} | % {
  $k,$v = $_.Split('=',2); [Environment]::SetEnvironmentVariable($k,$v)
}}

Step "Check Node" 10
if(-not (Get-Command node -ErrorAction SilentlyContinue)){ Write-Host "Install Node.js" -Foreground Yellow; exit 1 }
if(-not (Get-Command npm -ErrorAction SilentlyContinue)){ Write-Host "Install npm" -Foreground Yellow; exit 1 }

Step "Install frontend deps" 20
npm install | Out-Null

Step "Python venv + API deps" 40
Push-Location api
if(Test-Path ".venv"){ Remove-Item -Recurse -Force ".venv" }
python -m venv .venv
& ".\.venv\Scripts\pip.exe" install -r requirements.txt | Out-Null
Pop-Location

Step "Start API :8011" 60
Start-Process -WindowStyle Minimized -FilePath ".\api\.venv\Scripts\python.exe" -ArgumentList "-m","uvicorn","app:app","--host","0.0.0.0","--port","8011"

Step "Start Console :8080" 80
$env:API_BASE="http://127.0.0.1:8011"
npm start
Step "Done" 100
