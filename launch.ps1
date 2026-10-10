param([switch]$Check, [switch]$Tui, [switch]$Stop, [switch]$Install)
$ErrorActionPreference = 'Stop'
try {
    $configPath = Join-Path $PSScriptRoot 'config.json'
    if (-not (Test-Path -LiteralPath $configPath)) {
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'config.example.json') -Destination $configPath
    }
    $config = Get-Content -LiteralPath $configPath -Raw -Encoding utf8 | ConvertFrom-Json
    $candidates = [System.Collections.Generic.List[string]]::new()
    if ($config.paths.python) { $candidates.Add([string]$config.paths.python) }
    foreach ($command in @(Get-Command python.exe, python3.exe -ErrorAction SilentlyContinue)) { $candidates.Add($command.Source) }
    foreach ($root in @('HKCU:\Software\Python\PythonCore', 'HKLM:\Software\Python\PythonCore', 'HKLM:\Software\WOW6432Node\Python\PythonCore')) {
        if (Test-Path -LiteralPath $root) {
            foreach ($version in Get-ChildItem -LiteralPath $root) {
                $installKey = Join-Path $version.PSPath 'InstallPath'
                if (Test-Path -LiteralPath $installKey) {
                    $pythonInstallKey = Get-Item -LiteralPath $installKey
                    if ($pythonInstallKey.GetValue('ExecutablePath')) { $candidates.Add($pythonInstallKey.GetValue('ExecutablePath')) }
                    if ($pythonInstallKey.GetValue('')) { $candidates.Add((Join-Path $pythonInstallKey.GetValue('') 'python.exe')) }
                }
            }
        }
    }
    function Resolve-Python([string]$Value) {
        if (-not $Value) { return $null }
        $candidate = [Environment]::ExpandEnvironmentVariables($Value.Trim().Trim('"'))
        if (Test-Path -LiteralPath $candidate -PathType Container) { $candidate = Join-Path $candidate 'python.exe' }
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { return $null }
        if ($candidate -like '*\WindowsApps\*') { return $null }
        if (-not (Test-Path -LiteralPath (Join-Path (Split-Path $candidate) 'pythonw.exe'))) { return $null }
        try {
            $probe = & $candidate -c 'import sys; print("PYTHON_OK" if sys.version_info >= (3,10) else "TOO_OLD")' 2>$null
            if ($LASTEXITCODE -eq 0 -and $probe -contains 'PYTHON_OK') { return (Resolve-Path -LiteralPath $candidate).Path }
        } catch { return $null }
        return $null
    }
    $pythonPath = $null
    foreach ($candidate in $candidates | Select-Object -Unique) {
        $pythonPath = Resolve-Python $candidate
        if ($pythonPath) { break }
    }
    if (-not $pythonPath -and $Check) { throw '未检测到 Python 3.10+（需要同目录 pythonw.exe）。请运行 Start-WeCom.cmd 手动填写。' }
    if (-not $pythonPath -and -not $Tui) {
        $arguments = @('-NoLogo', '-NoProfile', '-File', ('"{0}"' -f $PSCommandPath), '-Tui')
        if ($Stop) { $arguments += '-Stop' }
        if ($Install) { $arguments += '-Install' }
        Start-Process -FilePath (Join-Path $PSHOME 'pwsh.exe') -ArgumentList $arguments -WindowStyle Normal
        exit 0
    }
    while (-not $pythonPath) {
        Write-Host '未检测到 Python。请输入 python.exe 完整路径或安装目录（需 Python 3.10+ 及 pythonw.exe）；留空取消。'
        $manual = Read-Host 'Python 路径'
        if (-not $manual) { exit 0 }
        $pythonPath = Resolve-Python $manual
        if (-not $pythonPath) { Write-Host '路径不可用，请重新填写。' -ForegroundColor Yellow }
    }
    $env:PYTHONIOENCODING = 'utf-8'
    if ($Install) {
        & $pythonPath -m pip install --target (Join-Path $PSScriptRoot 'deps') --requirement (Join-Path $PSScriptRoot 'requirements.txt')
        if ($LASTEXITCODE -ne 0) { throw '依赖安装失败，请查看上方输出。' }
        Write-Host '依赖安装完成。双击 Start-WeCom.cmd 选择导航项目。'
        if ($Tui) { Read-Host '按回车关闭窗口' }
        exit 0
    } elseif ($Stop) {
        & $pythonPath (Join-Path $PSScriptRoot 'launcher.py') --stop
    } elseif ($Check) {
        & $pythonPath (Join-Path $PSScriptRoot 'launcher.py') --check
    } elseif ($Tui) {
        & $pythonPath (Join-Path $PSScriptRoot 'tui.py')
    } else {
        $pythonWindowless = Join-Path (Split-Path $pythonPath) 'pythonw.exe'
        if (-not (Test-Path -LiteralPath $pythonWindowless)) { throw "找不到 Python 后台运行程序" }
        Start-Process -FilePath $pythonWindowless -ArgumentList @(('"{0}"' -f (Join-Path $PSScriptRoot 'launcher.py')), '--background') -WindowStyle Hidden
        exit 0
    }
    if ($LASTEXITCODE -ne 0) { throw "启动器已停止，错误信息见上方。" }
} catch {
    Write-Host $_ -ForegroundColor Red
    if ($Tui) { Read-Host '按回车关闭窗口' }
    elseif (-not $Check) {
        $popup = New-Object -ComObject WScript.Shell
        $popup.Popup([string]$_, 0, '企业微信导航启动器', 16) | Out-Null
    }
    exit 1
}
