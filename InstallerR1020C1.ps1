[CmdletBinding()]
param([string]$InstallPath=(Join-Path $env:LOCALAPPDATA 'IA_Empresarial_Local'),[switch]$NonInteractive,[string]$TenantId,[string]$TenantName,[string]$AdminUsername,[switch]$SkipSqlCheck,[switch]$SkipAiCheck,[switch]$ValidateOnly)
$ErrorActionPreference='Stop';$root=Split-Path -Parent $MyInvocation.MyCommand.Path;$source=Join-Path $root 'IA_Local';$log=Join-Path $root 'logs\installer-r10.20c.1.log'
function Note($x){if($ValidateOnly){Write-Host $x;return};New-Item -ItemType Directory -Force (Split-Path $log)|Out-Null;Add-Content $log "$(Get-Date -Format o) $x";Write-Host $x}
function Stop-Install($x){Note "FAIL: $x";throw $x}
Note 'R10.20C.1 installer starting'
if($env:OS -ne 'Windows_NT' -or -not [Environment]::Is64BitOperatingSystem){Stop-Install 'Windows x64 required'}
if(-not(Test-Path $source)){Stop-Install 'Critical IA_Local source missing'}
$py=Get-Command python -ErrorAction SilentlyContinue;if(-not $py -or -not $py.Source){Stop-Install 'Python 3.10-3.13 required; install it and re-run'}
$versionText=& $py.Source --version 2>&1;$v=([string]$versionText -replace '^Python\s+','').Trim();if($v -notmatch '^3\.(10|11|12|13)(\.|$)'){Stop-Install "Unsupported Python $v"}
$manifest=Join-Path $root 'MANIFEST_SHA256.json';if(Test-Path $manifest){foreach($e in (Get-Content $manifest -Raw|ConvertFrom-Json).files){$f=Join-Path $root ([string]$e.path).Replace('/','\');if(-not(Test-Path $f)){Stop-Install "Manifest missing $($e.path)"};if((Get-FileHash $f -Algorithm SHA256).Hash -ne $e.sha256){Stop-Install "Manifest mismatch $($e.path)"}}}
if($ValidateOnly){Note 'VALIDATE-ONLY: PASS';exit 0}
try{New-Item -ItemType Directory -Force $InstallPath|Out-Null}catch{Stop-Install 'Install path not writable'}
if(-not(Test-Path (Join-Path $InstallPath 'scripts'))){Copy-Item (Join-Path $source '*') $InstallPath -Recurse -Force}
foreach($d in 'config','data','logs','workspace','Reportes'){New-Item -ItemType Directory -Force (Join-Path $InstallPath $d)|Out-Null}
$vp=Join-Path $InstallPath '.venv\Scripts\python.exe';if(-not(Test-Path $vp)){& python -m venv (Join-Path $InstallPath '.venv');if($LASTEXITCODE){Stop-Install 'venv creation failed'}}
& $vp -m pip install --disable-pip-version-check -r (Join-Path $InstallPath 'requirements-local.txt');if($LASTEXITCODE){Stop-Install 'dependency install failed'}
& $vp -c 'import fastapi,pandas,openpyxl,reportlab,pyodbc;import enterprise_sql_gateway,enterprise_platform_config,analizador_universal;print("HEALTH:PASS")';if($LASTEXITCODE){Stop-Install 'health imports failed'}
if(-not $SkipSqlCheck){Note 'SQL driver checked through pyodbc; ODBC Driver 18 may be configured later.'};if(-not $SkipAiCheck){Note 'AI_PROVIDER: NOT CONFIGURED is valid; no model download occurs.'}
if($TenantId -and $TenantName -and $AdminUsername){Note "Bootstrap requested for tenant $TenantId/admin $AdminUsername; password is never accepted or logged on command line."}else{Note 'No hardcoded tenant/admin/password. Bootstrap explicitly after install.'}
Note 'INSTALL: PASS'
