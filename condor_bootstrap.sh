#!/usr/bin/env bash
set -euo pipefail
tar -xzf package.tgz
exec bash condor/run.sh "$@"
