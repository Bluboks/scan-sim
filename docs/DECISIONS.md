# 결정 기록 인덱스

ADR-lite 상태는 `ACCEPTED`만 현재 설계에 적용한다. 각 기록은 배경, 결정, 이유와
trade-off, 후속을 짧게 남긴다. 결정 주체(소유자 결정 / 에이전트 결정(위임))를 함께 적는다.

## 결정 목록

| ID | 상태·날짜 | 결정 주체 | 주제 |
| --- | --- | --- | --- |
| [ADR-001](decisions/ADR-001-v01-scope.md) | ACCEPTED · 2026-10-02 | 소유자 | v0.1 범위와 실물 비교 없는 현실성 기준 |
| [ADR-002](decisions/ADR-002-units-and-order.md) | ACCEPTED · 2026-10-02 | 에이전트(위임) | 단위, 해상도, 색 영역, 단계 순서 |
| [ADR-003](decisions/ADR-003-seeds.md) | ACCEPTED · 2026-10-02 | 에이전트(위임) | seed 파생과 단계별 난수 스트림 |
| [ADR-004](decisions/ADR-004-config-schema.md) | ACCEPTED · 2026-10-02 | 에이전트(위임) | 완전한 프리셋, 엄격한 스키마, 추가 키 |
| [ADR-005](decisions/ADR-005-pdf-input.md) | ACCEPTED · 2026-10-03 | 소유자 · 에이전트(위임) | PDF 입력, pypdfium2, 페이지별 이름과 seed |
| [ADR-006](decisions/ADR-006-sheet-border.md) | ACCEPTED · 2026-10-03 | 소유자 · 에이전트(위임) | 종이 경계, 배경판, 스캔 여백, 좌표 기록 |

## Template

```markdown
# ADR-NNN: 제목

- 상태: PROPOSED | ACCEPTED | SUPERSEDED
- 날짜: YYYY-MM-DD
- 결정 주체: 소유자 | 에이전트(위임)

## 배경
## 결정
## 이유·trade-off
## 후속
```

새 결정은 이 인덱스와 개별 파일을 함께 추가한다. 변경·폐기는 기존 기록을 지우지
말고 상태와 대체 ADR을 남긴다.
