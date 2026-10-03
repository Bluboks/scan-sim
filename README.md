# scan-sim

`scan-sim`은 디지털 문서 이미지를 사무용 레이저 프린터로 출력한 뒤 복합기로 다시
스캔한 것처럼 바꾸는 로컬 일괄 변환 도구다. OCR 자동화 소프트웨어의 테스트 데이터를
만드는 것이 목적이다. 원본 픽셀은 그대로 두고 `print → paper → scan → JPEG` 과정의
물리적·광학적 열화만 고정된 16단계 순서로 합성한다. 생성형 모델은 쓰지 않는다.

## 현재 범위 (v0.1)

- 입력: PNG, JPG, TIFF, BMP, PDF(페이지마다 600 dpi로 렌더링). 출력: JPG, PNG.
  PDF 출력은 아직 없다.
- 프린터 색·톤, 프린터 PSF(점 확산 함수, 즉 흐림 정도), 토너 dot gain(획이 미세하게
  두꺼워지는 현상)과 가장자리 거칠기, 3층 종이 질감, 반사율 합성, 배치 오차,
  스캐너 재샘플링·PSF·조명 불균일·센서 노이즈·색 보정·톤·배경 날리기·샤프닝,
  희귀한 세로줄/가로 띠, 마지막 1회 JPEG 압축.
- 프리셋 5개: `office-clean`, `office-medium`(기본), `office-adf`, `office-aged`,
  `ocr-stress`.
- seed 재현성, 원본당 N개 변형, 디렉터리 일괄 처리, 다중 프로세스, JSON 메타데이터.
- 실물 프린터·스캐너로 보정한 값은 아직 없다. 현재 값은 일반적인 사무용 복합기
  특성에 맞춘 추정치다. 근거와 한계는 [VALIDATION](docs/ops/VALIDATION.md)에 있다.

## 설치

Python 3.11 이상.

```bash
pip install -e .          # 또는: uv sync --extra dev
```

## 사용

```bash
# 파일 하나
scan-sim ./sample.png ./out.jpg --preset office-medium --seed 1234

# 폴더 전체, 원본당 10개 변형, 8개 프로세스
scan-sim ./input ./output --preset office-medium --variants 10 --workers 8 \
  --seed 1000 --save-metadata

# OCR 스트레스 테스트
scan-sim ./input ./ocr_stress --preset ocr-stress --variants 20 --seed 2000

# 설정 일부 바꾸기, 계획만 확인하기
scan-sim ./input ./output --set geometry.rotation_deg=-0.5,0.5 \
  --set encoding.jpeg_quality=82,94 --dry-run
```

출력 이름은 `<원본 이름>_scan_0001.jpg`이고, PDF는 `<이름>_p001_scan_0001.jpg`처럼 쪽 번호가
붙는다. 하위 폴더 구조를 유지한다. 같은 명령을
다시 실행하면 바이트 단위로 같은 파일이 나온다. 옵션, 이름 규칙, 종료 코드는
[CLI reference](docs/reference/CLI.md), 설정 키와 단위는
[CONFIG reference](docs/reference/CONFIG.md)에 있다.

Python에서 사용:

```python
from scan_sim import load_config, simulate_scan

config, _ = load_config("office-medium")
scanned, params = simulate_scan(image_uint8_rgb, config, seed=123)
```

## 웹 화면

브라우저에서 프리셋을 바꿔 가며 원본과 스캔을 겹쳐 비교할 수 있다.

```bash
uv sync --extra web && uv run scan-sim-web    # http://127.0.0.1:8789
```

Tailscale tailnet 안에서만 여는 상시 실행 방법과 API는 [WEB](docs/ops/WEB.md)에 있다.

## 샘플

`samples/input/`은 `scripts/make_samples.py`로 만든 A4 300 dpi 합성 문서 5종이다
(거래명세서, 계약서, 엑셀 표, 신청서, 업무 연락)와 2쪽짜리 PDF 1개다. 8~13 pt 한글, 작은 숫자, 1 px
표 선, 회색 음영, 붉은 도장, 바코드·QR 모양 패턴이 들어 있다. `samples/output/`에는
`office-medium` 결과 5장과 거래명세서의 프리셋별 결과가 메타데이터와 함께 있다.

## 검증

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
uv run pytest -q
```

## 라이선스

[MIT](LICENSE). 샘플 문서의 회사명, 사람 이름, 번호, 주소는 모두 지어낸 것이다.

## 문서

처음에는 [docs/README.md](docs/README.md)를 읽는다. 처리 단계별 물리 모델은
[PIPELINE](docs/architecture/PIPELINE.md), 설계 결정은 [DECISIONS](docs/DECISIONS.md),
변경 이력은 [CHANGELOG](CHANGELOG.md)에 있다. 최초 개발 명세 원문은
[archive](docs/archive/2026-10-02-initial-brief.md)에 보관했다.
