# 인터랙티브 설명서 사실 검증 보고서

검증 대상: `TODO_PRD.html`, `TODO_PRD_ELI5.html`

| # | 주장 | 위치 | 판정 | 근거 | 심각도 | 수정 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 기록된 작업 40개가 모두 완료됐다 | 두 문서의 현황 카드 | supported | `TODO_PRD.md`의 체크 항목 40개가 모두 `[x]`이며 각 항목에 완료 시각이 있다 | high | 없음 |
| 2 | 파서 테스트 163개가 통과했다 | 두 문서의 검사 설명 | supported | 2026-09-20 실행한 `uv run pytest -q` 결과 `163 passed`; `TODO_PRD.md` 진행 로그 | high | 없음 |
| 3 | 웹 테스트 25개가 통과했다 | 두 문서의 검사 설명 | supported | 2026-09-20 실행한 unittest 결과 `Ran 25 tests`, `OK`; `TODO_PRD.md` 진행 로그 | high | 없음 |
| 4 | 알 수 없는 콘텐츠 정책은 preserve, error, drop이다 | 상세판 Figure 2 | supported | `src/confluence_content_parser/diagnostics.py:9`의 `UnknownContentPolicy` | high | 없음 |
| 5 | GenericElement는 이름, 네임스페이스, 속성, 자식을 보존한다 | 상세판 손실 방지 섹션 | supported | `nodes.py:133`, `parser.py:454`의 보존 분기 | high | 없음 |
| 6 | GenericMacro는 정렬된 매개변수와 본문 종류를 보존한다 | 상세판 손실 방지 섹션 | supported | `nodes.py:585`, `nodes.py:593`, `nodes.py:601` | high | 없음 |
| 7 | 공개 등록 API는 인스턴스별이며 충돌을 막는다 | 상세판 확장성과 안전성 섹션 | supported | `parser.py:130`, `parser.py:231`, `parser.py:236`, `parser.py:241` | high | 없음 |
| 8 | XML 크기, 깊이, 노드, 매개변수, 평문 제한이 있다 | 상세판 Figure 3 설명 | supported | `diagnostics.py:44`의 `ParserLimits` 필드 | high | 없음 |
| 9 | 탭과 PlantUML은 선택형 어댑터로 등록된다 | 상세판 어댑터 섹션 | supported | `extensions.py:36`, `extensions.py:70` | high | 없음 |
| 10 | draw.io 인라인 XML은 로컬 SVG로, 첨부 전용 매크로는 fallback으로 처리된다 | 두 문서의 draw.io 설명 | supported | `https://github.com/huklee/confluence-content-server/blob/main/parse_confluence.py:328`, `parse_confluence.py:440`; 관련 웹 테스트 | high | 없음 |
| 11 | 서버 launcher는 호스트, 포트, reload, PlantUML jar를 받는다 | ELI5 결과 섹션 | supported | `https://github.com/huklee/confluence-content-server/blob/main/run_server.sh`; `tests/test_launcher.py` | high | 없음 |
| 12 | 사용자는 결과와 피드백을 제시했고 실행 과정은 위임했다 | ELI5 위임 섹션 | supported | 이 대화의 사용자 요청 순서와 “모든 일을 위임했다는 점을 강조”하라는 명시적 지시 | low | 없음 |
| 13 | 완료 시각과 기능 묶음의 순서 | 상세판 Figure 5 | supported | `TODO_PRD.md` 진행 로그의 2026-09-19 22:01:37부터 2026-09-20 00:37:00까지의 기록 | high | 없음 |

전체 판정: **PASS**

미해결 `needs-source`, `unsupported`, `contradicted` 항목: **0개**
