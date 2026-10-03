# OCR 테스트용 Print–Scan Simulator 개발 명세

## 1. 목적

디지털 원본 이미지/PDF를 실제 사무용 프린터로 출력한 뒤 복합기/스캐너로 다시 스캔한 것처럼 변환하는 **로컬 일괄 변환 프로그램**을 구현한다.

주 목적은 OCR 자동화 소프트웨어의 테스트 데이터 생성이다.

중요 원칙:

- 원본 문서의 **문자 내용, 표 구조, 레이아웃, 로고, 서명 등 의미 정보는 생성형 AI로 다시 그리지 않는다.**
- 원본 픽셀을 기반으로 실제 `print → paper → scan → compression` 과정에서 생기는 물리적/광학적 열화만 합성한다.
- 같은 입력에서도 seed를 바꾸면 서로 다른 스캔본 변형을 생성할 수 있어야 한다.
- seed를 고정하면 동일 결과가 재현되어야 한다.
- 대량 배치 처리를 전제로 한다.
- OCR 성능 평가를 위해 열화 강도를 수치적으로 조절할 수 있어야 한다.

---

# 2. 목표 결과

입력:

- PNG
- JPG/JPEG
- TIFF
- BMP
- 가능하면 PDF

출력:

- PNG
- JPG
- TIFF
- 가능하면 PDF

예:

```text
input/
 ├─ invoice_001.png
 ├─ invoice_002.jpg
 ├─ contract_003.pdf
 └─ table_004.png

output/
 ├─ invoice_001_scan_0001.jpg
 ├─ invoice_001_scan_0002.jpg
 ├─ invoice_002_scan_0001.jpg
 ├─ contract_003_p001_scan_0001.jpg
 └─ table_004_scan_0001.jpg
```

한 원본당 N개의 변형본을 생성할 수 있어야 한다.

예:

```bash
scan-sim ./input ./output --variants 10 --preset office-medium
```

---

# 3. 구현 우선순위

우선 구현할 대상은 아래 환경이다.

```text
A4/A3 문서
↓
사무용 레이저 프린터
↓
일반 백색 복사용지
↓
사무용 평판 또는 ADF 복합기
↓
300 dpi 또는 600 dpi
↓
JPEG/PDF 저장
```

사진 인쇄, 잉크젯 아트프린트 등은 초기 범위에서 제외한다.

---

# 4. 전체 처리 파이프라인

반드시 처리 순서를 유지한다.

```text
Digital Original
    ↓
[1] Input normalization / working DPI
    ↓
[2] Printer color/tone transform
    ↓
[3] Printer PSF / effective print blur
    ↓
[4] Toner / dot gain / edge roughness
    ↓
[5] Paper reflectance + texture
    ↓
[6] Print-paper compositing
    ↓
[7] Geometric placement error
    ↓
[8] Scanner optical resampling
    ↓
[9] Scanner PSF
    ↓
[10] Illumination non-uniformity
    ↓
[11] Sensor / row / column noise
    ↓
[12] Scanner color matrix + white balance
    ↓
[13] Tone curve / background suppression
    ↓
[14] Scanner sharpening
    ↓
[15] Optional scan artifacts
    ↓
[16] JPEG/TIFF/PDF encoding
```

단순히 마지막 이미지에 blur/noise를 한 번 넣는 식으로 구현하지 않는다.

---

# 5. 권장 기술 스택

Python 기준.

필수 후보:

```text
Python 3.11+
numpy
opencv-python
Pillow
scipy
PyYAML
tqdm
```

PDF 지원 시:

```text
PyMuPDF
```

선택:

```text
numba
multiprocessing
concurrent.futures
```

GUI는 1차 버전에서 필수 아님.

CLI가 우선이다.

---

# 6. 내부 이미지 표현

중간 연산에서는 JPEG 재압축을 반복하지 않는다.

권장:

```text
uint8 입력
↓
float32, range 0.0 ~ 1.0
↓
linear-light 또는 명시적 working color space
↓
모든 시뮬레이션
↓
최종 단계에서 uint8 인코딩
```

가능하면 아래를 구분한다.

```python
srgb_to_linear()
linear_to_srgb()
```

빛/반사율 기반 연산은 linear-light에서 수행한다.

