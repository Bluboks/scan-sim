# 프로젝트 역사

2026-10-02 소유자가 OCR 테스트용 print-scan 시뮬레이터 개발 명세(`brief.md`)를
작성했다. 원문은 [archive](archive/2026-10-02-initial-brief.md)에 그대로 보관한다.

같은 날 소유자 결정으로 v0.1 범위만 먼저 구현했다(ADR-001). 실물 비교 쌍이 없어서
현실성 판단은 소유자 위임에 따라 에이전트가 맡았다. 문서 체계는
`~/coding/document-normalizer`의 구성(GOVERNANCE, DECISIONS, ADR-lite, archive)을
이 프로젝트 규모에 맞게 줄여 따른다.

같은 날 소유자 요청으로 웹 화면([WEB](ops/WEB.md))을, 2026-10-03에 PDF 입력(ADR-005)과
휴대폰 조작을 추가했다. 2026-10-03 GitHub 공개 저장소로 올리면서 로컬 커밋 이력을 첫 커밋
하나로 합쳤다(내부 네트워크 주소 제거). 샘플의 회사명·번호·주소는 이때 확실히 지어낸 값으로
바꿨다.

이후 사용자에게 보이는 변경은 [CHANGELOG](../CHANGELOG.md), 설계 선택은
[DECISIONS](DECISIONS.md)에서 관리한다.
