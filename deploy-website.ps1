#requires -version 5.1
<#
.SYNOPSIS
  Deploy Twin Boss Agent website to GitHub Pages with domain management
.DESCRIPTION
  Secure deployment script that handles website deployment without exposing credentials
#>

param(
    [string]$GitHubUsername = $env:GITHUB_USERNAME,
    [string]$DomainName = $env:DOMAIN_MAIN,
    [string]$GitHubToken = $env:GITHUB_PAT,
    [string]$CloudflareToken = $env:CLOUDFLARE_API_TOKEN,
    [string]$RepoName = $env:REPO_NAME
)

$ErrorActionPreference = 'Stop'

function Write-Status($Message, $Color = "Green") {
    Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $Message" -ForegroundColor $Color
}

function Write-Warning($Message) {
    Write-Status $Message "Yellow"
}

function Write-Error($Message) {
    Write-Status $Message "Red"
}

function Test-Prerequisites {
    Write-Status "Checking prerequisites..."
    
    if (-not $GitHubUsername) {
        throw "GitHubUsername is required. Set GITHUB_USERNAME environment variable."
    }
    
    if (-not $GitHubToken) {
        throw "GitHub token is required. Set GITHUB_PAT environment variable."
    }
    
    if (-not $RepoName) {
        $RepoName = "$GitHubUsername.github.io"
        Write-Status "Using default repo name: $RepoName"
    }
    
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        throw "Git is required but not found in PATH"
    }
    
    Write-Status "Prerequisites check passed ✓"
}

function Initialize-LocalRepo {
    Write-Status "Setting up local repository..."
    
    $LocalPath = Join-Path $PWD "web"
    if (-not (Test-Path $LocalPath)) {
        New-Item -ItemType Directory -Path $LocalPath -Force | Out-Null
    }
    
    Push-Location $LocalPath
    
    if (-not (Test-Path ".git")) {
        Write-Status "Initializing Git repository..."
        git init
        git remote add origin "https://$GitHubUsername`:$GitHubToken@github.com/$GitHubUsername/$RepoName.git"
    }
    
    Write-Status "Local repository ready ✓"
}

function Ensure-GitHubRepo {
    Write-Status "Checking GitHub repository: $RepoName"
    
    $headers = @{
        Authorization = "token $GitHubToken"
        "User-Agent" = "PowerShell-TwinBoss-Deploy"
        Accept = "application/vnd.github.v3+json"
    }
    
    try {
        $repoCheck = Invoke-RestMethod -Uri "https://api.github.com/repos/$GitHubUsername/$RepoName" -Headers $headers -Method Get
        Write-Status "Repository exists ✓"
    }
    catch {
        if ($_.Exception.Response.StatusCode -eq 404) {
            Write-Status "Creating repository: $RepoName"
            
            $repoData = @{
                name = $RepoName
                private = $false
                description = "Twin Boss Agent Website"
                has_issues = $true
                has_projects = $true
                has_wiki = $true
            } | ConvertTo-Json
            
            try {
                Invoke-RestMethod -Uri "https://api.github.com/user/repos" -Headers $headers -Method Post -Body $repoData -ContentType "application/json"
                Write-Status "Repository created ✓"
            }
            catch {
                throw "Failed to create repository: $($_.Exception.Message)"
            }
        }
        else {
            throw "Failed to check repository: $($_.Exception.Message)"
        }
    }
}

function Deploy-Website {
    Write-Status "Deploying website content..."
    
    # Create .gitignore for web deployment
    @"
# Deployment artifacts
.DS_Store
Thumbs.db
"@ | Out-File -Encoding utf8 -FilePath ".gitignore"

    # Create CNAME file if domain is specified
    if ($DomainName) {
        Write-Status "Setting up custom domain: $DomainName"
        $DomainName | Out-File -Encoding ascii -FilePath "CNAME"
    }
    
    # Create index.html redirecting to fundraiser
    @"
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Twin Boss Agent</title>
    <meta http-equiv="refresh" content="0; url=./fundraiser.html">
    <link rel="canonical" href="./fundraiser.html">
</head>
<body>
    <p>Redirecting to <a href="./fundraiser.html">Twin Boss Agent</a>...</p>
</body>
</html>
"@ | Out-File -Encoding utf8 -FilePath "index.html"
    
    # Stage all changes
    git add .
    
    # Check if there are changes to commit
    $gitStatus = git status --porcelain
    if ($gitStatus) {
        Write-Status "Committing changes..."
        git commit -m "Deploy website - $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
        
        Write-Status "Pushing to GitHub Pages..."
        git branch -M main
        git push -u origin main --force
        
        Write-Status "Website deployed ✓"
    }
    else {
        Write-Status "No changes to deploy"
    }
}

function Clear-CloudflareCache {
    if ($CloudflareToken -and $DomainName) {
        Write-Status "Clearing Cloudflare cache for $DomainName..."
        
        try {
            # Get zone ID
            $headers = @{
                Authorization = "Bearer $CloudflareToken"
                "Content-Type" = "application/json"
            }
            
            $zoneResponse = Invoke-RestMethod -Uri "https://api.cloudflare.com/client/v4/zones?name=$DomainName" -Headers $headers -Method Get
            
            if ($zoneResponse.result -and $zoneResponse.result.Count -gt 0) {
                $zoneId = $zoneResponse.result[0].id
                
                # Purge cache
                $purgeData = @{ purge_everything = $true } | ConvertTo-Json
                Invoke-RestMethod -Uri "https://api.cloudflare.com/client/v4/zones/$zoneId/purge_cache" -Headers $headers -Method Post -Body $purgeData
                
                Write-Status "Cloudflare cache cleared ✓"
            }
            else {
                Write-Warning "Domain not found in Cloudflare"
            }
        }
        catch {
            Write-Warning "Failed to clear Cloudflare cache: $($_.Exception.Message)"
        }
    }
}

function Open-Website {
    $url = if ($DomainName) { "https://$DomainName" } else { "https://$GitHubUsername.github.io/$RepoName" }
    
    Write-Status "Opening website: $url"
    
    try {
        Start-Process $url
    }
    catch {
        Write-Status "Website URL: $url"
    }
}

function Main {
    try {
        Write-Status "Starting Twin Boss Agent deployment..."
        
        Test-Prerequisites
        Initialize-LocalRepo
        Ensure-GitHubRepo
        Deploy-Website
        Clear-CloudflareCache
        
        Pop-Location
        
        Write-Status "Deployment completed successfully! 🎉" "Green"
        Open-Website
    }
    catch {
        Write-Error "Deployment failed: $($_.Exception.Message)"
        if (Get-Location | Where-Object { $_.Path -match "web" }) {
            Pop-Location
        }
        exit 1
    }
}

# Run main function
Main