---

# 7. 1단계 — 입력 정규화

## 7.1 DPI

입력 이미지에 DPI 정보가 없으면 기본값을 설정한다.

```yaml
input:
  assumed_dpi: 300
```

내부 working DPI 권장:

```text
600 dpi
```

입력이 300 dpi일 경우 600 dpi 작업 공간으로 올린 뒤 마지막에 scanner DPI로 재샘플링한다.

단, 단순 업스케일만으로 디테일을 새로 생성하지 않는다.

## 7.2 alpha

투명 배경은 흰 종이로 합성한다.

---

# 8. 2단계 — 프린터 tone/color transform

실제 프린터 출력은 디지털 RGB와 동일하지 않다.

초기 버전은 CMYK 전체 물리 모델까지 가지 않아도 된다.

대신 아래를 적용한다.

```python
rgb = apply_printer_color_matrix(rgb)
rgb = apply_printer_tone_lut(rgb)
```

권장 기본값은 identity에 가깝게 두고 preset별로 미세 조정한다.

예:

```yaml
printer:
  color_matrix:
    - [0.995, 0.004, 0.001]
    - [0.003, 0.994, 0.003]
    - [0.001, 0.006, 0.993]

  gamma: 1.02
  black_density: 0.985
```

---

# 9. 3단계 — Printer PSF

디지털 경계가 실제 토너 출력처럼 약간 퍼져야 한다.

단순 전체 Gaussian blur 한 번으로 끝내지 말 것.

최소한 anisotropic Gaussian PSF를 지원한다.

```yaml
printer:
  psf:
    sigma_x: [0.25, 0.55]
    sigma_y: [0.25, 0.65]
```

값이 배열이면 seed 기반 uniform random sampling.

구현 예:

```python
sigma_x = rng.uniform(*cfg.printer.psf.sigma_x)
sigma_y = rng.uniform(*cfg.printer.psf.sigma_y)
printed = anisotropic_gaussian_blur(img, sigma_x, sigma_y)
```

---

# 10. 4단계 — Toner / Dot Gain / Edge Roughness

## 10.1 dot gain

검은 획이 종이에 출력될 때 아주 미세하게 두꺼워지는 효과.

형태학적 dilation을 그대로 쓰면 부자연스럽다.

권장:

```text
darkness mask 추출
↓
soft morphology / distance transform
↓
subpixel 수준으로 edge 확장
```

파라미터:

```yaml
printer:
  dot_gain:
    enabled: true
    radius_px: [0.05, 0.35]
    strength: [0.05, 0.20]
```

---

## 10.2 edge roughness

글자 가장자리에 미세한 불규칙성을 준다.

원칙:

- 텍스트 자체 형태를 바꿀 정도로 강하게 넣지 않는다.
- 고주파 noise를 edge mask에만 적용한다.

```text
edge mask
×
band-limited random field
→
local edge displacement
```

권장 amplitude:

```yaml
edge_roughness_px: [0.0, 0.25]
```

---

## 10.3 toner density variation

검정 대면적이나 굵은 글씨가 완전히 균일하지 않은 효과.

```yaml
printer:
  toner_density_noise:
    strength: [0.0, 0.012]
    scale_px: [4, 30]
```

저주파 noise를 사용한다.

white area에는 거의 영향을 주지 않는다.

---

# 11. 5단계 — 종이 모델

`#FFFFFF` 단색 배경 사용 금지.

종이 반사율을 아래 세 층으로 모델링한다.

```text
Paper =
  base white
+ low-frequency shading
+ medium-frequency fiber texture
+ fine grain
```

예:

```yaml
paper:
  base_rgb: [0.965, 0.962, 0.950]

  low_frequency:
    strength: [0.002, 0.012]
    scale_px: [200, 1500]

  fiber:
    strength: [0.001, 0.008]
    scale_px: [8, 60]

  fine_grain:
    strength: [0.0005, 0.004]
```

노이즈는 단순 independent RGB white noise만 쓰지 말 것.

RGB 채널 간 높은 상관을 갖도록 한다.

---

# 12. 6단계 — Print/Paper 합성

alpha blend 방식보다 reflectance 형태로 구현한다.

개념적으로:

```text
R_output = R_paper × R_print
```

예:

