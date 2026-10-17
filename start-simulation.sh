#!/bin/sh
set -eu
cd "$(dirname "$0")"
# Separate account; real quotes; simulated fills; GAN direction with mandatory LAYA approval.
export LAYA_EXECUTION=gan_laya
exec ./start-live.sh
