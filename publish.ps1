<#
  Create and push this repository. Bound to Ctrl+Shift+B by .vscode/tasks.json.

  First run  : initialises the repository, commits, creates it on GitHub and pushes.
  Later runs : commits whatever changed and pushes.

  The repository is created public. To create it private instead, run this
  script with -Visibility private; to change it afterwards,
      gh repo edit vaspapa79/manning-atlas-europe --visibility private
#>
param(
    [string]$Message = "",
    [ValidateSet("public", "private")]
    [string]$Visibility = "public"
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# refuse to publish the CLMS credentials under any circumstances
if (Test-Path "clms_apikey.json") {
    throw "clms_apikey.json is present in the repository tree. Remove it before publishing."
}

if (-not (Test-Path ".git")) {
    Write-Host "initialising repository"
    git init -b main
}

git add -A
$staged = git diff --cached --name-only
if ($staged) {
    if (-not $Message) {
        $Message = "Manning's n atlas: code, look-up tables and derived tables"
    }
    git commit -m $Message
} else {
    Write-Host "nothing new to commit"
}

$remote = git remote
if (-not $remote) {
    $visFlag = "--" + $Visibility
    Write-Host "creating vaspapa79/manning-atlas-europe on GitHub ($Visibility)"
    gh repo create "manning-atlas-europe" $visFlag --source . --remote origin --push
} else {
    git push -u origin main
}

Write-Host ""
Write-Host "done:" (git remote get-url origin)