```python
paper = generate_paper(...)
ink_absorption = compute_ink_absorption(printed)
out = paper * (1.0 - ink_absorption)
```

최종 수식은 구현자가 조정해도 된다.

중요한 것은 흰 영역에도 paper texture가 남고, 검정 토너 영역은 별도 noise/밀도를 가진다는 점이다.

---

# 13. 7단계 — 기하학적 오차

실제 출력물과 스캐너 좌표계는 정확히 일치하지 않는다.

아래 항목 각각을 지원한다.

```text
rotation
scale_x
scale_y
translation_x
translation_y
subpixel offset
small perspective
```

권장 기본 범위:

```yaml
geometry:
  rotation_deg: [-0.20, 0.20]

  scale_x: [0.9990, 1.0010]
  scale_y: [0.9990, 1.0010]

  translation_px:
    x: [-2.0, 2.0]
    y: [-2.0, 2.0]

  perspective:
    enabled: true
    max_corner_shift_ratio: 0.0008
```

`office-clean` preset에서는 perspective를 매우 작게 한다.

사진 촬영처럼 큰 perspective distortion을 주지 않는다.

---

# 14. 8단계 — Scanner DPI 재샘플링

프린터 픽셀과 scanner sample 위치는 1:1이 아니다.

scanner DPI 설정:

```yaml
scanner:
  dpi: 300
```

600 dpi working image를 300 dpi scanner image로 다운샘플한다.

Interpolation 후보:

```text
INTER_AREA
Lanczos
Bicubic
```

preset별 선택 가능하게 한다.

---

# 15. 9단계 — Scanner optical PSF

프린터 PSF와 별개의 blur다.

권장:

```yaml
scanner:
  psf:
    sigma_x: [0.25, 0.55]
    sigma_y: [0.35, 0.75]
```

ADF의 경우 진행 방향 blur를 조금 더 크게 할 수 있다.

---

# 16. 10단계 — Scanner illumination field

실제 스캔본은 화면 전체 밝기가 완전히 균일하지 않다.

다항식 + 저주파 noise 조합 권장.

예:

```text
L(x,y)
=
1
+ ax*x
+ ay*y
+ axx*x²
+ ayy*y²
+ axy*x*y
+ low_frequency_field
```

파라미터:

```yaml
scanner:
  illumination:
    strength: [0.001, 0.015]
    edge_falloff: [0.0, 0.012]
```

최종:

```python
scan *= illumination_map
```

---

# 17. 11단계 — 센서 노이즈

현대 복합기 수준에서 매우 약하게 적용한다.

지원:

```text
Gaussian read noise
signal-dependent shot-like noise
row noise
column noise
```

예:

```yaml
scanner:
  noise:
    gaussian_sigma: [0.0005, 0.0030]
    shot_strength: [0.0, 0.003]
    row_sigma: [0.0, 0.0015]
    column_sigma: [0.0, 0.0010]
```

노이즈를 과도하게 넣지 않는다.

---

# 18. 12단계 — Scanner RGB matrix / white balance

```python
rgb = M @ rgb
rgb *= white_balance
```

예:

```yaml
scanner:
  white_balance: [1.003, 1.000, 0.994]

  color_matrix:
    - [1.002, -0.001, -0.001]
    - [-0.002, 1.004, -0.002]
    - [-0.001, 0.001, 1.000]
```

preset마다 미세하게 다르게 한다.

---

# 19. 13단계 — Tone curve / Background suppression

실제 복합기는 종이 배경을 어느 정도 흰색으로 밀어내는 경향이 있다.

지원 옵션:

```yaml
scanner:
  background_suppression:
    enabled: true
    threshold: [0.82, 0.94]
    strength: [0.0, 0.45]
```

구현 시 hard threshold를 사용하지 말고 smooth curve를 적용한다.

예:

```text
밝은 영역 → 조금 더 흰색
중간톤 → 거의 유지
어두운 영역 → 토너 밀도 유지
```

---

# 20. 14단계 — Scanner sharpening

Unsharp masking 지원.

```python
blur = gaussian(scan, sigma)
scan = scan + amount * (scan - blur)
```

파라미터:

```yaml
scanner:
  sharpening:
    enabled: true
    sigma: [0.4, 1.0]
    amount: [0.15, 0.60]
```

