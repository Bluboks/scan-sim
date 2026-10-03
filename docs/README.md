# 문서 허브

이 디렉터리는 `scan-sim`의 현행 문서를 주제와 수명주기로 나눈다. 루트 README는
설치·사용 진입점이고, 이 문서는 문서 자체의 진입점이다.

## 처음 읽는 순서

1. [GOVERNANCE](GOVERNANCE.md) — 문서 SoT, 위치, 변경 규칙.
2. [DECISIONS](DECISIONS.md) — 확정된 설계 결정과 근거.
3. [architecture/PIPELINE](architecture/PIPELINE.md) — 16단계 처리 순서와 단계별 물리 모델.
4. [reference/CLI](reference/CLI.md)와 [reference/CONFIG](reference/CONFIG.md) — 사용자가 보는 표면.
5. [ops/VALIDATION](ops/VALIDATION.md) — 검증 게이트, 현실성 점검 결과, 성능, 한계.
6. [ops/WEB](ops/WEB.md) — 브라우저 화면 실행, tailnet 배포, API.

## 구역과 역할

| 구역 | 역할 |
| --- | --- |
| 루트 `README.md` | 설치, 최소 사용 예, 문서 진입 링크 |
| `GOVERNANCE.md`, `DECISIONS.md`, `HISTORY.md` | 규칙, ADR-lite 인덱스, provenance |
| `architecture/` | 처리 단계와 물리 모델 |
| `reference/` | CLI 옵션과 설정 키 |
| `ops/` | 검증 절차, 측정 결과, 웹 화면 운영 |
| `decisions/` | 짧은 결정 기록(ADR-lite) |
| `archive/` | 원문 보존. 현행 규칙이 아님 |

## 파일 인덱스

- 규칙·결정·역사: [GOVERNANCE](GOVERNANCE.md), [DECISIONS](DECISIONS.md),
  [HISTORY](HISTORY.md), [ADR-001](decisions/ADR-001-v01-scope.md),
  [ADR-002](decisions/ADR-002-units-and-order.md),
  [ADR-003](decisions/ADR-003-seeds.md), [ADR-004](decisions/ADR-004-config-schema.md),
  [ADR-005](decisions/ADR-005-pdf-input.md)
- 구현: [PIPELINE](architecture/PIPELINE.md)
- 사용자 표면: [CLI](reference/CLI.md), [CONFIG](reference/CONFIG.md)
- 검증·운영: [VALIDATION](ops/VALIDATION.md), [WEB](ops/WEB.md)
- 보관: [최초 개발 명세](archive/2026-10-02-initial-brief.md)

## 현행·초안·보관

- 현행 문서는 루트와 위 구역의 주제별 파일이다.
- 초안이 필요하면 `docs/drafts/`에만 둔다. 초안은 현행 규칙의 근거가 아니다. 빈
  디렉터리나 placeholder는 만들지 않는다.
- [최초 개발 명세](archive/2026-10-02-initial-brief.md)는 2026-10-02 구현 당시의 요구를
  그대로 보존한 역사 자료다. 명세와 현행 동작이 다른 부분은 DECISIONS에 근거가 있다.
