param(
    [string]$WeFlowUrl = "http://127.0.0.1:5031",
    [switch]$IncludeEasyChatDeps,
    [switch]$SkipStatusCheck
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Get-PythonCommand {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return @($python.Source)
    }

    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        return @($py.Source, "-3")
    }

    throw "未找到 Python。请先安装 Python 3.9+，并确保 python 或 py 可用。"
}

function Invoke-Python {
    param([string[]]$Arguments)
    $executable = $script:PythonCommand[0]
    $prefixArgs = @()
    if ($script:PythonCommand.Length -gt 1) {
        $prefixArgs = $script:PythonCommand[1..($script:PythonCommand.Length - 1)]
    }
    & $executable @prefixArgs @Arguments
}

function Test-WeFlowApi {
    param([string]$Url)

    try {
        $health = Invoke-RestMethod -Uri "$Url/health" -Method Get -TimeoutSec 3
        return $null -ne $health
    }
    catch {
        return $false
    }
}

function Install-WeFlow {
    param([string]$Url)

    if (Test-WeFlowApi -Url $Url) {
        Write-Host "WeFlow API 已可用：$Url" -ForegroundColor Green
        return
    }

    Write-Step "未检测到 WeFlow API，开始安装 WeFlow"
    if (-not [System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform([System.Runtime.InteropServices.OSPlatform]::Windows)) {
        throw "自动安装 WeFlow 仅支持 Windows。请手动安装并启动 WeFlow 后重试。"
    }

    $release = Invoke-RestMethod `
        -Uri "https://api.github.com/repos/hicccc77/WeFlow/releases/latest" `
        -Headers @{ "User-Agent" = "wechat-cli-installer" }

    $asset = $release.assets |
        Where-Object { $_.name -match "x64-Setup\.exe$" } |
        Select-Object -First 1

    if (-not $asset) {
        throw "未能在 WeFlow 最新 Release 中找到 Windows x64 安装包。"
    }

    $downloadDir = Join-Path $env:TEMP "wechat-cli-install"
    New-Item -ItemType Directory -Force -Path $downloadDir | Out-Null
    $installerPath = Join-Path $downloadDir $asset.name

    Write-Host "下载 WeFlow：$($asset.name)"
    Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $installerPath

    Write-Host "启动 WeFlow 安装程序，请按安装向导完成安装。"
    $process = Start-Process -FilePath $installerPath -PassThru
    $process.WaitForExit()

    Write-Host "等待 WeFlow API 可用：$Url"
    for ($i = 1; $i -le 60; $i++) {
        if (Test-WeFlowApi -Url $Url) {
            Write-Host "WeFlow API 已可用。" -ForegroundColor Green
            return
        }
        Start-Sleep -Seconds 2
    }

    throw "WeFlow 已安装程序执行完成，但 API 仍不可用。请打开 WeFlow，连接微信数据源，并启用 API 服务后重新运行本脚本。"
}

Set-Location (Resolve-Path (Join-Path $PSScriptRoot ".."))

Write-Step "检查 Python"
$script:PythonCommand = Get-PythonCommand
Invoke-Python -Arguments @("--version")

Write-Step "创建或复用虚拟环境"
if (-not (Test-Path ".venv/Scripts/python.exe")) {
    Invoke-Python -Arguments @("-m", "venv", ".venv")
}

$VenvPython = Resolve-Path ".venv/Scripts/python.exe"

Write-Step "安装 Python 依赖"
& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r requirements.txt
& $VenvPython -m pip install -e .
& $VenvPython -m pip install uiautomation pyperclip pycryptodome psutil

if ($IncludeEasyChatDeps) {
    Write-Step "安装 easyChat 兼容依赖"
    & $VenvPython -m pip install PyQt5 pyautogui pandas numpy Pillow
}

Install-WeFlow -Url $WeFlowUrl

Write-Step "写入默认配置"
& $VenvPython -m wechat_cli.cli config set read_driver weflow
& $VenvPython -m wechat_cli.cli config set send_driver native
& $VenvPython -m wechat_cli.cli config set use_native_driver false
& $VenvPython -m wechat_cli.cli config set weflow_url $WeFlowUrl

Write-Step "验证安装"
& $VenvPython -m wechat_cli.cli --help | Out-Null
& $VenvPython -m compileall wechat_cli

if (-not $SkipStatusCheck) {
    & $VenvPython -m wechat_cli.cli status
}

Write-Host ""
Write-Host "安装完成。常用命令：" -ForegroundColor Green
Write-Host "  .\.venv\Scripts\python.exe -m wechat_cli.cli status"
Write-Host "  .\.venv\Scripts\python.exe -m wechat_cli.cli sessions --limit 5"
Write-Host "  .\.venv\Scripts\python.exe -m wechat_cli.cli send `"文件传输助手`" `"测试发送`""