과도한 halo 금지.

---

# 21. 15단계 — 선택적 Scan Artifact

기본 preset에는 약하게 또는 OFF.

별도 OCR stress-test preset에서 켠다.

지원 후보:

## ADF skew

```yaml
adf_skew_deg: [-0.4, 0.4]
```

## faint vertical line

스캐너 유리 먼지/ADF 오염으로 발생하는 아주 얇은 세로줄.

```yaml
vertical_streak:
  probability: 0.05
  strength: [0.005, 0.03]
  width_px: [1, 3]
```

## faint horizontal banding

```yaml
horizontal_banding:
  probability: 0.10
  strength: [0.002, 0.01]
```

## dust / speck

OCR 학습용일 때만 약하게.

문서 위에 검은 점을 수백 개 랜덤으로 뿌리는 식으로 구현하지 않는다.

확률적으로 드물게 생성한다.

---

# 22. 16단계 — 최종 압축

JPEG 출력 시 마지막 단계에서 1회만 압축한다.

```yaml
encoding:
  format: jpg
  jpeg_quality: [88, 97]
  subsampling: auto
```

OCR stress test preset:

```yaml
jpeg_quality: [70, 90]
```

PNG는 무손실 reference 출력용으로 지원한다.

---

# 23. 필수 Preset

최소 아래 5개를 구현한다.

## `office-clean`

최신 복합기로 깨끗하게 스캔한 문서.

```text
noise 매우 낮음
skew 매우 낮음
paper texture 약함
300 dpi
sharpening 보통
JPEG quality 높음
```

## `office-medium`

일반 사무실 스캔본.

기본 preset.

```text
약한 paper texture
약한 illumination variation
미세 skew
일반 sharpening
JPEG 90 전후
```

## `office-adf`

ADF 통과 문서.

```text
rotation 범위 증가
y-direction PSF 약간 증가
row/column variation 약간 증가
vertical streak 낮은 확률
```

## `office-aged`

여러 번 복사/스캔된 문서 느낌.

단, 누렇게 만드는 필터 수준으로 끝내지 않는다.

```text
contrast 감소
background 약간 어두움
noise 증가
edge quality 감소
JPEG quality 감소
```

## `ocr-stress`

OCR robustness 시험용.

```text
skew
blur
low contrast
JPEG artifact
banding
paper variation
small geometric distortion
```

각 효과는 독립 설정 가능해야 한다.

---

# 24. 랜덤성 및 재현성

모든 랜덤 요소는 하나의 RNG에서 파생한다.

```python
rng = np.random.default_rng(seed)
```

CLI:

```bash
--seed 12345
```

variant 생성 시:

```text
base seed + variant index
```

또는 deterministic hash 사용.

예:

```text
seed = hash(file_path, base_seed, variant_index)
```

동일 조건에서 항상 동일 결과가 나와야 한다.

---

# 25. CLI 요구사항

예:

```bash
scan-sim input.png output.jpg
```

디렉터리:

```bash
scan-sim ./input ./output
```

preset:

```bash
scan-sim ./input ./output --preset office-medium
```

여러 변형:

```bash
scan-sim ./input ./output --variants 20
```

seed:

```bash
scan-sim ./input ./output --seed 1234
```

설정 override:

```bash
scan-sim ./input ./output \
  --preset office-medium \
  --set geometry.rotation_deg=-0.5,0.5 \
  --set encoding.jpeg_quality=82,94
```

config 직접 지정:

```bash
scan-sim ./input ./output --config ./configs/custom.yaml
```

CPU 병렬 처리:

```bash
scan-sim ./input ./output --workers 8
```

dry run:

```bash
scan-sim ./input ./output --dry-run
```

---

# 26. 출력 Metadata

각 생성 파일 옆에 JSON sidecar 저장 옵션을 제공한다.

예:

```text
invoice_scan_001.jpg
invoice_scan_001.json
```

내용:

```json
{
  "source": "invoice.png",
  "preset": "office-medium",
  "seed": 13849221,
  "variant": 1,
  "dpi": 300,
  "parameters": {
    "printer_psf_sigma_x": 0.39,
    "printer_psf_sigma_y": 0.48,
    "rotation_deg": 0.072,
    "scanner_psf_sigma_x": 0.31,
    "scanner_psf_sigma_y": 0.56,
    "jpeg_quality": 92
  }
}
```

