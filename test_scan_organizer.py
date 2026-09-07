"""scan_organizer 추출 로직 검증. 실행: python test_scan_organizer.py"""

import tempfile
from pathlib import Path

from scan_organizer import (
    PdfReadError,
    extract_number,
    load_patterns,
    RenamePlan,
    normalize,
    plan_renames,
    read_first_page,
    sanitize,
)

P = load_patterns()  # config.ini 없으면 내장 기본값


def test_라벨있는_7자리():
    assert extract_number("결의번호 : 20260315-0000005", P) == "20260315-0000005"


def test_라벨없는_4자리():
    assert extract_number("20260414-0001", P) == "20260414-0001"


def test_줄바꿈_섞인_라벨():
    text = "지출결의서\n결의번호\n:\n20260315-0000005\n부서: 교무부"
    assert extract_number(text, P) == "20260315-0000005"


def test_6자리는_인식안됨():
    # 일련번호는 7자리 또는 4자리만 존재한다. 6자리는 다른 숫자로 본다.
    assert extract_number("20260315-000005", P) is None


def test_8자리는_인식안됨():
    # (?!\d) 경계 검증. 뒤에 숫자가 더 붙으면 매치 실패해야 한다.
    assert extract_number("20260315-00000055", P) is None


def test_다른_숫자만_있으면_없음():
    text = "계좌번호 123-456-789012  금액 1,250,000원  전화 02-1234-5678"
    assert extract_number(text, P) is None


def test_라벨이_다른_숫자보다_우선():
    # 단독 패턴이 먼저 걸릴 위치에 다른 숫자가 있어도 라벨 쪽을 집어야 한다.
    text = "문서번호 20260101-9999  본문  결의번호 : 20260315-0000005"
    assert extract_number(text, P) == "20260315-0000005"


def test_빈_문자열():
    assert extract_number("", P) is None


def test_normalize_공백_압축():
    assert normalize("가  나\n\n다\t라") == "가 나 다 라"


def test_손상된_pdf는_예외():
    임시 = Path(tempfile.mkdtemp()) / "깨진.pdf"
    임시.write_bytes("이건 PDF가 아닙니다".encode())
    try:
        read_first_page(임시)
        raise AssertionError("PdfReadError가 발생해야 한다")
    except PdfReadError:
        pass


def test_없는_파일은_예외():
    try:
        read_first_page(Path("/존재하지/않는/경로.pdf"))
        raise AssertionError("PdfReadError가 발생해야 한다")
    except PdfReadError:
        pass


def _가짜_pdf들(작업폴더: Path, 항목: list[tuple[str, str]]) -> list[Path]:
    """(파일명, 첫페이지텍스트) 목록을 받아 read_first_page가 읽을 수 있는
    가짜 파일을 만든다. 본문은 monkeypatch로 대체한다."""
    경로들 = []
    for i, (이름, _) in enumerate(항목):
        p = 작업폴더 / 이름
        p.write_bytes(b"dummy")
        import os
        os.utime(p, (1000 + i, 1000 + i))  # 수정 시각을 순서대로 벌린다
        경로들.append(p)
    return 경로들


def _텍스트_주입(항목: dict[str, str]):
    """read_first_page를 파일명 기반 사전 조회로 바꿔치기한다."""
    import scan_organizer

    원본 = scan_organizer.read_first_page
    scan_organizer.read_first_page = lambda p: 항목[p.name]
    return 원본


def _텍스트_복원(원본):
    import scan_organizer

    scan_organizer.read_first_page = 원본


def test_수정시각_오름차순_정렬():
    폴더 = Path(tempfile.mkdtemp())
    항목 = [
        ("Scan_0009.pdf", "결의번호 : 20260315-0000008"),
        ("Scan_0007.pdf", "결의번호 : 20260315-0000012"),
        ("Scan_0008.pdf", "결의번호 : 20260315-0000005"),
    ]
    경로들 = _가짜_pdf들(폴더, 항목)
    원본 = _텍스트_주입(dict(항목))
    try:
        계획 = plan_renames(경로들, P)
    finally:
        _텍스트_복원(원본)

    assert [c.path.name for c in 계획] == ["Scan_0009.pdf", "Scan_0007.pdf", "Scan_0008.pdf"]
    assert [c.number for c in 계획] == [
        "20260315-0000008",
        "20260315-0000012",
        "20260315-0000005",
    ]


