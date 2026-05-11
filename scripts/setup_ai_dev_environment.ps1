# Set up Codebot AI development environment (Windows PowerShell).
# Run from project root:  .\scripts\setup_ai_dev_environment.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "Project root: $Root"

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "Creating .venv ..."
    py -3 -m venv .venv
}

$Py = ".\.venv\Scripts\python.exe"
$Pip = ".\.venv\Scripts\pip.exe"

Write-Host "Installing requirements-ai-dev.txt (large download: PyTorch + spaCy + ...) ..."
& $Pip install -U pip
& $Pip install -r requirements-ai-dev.txt

Write-Host "Downloading spaCy English model (en_core_web_sm) ..."
& $Py -m spacy download en_core_web_sm

Write-Host "Downloading common NLTK data..."
& $Py -c @"
import nltk
for pkg in ('punkt', 'punkt_tab', 'stopwords', 'wordnet'):
    try:
        nltk.download(pkg, quiet=True)
    except Exception as e:
        print('skip', pkg, e)
print('NLTK downloads done.')
"@

Write-Host ""
Write-Host "Done. Activate with:  .\.venv\Scripts\Activate.ps1"
Write-Host "Start Jupyter:        jupyter notebook"
Write-Host ""
