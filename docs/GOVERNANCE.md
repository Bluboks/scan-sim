# 문서 거버넌스

이 문서는 문서 체계의 규칙 SoT다. 작업 규칙은 [AGENTS.md](../AGENTS.md)를 따른다.

## SoT 맵

| 문서 | SoT 역할 |
| --- | --- |
| [README](../README.md) | 설치·사용·문서 진입점 |
| [PIPELINE](architecture/PIPELINE.md) | 처리 순서, 색 영역, 단계별 모델 |
| [CLI](reference/CLI.md) | 명령줄 옵션, 출력 이름, 종료 코드 |
| [CONFIG](reference/CONFIG.md) | 설정 키, 단위, 프리셋 차이 |
| [VALIDATION](ops/VALIDATION.md) | 검증 게이트, 측정값, 알려진 한계 |
| [WEB](ops/WEB.md) | 웹 화면 실행, tailnet 배포, API |
| [DECISIONS](DECISIONS.md)와 `decisions/` | 확정된 설계 결정과 trade-off |
| [CHANGELOG](../CHANGELOG.md) | 사용자에게 보이는 변경 |
| [HISTORY](HISTORY.md) | 프로젝트 출처와 주요 milestone |
| `archive/` | 과거 원문. 현행 규칙이 아님 |

설정 값 자체의 SoT는 `src/scan_sim/configs/*.yaml`과 `src/scan_sim/config.py`다.
문서에는 값을 복제하지 않고 의미와 단위를 쓴다. 예외는 [CONFIG](reference/CONFIG.md)의
프리셋 차이 요약표 하나이며, 프리셋을 고칠 때 함께 갱신한다.

## 위치와 중복 금지

- 구현 구조는 `docs/architecture/`, 사용자 표면은 `docs/reference/`, 검증은
  `docs/ops/`, 결정은 `docs/decisions/`에 둔다.
- 루트에는 README, CHANGELOG, LICENSE, AGENTS, CLAUDE처럼 프로젝트 전체를 가리키는 파일만 둔다.
- 같은 사실을 여러 문서에 긴 본문으로 복제하지 말고 SoT 링크와 짧은 요약을 쓴다.

## 사실·계획·역사

- 사실은 현재 코드와 검증 결과로 확인된 것만 현재형으로 쓴다.
- 계획(v0.2 등)은 완료된 것처럼 쓰지 않는다.
- 역사는 날짜와 출처를 남기고 현행 규칙과 분리한다.
- 결정 기록에는 결정 주체를 적는다. 소유자가 정한 것은 "소유자 결정", 소유자가
  위임해 에이전트가 정한 것은 "에이전트 결정(위임)"이다. 제안만 된 것은 PROPOSED로
  두고 ACCEPTED로 쓰지 않는다.
- 실물 보정 없이 정한 값은 "추정"이라고 쓰고 실측처럼 표현하지 않는다.

## 변경 규칙

설정 키, 출력 이름, 메타데이터 필드, seed 파생 방식, 단계별 난수 순서를 바꾸면
CHANGELOG에 기록한다. 마지막 두 가지는 기존 데이터셋 재현성을 깨므로 "재현성 변경"이라고
명시한다. 문서만 재편한 변경은 버전 변경으로 표현하지 않는다.

## 크기

archive를 제외한 Markdown은 목표 200줄 이하다. README는 120줄 이하다. 독립된 두 번째
독자나 주제가 생기면 하위 파일로 나누고, 나눈 뒤에는 한 곳만 SoT로 둔다.