def test_미인식은_새이름_없음():
    폴더 = Path(tempfile.mkdtemp())
    항목 = [("Scan_0001.pdf", "결의번호가 없는 문서입니다")]
    경로들 = _가짜_pdf들(폴더, 항목)
    원본 = _텍스트_주입(dict(항목))
    try:
        계획 = plan_renames(경로들, P)
    finally:
        _텍스트_복원(원본)

    assert 계획[0].status == "미인식"
    assert 계획[0].new_name is None
    assert "결의번호가 없는 문서입니다" in 계획[0].reason


def test_배치_내_중복은_접미어():
    폴더 = Path(tempfile.mkdtemp())
    항목 = [
        ("Scan_0001.pdf", "결의번호 : 20260315-0000005"),
        ("Scan_0002.pdf", "결의번호 : 20260315-0000005"),
        ("Scan_0003.pdf", "결의번호 : 20260315-0000005"),
    ]
    경로들 = _가짜_pdf들(폴더, 항목)
    원본 = _텍스트_주입(dict(항목))
    try:
        계획 = plan_renames(경로들, P)
    finally:
        _텍스트_복원(원본)

    assert [c.new_name for c in 계획] == [
        "20260315-0000005.pdf",
        "20260315-0000005_2.pdf",
        "20260315-0000005_3.pdf",
    ]
    assert [c.status for c in 계획] == ["정상", "중복", "중복"]


def test_기존_파일과_충돌하면_접미어():
    폴더 = Path(tempfile.mkdtemp())
    (폴더 / "20260315-0000005.pdf").write_bytes(b"already here")
    항목 = [("Scan_0001.pdf", "결의번호 : 20260315-0000005")]
    경로들 = _가짜_pdf들(폴더, 항목)
    원본 = _텍스트_주입(dict(항목))
    try:
        계획 = plan_renames(경로들, P)
    finally:
        _텍스트_복원(원본)

    assert 계획[0].new_name == "20260315-0000005_2.pdf"
    assert 계획[0].status == "중복"


def test_이미_올바른_이름이면_그대로():
    # 자기 자신을 "이미 존재하는 파일"로 세어 _2를 붙이면 안 된다
    폴더 = Path(tempfile.mkdtemp())
    항목 = [("20260315-0000005.pdf", "결의번호 : 20260315-0000005")]
    경로들 = _가짜_pdf들(폴더, 항목)
    원본 = _텍스트_주입(dict(항목))
    try:
        계획 = plan_renames(경로들, P)
    finally:
        _텍스트_복원(원본)

    assert 계획[0].new_name == "20260315-0000005.pdf"
    assert 계획[0].status == "정상"


def test_읽기_실패는_미인식():
    폴더 = Path(tempfile.mkdtemp())
    경로들 = _가짜_pdf들(폴더, [("깨진.pdf", "")])
    import scan_organizer

    원본 = scan_organizer.read_first_page

    def 터짐(p):
        raise scan_organizer.PdfReadError("EOF marker not found")

    scan_organizer.read_first_page = 터짐
    try:
        계획 = plan_renames(경로들, P)
    finally:
        scan_organizer.read_first_page = 원본

    assert 계획[0].status == "미인식"
    assert "EOF marker not found" in 계획[0].reason


def test_sanitize_금지문자():
    assert sanitize('a/b:c*d?e"f<g>h|i\\j') == "a-b-c-d-e-f-g-h-i-j"


if __name__ == "__main__":
    수행 = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in 수행:
        fn()
        print(f"  통과  {fn.__name__}")
    print(f"\n{len(수행)}개 모두 통과")
