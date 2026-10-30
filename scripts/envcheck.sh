#!/usr/bin/env bash
# 환경 기록. 사용: bash scripts/envcheck.sh > ENV.md
echo "# ENV ($(date '+%F %H:%M'))"
echo; echo "## 도구"
for c in python3 node npm git codex; do
  printf -- "- %s: " "$c"
  command -v "$c" >/dev/null 2>&1 && "$c" --version 2>&1 | head -1 || echo "없음"
done
echo; echo "## 파이썬 패키지"
python3 - <<'PY'
import importlib.util as u
mods = ["pandas","numpy","scipy","sklearn","lightgbm","xgboost","matplotlib","seaborn","plotly",
        "openpyxl","polars","statsmodels","requests","openai","flask","fastapi","pytest"]
for m in mods:
    s = u.find_spec(m)
    v = ""
    if s:
        try: v = __import__(m).__version__
        except Exception: v = "?"
    print(f"- {m}: {'있음 ' + v if s else '없음'}")
PY
echo; echo "## 네트워크"
printf -- "- github: "; (curl -sI -m 5 https://github.com | head -1) 2>/dev/null || echo "연결 안 됨"
printf -- "- pypi: ";   (curl -sI -m 5 https://pypi.org | head -1) 2>/dev/null || echo "연결 안 됨"
echo; echo "## 환경변수 (키 이름만)"
env | grep -iE "api|key|token|openai" | cut -d= -f1 | sed 's/^/- /' || true
echo; echo "## 파일"
ls -la
echo
find . -maxdepth 3 -type f \( -name "*.csv" -o -name "*.xlsx" -o -name "*.json" -o -name "*.parquet" -o -name "*.txt" -o -name "*.md" \) \
  -not -path "./.git/*" -not -path "./.agents/*" | head -50
