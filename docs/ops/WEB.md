# 웹 화면 (scan-sim-web)

브라우저에서 문서를 올리거나 샘플을 고르고, 프리셋·seed·변형 수·`--set` 값을 바꿔
원본과 스캔 결과를 겹쳐 비교하는 도구다. 시험용이며 일괄 처리는 CLI를 쓴다.

## 실행

```bash
uv sync --extra web
uv run scan-sim-web --port 8789            # http://127.0.0.1:8789
```

| 옵션 | 기본값 | 설명 |
| --- | --- | --- |
| `--host` | `127.0.0.1` | 바인드 주소. 외부 공개는 아래 tailnet 방식을 쓴다 |
| `--port` | `8789` | 포트 |
| `--data-dir` | `./.web-data` | 작업 결과 저장 위치. 최근 40개 작업만 남긴다 |
| `--samples-dir` | 저장소 `samples/input` | 샘플 목록. 없으면 업로드만 가능하다 |

## 상시 실행과 tailnet 공개 (예시)

systemd 사용자 서비스로 띄우고 `tailscale serve`로 tailnet 안에만 공개하는 예시다.
경로와 포트는 환경에 맞게 바꾼다.

```ini
# ~/.config/systemd/user/scan-sim-web.service
[Unit]
Description=scan-sim browser UI

[Service]
WorkingDirectory=/path/to/scan-sim
ExecStart=/path/to/scan-sim/.venv/bin/scan-sim-web --host 127.0.0.1 --port 8789 --data-dir /path/to/scan-sim/.web-data
Restart=on-failure
MemoryMax=8G

[Install]
WantedBy=default.target
```

```bash
systemctl --user enable --now scan-sim-web
loginctl enable-linger "$USER"                       # 로그아웃 후에도 유지
tailscale serve --bg --https=8445 http://127.0.0.1:8789
# → https://<host>.<tailnet>.ts.net:8445 (tailnet 전용, Funnel 아님)
systemctl --user restart scan-sim-web                # 코드를 바꾼 뒤
journalctl --user -u scan-sim-web -f                 # 로그
tailscale serve --https=8445 off                     # 공개 중지
```

인증 기능은 없으므로 tailnet 접근 권한이 곧 사용 권한이다. 인터넷에 직접 열지 않는다.
서비스는 작업 트리의 코드를 그대로 실행한다. Python 코드를 고치면 재시작해야 하고,
`static/index.html`은 요청마다 다시 읽는다.

## 동작

- 작업은 한 번에 하나씩 처리한다(A4 한 장에 약 2.4 GB 필요). 동시에 누르면 앞 작업이
  끝날 때까지 기다린다.
- 업로드 상한 50 MB, 변형 수 1~6.
- PDF는 "PDF 페이지" 칸에서 고른 한 쪽만 변환한다. 범위를 벗어나면 전체 쪽 수를 담은
  오류가 나온다. 결과 파일 이름은 CLI와 같은 `<stem>_p00N_scan_0001.jpg`다.
- 클립보드 이미지는 페이지 어디서나 Ctrl+V로, 또는 "클립보드에서 붙여넣기" 버튼으로
  넣는다. 버튼은 브라우저의 클립보드 읽기 권한이 필요하고, 거부되면 그 이유를 보여 준다.
  붙여넣은 이미지는 `clipboard-YYYYMMDD-HHMMSS.<확장자>` 이름을 받는다. 이 이름이
  variant seed에 들어간다. 서버가 읽지 못하는 형식(WebP, GIF 등)은 브라우저에서 PNG로
  바꿔 올린다. 클립보드 이미지에는 DPI 정보가 없으므로 `input.assumed_dpi`(300)로 본다.
  텍스트만 붙여넣을 때는 가로채지 않는다.
- variant seed는 CLI의 `scan-sim <파일> <폴더> --seed S --variants N`과 같다(ADR-003).
  화면에 같은 결과를 내는 CLI 명령을 함께 보여 준다. 63비트 seed는 JavaScript 정수
  범위를 넘으므로 API는 seed를 문자열로 보낸다.
- 보기 조작은 마우스와 터치가 같은 규칙을 따른다. 한 손가락(또는 마우스)으로 끌면 이동,
  두 손가락 핀치(트랙패드 핀치, Ctrl+휠)는 그 지점을 중심으로 확대, 두 번 탭(더블클릭)은
  맞춤 → 100% → 200% → 400% 순서로 확대한다. 비교 모드에서 터치로 한 번 탭하면 그 위치로
  경계선이 옮겨진다. 휴대폰처럼 화면이 좁거나 터치 기기면 아래에 경계 위치 슬라이더가
  나타난다. 보기 영역은 브라우저 기본 확대·스크롤을 막고(`touch-action: none`) 직접 처리한다.
- 비교 화면의 원본은 스캔 결과와 같은 픽셀 크기로 맞춘 미리보기다. 배치 오차(회전·이동)는
  보정하지 않으므로 그대로 보인다.
- 오류는 서버가 보낸 메시지를 그대로 보여 준다. 예상 밖 오류는 traceback을 펼쳐 볼 수
  있고 서버 로그에도 남는다.

## API

| 메서드 | 경로 | 설명 |
| --- | --- | --- |
| GET | `/api/options` | 프리셋(요약 포함), 샘플, 한도 |
| POST | `/api/jobs` | multipart: `file` 또는 `sample`, `preset`, `seed`, `variants`, `overrides`(줄마다 `--set` 값), `page`(PDF 쪽, 기본 1) |
| GET | `/files/{job}/{name}` | `original.png`, `scan_0001.jpg`, `scan_0001.json` 등 |
| GET | `/samples/{name}` | 샘플 원본 |

`/api/jobs` 오류: 400(설정·입력 오류, 메시지 그대로), 413(업로드 크기 초과),
500(`detail`과 `traceback`).
