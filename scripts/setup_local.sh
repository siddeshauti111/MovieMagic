#!/usr/bin/env bash
set -eu
cd "$(dirname "$0")/.."
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
if [ ! -e .env ]; then
    umask 077
    secret=$(.venv/bin/python -c 'import secrets; print(secrets.token_hex(32))')
    sed "s/^FLASK_SECRET_KEY=$/FLASK_SECRET_KEY=$secret/" .env.example > .env
fi
