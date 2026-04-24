# PM Standards Comparator - API Key Setup Script
# Run this script to set up the Hugging Face API key

Write-Host "Setting up Hugging Face API key..." -ForegroundColor Green

# IMPORTANT:
# Do NOT hardcode tokens in this repo. Paste your own token locally when needed.
# Get a token from: https://huggingface.co/settings/tokens

# Set API key for current session (recommended)
$env:HUGGINGFACEHUB_API_TOKEN = "<PASTE_YOUR_HF_TOKEN_HERE>"

# Optional: set API key permanently for your Windows user
# setx HUGGINGFACEHUB_API_TOKEN "<PASTE_YOUR_HF_TOKEN_HERE>"

# Verify the key is set (will print placeholder unless you replaced it)
Write-Host "HUGGINGFACEHUB_API_TOKEN is set for this session." -ForegroundColor Yellow

# Navigate to project directory
Set-Location "E:\University\Semester 5\Project Management\Assigements\rte (2) - Copy\rte\Assignment_1"

Write-Host "Starting PM Standards Comparator application..." -ForegroundColor Green
python start_app.py
