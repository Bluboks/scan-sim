# ADR-003: seed 파생과 단계별 난수 스트림

- 상태: ACCEPTED
- 날짜: 2026-10-02
- 결정 주체: 에이전트(위임)

## 배경

명세는 seed를 고정하면 결과가 같아야 하고, variant seed를 `hash(file_path, base_seed,
variant_index)`처럼 만들 수 있다고 한다. Python 내장 `hash()`는 프로세스마다 값이
달라지므로 그대로 쓰면 재현이 깨진다.

## 결정

- variant seed = SHA-256(`상대 경로` NUL `base seed` NUL `variant 번호`)의 앞 8바이트를
  63비트로 줄인 값이다. 상대 경로는 입력 폴더 기준이며 `/`로 정규화한다. 파일 하나를
  입력할 때는 파일 이름을 쓴다.
- 단계마다 `numpy.random.default_rng([seed, 단계 ID])`로 따로 스트림을 만든다. 단계
  ID는 printer=1, paper=2, geometry=3, scanner=4, artifacts=5, encoding=6으로 고정한다.
- 잡티처럼 조건부로 일어나는 효과도 난수는 항상 같은 순서로 미리 뽑는다.
- 메타데이터에는 base seed와 variant seed를 모두 기록한다. `simulate_scan(image, config,
  variant_seed)`를 호출하면 같은 결과가 다시 나온다.

## 이유·trade-off

입력 폴더 위치나 처리 순서, 프로세스 수와 무관하게 같은 파일이 나온다(테스트로 확인).
단계별 스트림 덕분에 한 단계의 설정을 바꿔도 다른 단계의 난수는 그대로라서, 파라미터
하나만 바꾼 비교 실험이 가능하다. 대신 상대 경로가 seed에 들어가므로 파일 이름이나
폴더 구조를 바꾸면 결과도 바뀐다. 결과는 같은 플랫폼과 같은 라이브러리 버전에서만
바이트 단위로 같다. 버전은 메타데이터에 기록한다.

## 보완 (2026-10-03)

PDF 페이지는 상대 경로 대신 `<상대 경로>#p<쪽>`을 해시한다([ADR-005](ADR-005-pdf-input.md)).
이미지 입력의 seed는 바뀌지 않았다.

## 후속

단계 ID, 파생 방식, 난수를 뽑는 순서를 바꾸면 "재현성 변경"으로 CHANGELOG에 기록한다.