OCR benchmark 결과와 열화 파라미터를 나중에 연계 분석할 수 있어야 한다.

CLI:

```bash
--save-metadata
```

---

# 27. PDF 처리

PDF는 페이지별로 rasterize한 뒤 처리한다.

권장:

```text
PDF
↓
600 dpi rasterization
↓
print-scan simulation
↓
개별 이미지 또는 PDF 재조립
```

옵션:

```bash
--pdf-output images
```

또는:

```bash
--pdf-output pdf
```

OCR 테스트가 목적이므로 원본 PDF의 text layer를 유지하면 안 된다.

출력 PDF는 **raster-only PDF**여야 한다.

---

# 28. OCR 데이터셋용 모드

입력 1개에서 여러 강도의 sample 생성 가능하게 한다.

예:

```bash
scan-sim dataset/input dataset/output \
  --variants 20 \
  --preset-family office
```

예상 결과:

```text
doc001_clean_01.jpg
doc001_medium_02.jpg
doc001_adf_03.jpg
doc001_stress_04.jpg
...
```

가능하면 parameter sweep도 지원한다.

예:

```yaml
dataset:
  sweep:
    rotation_deg:
      - [-0.05, 0.05]
      - [-0.20, 0.20]
      - [-0.70, 0.70]

    scanner_blur:
      - [0.2, 0.4]
      - [0.4, 0.8]
      - [0.8, 1.4]
```

---

# 29. 폴더 구조 권장

```text
print_scan_simulator/
├─ pyproject.toml
├─ README.md
├─ configs/
│  ├─ office-clean.yaml
│  ├─ office-medium.yaml
│  ├─ office-adf.yaml
│  ├─ office-aged.yaml
│  └─ ocr-stress.yaml
├─ src/
│  └─ scan_sim/
│     ├─ __init__.py
│     ├─ cli.py
│     ├─ config.py
│     ├─ pipeline.py
│     ├─ rng.py
│     ├─ io.py
│     ├─ pdf.py
│     ├─ printer.py
│     ├─ paper.py
│     ├─ geometry.py
│     ├─ scanner.py
│     ├─ artifacts.py
│     ├─ encoding.py
│     └─ metadata.py
├─ tests/
│  ├─ test_determinism.py
│  ├─ test_dimensions.py
│  ├─ test_pdf.py
│  ├─ test_presets.py
│  └─ test_pipeline.py
└─ samples/
```

한 파일에 모든 함수를 몰아넣지 않는다.

---

# 30. 핵심 API

최소 아래 API를 내부에 제공한다.

```python
def simulate_scan(
    image: np.ndarray,
    config: SimulationConfig,
    seed: int,
) -> tuple[np.ndarray, dict]:
    ...
```

파일 API:

```python
def process_file(
    input_path: Path,
    output_path: Path,
    config: SimulationConfig,
    seed: int,
) -> dict:
    ...
```

batch:

```python
def process_directory(
    input_dir: Path,
    output_dir: Path,
    config: SimulationConfig,
    variants: int,
    seed: int,
    workers: int,
) -> None:
    ...
```

---

# 31. Configuration schema

dataclass 또는 Pydantic를 써도 된다.

예:

```python
@dataclass
class Range:
    min: float
    max: float
```

모든 range parameter는 helper로 sampling한다.

```python
def sample_value(value, rng):
    if isinstance(value, (int, float)):
        return value

    if len(value) == 2:
        return rng.uniform(value[0], value[1])
```

---

# 32. 처리 속도

목표:

```text
A4 300 dpi 출력 기준
CPU 1개 문서 수초 이내
```

600 dpi 내부 처리 때문에 메모리가 커질 수 있다.

A4 600 dpi:

```text
약 4960 × 7016 px
```

float32 RGB는 상당한 메모리를 사용한다.

필요하면 일부 단계에서:

```text
float32 grayscale / luminance mask
uint8 intermediate
tiling
```

등을 고려한다.

단, 경계 artifact가 생기는 타일 처리는 피한다.

---

# 33. 성능 최적화 우선순위

