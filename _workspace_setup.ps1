param(
    [string]$ProjectPath = "$env:USERPROFILE\WorkspaceProject",
    [string]$SourcePath = (Get-Location).Path,
    [string]$GitUser = "Trollz1004",
    [string]$GitEmail = "joshlcoleman@gmail.com",
    [string]$RepoName = "Azure",
    [string]$GitHubPAT = $env:GITHUB_PAT
)

function Fail($msg) {
    Write-Error "[✗] $msg"
    exit 1
}

Write-Progress -Activity "Workspace Setup" -Status "Preparing folder" -PercentComplete 0
try {
    if (Test-Path $ProjectPath) { Remove-Item -Recurse -Force $ProjectPath }
    New-Item -ItemType Directory -Force -Path $ProjectPath | Out-Null
} catch { Fail "Failed to create workspace at $ProjectPath" }
Write-Output "[+] Workspace ready at $ProjectPath"

Write-Progress -Activity "Workspace Setup" -Status "Copying source files" -PercentComplete 15
try {
    Copy-Item -Path "$SourcePath\*" -Destination $ProjectPath -Recurse -Force -ErrorAction SilentlyContinue
} catch { Fail "Failed to copy files from $SourcePath" }
Set-Location $ProjectPath
Write-Output "[+] Files copied from $SourcePath"

Write-Progress -Activity "Workspace Setup" -Status "Creating config.env" -PercentComplete 30
try {
@"
OPENAI_API_KEY=$($env:OPENAI_API_KEY)
STABILITY_API_KEY=$($env:STABILITY_API_KEY)
REPLICATE_API_TOKEN=$($env:REPLICATE_API_TOKEN)
GEMINI_API_KEY=$($env:GEMINI_API_KEY)
PEXELS_API_KEY=$($env:PEXELS_API_KEY)
CIVITAI_API_KEY=$($env:CIVITAI_API_KEY)
HUGGINGFACE_TOKEN=$($env:HUGGINGFACE_TOKEN)
UNSPLASH_ACCESS_KEY=$($env:UNSPLASH_ACCESS_KEY)
CLOUDFLARE_DOCKER_PAT=$($env:CLOUDFLARE_DOCKER_PAT)
GITHUB_PAT=$GitHubPAT
EMAIL_MAIN=joshlcoleman@gmail.com
DOMAIN_MAIN=youandinotai.com
SQUARE_CHECKOUT_LINK=https://square.link/u/wLqSfreC
"@ | Set-Content -Path "$ProjectPath\config.env" -Encoding UTF8
} catch { Fail "Failed to write config.env" }
Write-Output "[+] config.env created."

Write-Progress -Activity "Workspace Setup" -Status "Creating .gitignore" -PercentComplete 45
try {
@"
config.env
.env
*.env
node_modules/
__pycache__/
*.log
.vscode/
.DS_Store
"@ | Set-Content -Path "$ProjectPath\.gitignore" -Encoding UTF8
} catch { Fail "Failed to write .gitignore" }
Write-Output "[+] .gitignore created."

Write-Progress -Activity "Git Config" -Status "Setting global config + credentials" -PercentComplete 60
try {
    git config --global user.name $GitUser
    git config --global user.email $GitEmail
    git config --global credential.helper store
    if ($GitHubPAT) {
        $credPath = "$env:USERPROFILE\.git-credentials"
        "https://${GitUser}:${GitHubPAT}@github.com" | Out-File -Encoding ascii -FilePath $credPath
    }
} catch { Fail "Failed to configure Git" }
Write-Output "[+] Git configured with user $GitUser"

Write-Progress -Activity "Git Commit" -Status "Initializing + committing" -PercentComplete 75
try {
    if (-not (Test-Path ".git")) { git init }
    git add .
    git commit -m "Initial commit"
} catch { Fail "Failed to initialize or commit repository" }
Write-Output "[+] Git repo initialized and committed."

Write-Progress -Activity "GitHub Repo" -Status "Checking/creating repo $RepoName" -PercentComplete 85
try {
    if ($GitHubPAT) {
        $headers = @{Authorization="token $GitHubPAT"; "User-Agent"="PowerShell"}
        $repoCheck = Invoke-RestMethod -Uri "https://api.github.com/repos/$GitUser/$RepoName" -Headers $headers -ErrorAction SilentlyContinue
        if (-not $repoCheck) {
            $body = @{name=$RepoName; private=$false} | ConvertTo-Json
            Invoke-RestMethod -Method Post -Uri "https://api.github.com/user/repos" -Headers $headers -Body $body -ContentType "application/json"
            Write-Output "[+] GitHub repo created: $RepoName"
        } else {
            Write-Output "[✓] GitHub repo already exists."
        }
    } else {
        Write-Output "[!] GitHub PAT not provided; skipping repo check/creation."
    }
} catch { Fail "Failed to verify or create GitHub repository" }

Write-Progress -Activity "GitHub Push" -Status "Pushing to GitHub" -PercentComplete 95
try {
    git remote remove origin 2>$null
    git remote add origin "https://github.com/$GitUser/$RepoName.git"
    git branch -M main
    git push -u origin main
} catch { Fail "Failed to push to GitHub" }
Write-Output "[+] Repo pushed to https://github.com/$GitUser/$RepoName"

Write-Progress -Activity "Verification" -Status "Checking remote repo" -PercentComplete 100
try {
    $remoteCheck = git ls-remote "https://github.com/$GitUser/$RepoName.git"
    if ($LASTEXITCODE -eq 0 -and $remoteCheck) {
        Write-Output "`n[✓] Push verified. Remote repo is accessible:"
        Write-Output $remoteCheck
    } else {
        Fail "Verification failed. Remote repo not accessible."
    }
} catch { Fail "Failed to verify remote repo" }

Write-Output "`n[✓] Workspace setup, repo creation, push, and verification complete."
