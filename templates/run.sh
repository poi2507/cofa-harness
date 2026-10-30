#!/usr/bin/env bash
# 처음부터 끝까지 재실행. 단계가 실패하면 멈춘다.
set -euo pipefail
cd "$(dirname "$0")"
python3 src/data_check.py        # -> reports/data_check.md
# python3 src/prepare.py         # -> data/processed/
# python3 src/baseline.py        # -> outputs/, EXPERIMENTS 점수
# python3 src/build_dashboard.py # -> outputs/dashboard.html
echo "run.sh 완료 $(date +%H:%M)"
