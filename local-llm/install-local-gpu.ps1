$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$venvPath = Join-Path $projectRoot '.venv-local-llm'

if (-not (Test-Path -LiteralPath (Join-Path $venvPath 'Scripts\python.exe'))) {
    python -m venv $venvPath
}

$pythonExe = Join-Path $venvPath 'Scripts\python.exe'
& $pythonExe -m pip install --upgrade pip
& $pythonExe -m pip install -r (Join-Path $PSScriptRoot 'requirements.txt')
& $pythonExe -c "import torch; assert torch.cuda.is_available(), 'CUDA 不可用，拒绝安装为 CPU 推理'; print(torch.cuda.get_device_name(0))"