1. OpenCV vector operation
2. numpy vectorization
3. multiprocessing
4. 필요 시 numba

Python pixel loop 금지.

---

# 34. 품질 검증

## 34.1 원문 보존

시뮬레이터가 문서 내용을 임의 변경하면 실패다.

아래는 그대로 유지되어야 한다.

```text
문자
숫자
표 셀
행/열 구조
바코드/QR 구조
로고
도장
선
```

단, 실제 스캔 열화 때문에 일부 픽셀 경계가 흐려지는 것은 허용한다.

---

## 34.2 deterministic test

```python
a = simulate_scan(img, cfg, seed=123)
b = simulate_scan(img, cfg, seed=123)

assert np.array_equal(a, b)
```

---

## 34.3 seed variation

```python
a = simulate_scan(img, cfg, seed=123)
b = simulate_scan(img, cfg, seed=124)

assert not np.array_equal(a, b)
```

---

## 34.4 geometry sanity

office preset에서 문서가 눈에 띄게 기울거나 찌그러지면 실패.

```text
office-clean:
rotation <= 약 0.1°
```

---

## 34.5 OCR 활용성

OCR stress mode를 제외하면 사람이 읽을 수 있어야 한다.

특히:

```text
8~12 pt 한글
작은 숫자
엑셀 표
얇은 표 테두리
```

가 실제 사무용 복합기 스캔 정도로 남아야 한다.

---

# 35. 실물 캘리브레이션 기능

초기 구현 완료 후 반드시 추가할 것을 권장한다.

목적:

실제 복합기 1대의 특성을 측정해 preset으로 저장한다.

테스트 패턴:

```text
0~255 grayscale patches
RGB patches
1 px ~ 10 px lines
다양한 font size
checkerboard
gradient
solid black
solid gray
```

절차:

```text
원본 test chart
↓
실제 프린터 출력
↓
실제 scanner 스캔
↓
원본과 정렬
↓
PSF / tone LUT / color / noise 추정
↓
device preset 생성
```

예:

```text
configs/devices/canon_xxx_300dpi.yaml
configs/devices/hp_xxx_adf_300dpi.yaml
```

---

# 36. 캘리브레이션 시 추정 대상

가능하면 아래를 자동 추정한다.

## tone curve

grayscale patch의 원본 값과 scanner 결과를 대응시켜 LUT 생성.

## color matrix

color patch로 least-squares 3×3 matrix 추정.

## PSF

고대비 edge 또는 line spread function으로 추정.

```text
edge spread function
↓ derivative
line spread function
↓
PSF approximation
```

## noise

uniform patch residual에서 noise 분산 측정.

## illumination

흰 종이 scan에서 저주파 field 추정.

---

# 37. 생성형 AI 사용 금지 영역

이 프로젝트의 기본 pipeline에서는 아래를 사용하지 않는다.

```text
Stable Diffusion
image-to-image generative reconstruction
LLM vision based repainting
OCR 후 텍스트 재렌더링
```

이유:

OCR 테스트 데이터의 ground truth와 픽셀 문서 내용이 달라질 위험이 있다.

필요하면 향후 **residual-only model**을 선택적으로 연구할 수 있다.

구조:

```text
physical simulator output
↓
small residual CNN
↓
tiny residual correction only
```

CNN이 전체 문서를 재생성해서는 안 된다.

---

# 38. 추천 초기 구현 범위

v0.1에서 아래만 확실하게 구현한다.

```text
PNG/JPG 입력
PNG/JPG 출력
printer PSF
dot gain
paper texture
geometry
scanner resampling
scanner PSF
illumination
noise
tone curve
sharpening
JPEG compression
5 presets
seed
batch
variants
JSON metadata
```

v0.2:

```text
PDF input/output
ADF artifacts
parameter sweep
device calibration
```

---

# 39. 기본 preset 예시

`configs/office-medium.yaml`

