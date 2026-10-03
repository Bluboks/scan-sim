# CLI 레퍼런스

```text
scan-sim INPUT OUTPUT [--preset NAME | --config FILE] [--set KEY=VALUE ...]
         [--variants N] [--seed S] [--workers N] [--save-metadata]
         [--overwrite] [--dry-run] [--no-progress] [--version]
```

## 입력과 출력

| INPUT | OUTPUT | 결과 |
| --- | --- | --- |
| 파일 | 확장자가 있는 파일 경로 | 그 경로에 1장. 형식은 확장자(`.jpg`, `.jpeg`, `.png`)를 따른다. `--variants`가 2 이상이면 오류 |
| 파일 | 디렉터리 | `<이름>_scan_0001.jpg`부터 N장 |
| 디렉터리 | 디렉터리 | 하위 폴더를 포함한 모든 입력 이미지를 같은 구조로 출력 |

- 입력 확장자: `.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`, `.bmp`, `.pdf`(대소문자 무시).
- 출력 이름: `<원본 stem>_scan_<variant 4자리>.<jpg|png>`. 형식은 `encoding.format`을
  따른다. JSON 사이드카는 같은 이름에 `.json`이다.
- PDF는 모든 페이지를 각각 처리하고 `<stem>_p<쪽 3자리>_scan_<variant 4자리>`로 쓴다.
  파일 하나로 출력하는 경우는 1쪽짜리 PDF만 허용한다([ADR-005](../decisions/ADR-005-pdf-input.md)).
- 처리 전에 모든 출력 경로를 먼저 정하고, 아래 경우는 아무것도 쓰기 전에 오류로 멈춘다.
  - 출력 파일이 이미 있음. `--overwrite`로 덮어쓴다.
  - `a.png`와 `a.jpg`처럼 확장자만 다른 입력이 같은 출력 이름이 됨.
  - 출력 디렉터리가 입력 디렉터리 안에 있음. 다음 실행 때 출력이 입력으로 잡히기 때문이다.
  - 입력 디렉터리에 이미지가 없음.
  - 열 수 없는 PDF(손상, 암호)가 있음. 페이지 수를 계획 단계에서 세기 때문이다.
- 파일은 임시 이름(`.이름.part`)으로 쓴 뒤 바꾼다. 중간에 멈춰도 반쯤 쓴 결과 파일이
  남지 않는다.

## 옵션

| 옵션 | 기본값 | 설명 |
| --- | --- | --- |
| `--preset` | `office-medium` | 내장 프리셋. `--config`와 함께 쓸 수 없다 |
| `--config` | 없음 | YAML 설정 파일. `extends: <프리셋>` 사용 가능 |
| `--set KEY=VALUE` | 없음 | 설정 값 하나를 덮어쓴다. 여러 번 사용 가능. 키 목록은 [CONFIG](CONFIG.md) |
| `--variants` | 1 | 원본당 생성할 변형 수 |
| `--seed` | 0 | base seed. variant seed는 ADR-003으로 파생한다 |
| `--workers` | 1 | 병렬 프로세스 수. 각 프로세스는 OpenCV 스레드를 1개로 제한한다 |
| `--save-metadata` | 꺼짐 | 설정과 무관하게 JSON 사이드카를 쓴다(프리셋은 이미 켜져 있다) |
| `--overwrite` | 꺼짐 | 기존 출력을 덮어쓴다 |
| `--dry-run` | 꺼짐 | 입력 → 출력, variant, seed 목록만 출력하고 끝낸다 |
| `--no-progress` | 꺼짐 | 진행 막대를 숨긴다 |

## 종료 코드

| 코드 | 의미 |
| --- | --- |
| 0 | 모두 성공 |
| 1 | 일부 또는 전체 파일 실패. 실패한 파일마다 원인을 stderr에 출력한다. 예상 밖 오류는 전체 traceback을 함께 출력한다. 성공한 파일은 그대로 남는다 |
| 2 | 설정·인자·경로 오류. 아무것도 처리하지 않았다 |

## 메타데이터

사이드카 필드: `source`(입력 기준 상대 경로), `page`(PDF 쪽 번호, 이미지는 `null`), `output`, `preset`(프리셋 이름 또는 설정
파일 경로), `base_seed`, `seed`(variant seed), `variant`, `dpi`, `input_dpi`(x, y, 출처
`metadata`/`assumed`/`pdf-render`), `parameters`(이번 variant에서 실제로 뽑힌 모든 값, 발생한 잡티,
JPEG 품질), `versions`(scan_sim, numpy, opencv, pillow).

`simulate_scan(image, config, seed)`에 사이드카의 `seed`와 같은 설정을 넘기면 같은
픽셀이 다시 나온다. 단, 이 함수는 입력을 `input.assumed_dpi` 해상도로 간주한다.
