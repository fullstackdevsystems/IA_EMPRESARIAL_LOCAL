param([string]$InstallPath,[switch]$NonInteractive,[string]$TenantId,[string]$TenantName,[string]$AdminUsername,[switch]$SkipSqlCheck,[switch]$SkipAiCheck,[switch]$ValidateOnly)
$ErrorActionPreference = "Stop"
& (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) 'InstallerR1020C1.ps1') @PSBoundParameters
exit $LASTEXITCODE
