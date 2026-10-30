#!/usr/bin/env bash
# 당일 세팅. 과제 작업 폴더 안에서 실행한다.
#   bash /tmp/h/setup.sh                    공통 규칙만
#   bash /tmp/h/setup.sh predict            공통 + 예측·분류 프로필
#   bash /tmp/h/setup.sh analyze dashboard  둘 이상도 가능
#   bash /tmp/h/setup.sh analyze --claude   연습용: CLAUDE.md와 .claude/skills/ 도 생성
# 프로필: analyze(원인분석) predict(예측·분류) anomaly(이상탐지) text-llm(비정형 LLM) automation(자동화) dashboard(대시보드)
# 유형을 바꾸려면 다시 실행한 뒤 Codex에서 /new (AGENTS.md는 세션 시작 때 읽는다)
set -e
H="$(cd "$(dirname "$0")" && pwd)"
CLAUDE=0; ARGS=()
for a in "$@"; do [ "$a" = "--claude" ] && CLAUDE=1 || ARGS+=("$a"); done
set -- "${ARGS[@]+"${ARGS[@]}"}"
{
  cat "$H/AGENTS.md"
  for p in "$@"; do
    f="$H/profiles/$p.md"
    if [ -f "$f" ]; then printf '\n---\n\n'; cat "$f"
    else echo "프로필 없음: $p (가능: $(ls "$H/profiles" | sed 's/\.md$//' | tr '\n' ' '))" >&2; fi
  done
} > ./AGENTS.md
cp "$H/PLAYBOOK.md" ./PLAYBOOK.md
mkdir -p .agents/skills scripts reports outputs
cp -r "$H/skills/." .agents/skills/
cp "$H/scripts/envcheck.sh" "$H/scripts/data_check.py" "$H/scripts/make_split.py" scripts/
for p in "$@"; do
  if [ "$p" = automation ]; then
    mkdir -p src tests
    [ -f src/pipeline.py ] || cp "$H/templates/pipeline.py" src/pipeline.py
    [ -f tests/test_pipeline.py ] || cp "$H/templates/test_pipeline.py" tests/test_pipeline.py
  fi
done
for f in REQUIREMENTS NOTES EXPERIMENTS VERIFICATION QA_PREP; do
  [ -f "$f.md" ] || cp "$H/templates/$f.md" "./$f.md"
done
[ -f run.sh ] || cp "$H/templates/run.sh" ./run.sh
[ -f ENV.md ] || bash scripts/envcheck.sh > ENV.md 2>&1 || true
if [ "$CLAUDE" = 1 ]; then   # 연습용: Claude Code가 읽는 이름으로도 복사
  cp ./AGENTS.md ./CLAUDE.md
  mkdir -p .claude/skills && cp -r .agents/skills/. .claude/skills/
  echo "연습 모드: CLAUDE.md, .claude/skills/ 도 생성 (claude 실행, 스킬은 /이름)"
fi
echo "AGENTS.md = 공통 규칙$([ $# -gt 0 ] && echo " + 프로필: $*") ($(wc -c < AGENTS.md) bytes)"
echo "다음: codex 실행 → /status 로 AGENTS.md 반영 확인 → /skills"
