"""scan_organizer 추출 로직 검증. 실행: python test_scan_organizer.py"""

from scan_organizer import normalize, extract_number, load_patterns

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


if __name__ == "__main__":
    수행 = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in 수행:
        fn()
        print(f"  통과  {fn.__name__}")
    print(f"\n{len(수행)}개 모두 통과")
