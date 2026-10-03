# ADR-004: 완전한 프리셋, 엄격한 스키마, 명세 밖 추가 키

- 상태: ACCEPTED
- 날짜: 2026-10-02
- 결정 주체: 에이전트(위임)

## 배경

명세는 프리셋 YAML을 사용자가 고칠 수 있어야 하고 `--set`으로 값을 덮어쓸 수 있어야
한다고 한다. 기본값이 코드와 YAML 양쪽에 있으면 실제로 적용된 값을 알기 어렵다.

## 결정

- 설정 스키마는 `src/scan_sim/config.py`의 Pydantic 모델이다. 알 수 없는 키, 빠진 키,
  `min > max` 범위는 모두 오류다. 물리 파라미터에는 코드 기본값이 없다.
- 프리셋 5개는 각각 모든 키를 담은 완전한 파일이며 `src/scan_sim/configs/`에 있다.
  패키지에 함께 들어가므로 설치 후에도 찾을 수 있다.
- 사용자 YAML은 `extends: <프리셋 이름>`으로 프리셋을 상속하고 바꿀 키만 쓸 수 있다.
- `--set a.b=x,y`는 두 값짜리 범위로, `--set a.b=x`는 고정값으로 읽는다. 존재하지 않는
  키는 오류다.
- 현실성과 안전을 위해 명세에 없는 키를 추가했다.
  - `input.dpi_from_metadata`, `input.max_page_mm`: 72/96 dpi로 잘못 기록된 파일이
    포스터 크기 페이지와 수 GB 작업 이미지가 되는 것을 막는다. 상한을 넘으면 해결
    방법을 담은 오류를 낸다.
  - `paper.fiber.elongation`: 종이 섬유가 제조 방향으로 길게 늘어선 질감.
  - `scanner.resample`: 명세 §14의 보간 방식 선택.
  - `scanner.tone`(gamma, black_level, white_level): `office-aged`와 `ocr-stress`에
    필요한 대비 감소를 표현한다.
  - `artifacts.horizontal_banding.scale_px`: 띠 간격.

## 이유·trade-off

프리셋 파일 하나만 보면 그 프리셋이 하는 일을 모두 알 수 있다. 대신 프리셋 사이에
같은 값이 반복되고, 키를 추가하면 다섯 파일을 모두 고쳐야 한다. 테스트가 다섯 프리셋의
검증을 확인한다.

## 후속

키가 많아져 중복 관리가 부담되면 프리셋 간 `extends`로 바꾸는 것을 검토한다.
