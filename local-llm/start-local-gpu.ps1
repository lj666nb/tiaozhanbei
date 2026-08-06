$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $projectRoot '.venv-local-llm\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw '本地 GPU 推理环境尚未安装，请先运行 install-local-gpu.ps1'
}

$env:CUDA_VISIBLE_DEVICES = '0'
$env:LOCAL_LLM_MODEL_PATH = 'D:\QLDownload\Qwen3-1.7B-lora\Qwen3-1.7B-lora\merged'
$env:LOCAL_LLM_MODEL_NAME = 'tiaozhanbei-qwen3-1.7b-local'
$env:LOCAL_LLM_PORT = '8010'
& $pythonExe (Join-Path $PSScriptRoot 'server.py')
