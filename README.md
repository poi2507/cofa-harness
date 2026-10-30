# cofa-harness

데이터 기반 AI 문제 해결 과제를 Codex CLI로 수행할 때 쓰는 개인용 작업 방법 템플릿입니다.
작업 규칙(AGENTS.md), 유형별 프로필, 스킬, 문서 템플릿, 환경 확인 스크립트만 있습니다. 과제 내용·데이터·결과물은 포함하지 않습니다.

## 당일 순서 (과제 작업 폴더 안의 터미널에서)

```
git clone https://github.com/poi2507/cofa-harness.git /tmp/h     # 1. 받기 (이 줄만 외우면 됨)
cat /tmp/h/README.md                                              # 2. 이 안내 보기
bash /tmp/h/setup.sh                                              # 3. 세팅. 과제 유형을 알면 뒤에 붙인다 (아래 표)
codex                                                             # 4. 시작 → /status 로 AGENTS.md 확인 → /skills
```

| 과제가 이런 거면 | 3번에 붙일 것 |
|---|---|
| 원인을 찾아라, 왜 떨어졌나, 개선안 | `analyze` |
| 예측·분류, 타깃 컬럼, train/test | `predict` |
| 센서·시계열에서 이상·고장 징후 | `anomaly` |
| 텍스트·로그·메모를 LLM으로 분류·요약 | `text-llm` |
| 파일 여러 개를 정리·집계·보고서로 자동화 | `automation` |
| 대시보드, 한눈에, 현업이 쓸 화면 | `dashboard` |

예: `bash /tmp/h/setup.sh analyze` / 섞였으면 `bash /tmp/h/setup.sh analyze dashboard` / 모르겠으면 인자 없이.
유형을 바꾸려면 다시 실행하고 Codex에서 `/new`.

clone이 안 되면 `AGENTS.min.md`(9줄) 내용을 작업 폴더의 `AGENTS.md`로 직접 입력합니다.

## Codex 안에서
- 시작: `$problem-frame` → 데이터: `$data-check` → 분할: `$test-set` → `$baseline` → 검증: `$verify` → 마무리: `$report`, `$qa-prep`
- 패키지가 없으면 `$no-deps`, 텍스트 데이터면 `$llm-pipeline`, 화면이 필요하면 `$dashboard`
- 말로: **"시간 체크"** / **"설명해줘 X"** / **"Q&A 준비"**
- 스킬이 안 먹히는 버전이면 AGENTS.md만으로 같은 절차가 돌아갑니다. 첫 프롬프트: `BRIEF를 읽고 AGENTS.md의 시작 절차 1단계부터 진행해. 계획 승인 전에는 코드를 쓰지 마.`

## 연습 (Claude Code로)
`bash /tmp/h/setup.sh analyze --claude` 처럼 `--claude`를 붙이면 `CLAUDE.md`와 `.claude/skills/`도 같이 만들어집니다. 그다음 `claude`. 스킬은 `$data-check` 대신 `/data-check`.

## 구성
- `AGENTS.md` 작업 규칙 전체 / `AGENTS.min.md` 직접 입력용 축약판
- `profiles/` 유형별 추가 규칙: analyze · predict · anomaly · text-llm · automation · dashboard
- `PLAYBOOK.md` 미션 유형별 대응과 예상 질문 (시험 전 읽기용)
- `skills/` problem-frame · data-check · test-set · baseline · verify · report · qa-prep · llm-pipeline · dashboard · no-deps
- `templates/` REQUIREMENTS · NOTES · EXPERIMENTS · VERIFICATION · QA_PREP · run.sh · pipeline.py + test_pipeline.py (자동화 뼈대, `automation` 프로필일 때 src/·tests/에 배치)
- `scripts/envcheck.sh` 환경 기록 → ENV.md / `scripts/data_check.py` CSV 품질 점검 → reports/data_check.md / `scripts/make_split.py` 학습·검증·테스트 분할(random·stratify·time·group) → data/splits/ (모두 표준 라이브러리만)
- `setup.sh` 위 파일을 작업 폴더에 배치
