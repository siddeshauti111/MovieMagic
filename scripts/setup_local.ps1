$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
if (!(Test-Path .venv/Scripts/python.exe)) {
    python -m venv .venv
    if ($LASTEXITCODE) { exit $LASTEXITCODE }
}
& .venv/Scripts/python.exe -m pip install -r requirements-dev.txt
if ($LASTEXITCODE) { exit $LASTEXITCODE }
if (!(Test-Path .env)) {
    $secret = & .venv/Scripts/python.exe -c 'import secrets; print(secrets.token_hex(32))'
    (Get-Content .env.example -Raw).Replace('FLASK_SECRET_KEY=', "FLASK_SECRET_KEY=$secret") | Set-Content .env -Encoding ascii
}