```yaml
input:
  assumed_dpi: 300

working:
  dpi: 600

printer:
  gamma: 1.02
  black_density: 0.985

  psf:
    sigma_x: [0.25, 0.45]
    sigma_y: [0.30, 0.55]

  dot_gain:
    enabled: true
    radius_px: [0.05, 0.25]
    strength: [0.05, 0.15]

  edge_roughness_px: [0.0, 0.15]

  toner_density_noise:
    strength: [0.001, 0.008]
    scale_px: [6, 25]

paper:
  base_rgb: [0.968, 0.965, 0.954]

  low_frequency:
    strength: [0.002, 0.008]
    scale_px: [250, 1000]

  fiber:
    strength: [0.001, 0.004]
    scale_px: [10, 40]

  fine_grain:
    strength: [0.0005, 0.002]

geometry:
  rotation_deg: [-0.15, 0.15]

  scale_x: [0.9994, 1.0006]
  scale_y: [0.9994, 1.0006]

  translation_px:
    x: [-1.5, 1.5]
    y: [-1.5, 1.5]

  perspective:
    enabled: true
    max_corner_shift_ratio: 0.0004

scanner:
  dpi: 300

  psf:
    sigma_x: [0.25, 0.45]
    sigma_y: [0.35, 0.60]

  illumination:
    strength: [0.002, 0.010]
    edge_falloff: [0.001, 0.008]

  noise:
    gaussian_sigma: [0.0005, 0.0020]
    shot_strength: [0.0, 0.0015]
    row_sigma: [0.0, 0.0008]
    column_sigma: [0.0, 0.0005]

  white_balance:
    - [0.998, 1.004]
    - [0.998, 1.003]
    - [0.992, 1.000]

  background_suppression:
    enabled: true
    threshold: [0.86, 0.92]
    strength: [0.05, 0.25]

  sharpening:
    enabled: true
    sigma: [0.45, 0.85]
    amount: [0.20, 0.45]

artifacts:
  vertical_streak:
    probability: 0.02
    strength: [0.004, 0.012]
    width_px: [1, 2]

encoding:
  format: jpg
  jpeg_quality: [90, 96]

metadata:
  save: true
```

---

# 40. README에 넣을 최소 사용 예

```bash
pip install -e .
```

단일 파일:

```bash
scan-sim ./sample.png ./out.jpg \
  --preset office-medium \
  --seed 1234
```

폴더 전체:

```bash
scan-sim ./input ./output \
  --preset office-medium \
  --variants 10 \
  --workers 8 \
  --seed 1000 \
  --save-metadata
```

OCR 스트레스 테스트:

```bash
scan-sim ./input ./ocr_stress \
  --preset ocr-stress \
  --variants 20 \
  --seed 2000
```

---

# 41. 완료 조건

아래 조건을 모두 만족하면 1차 완료로 본다.

- CLI에서 파일/디렉터리 입력 가능
- PNG/JPG batch 변환 가능
- 한 원본당 N개 variant 생성 가능
- seed 재현 가능
- 5 preset 제공
- preset YAML 수정 가능
- print와 scan blur가 별도 단계
- paper texture가 흰 배경 전체에 물리적으로 합성됨
- geometry/resampling 구현
- illumination/noise/sharpening 구현
- JPEG compression이 마지막에 수행됨
- metadata JSON 저장 가능
- pytest 기본 테스트 통과
- Windows에서 정상 실행 가능
- README에 설치/사용법 기재

---

# 42. 구현 시 피해야 할 것

아래 방식으로 대충 구현하지 않는다.

```text
GaussianBlur
+ random noise
+ yellow tint
+ JPEG
```

또는:

```text
paper texture overlay
+ rotate
```

만으로 끝내지 않는다.

이 프로그램의 목적은 필터 효과가 아니라 **실제 사무용 print/scan chain의 근사 시뮬레이션**이다.

또한 테스트 문서의 의미 정보를 생성형 모델로 수정하거나 재구성하지 않는다.

---

# 43. 개발자에게 요청하는 최종 산출물

다음을 모두 제공한다.

```text
1. 동작 가능한 Python 프로젝트
2. CLI
3. 5개 preset YAML
4. README
5. requirements 또는 pyproject
6. pytest
7. sample input/output
8. parameter metadata 저장 기능
9. PDF 확장 가능한 구조
```

최초 구현 후 sample 문서 5~10개를 대상으로 결과 이미지를 확인하여 파라미터를 조정한다.

가장 먼저 **office-medium preset이 실제 일반 사무용 복합기 300 dpi 컬러 스캔본과 육안상 가까워지는 것**을 목표로 한다.
