#!/usr/bin/env bash
# 당일 세팅. 과제 작업 폴더 안에서:  bash /tmp/h/setup.sh
set -e
H="$(cd "$(dirname "$0")" && pwd)"
cp "$H/AGENTS.md" ./AGENTS.md
cp "$H/PLAYBOOK.md" ./PLAYBOOK.md
mkdir -p .agents/skills scripts reports outputs
cp -r "$H/skills/." .agents/skills/
cp "$H/scripts/envcheck.sh" scripts/
for f in REQUIREMENTS NOTES EXPERIMENTS VERIFICATION QA_PREP; do
  [ -f "$f.md" ] || cp "$H/templates/$f.md" "./$f.md"
done
[ -f run.sh ] || cp "$H/templates/run.sh" ./run.sh
bash scripts/envcheck.sh > ENV.md 2>&1 || true
echo "세팅 완료. 다음: codex 실행 → /status 로 AGENTS.md 반영 확인 → /skills 로 스킬 확인"
