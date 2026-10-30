# cofa-harness

데이터 기반 AI 문제 해결 과제를 Codex CLI로 수행할 때 쓰는 개인용 작업 방법 템플릿입니다.
작업 규칙(AGENTS.md), 스킬, 문서 템플릿, 환경 확인 스크립트만 있습니다. 과제 내용·데이터·결과물은 포함하지 않습니다.

## 사용
```
git clone https://github.com/<id>/cofa-harness.git /tmp/h && bash /tmp/h/setup.sh
```
clone이 안 되면 `AGENTS.min.md` 내용을 작업 폴더의 `AGENTS.md`로 직접 입력합니다.

## 구성
- `AGENTS.md` 작업 규칙 전체 / `AGENTS.min.md` 직접 입력용 축약판
- `PLAYBOOK.md` 미션 유형별 대응과 예상 질문
- `skills/` problem-frame · data-check · baseline · verify · report · qa-prep · llm-pipeline · dashboard · no-deps
- `templates/` REQUIREMENTS · NOTES · EXPERIMENTS · VERIFICATION · QA_PREP · run.sh
- `scripts/envcheck.sh` 환경 기록
- `setup.sh` 위 파일을 작업 폴더에 배치
