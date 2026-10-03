# 설정 레퍼런스

설정 값의 SoT는 `src/scan_sim/configs/<preset>.yaml`이고 스키마는
`src/scan_sim/config.py`다. 모든 키가 필수이며, 모르는 키는 오류다(ADR-004).

## 값 형식

- 숫자 하나: 고정값.
- `[min, max]`: variant마다 균등 분포로 뽑는다. 정수 키(`jpeg_quality`, `width_px`)는
  양 끝을 포함한다.
- `--set a.b=0.1,0.3`은 범위, `--set a.b=0.2`는 고정값이다.
- 사용자 파일은 `extends: office-medium`처럼 프리셋을 상속하고 바꿀 키만 쓸 수 있다.

단위: **W px**는 working 해상도 픽셀(기본 600 dpi에서 1 px = 42 µm), **S px**는 스캐너
해상도 픽셀(300 dpi에서 1 px = 85 µm)이다. 반사율과 세기는 0~1이다.

## 키

| 키 | 단위 | 의미 |
| --- | --- | --- |
| `input.assumed_dpi` | dpi | DPI 정보가 없거나 무시할 때 쓰는 입력 해상도. PDF에는 쓰지 않는다(페이지 크기가 정해져 있음) |
| `input.dpi_from_metadata` | bool | 파일의 DPI 정보를 믿을지 여부 |
| `input.max_page_mm` | mm | 입력 DPI로 계산한 페이지 긴 변의 상한. 넘으면 해결 방법을 담은 오류 |
| `working.dpi` | dpi | 내부 시뮬레이션 해상도. PDF 페이지는 이 해상도로 렌더링한다 |
| `printer.color_matrix` | 3×3 | 디지털 RGB 반사율에 곱하는 프린터 색 변환 |
| `printer.gamma` | 지수 | 반사율^gamma. 1보다 크면 중간톤이 어두워진다 |
| `printer.black_density` | 0~1 | 단색 검정 토너가 흡수하는 빛의 비율(최대 흡수율) |
| `printer.psf.sigma_x/y` | W px | 토너 번짐 가우시안 시그마 |
| `printer.dot_gain.radius_px` | W px | 토너 가장자리가 바깥으로 밀리는 거리. 음수면 얇아진다 |
| `printer.dot_gain.strength` | 0~1 | 중간 농도 영역이 진해지는 정도. 단색 검정과 흰 종이는 그대로다 |
| `printer.edge_roughness_px` | W px | 가장자리 위치 흔들림의 표준편차 |
| `printer.toner_density_noise.strength/scale_px` | 비율 / W px | 토너 농도 얼룩의 세기와 크기. 흰 종이에는 영향이 없다 |
| `paper.base_rgb` | 반사율 | 종이 기본 반사율(linear) |
| `paper.low_frequency.strength/scale_px` | 비율 / W px | 넓은 밝기 얼룩 |
| `paper.fiber.strength/scale_px` | 비율 / W px | 섬유 질감. scale은 짧은 축 기준 |
| `paper.fiber.elongation` | 배 | 섬유 질감이 한 축으로 늘어난 비율. 축(x/y)은 variant마다 무작위 |
| `paper.fine_grain.strength` | 비율 | 화소 크기의 미세 입자 |
| `geometry.rotation_deg` | 도 | 페이지 회전 |
| `geometry.scale_x/y` | 배 | 축별 배율(용지 이송 속도 오차 포함) |
| `geometry.translation_px.x/y` | S px | 페이지 이동 |
| `geometry.perspective.enabled/max_corner_shift_ratio` | bool / 비율 | 네 모서리를 페이지 크기 대비 이 비율 안에서 무작위로 민다 |
| `scanner.dpi` | dpi | 출력 해상도 |
| `scanner.resample` | `area`/`lanczos`/`cubic` | working → 스캐너 해상도 보간 방식 |
| `scanner.psf.sigma_x/y` | S px | 광학 흐림. y는 용지 진행 방향 |
| `scanner.illumination.strength` | 비율 | 조명 기울기·곡률과 저주파 얼룩의 크기 |
| `scanner.illumination.edge_falloff` | 비율 | 좌우 끝에서 어두워지는 정도(센서 램프 끝단) |
| `scanner.noise.gaussian_sigma` | linear 세기 | 읽기 노이즈 표준편차 |
| `scanner.noise.shot_strength` | linear 세기 | 밝기의 제곱근에 비례하는 노이즈 계수 |
| `scanner.noise.row_sigma` | 비율 | 스캔 줄마다 다른 이득 오차(램프 깜빡임, 색별) |
| `scanner.noise.column_sigma` | 비율 | 센서 소자마다 고정된 이득 오차(세 색 공통) |
| `scanner.color_matrix` | 3×3 | 스캐너 색 변환 |
| `scanner.white_balance` | 배 ×3 | R, G, B 채널 이득. 각 항목이 고정값 또는 범위 |
| `scanner.tone.gamma` | 지수 | sRGB 값^gamma. 1보다 크면 글자가 진해진다 |
| `scanner.tone.black_level/white_level` | 0~1 | 출력 검정·흰색 수준. 대비 감소 표현 |
| `scanner.background_suppression.threshold/strength` | sRGB 0~1 / 비율 | threshold 근처부터 부드럽게 시작해 흰색까지 남은 차이의 strength만큼 줄인다 |
| `scanner.sharpening.sigma/amount` | S px / 배 | 언샤프 마스크 |
| `artifacts.vertical_streak.probability/strength/width_px` | 확률 / 비율 / S px | 유리 먼지로 생기는 세로줄 |
| `artifacts.horizontal_banding.probability/strength/scale_px` | 확률 / 비율 / S px | 이송 속도 흔들림으로 생기는 가로 띠 |
| `encoding.format` | `jpg`/`png` | 디렉터리 출력 형식. 파일 출력은 확장자를 따른다 |
| `encoding.jpeg_quality` | 1~100 | JPEG 품질 |
| `encoding.subsampling` | `auto`/`444`/`422`/`420` | 색 서브샘플링. `auto`는 복합기에서 흔한 4:2:0 |
| `metadata.save` | bool | JSON 사이드카 저장. `--save-metadata`가 있으면 항상 저장 |

