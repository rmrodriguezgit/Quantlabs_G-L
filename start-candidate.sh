#!/bin/sh
set -eu
cd "$(dirname "$0")"
# Independent paper account in this checkout. Does not replace the engine on 8000.
export PORT=${PORT:-8002}
export LAYA_EXECUTION=${LAYA_EXECUTION:-quant_laya}
exec ./start-live.sh
