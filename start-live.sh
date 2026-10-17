#!/bin/sh
set -eu
cd "$(dirname "$0")"
export LAYA_MODE=live
export LAYA_MODEL=${LAYA_MODEL:-aac6fef/laya-mlx}
export HF_HOME=${HF_HOME:-"$PWD/backend/data/huggingface"}
export HF_HUB_DISABLE_XET=1
export LAYA_INSTALL_ML=1
[ -d .venv ] || "${PYTHON:-python3}" -m venv .venv
.venv/bin/python -m pip install --no-cache-dir -r requirements-laya.txt
exec ./start.sh