`scanner.*`의 S px 단위 파라미터는 `scanner.dpi`를 바꾸면 물리적 크기도 함께 바뀐다(ADR-002).

## 프리셋 차이 요약

프리셋 YAML이 SoT다. 아래 표는 프리셋을 고칠 때 함께 갱신한다.

| 키 | office-clean | office-medium | office-adf | office-aged | ocr-stress |
| --- | --- | --- | --- | --- | --- |
| `printer.black_density` | 0.982~0.99 | 0.975~0.99 | 0.975~0.99 | 0.95~0.98 | 0.88~0.97 |
| `printer.psf.sigma_x` | 0.25~0.4 | 0.25~0.45 | 0.25~0.45 | 0.5~0.9 | 0.4~1 |
| `printer.edge_roughness_px` | 0~0.08 | 0~0.15 | 0~0.15 | 0.1~0.3 | 0.05~0.3 |
| `paper.base_rgb` | 0.972/0.97/0.962 | 0.968/0.965/0.954 | 0.968/0.965/0.954 | 0.935/0.925/0.895 | 0.95/0.945/0.925 |
| `paper.low_frequency.strength` | 0.001~0.004 | 0.002~0.008 | 0.002~0.008 | 0.008~0.02 | 0.005~0.02 |
| `geometry.rotation_deg` | -0.08~0.08 | -0.15~0.15 | -0.4~0.4 | -0.3~0.3 | -0.8~0.8 |
| `geometry.translation_px.y` | -1~1 | -1.5~1.5 | -6~6 | -3~3 | -8~8 |
| `geometry.perspective.max_corner_shift_ratio` | 0.0001 | 0.0004 | 0.0004 | 0.0008 | 0.0015 |
| `scanner.psf.sigma_y` | 0.3~0.5 | 0.35~0.6 | 0.45~0.8 | 0.5~0.85 | 0.5~1.2 |
| `scanner.illumination.strength` | 0.001~0.005 | 0.002~0.01 | 0.002~0.01 | 0.01~0.025 | 0.01~0.03 |
| `scanner.noise.gaussian_sigma` | 0.0003~0.001 | 0.0005~0.002 | 0.0005~0.002 | 0.002~0.005 | 0.002~0.006 |
| `scanner.noise.row_sigma` | 0~0.0003 | 0~0.0008 | 0.0005~0.002 | 0.0005~0.0015 | 0.0005~0.002 |
| `scanner.tone.black_level` | 0~0.01 | 0~0.02 | 0~0.02 | 0.03~0.07 | 0.05~0.18 |
| `scanner.tone.white_level` | 1 | 1 | 1 | 0.93~0.97 | 0.88~0.98 |
| `scanner.background_suppression.strength` | 0.15~0.35 | 0.05~0.25 | 0.05~0.25 | 0~0.1 | 0~0.45 |
| `artifacts.vertical_streak.probability` | 0 | 0.02 | 0.08 | 0.05 | 0.15 |
| `artifacts.horizontal_banding.probability` | 0 | 0 | 0.05 | 0.1 | 0.3 |
| `encoding.jpeg_quality` | 93~97 | 90~96 | 90~96 | 78~88 | 70~90 |
