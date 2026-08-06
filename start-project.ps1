$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$modelScript = Join-Path $projectRoot 'local-llm\start-local-gpu.ps1'
$modelOut = Join-Path $projectRoot 'local-llm\server.out.log'
$modelErr = Join-Path $projectRoot 'local-llm\server.err.log'
$expectedModel = 'tiaozhanbei-qwen3-1.7b-local'
$expectedModelPath = [IO.Path]::GetFullPath('D:\QLDownload\Qwen3-1.7B-lora\Qwen3-1.7B-lora\merged')

$listening = Get-NetTCPConnection -LocalPort 8010 -State Listen -ErrorAction SilentlyContinue
$startModel = -not $listening

if ($listening) {
    try {
        $runningHealth = Invoke-RestMethod 'http://127.0.0.1:8010/health' -TimeoutSec 3
        $runningPath = [IO.Path]::GetFullPath([string]$runningHealth.model_path)
        $isExpectedModel = $runningHealth.ok `
            -and $runningHealth.cuda `
            -and ([string]$runningHealth.model -eq $expectedModel) `
            -and ($runningPath -eq $expectedModelPath)
    } catch {
        $isExpectedModel = $false
    }

    if (-not $isExpectedModel) {
        $modelProcessIds = $listening | Select-Object -ExpandProperty OwningProcess -Unique
        foreach ($modelProcessId in $modelProcessIds) {
            Stop-Process -Id $modelProcessId -Force -ErrorAction SilentlyContinue
        }
        for ($attempt = 0; $attempt -lt 20; $attempt++) {
            if (-not (Get-NetTCPConnection -LocalPort 8010 -State Listen -ErrorAction SilentlyContinue)) {
                break
            }
            Start-Sleep -Milliseconds 250
        }
        $startModel = $true
    }
}

if ($startModel) {
    Start-Process -FilePath 'powershell.exe' `
        -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $modelScript) `
        -RedirectStandardOutput $modelOut `
        -RedirectStandardError $modelErr `
        -WindowStyle Hidden
}

$ready = $false
for ($attempt = 0; $attempt -lt 60; $attempt++) {
    try {
        $health = Invoke-RestMethod 'http://127.0.0.1:8010/health' -TimeoutSec 2
        if ($health.ok -and $health.cuda) {
            $ready = $true
            break
        }
    } catch {
        Start-Sleep -Seconds 2
    }
}
if (-not $ready) {
    throw "本机 CUDA 模型启动失败，请查看 $modelErr"
}

docker compose -f (Join-Path $projectRoot 'docker-compose.yml') up -d --build
Write-Host 'Project started. Local GPU model connected.'
