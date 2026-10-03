"""Render synthetic A4 test documents (300 dpi PNG, plus a 2-page PDF) into samples/input.

The documents stress what office OCR must survive: 8-12 pt Hangul, small digits,
dense spreadsheet grids, hairline borders, grey shading, a red seal, a barcode and a
QR-like module grid. All content is invented. The bar and module patterns are
structural stand-ins and are not decodable codes.

Usage: uv run python scripts/make_samples.py [--font-dir DIR]
Requires Noto Sans/Serif CJK (OFL). On Windows pass --font-dir pointing at them.
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

DPI = 300
W, H = 2480, 3508  # A4 at 300 dpi
OUT = Path(__file__).resolve().parent.parent / "samples" / "input"
FONT_FILES = {
    "sans": "NotoSansCJK-Regular.ttc",
    "sans-bold": "NotoSansCJK-Bold.ttc",
    "serif": "NotoSerifCJK-Regular.ttc",
    "serif-bold": "NotoSerifCJK-Bold.ttc",
}
KR_INDEX = 1  # face index of "KR" inside the Noto CJK collections


class Fonts:
    def __init__(self, font_dir: Path) -> None:
        missing = [f for f in FONT_FILES.values() if not (font_dir / f).is_file()]
        if missing:
            raise SystemExit(f"missing fonts in {font_dir}: {', '.join(missing)}")
        self.dir = font_dir

    def get(self, kind: str, pt: float) -> ImageFont.FreeTypeFont:
        size = round(pt * DPI / 72)
        return ImageFont.truetype(str(self.dir / FONT_FILES[kind]), size, index=KR_INDEX)


def mm(v: float) -> int:
    return round(v * DPI / 25.4)


def page() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), "white")
    return img, ImageDraw.Draw(img)


def grid(
    d: ImageDraw.ImageDraw, x0: int, y0: int, cols: list[int], rows: list[int], width: int = 2
) -> None:
    xs = [x0]
    for c in cols:
        xs.append(xs[-1] + c)
    ys = [y0]
    for r in rows:
        ys.append(ys[-1] + r)
    for x in xs:
        d.line([(x, ys[0]), (x, ys[-1])], fill="black", width=width)
    for y in ys:
        d.line([(xs[0], y), (xs[-1], y)], fill="black", width=width)


def seal(d: ImageDraw.ImageDraw, f: Fonts, cx: int, cy: int, text: str) -> None:
    red = (200, 30, 35)
    r = mm(9)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=red, width=8)
    font = f.get("serif-bold", 11)
    d.text((cx, cy), text, font=font, fill=red, anchor="mm")


def barcode(d: ImageDraw.ImageDraw, x: int, y: int, h: int, rng: random.Random) -> None:
    pos = x
    for _ in range(60):
        bar, gap = rng.choice((2, 4, 6, 8)), rng.choice((2, 4, 6))
        d.rectangle([pos, y, pos + bar - 1, y + h], fill="black")
        pos += bar + gap


def module_grid(
    d: ImageDraw.ImageDraw, x: int, y: int, n: int, cell: int, rng: random.Random
) -> None:
    def finder(fx: int, fy: int) -> None:
        d.rectangle([fx, fy, fx + 7 * cell - 1, fy + 7 * cell - 1], fill="black")
        d.rectangle([fx + cell, fy + cell, fx + 6 * cell - 1, fy + 6 * cell - 1], fill="white")
        d.rectangle(
            [fx + 2 * cell, fy + 2 * cell, fx + 5 * cell - 1, fy + 5 * cell - 1], fill="black"
        )

    for i in range(n):
        for j in range(n):
            in_finder = (i < 8 and j < 8) or (i < 8 and j >= n - 8) or (i >= n - 8 and j < 8)
            if not in_finder and rng.random() < 0.5:
                d.rectangle(
                    [x + j * cell, y + i * cell, x + (j + 1) * cell - 1, y + (i + 1) * cell - 1],
                    fill="black",
                )
    for fx, fy in ((0, 0), (n - 7, 0), (0, n - 7)):
        finder(x + fx * cell, y + fy * cell)


def invoice(f: Fonts, rng: random.Random) -> Image.Image:
    img, d = page()
    d.text(
        (W // 2, mm(25)), "거 래 명 세 서", font=f.get("sans-bold", 22), fill="black", anchor="mm"
    )
    d.text((mm(20), mm(40)), "No. 2026-1002-0417", font=f.get("sans", 9), fill="black")
    d.text(
        (W - mm(20), mm(40)),
        "작성일자: 2026년 10월 2일",
        font=f.get("sans", 9),
        fill="black",
        anchor="ra",
    )
    # supplier / buyer boxes
    small = f.get("sans", 9)
    grid(d, mm(20), mm(48), [mm(25), mm(60)], [mm(9)] * 4)
    grid(d, mm(110), mm(48), [mm(25), mm(55)], [mm(9)] * 4)
    left = [
        ("등록번호", "123-45-67890"),
        ("상호", "(주)샘플정밀"),
        ("대표자", "김민준"),
        ("주소", "서울시 ○○구 예시로 123"),
    ]
    right = [
        ("등록번호", "987-65-43210"),
        ("상호", "예시산업(주)"),
        ("대표자", "이서연"),
        ("전화", "02-0000-0000"),
    ]
    for i, ((k1, v1), (k2, v2)) in enumerate(zip(left, right, strict=True)):
        y = mm(48) + i * mm(9) + mm(4.5)
        d.text((mm(22), y), k1, font=small, fill="black", anchor="lm")
        d.text((mm(47), y), v1, font=small, fill="black", anchor="lm")
        d.text((mm(112), y), k2, font=small, fill="black", anchor="lm")
        d.text((mm(137), y), v2, font=small, fill="black", anchor="lm")
    seal(d, f, mm(98), mm(66), "샘플")
    # item table with grey header
    cols = [mm(10), mm(62), mm(22), mm(15), mm(28), mm(33)]
    top, row_h = mm(95), mm(8)
    d.rectangle([mm(20), top, mm(20) + sum(cols), top + row_h], fill=(225, 225, 225))
    grid(d, mm(20), top, cols, [row_h] * 19, width=2)
    heads = ["No", "품명 / 규격", "단위", "수량", "단가", "공급가액"]
    x = mm(20)
    for c, h in zip(cols, heads, strict=True):
        d.text(
            (x + c // 2, top + row_h // 2), h, font=f.get("sans-bold", 9), fill="black", anchor="mm"
        )
        x += c
    items = [
        "알루미늄 프로파일 40x40",
        "볼트 M6x20 SUS304",
        "베어링 6204ZZ",
        "타이밍벨트 HTD-5M 15W",
        "리니어가이드 HGR20 L=600",
        "커플링 D25 L30",
        "스텝모터 NEMA17 1.8°",
        "케이블타이 200mm 흑색",
        "방열판 50x50x20",
        "실리콘 패드 t=1.0",
    ]
    total = 0
    for i in range(18):
        y = top + row_h * (i + 1) + row_h // 2
        if i >= len(items):
            continue
        qty, price = rng.randint(1, 240), rng.randint(3, 900) * 100
        total += qty * price
        cells = [
            str(i + 1),
            items[i],
            rng.choice(["EA", "SET", "M", "BOX"]),
            f"{qty:,}",
            f"{price:,}",
            f"{qty * price:,}",
        ]
        x = mm(20)
        for j, (c, v) in enumerate(zip(cols, cells, strict=True)):
            if j in (0, 2):
                d.text((x + c // 2, y), v, font=small, fill="black", anchor="mm")
            elif j == 1:
                d.text((x + mm(2), y), v, font=small, fill="black", anchor="lm")
            else:
                d.text((x + c - mm(2), y), v, font=small, fill="black", anchor="rm")
            x += c
    y = top + row_h * 19 + mm(8)
    vat = total // 10
    for label, v in (("공급가액", total), ("부가세", vat), ("합계금액", total + vat)):
        d.text((mm(130), y), label, font=f.get("sans-bold", 10), fill="black", anchor="lm")
        d.text((mm(190), y), f"₩ {v:,}", font=f.get("sans", 10), fill="black", anchor="rm")
        y += mm(8)
    d.text(
        (mm(20), mm(272)),
        "※ 본 명세서는 전자세금계산서 발행 근거 자료로 사용됩니다.",
        font=f.get("sans", 8),
        fill=(60, 60, 60),
    )
    barcode(d, mm(20), mm(250), mm(12), rng)
    return img


def contract(f: Fonts, rng: random.Random) -> Image.Image:
    img, d = page()
    d.text(
        (W // 2, mm(28)),
        "물품 공급 계약서",
        font=f.get("serif-bold", 20),
        fill="black",
        anchor="mm",
    )
    body = f.get("serif", 10.5)
    clauses = [
        (
            "제1조 (목적)",
            "본 계약은 갑이 을에게 공급하는 물품의 품목, 수량, 단가, 납기 및 "
            "대금 지급 조건 등 거래에 관한 기본 사항을 정함을 목적으로 한다.",
        ),
        (
            "제2조 (공급 물품)",
            "공급 물품의 명세는 별첨 견적서(견적번호 Q-2026-0915)에 "
            "따르며, 총 공급가액은 금 일억이천삼백사십오만육천칠백팔십구원"
            "(₩123,456,789, 부가세 별도)으로 한다.",
        ),
        (
            "제3조 (납품)",
            "을은 2026년 11월 30일까지 갑이 지정한 장소(경기도 ○○시 "
            "○○산단로 45)에 물품을 납품하여야 하며, 납품 시 검수 확인서를 받아야 한다.",
        ),
        (
            "제4조 (대금 지급)",
            "갑은 검수 완료일로부터 30일 이내에 을이 지정한 계좌"
            "(○○은행 000-00-0000-000)로 대금을 지급한다. 지급이 지연되는 경우 연 6%의 "
            "지연이자를 가산한다.",
        ),
        (
            "제5조 (하자 보증)",
            "을은 납품일로부터 12개월간 물품의 하자를 보증하며, 하자가 "
            "발견된 경우 7일 이내에 무상으로 수리 또는 교환한다.",
        ),
        (
            "제6조 (계약 해지)",
            "당사자 일방이 본 계약을 위반하고 서면 통지 후 14일 이내에 "
            "시정하지 않는 경우 상대방은 본 계약을 해지할 수 있다.",
        ),
        ("제7조 (관할)", "본 계약과 관련한 분쟁은 서울중앙지방법원을 제1심 관할 법원으로 한다."),
    ]
    y, max_w = mm(48), W - mm(50)
    for head, text in clauses:
        d.text((mm(25), y), head, font=f.get("serif-bold", 11), fill="black")
        y += mm(7)
        line = ""
        for ch in text:
            if d.textlength(line + ch, font=body) > max_w:
                d.text((mm(25), y), line, font=body, fill="black")
                y += mm(6.2)
                line = ""
            line += ch
        d.text((mm(25), y), line, font=body, fill="black")
        y += mm(10)
    d.text(
        (W // 2, y + mm(5)), "2026년 10월 2일", font=f.get("serif", 12), fill="black", anchor="mm"
    )
    y += mm(20)
    for i, (role, name, co) in enumerate(
        (("갑", "박지훈", "예시산업 주식회사"), ("을", "김민준", "주식회사 샘플정밀"))
    ):
        x = mm(25) + i * mm(90)
        d.text((x, y), f"({role}) {co}", font=f.get("serif", 10.5), fill="black")
        d.text((x, y + mm(8)), f"대표이사  {name}  (인)", font=f.get("serif", 10.5), fill="black")
        # hand-signature-like stroke in blue ballpoint
        pts = [
            (x + mm(48) + k * 9, y + mm(10) + int(18 * rng.random() - 9 + 14 * ((k % 6) - 3)))
            for k in range(24)
        ]
        d.line(pts, fill=(25, 45, 140), width=4, joint="curve")
    seal(d, f, mm(85), y + mm(10), "예시")
    return img


def spreadsheet(f: Fonts, rng: random.Random) -> Image.Image:
    img, d = page()
    d.text(
        (mm(15), mm(15)),
        "2026년 3분기 부서별 경비 집계표",
        font=f.get("sans-bold", 14),
        fill="black",
    )
    d.text((W - mm(15), mm(18)), "(단위: 원)", font=f.get("sans", 8), fill="black", anchor="ra")
    cols = [mm(28)] + [mm(17)] * 9 + [mm(25)]
    rows = [mm(6)] * 40
    top, left = mm(28), mm(12)
    d.rectangle([left, top, left + sum(cols), top + rows[0]], fill=(217, 225, 242))
    font, bold = f.get("sans", 8), f.get("sans-bold", 8)
    heads = [
        "부서",
        "7월 출장",
        "7월 소모품",
        "7월 기타",
        "8월 출장",
        "8월 소모품",
        "8월 기타",
        "9월 출장",
        "9월 소모품",
        "9월 기타",
        "합계",
    ]
    depts = [
        "경영지원팀",
        "재무회계팀",
        "인사총무팀",
        "영업1팀",
        "영업2팀",
        "해외영업팀",
        "생산관리팀",
        "품질보증팀",
        "구매팀",
        "연구개발1팀",
        "연구개발2팀",
        "설계팀",
        "IT운영팀",
        "고객지원팀",
        "물류팀",
        "안전환경팀",
    ]
    x = left
    for c, h in zip(cols, heads, strict=True):
        d.text((x + c // 2, top + rows[0] // 2), h, font=bold, fill="black", anchor="mm")
        x += c
    for i in range(1, 40):
        y = top + sum(rows[:i]) + rows[i] // 2
        dept = depts[(i - 1) % len(depts)] + ("" if i <= len(depts) else f"-{(i - 1) // 16}")
        vals = [rng.randint(0, 4_800_000) // 10 * 10 for _ in range(9)]
        if i % 7 == 0:
            vals[rng.randrange(9)] = 0
        d.text((x := left + mm(1.5), y), dept, font=font, fill="black", anchor="lm")
        x = left + cols[0]
        for c, v in zip(cols[1:-1], vals, strict=True):
            text = f"{v:,}" if v else "-"
            color = (192, 0, 0) if v > 4_500_000 else "black"
            d.text((x + c - mm(1.2), y), text, font=font, fill=color, anchor="rm")
            x += c
        d.text((x + cols[-1] - mm(1.2), y), f"{sum(vals):,}", font=bold, fill="black", anchor="rm")
    grid(d, left, top, cols, rows, width=1)  # Excel default hairline: 1 px at 300 dpi
    d.rectangle([left, top, left + sum(cols), top + sum(rows)], outline="black", width=3)
    d.text(
        (mm(15), top + sum(rows) + mm(6)),
        "주: 붉은 글씨는 월 한도(4,500,000원) 초과 항목.",
        font=f.get("sans", 7),
        fill="black",
    )
    return img


def form(f: Fonts, rng: random.Random) -> Image.Image:
    img, d = page()
    # simple logo: blue square + wordmark
    d.rectangle([mm(20), mm(15), mm(32), mm(27)], fill=(0, 82, 155))
    d.ellipse([mm(23), mm(18), mm(29), mm(24)], fill="white")
    d.text(
        (mm(35), mm(21)), "샘플정밀", font=f.get("sans-bold", 16), fill=(0, 82, 155), anchor="lm"
    )
    d.text(
        (W // 2, mm(42)), "출 장 신 청 서", font=f.get("sans-bold", 18), fill="black", anchor="mm"
    )
    font, small = f.get("sans", 10), f.get("sans", 8)
    labels = ["성명", "소속", "사번", "출장지", "기간", "목적", "교통편", "예상경비"]
    values = [
        "정하은",
        "생산관리팀",
        "20190347",
        "부산광역시 ○○구 예시산단로 321",
        "2026.10.12 ~ 2026.10.14 (2박 3일)",
        "협력사 품질 감사 및 공정 점검",
        None,
        "₩ 684,500",
    ]
    top = mm(55)
    grid(d, mm(20), top, [mm(35), mm(135)], [mm(12)] * len(labels))
    for i, (k, v) in enumerate(zip(labels, values, strict=True)):
        y = top + i * mm(12) + mm(6)
        d.rectangle(
            [mm(20) + 2, top + i * mm(12) + 2, mm(55) - 2, top + (i + 1) * mm(12) - 2],
            fill=(240, 240, 240),
        )
        d.text((mm(37.5), y), k, font=font, fill="black", anchor="mm")
        if v is not None:
            d.text((mm(58), y), v, font=font, fill="black", anchor="lm")
            continue
        x = mm(58)
        for opt, checked in (("KTX", True), ("항공", False), ("자가용", False), ("버스", False)):
            box = mm(4)
            d.rectangle([x, y - box // 2, x + box, y + box // 2], outline="black", width=3)
            if checked:
                d.line(
                    [(x + 6, y), (x + box // 2, y + box // 2 - 6), (x + box + 8, y - box)],
                    fill="black",
                    width=6,
                )
            d.text((x + box + mm(2), y), opt, font=font, fill="black", anchor="lm")
            x += mm(30)
    y = top + len(labels) * mm(12) + mm(10)
    d.text((mm(20), y), "결재", font=f.get("sans-bold", 10), fill="black")
    grid(d, mm(110), y, [mm(20)] * 4, [mm(7), mm(18)])
    for i, r in enumerate(("담당", "팀장", "부장", "대표")):
        d.text((mm(120) + i * mm(20), y + mm(3.5)), r, font=small, fill="black", anchor="mm")
    seal(d, f, mm(120), y + mm(16), "정하")
    y += mm(40)
    lines = [
        "1. 출장 종료 후 5일 이내에 출장 보고서와 영수증을 제출한다.",
        "2. 숙박비 한도: 1박 100,000원 (광역시 기준), 일비 30,000원.",
        "3. 법인카드 사용분은 개인 정산 대상에서 제외한다.",
        "4. 문의: 경영지원팀 내선 2417 / expense@sample-precision.example",
    ]
    for line in lines:
        d.text((mm(20), y), line, font=small, fill="black")
        y += mm(5.5)
    module_grid(d, mm(160), mm(250), 25, 12, rng)
    d.text((mm(20), mm(280)), "양식번호 HB-F-031 (Rev.4)", font=f.get("sans", 7), fill="black")
    return img


def memo(f: Fonts, rng: random.Random) -> Image.Image:
    img, d = page()
    d.text((mm(20), mm(20)), "업무 연락", font=f.get("sans-bold", 20), fill="black")
    d.line([(mm(20), mm(32)), (W - mm(20), mm(32))], fill="black", width=6)
    d.line([(mm(20), mm(33.5)), (W - mm(20), mm(33.5))], fill="black", width=1)
    font = f.get("sans", 11)
    meta = [
        ("수신", "각 팀장"),
        ("발신", "품질보증팀 최도윤 책임"),
        ("일자", "2026-10-02"),
        ("제목", "협력사 수입검사 기준 개정(QA-STD-118 Rev.C) 안내"),
    ]
    y = mm(40)
    for k, v in meta:
        d.text((mm(20), y), k, font=f.get("sans-bold", 11), fill="black")
        d.text((mm(40), y), v, font=font, fill="black")
        y += mm(8)
    y += mm(6)
    paragraphs = [
        "1. 10월 13일(월) 입고분부터 수입검사 샘플링 기준이 AQL 1.0에서 AQL 0.65로 강화됩니다.",
        "2. 치수 검사 항목 중 공차 ±0.05 mm 이하 항목은 전수 검사로 전환합니다.",
        "3. 성적서 미첨부 로트는 입고 보류 후 협력사에 회신합니다(회신 기한 3영업일).",
        "4. 변경 내역 요약은 아래 표를 참고하시기 바랍니다.",
    ]
    for ptext in paragraphs:
        d.text((mm(22), y), ptext, font=font, fill="black")
        y += mm(9)
    cols, top = [mm(40), mm(60), mm(60)], y + mm(4)
    d.rectangle([mm(22), top, mm(22) + sum(cols), top + mm(8)], fill=(80, 80, 80))
    grid(d, mm(22), top, cols, [mm(8)] * 6, width=2)
    rows = [
        ("구분", "현행", "개정"),
        ("샘플링", "AQL 1.0", "AQL 0.65"),
        ("치수 ±0.05 이하", "샘플 5 EA", "전수"),
        ("외관", "육안", "육안 + 확대경(10x)"),
        ("성적서", "권장", "필수"),
        ("회신 기한", "5영업일", "3영업일"),
    ]
    for i, row in enumerate(rows):
        x = mm(22)
        for c, v in zip(cols, row, strict=True):
            color = "white" if i == 0 else "black"
            d.text(
                (x + c // 2, top + i * mm(8) + mm(4)),
                v,
                font=f.get("sans", 10),
                fill=color,
                anchor="mm",
            )
            x += c
    y = top + mm(60)
    d.text(
        (mm(22), y), "※ 회색 글씨 문단은 참고용입니다.", font=f.get("sans", 9), fill=(110, 110, 110)
    )
    y += mm(8)
    d.text(
        (mm(22), y),
        "중요: 미준수 시 해당 로트는 전량 반품 처리됩니다.",
        font=f.get("sans-bold", 11),
        fill=(200, 0, 0),
    )
    y += mm(10)
    for k in range(6):
        size = 8 + k
        d.text(
            (mm(22), y),
            f"{size}pt 글자 크기 시험 0123456789 가나다라마바사 ABCabc",
            font=f.get("sans", size),
            fill="black",
        )
        y += mm(size * 0.55 + 2)
    return img


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font-dir", type=Path, default=Path("/usr/share/fonts/opentype/noto"))
    args = parser.parse_args()
    fonts = Fonts(args.font_dir)
    OUT.mkdir(parents=True, exist_ok=True)
    makers = {
        "invoice_001": invoice,
        "contract_002": contract,
        "spreadsheet_003": spreadsheet,
        "form_004": form,
        "memo_005": memo,
    }
    pages = {}
    for i, (name, make) in enumerate(makers.items()):
        img = make(fonts, random.Random(1000 + i))
        pages[name] = img
        path = OUT / f"{name}.png"
        img.save(path, dpi=(DPI, DPI), optimize=True)
        print(path)
    # Multi-page PDF input. Pillow embeds the pages as 300 dpi images (no text layer).
    bundle = [pages["contract_002"], pages["memo_005"]]
    path = OUT / "bundle_006.pdf"
    bundle[0].save(path, save_all=True, append_images=bundle[1:], resolution=DPI)
    print(path)


if __name__ == "__main__":
    main()
