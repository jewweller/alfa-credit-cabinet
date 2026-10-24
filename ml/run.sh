#!/bin/sh
set -eu
ML_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$ML_ROOT"
export PYTHONDONTWRITEBYTECODE=1
export UV_CACHE_DIR="$ML_ROOT/.uv-cache"
export PYTHONPATH="$ML_ROOT/..:$ML_ROOT/../backend${PYTHONPATH:+:$PYTHONPATH}"
exec uv run --frozen "$@"
