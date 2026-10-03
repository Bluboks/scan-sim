# scan-sim 프로젝트 지침

1. 작업 시작 전에 `docs/README.md`와 `docs/GOVERNANCE.md`를 끝까지 읽고 문서 SoT와
   변경 규칙을 따른다. 최초 명세 `docs/archive/2026-10-02-initial-brief.md`는 역사
   자료다. 현행 범위와 결정은 `docs/DECISIONS.md`가 우선한다.
2. 원본 문서의 의미 정보(문자, 숫자, 표, 선, 로고, 도장, 바코드)를 바꾸지 않는다.
   생성형 모델, OCR 후 재렌더링, 이미지 재생성은 기본 파이프라인에 넣지 않는다.
3. 16단계 처리 순서([PIPELINE](docs/architecture/PIPELINE.md))를 유지한다. 빛·반사율
   연산은 linear-light에서, 톤 곡선·샤프닝은 sRGB 인코딩 값에서 한다. JPEG 압축은
   마지막에 한 번만 한다.
4. 모든 난수는 variant seed 하나에서 단계별 스트림으로 파생한다(ADR-003). 단계 ID를
   바꾸거나 난수 뽑는 순서를 바꾸면 기존 데이터셋이 재현되지 않으므로 CHANGELOG에
   기록한다.
5. 설정 스키마가 SSOT다. 키를 추가·변경하면 프리셋 5개, `docs/reference/CONFIG.md`,
   CHANGELOG를 함께 갱신한다. 물리 파라미터에 숨은 기본값을 두지 않는다(ADR-004).
6. 오류는 조용히 삼키지 않는다. 예상된 실패는 `ScanSimError` 계열로 원인과 해결
   방법을 담아 던지고, 일괄 처리 실패는 파일별로 보고한 뒤 종료 코드 1을 낸다.
   실패를 그럴듯한 기본값으로 덮지 않는다.
7. Python 픽셀 루프를 쓰지 않는다. OpenCV·numpy 벡터 연산을 쓴다. 이미지 입출력은
   Windows 한글 경로 때문에 Pillow로 한다.
8. 변경 후 `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src tests`,
   `uv run pytest -q`를 실행해 결과를 보고한다. 커밋·push는 사용자의 명시적 승인이
   필요하다.
