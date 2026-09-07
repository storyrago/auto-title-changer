# 스캔 결의서 파일명 자동 변경 프로그램 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 담당자가 스캔 폴더에서 PDF들을 선택하면 각 PDF 첫 페이지의 결의번호를 읽어, 사전 확인 후 제자리에서 파일명을 변경하는 Windows 데스크톱 프로그램을 만든다.

**Architecture:** 순수 함수 층(텍스트 → 결의번호), PDF 읽기 층, 계획 수립 층(`plan_renames` — 파일을 건드리지 않음), 실행 층(`apply_renames`), GUI 층으로 분리한다. 계획과 실행이 분리되어 있어야 "바꾸기 전에 보여주고 승인받는" 화면이 성립한다. 파일은 삭제·이동하지 않고 같은 폴더 안에서 이름만 바꾼다.

**Tech Stack:** Python 3.10+, `pypdf` (유일한 외부 의존성), 표준 라이브러리 `tkinter` / `configparser` / `pathlib` / `re` / `dataclasses`

## Global Constraints

- Python 3.10 이상. 타입 힌트에 `str | None` 문법 사용 가능.
- 외부 의존성은 `pypdf` **하나뿐**. 다른 패키지를 추가하지 않는다 (NFR-05).
- 테스트 프레임워크를 설치하지 않는다. `assert` 기반 스크립트를 `python test_scan_organizer.py`로 실행한다.
- 파일 **삭제 금지, 이동 금지**. `Path.rename()`으로 같은 폴더 내 이름 변경만 한다 (FR-10).
- 기존 파일 **덮어쓰기 금지**. 충돌 시 `_2`, `_3` 접미어 (FR-07).
- 모든 파일 입출력은 UTF-8. 경로는 `pathlib` 사용 (NFR-06).
- 네트워크 통신 코드를 넣지 않는다 (NFR-08).
- 개별 파일의 오류가 전체 처리를 중단시키지 않는다 (NFR-02).
- 결의번호 형식: `YYYYMMDD-` + 일련번호 **7자리 또는 4자리**. 5·6자리는 인식되지 않아야 한다.
- 사용자는 비개발자. 주요 함수에 한글 docstring, 설정 파일에 한글 주석 (NFR-07).
- 최종 실행 환경은 Windows 10/11. 개발은 macOS에서 하되 OS 의존 코드를 넣지 않는다.

---

### Task 1: 결의번호 추출 (순수 함수) + 설정 파일 로딩

프로그램의 심장부. 텍스트를 받아 결의번호를 돌려주는 순수 함수와, 정규식을 `config.ini`에서 읽어오는 함수를 만든다. 파일 시스템이나 PDF와 무관하므로 완전히 독립적으로 테스트된다.

**Files:**
- Create: `scan_organizer.py`
- Create: `config.ini`
- Test: `test_scan_organizer.py`

**Interfaces:**
- Consumes: 없음 (첫 태스크)
- Produces:
  - `normalize(text: str) -> str` — 공백·줄바꿈을 단일 공백으로 정규화
  - `load_patterns(config_path: Path | None = None) -> list[re.Pattern]` — 라벨패턴, 단독패턴 순서의 리스트 반환
  - `extract_number(text: str, patterns: list[re.Pattern]) -> str | None`
  - `DEFAULT_LABEL_PATTERN: str`, `DEFAULT_BARE_PATTERN: str` — config.ini 부재 시 내장 기본값

---

- [ ] **Step 1: 실패하는 테스트 작성**

`test_scan_organizer.py`를 새로 만든다.

```python
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
```

- [ ] **Step 2: 테스트를 실행해 실패를 확인**

Run: `python3 test_scan_organizer.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'scan_organizer'`

- [ ] **Step 3: 최소 구현 작성**

`scan_organizer.py`를 새로 만든다.

```python
"""스캔된 결의서 PDF의 첫 페이지에서 결의번호를 읽어 파일명을 바꾼다."""

from __future__ import annotations

import configparser
import re
from pathlib import Path

# config.ini가 없을 때 사용하는 내장 기본값.
# 일련번호는 7자리 또는 4자리 두 가지만 존재한다.
# 7자리를 먼저 시도해야 한다. 순서가 반대면 "0000005"에서 앞 4자리만 잘린다.
# (?!\d)는 뒤에 숫자가 더 오면 매치를 실패시켜, 더 긴 숫자열의 일부가
# 잘못 잡히는 것을 막는다.
DEFAULT_LABEL_PATTERN = r"결의번호\s*[:：]?\s*(\d{8}-(?:\d{7}|\d{4}))(?!\d)"
DEFAULT_BARE_PATTERN = r"(\d{8}-(?:\d{7}|\d{4}))(?!\d)"


def normalize(text: str) -> str:
    """공백·줄바꿈·탭을 모두 단일 공백으로 바꾼다.

    OCR이 결의번호 주위에서 줄을 어떻게 끊든 정규식이 영향받지 않게 한다.
    """
    return re.sub(r"\s+", " ", text).strip()


def load_patterns(config_path: Path | None = None) -> list[re.Pattern]:
    """config.ini에서 정규식을 읽는다. 없으면 내장 기본값을 쓴다.

    반환 순서가 곧 적용 순서다. 라벨 패턴을 먼저 시도한다.
    정규식이 잘못되어 컴파일에 실패하면 ValueError를 올린다.
    """
    label, bare = DEFAULT_LABEL_PATTERN, DEFAULT_BARE_PATTERN

    if config_path and config_path.exists():
        parser = configparser.ConfigParser(interpolation=None)
        parser.read(config_path, encoding="utf-8")
        if parser.has_section("결의번호"):
            label = parser.get("결의번호", "라벨패턴", fallback=label)
            bare = parser.get("결의번호", "단독패턴", fallback=bare)

    patterns = []
    for 이름, 식 in (("라벨패턴", label), ("단독패턴", bare)):
        try:
            patterns.append(re.compile(식))
        except re.error as e:
            raise ValueError(f"{이름}이 올바른 정규식이 아닙니다: {e}") from e
    return patterns


def extract_number(text: str, patterns: list[re.Pattern]) -> str | None:
    """텍스트에서 결의번호를 찾는다. 못 찾으면 None.

    patterns를 순서대로 시도하고, 첫 매치의 첫 그룹을 돌려준다.
    """
    정규화 = normalize(text)
    for pattern in patterns:
        m = pattern.search(정규화)
        if m:
            return m.group(1)
    return None
```

- [ ] **Step 4: 테스트를 실행해 통과를 확인**

Run: `python3 test_scan_organizer.py`
Expected: PASS — `9개 모두 통과`

- [ ] **Step 5: config.ini 작성**

`config.ini`를 새로 만든다. 담당자가 메모장으로 여는 파일이므로 주석이 설명서 역할을 한다.

```ini
# 결의번호를 찾는 규칙입니다. 메모장으로 수정할 수 있습니다.
# 수정 후에는 프로그램을 껐다 켜야 반영됩니다.
#
# 프로그램은 라벨패턴을 먼저 시도하고, 못 찾으면 단독패턴을 시도합니다.
# 괄호 ( ) 안의 부분이 파일명이 됩니다. 괄호를 지우지 마세요.
#
# \d{8}      숫자 8자리 (앞의 날짜 부분, 예: 20260315)
# \d{7}      숫자 7자리 (일련번호가 긴 경우)
# \d{4}      숫자 4자리 (일련번호가 짧은 경우)
# \s*        공백이 없거나 여러 개 있어도 됨
# (?!\d)     바로 뒤에 숫자가 더 오면 인식하지 않음 (계좌번호 등 오인식 방지)

[결의번호]

# 1단계: 문서에 "결의번호 : 20260315-0000005" 처럼 라벨이 붙은 경우
라벨패턴 = 결의번호\s*[:：]?\s*(\d{8}-(?:\d{7}|\d{4}))(?!\d)

# 2단계: 라벨 없이 "20260315-0000005" 만 찍힌 경우
단독패턴 = (\d{8}-(?:\d{7}|\d{4}))(?!\d)
```

- [ ] **Step 6: config.ini를 실제로 읽는지 확인**

Run:
```bash
python3 -c "
from pathlib import Path
from scan_organizer import load_patterns, extract_number
P = load_patterns(Path('config.ini'))
print(extract_number('결의번호 : 20260315-0000005', P))
print(extract_number('20260414-0001', P))
print(extract_number('20260315-000005', P))
"
```
Expected:
```
20260315-0000005
20260414-0001
None
```

- [ ] **Step 7: 잘못된 정규식이 ValueError를 내는지 확인**

Run:
```bash
python3 -c "
import configparser, tempfile
from pathlib import Path
from scan_organizer import load_patterns
p = Path(tempfile.mkdtemp()) / 'config.ini'
p.write_text('[결의번호]\n라벨패턴 = (((\n', encoding='utf-8')
try:
    load_patterns(p)
    print('실패: 예외가 발생하지 않음')
except ValueError as e:
    print('통과:', e)
"
```
Expected: `통과: 라벨패턴이 올바른 정규식이 아닙니다: ...`

- [ ] **Step 8: 커밋**

```bash
git add scan_organizer.py config.ini test_scan_organizer.py
git commit -m "$(cat <<'EOF'
결의번호 추출 로직과 설정 파일 로딩 구현

7자리를 4자리보다 먼저 시도하고 (?!\d) 경계를 붙여 오인식을 막는다.
정규식은 config.ini에서 코드 수정 없이 변경 가능하다.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: PDF 첫 페이지 텍스트 읽기

100페이지 PDF도 첫 장만 읽어 성능을 유지한다(NFR-01). 손상된 PDF가 전체 처리를 멈추지 않도록 예외를 이 층에서 정리해 올린다.

**Files:**
- Modify: `scan_organizer.py` (함수 추가)
- Test: `test_scan_organizer.py` (테스트 추가)

**Interfaces:**
- Consumes: Task 1의 `scan_organizer` 모듈
- Produces:
  - `read_first_page(path: Path) -> str` — 첫 페이지 텍스트. 읽기 실패 시 `PdfReadError` 발생
  - `class PdfReadError(Exception)` — PDF 손상·암호화·읽기 불가

---

- [ ] **Step 1: 실패하는 테스트 작성**

`test_scan_organizer.py`의 `import` 줄을 아래로 교체한다.

```python
"""scan_organizer 추출 로직 검증. 실행: python test_scan_organizer.py"""

import tempfile
from pathlib import Path

from scan_organizer import (
    PdfReadError,
    extract_number,
    load_patterns,
    normalize,
    read_first_page,
)
```

그리고 `if __name__ == "__main__":` 블록 **앞에** 다음 테스트를 추가한다.

```python
def test_손상된_pdf는_예외():
    임시 = Path(tempfile.mkdtemp()) / "깨진.pdf"
    임시.write_bytes(b"이건 PDF가 아닙니다")
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
```

- [ ] **Step 2: 테스트를 실행해 실패를 확인**

Run: `python3 test_scan_organizer.py`
Expected: FAIL — `ImportError: cannot import name 'PdfReadError' from 'scan_organizer'`

- [ ] **Step 3: 최소 구현 작성**

`scan_organizer.py`의 import 블록에 `from pypdf import PdfReader`를 추가하고, `extract_number` 함수 **뒤에** 다음을 추가한다.

```python
class PdfReadError(Exception):
    """PDF를 읽을 수 없을 때 (손상·암호화·파일 없음 등)."""


def read_first_page(path: Path) -> str:
    """PDF의 첫 페이지 텍스트만 읽는다.

    전체 페이지를 로드하지 않으므로 100페이지 문서도 1페이지 문서와
    같은 속도로 처리된다. 읽기에 실패하면 PdfReadError를 올린다.
    """
    try:
        reader = PdfReader(str(path))
        if not reader.pages:
            return ""
        return reader.pages[0].extract_text() or ""
    except PdfReadError:
        raise
    except Exception as e:
        raise PdfReadError(f"{type(e).__name__}: {e}") from e
```

import 블록은 다음과 같이 된다.

```python
import configparser
import re
from pathlib import Path

from pypdf import PdfReader
```

- [ ] **Step 4: 테스트를 실행해 통과를 확인**

Run: `python3 test_scan_organizer.py`
Expected: PASS — `11개 모두 통과`

- [ ] **Step 5: 정상 PDF에서 텍스트가 나오는지 확인**

pypdf로 텍스트가 든 PDF를 즉석에서 만들어 왕복 검증한다.

Run:
```bash
python3 -c "
import tempfile, zlib
from pathlib import Path
from scan_organizer import read_first_page

# 텍스트 레이어가 있는 최소 PDF를 직접 만든다
내용 = b'BT /F1 12 Tf 72 720 Td (Gyului 20260315-0000005) Tj ET'
objs = [
    b'<< /Type /Catalog /Pages 2 0 R >>',
    b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
    b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>',
    b'<< /Length ' + str(len(내용)).encode() + b' >>\nstream\n' + 내용 + b'\nendstream',
    b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
]
out = bytearray(b'%PDF-1.4\n')
offsets = []
for i, o in enumerate(objs, 1):
    offsets.append(len(out))
    out += str(i).encode() + b' 0 obj\n' + o + b'\nendobj\n'
xref = len(out)
out += b'xref\n0 ' + str(len(objs)+1).encode() + b'\n0000000000 65535 f \n'
for off in offsets:
    out += ('%010d 00000 n \n' % off).encode()
out += b'trailer\n<< /Size ' + str(len(objs)+1).encode() + b' /Root 1 0 R >>\nstartxref\n' + str(xref).encode() + b'\n%%EOF\n'

p = Path(tempfile.mkdtemp()) / 'sample.pdf'
p.write_bytes(bytes(out))
텍스트 = read_first_page(p)
print(repr(텍스트))
assert '20260315-0000005' in 텍스트, '텍스트 추출 실패'
print('통과')
"
```
Expected: 추출된 텍스트가 출력되고 마지막 줄에 `통과`

- [ ] **Step 6: 커밋**

```bash
git add scan_organizer.py test_scan_organizer.py
git commit -m "$(cat <<'EOF'
PDF 첫 페이지 텍스트 읽기 구현

첫 페이지만 로드해 대용량 PDF에서도 성능을 유지한다.
읽기 실패는 PdfReadError로 정리해, 호출부가 파일 단위로 격리할 수 있게 한다.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: 이름 변경 계획 수립 (파일 미변경)

**이 태스크가 설계의 핵심이다.** `plan_renames`는 파일을 절대 건드리지 않는다. 오직 "무엇을 무엇으로 바꿀 것인가"를 계산해서 돌려준다. 그래야 GUI가 사용자에게 미리 보여주고 승인받을 수 있다.

정렬(수정 시각 오름차순 = 스캔된 순서), 중복 접미어 부여, 미인식 판정이 모두 여기서 일어난다.

**Files:**
- Modify: `scan_organizer.py` (함수·데이터클래스 추가)
- Test: `test_scan_organizer.py` (테스트 추가)

**Interfaces:**
- Consumes: Task 1의 `extract_number`, Task 2의 `read_first_page` / `PdfReadError`
- Produces:
  - `@dataclass RenamePlan` — 필드: `path: Path`, `mtime: float`, `number: str | None`, `new_name: str | None`, `status: str`, `reason: str`
  - `status` 값은 `"정상"` / `"중복"` / `"미인식"` 세 가지뿐
  - `sanitize(name: str) -> str`
  - `plan_renames(paths: list[Path], patterns: list[re.Pattern]) -> list[RenamePlan]`

---

- [ ] **Step 1: 실패하는 테스트 작성**

`test_scan_organizer.py`의 import 블록에 `plan_renames`, `sanitize`, `RenamePlan`을 추가하고, `if __name__` 블록 앞에 다음을 추가한다.

```python
def _가짜_pdf들(작업폴더: Path, 항목: list[tuple[str, str]]) -> list[Path]:
    """(파일명, 첫페이지텍스트) 목록을 받아 read_first_page가 읽을 수 있는
    가짜 파일을 만든다. 본문은 Task 4에서 monkeypatch로 대체한다."""
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

    # 파일을 만든 순서대로 mtime을 벌렸으므로 그 순서 그대로여야 한다
    assert [c.path.name for c in 계획] == ["Scan_0009.pdf", "Scan_0007.pdf", "Scan_0008.pdf"]
    # 문서 안 번호는 순서와 무관하게 각자 정확해야 한다
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
    (폴더 / "20260315-0000005.pdf").write_bytes(b"이미 있던 파일")
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
```

- [ ] **Step 2: 테스트를 실행해 실패를 확인**

Run: `python3 test_scan_organizer.py`
Expected: FAIL — `ImportError: cannot import name 'plan_renames' from 'scan_organizer'`

- [ ] **Step 3: 최소 구현 작성**

`scan_organizer.py`의 import 블록에 `from dataclasses import dataclass`를 추가하고, `read_first_page` **뒤에** 다음을 추가한다.

```python
FORBIDDEN = r'\/:*?"<>|'
TEXT_PREVIEW = 200  # 미인식 사유에 남길 추출 텍스트 길이


def sanitize(name: str) -> str:
    """Windows 파일명에 쓸 수 없는 문자를 -로 바꾼다.

    결의번호 형식상 발생 가능성은 낮으나 방어적으로 적용한다.
    """
    for ch in FORBIDDEN:
        name = name.replace(ch, "-")
    return name


@dataclass
class RenamePlan:
    """파일 한 건의 처리 계획. 아직 아무것도 실행되지 않은 상태."""

    path: Path          # 원본 경로
    mtime: float        # 파일 수정 시각 (정렬 기준 = 스캔된 순서)
    number: str | None  # 인식된 결의번호
    new_name: str | None  # 바꿀 파일명. 미인식이면 None
    status: str         # "정상" | "중복" | "미인식"
    reason: str         # 미인식 사유 또는 중복 안내


def plan_renames(paths: list[Path], patterns: list[re.Pattern]) -> list[RenamePlan]:
    """파일 목록을 받아 이름 변경 계획을 세운다. 파일은 건드리지 않는다.

    수정 시각 오름차순(= 스캔된 순서)으로 정렬한 뒤, 각 PDF의 첫 페이지에서
    결의번호를 찾는다. 정렬은 표시·처리 순서에만 영향을 주며, 파일명은
    각 문서 안에 적힌 번호에서 나온다.

    개별 파일의 오류는 그 파일만 "미인식"으로 처리하고 나머지는 계속한다.
    """
    대상 = sorted(paths, key=lambda p: p.stat().st_mtime)

    # 이미 쓰이고 있는 이름들. 이번에 이름을 바꿀 파일 자신은 제외해야
    # 자기 자신과 충돌한 것으로 오해하지 않는다.
    처리중 = {p.name for p in 대상}
    사용중: set[str] = set()
    for p in 대상:
        for 기존 in p.parent.iterdir():
            if 기존.name not in 처리중:
                사용중.add(기존.name)

    계획: list[RenamePlan] = []
    for p in 대상:
        mtime = p.stat().st_mtime
        try:
            텍스트 = read_first_page(p)
        except PdfReadError as e:
            계획.append(RenamePlan(p, mtime, None, None, "미인식", f"PDF 읽기 오류 - {e}"))
            continue

        번호 = extract_number(텍스트, patterns)
        if 번호 is None:
            미리보기 = normalize(텍스트)[:TEXT_PREVIEW]
            사유 = "텍스트 없음" if not 미리보기 else f"결의번호 미인식 | 추출텍스트: {미리보기}"
            계획.append(RenamePlan(p, mtime, None, None, "미인식", 사유))
            continue

        기본 = sanitize(번호)
        후보 = f"{기본}.pdf"
        n = 1
        while 후보 in 사용중:
            n += 1
            후보 = f"{기본}_{n}.pdf"
        사용중.add(후보)

        상태 = "정상" if n == 1 else "중복"
        사유 = "" if n == 1 else f"같은 번호가 이미 있어 _{n} 부여"
        계획.append(RenamePlan(p, mtime, 번호, 후보, 상태, 사유))

    return 계획
```

import 블록은 다음과 같이 된다.

```python
import configparser
import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader
```

- [ ] **Step 4: 테스트를 실행해 통과를 확인**

Run: `python3 test_scan_organizer.py`
Expected: PASS — `18개 모두 통과`

- [ ] **Step 5: 계획 수립이 파일을 건드리지 않았는지 확인**

`plan_renames` 호출 전후로 폴더 내용이 완전히 같아야 한다.

Run:
```bash
python3 -c "
import tempfile, os
from pathlib import Path
import scan_organizer
from scan_organizer import plan_renames, load_patterns

폴더 = Path(tempfile.mkdtemp())
for 이름 in ['Scan_0001.pdf', 'Scan_0002.pdf']:
    (폴더 / 이름).write_bytes(b'dummy')
scan_organizer.read_first_page = lambda p: '결의번호 : 20260315-0000005'

전 = sorted(f.name for f in 폴더.iterdir())
plan_renames(list(폴더.iterdir()), load_patterns())
후 = sorted(f.name for f in 폴더.iterdir())
assert 전 == 후, f'파일이 바뀌었다: {전} -> {후}'
print('통과: 계획 수립은 파일을 변경하지 않는다')
"
```
Expected: `통과: 계획 수립은 파일을 변경하지 않는다`

- [ ] **Step 6: 커밋**

```bash
git add scan_organizer.py test_scan_organizer.py
git commit -m "$(cat <<'EOF'
이름 변경 계획 수립 구현

plan_renames는 파일을 건드리지 않고 계획만 돌려준다.
계획과 실행이 분리되어야 사용자 사전 확인 화면이 성립한다.
수정 시각 오름차순 정렬, 중복 접미어, 미인식 판정을 포함한다.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: 이름 변경 실행 + 로그 기록

계획을 받아 실제로 이름을 바꾸고 `정리기록.log`에 남긴다. 미인식 건은 손대지 않는다. 개별 실패가 나머지를 막지 않는다.

**Files:**
- Modify: `scan_organizer.py` (함수 추가)
- Test: `test_scan_organizer.py` (테스트 추가)

**Interfaces:**
- Consumes: Task 3의 `RenamePlan`
- Produces:
  - `@dataclass RenameResult` — 필드: `plan: RenamePlan`, `ok: bool`, `message: str`
  - `apply_renames(plans: list[RenamePlan], log_path: Path | None = None) -> list[RenameResult]`
  - `LOG_NAME = "정리기록.log"`

---

- [ ] **Step 1: 실패하는 테스트 작성**

import 블록에 `apply_renames`, `RenameResult`, `LOG_NAME`을 추가하고, `if __name__` 블록 앞에 다음을 추가한다.

```python
def test_실행하면_이름이_바뀐다():
    폴더 = Path(tempfile.mkdtemp())
    항목 = [
        ("Scan_0001.pdf", "결의번호 : 20260315-0000005"),
        ("Scan_0002.pdf", "결의번호 : 20260414-0001"),
    ]
    경로들 = _가짜_pdf들(폴더, 항목)
    원본 = _텍스트_주입(dict(항목))
    try:
        계획 = plan_renames(경로들, P)
    finally:
        _텍스트_복원(원본)

    결과 = apply_renames(계획)

    assert all(r.ok for r in 결과)
    남은것 = sorted(f.name for f in 폴더.iterdir() if f.suffix == ".pdf")
    assert 남은것 == ["20260315-0000005.pdf", "20260414-0001.pdf"]


def test_미인식은_손대지_않는다():
    폴더 = Path(tempfile.mkdtemp())
    항목 = [("Scan_0001.pdf", "번호가 없는 문서")]
    경로들 = _가짜_pdf들(폴더, 항목)
    원본 = _텍스트_주입(dict(항목))
    try:
        계획 = plan_renames(경로들, P)
    finally:
        _텍스트_복원(원본)

    결과 = apply_renames(계획)

    assert 결과[0].ok is False
    assert (폴더 / "Scan_0001.pdf").exists(), "원본이 그대로 남아야 한다"


def test_이미_올바른_이름은_건너뛴다():
    폴더 = Path(tempfile.mkdtemp())
    항목 = [("20260315-0000005.pdf", "결의번호 : 20260315-0000005")]
    경로들 = _가짜_pdf들(폴더, 항목)
    원본 = _텍스트_주입(dict(항목))
    try:
        계획 = plan_renames(경로들, P)
    finally:
        _텍스트_복원(원본)

    결과 = apply_renames(계획)

    assert 결과[0].ok is True
    assert (폴더 / "20260315-0000005.pdf").exists()


def test_한_건_실패해도_나머지는_처리된다():
    폴더 = Path(tempfile.mkdtemp())
    항목 = [
        ("Scan_0001.pdf", "결의번호 : 20260315-0000005"),
        ("Scan_0002.pdf", "결의번호 : 20260414-0001"),
    ]
    경로들 = _가짜_pdf들(폴더, 항목)
    원본 = _텍스트_주입(dict(항목))
    try:
        계획 = plan_renames(경로들, P)
    finally:
        _텍스트_복원(원본)

    # 첫 건의 원본을 미리 지워 rename이 실패하게 만든다
    계획[0].path.unlink()

    결과 = apply_renames(계획)

    assert 결과[0].ok is False
    assert 결과[1].ok is True, "앞 건이 실패해도 뒤 건은 처리되어야 한다"
    assert (폴더 / "20260414-0001.pdf").exists()


def test_로그가_기록된다():
    폴더 = Path(tempfile.mkdtemp())
    항목 = [
        ("Scan_0001.pdf", "결의번호 : 20260315-0000005"),
        ("Scan_0002.pdf", "번호가 없는 문서"),
    ]
    경로들 = _가짜_pdf들(폴더, 항목)
    원본 = _텍스트_주입(dict(항목))
    try:
        계획 = plan_renames(경로들, P)
    finally:
        _텍스트_복원(원본)

    apply_renames(계획)

    로그 = (폴더 / LOG_NAME).read_text(encoding="utf-8")
    assert "성공" in 로그 and "20260315-0000005.pdf" in 로그
    assert "실패" in 로그 and "Scan_0002.pdf" in 로그


def test_로그는_이어붙는다():
    폴더 = Path(tempfile.mkdtemp())
    for 회차 in range(2):
        이름 = f"Scan_{회차}.pdf"
        항목 = [(이름, f"결의번호 : 2026031{회차}-0000005")]
        경로들 = _가짜_pdf들(폴더, 항목)
        원본 = _텍스트_주입(dict(항목))
        try:
            계획 = plan_renames([경로들[0]], P)
        finally:
            _텍스트_복원(원본)
        apply_renames(계획)

    줄수 = len((폴더 / LOG_NAME).read_text(encoding="utf-8").strip().splitlines())
    assert 줄수 == 2, f"두 번 실행하면 2줄이어야 하는데 {줄수}줄"
```

- [ ] **Step 2: 테스트를 실행해 실패를 확인**

Run: `python3 test_scan_organizer.py`
Expected: FAIL — `ImportError: cannot import name 'apply_renames' from 'scan_organizer'`

- [ ] **Step 3: 최소 구현 작성**

`scan_organizer.py`의 import 블록에 `from datetime import datetime`을 추가하고, `plan_renames` **뒤에** 다음을 추가한다.

```python
LOG_NAME = "정리기록.log"


@dataclass
class RenameResult:
    """실행 결과 한 건."""

    plan: RenamePlan
    ok: bool
    message: str


def apply_renames(plans: list[RenamePlan], log_path: Path | None = None) -> list[RenameResult]:
    """계획대로 이름을 바꾸고 로그를 남긴다.

    미인식 건은 손대지 않고 실패로 기록한다. 개별 파일의 실패가 나머지
    처리를 막지 않는다. 파일을 삭제하거나 이동하지 않는다.

    log_path를 주지 않으면 첫 파일과 같은 폴더에 정리기록.log를 만든다.
    """
    if not plans:
        return []

    if log_path is None:
        log_path = plans[0].path.parent / LOG_NAME

    결과: list[RenameResult] = []
    줄들: list[str] = []
    시각 = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for c in plans:
        if c.new_name is None:
            결과.append(RenameResult(c, False, c.reason))
            줄들.append(f"{시각}  실패  {c.path.name}  (사유: {c.reason})")
            continue

        대상 = c.path.parent / c.new_name
        if 대상 == c.path:
            결과.append(RenameResult(c, True, "이미 올바른 이름"))
            줄들.append(f"{시각}  성공  {c.path.name}  ->  {c.new_name}  (변경 없음)")
            continue

        try:
            c.path.rename(대상)
        except OSError as e:
            사유 = f"이름 변경 실패 - {type(e).__name__}: {e}"
            결과.append(RenameResult(c, False, 사유))
            줄들.append(f"{시각}  실패  {c.path.name}  (사유: {사유})")
            continue

        꼬리 = f"  ({c.reason})" if c.reason else ""
        결과.append(RenameResult(c, True, ""))
        줄들.append(f"{시각}  성공  {c.path.name}  ->  {c.new_name}{꼬리}")

    try:
        with log_path.open("a", encoding="utf-8") as f:
            f.write("\n".join(줄들) + "\n")
    except OSError:
        pass  # 로그를 못 써도 이름 변경 결과는 유지한다

    return 결과
```

import 블록은 다음과 같이 된다.

```python
import configparser
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pypdf import PdfReader
```

- [ ] **Step 4: 테스트를 실행해 통과를 확인**

Run: `python3 test_scan_organizer.py`
Expected: PASS — `24개 모두 통과`

- [ ] **Step 5: 덮어쓰기가 일어나지 않는지 확인**

기존 파일의 내용이 보존되어야 한다.

Run:
```bash
python3 -c "
import tempfile
from pathlib import Path
import scan_organizer
from scan_organizer import plan_renames, apply_renames, load_patterns

폴더 = Path(tempfile.mkdtemp())
(폴더 / '20260315-0000005.pdf').write_bytes(b'ORIGINAL')
새파일 = 폴더 / 'Scan_0001.pdf'
새파일.write_bytes(b'NEW')
scan_organizer.read_first_page = lambda p: '결의번호 : 20260315-0000005'

apply_renames(plan_renames([새파일], load_patterns()))

assert (폴더 / '20260315-0000005.pdf').read_bytes() == b'ORIGINAL', '덮어써졌다!'
assert (폴더 / '20260315-0000005_2.pdf').read_bytes() == b'NEW'
print('통과: 기존 파일이 보존되고 _2가 부여됨')
"
```
Expected: `통과: 기존 파일이 보존되고 _2가 부여됨`

- [ ] **Step 6: 커밋**

```bash
git add scan_organizer.py test_scan_organizer.py
git commit -m "$(cat <<'EOF'
이름 변경 실행과 로그 기록 구현

미인식 건은 손대지 않고, 개별 실패가 나머지를 막지 않는다.
로그는 대상 폴더의 정리기록.log에 UTF-8로 이어붙인다.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: GUI

파일 선택 → 목록 확인 → 실행. tkinter 표준 위젯만 쓴다. 로직은 Task 1~4의 함수를 호출할 뿐, GUI 안에 판단 로직을 넣지 않는다.

**Files:**
- Modify: `scan_organizer.py` (GUI 클래스와 `main()` 추가)

**Interfaces:**
- Consumes: `load_patterns`, `plan_renames`, `apply_renames`, `RenamePlan`, `RenameResult`
- Produces: `main() -> None` — 프로그램 진입점

---

- [ ] **Step 1: GUI 코드 작성**

`scan_organizer.py` 맨 끝에 다음을 추가한다.

```python
# ---------------------------------------------------------------- 화면

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

APP_TITLE = "스캔 결의서 파일명 변경"
COLUMNS = ("수정시각", "원본", "인식된 번호", "새 이름", "상태")


class App(tk.Tk):
    """파일 선택 → 결과 확인 → 이름 변경 실행 순서로 진행하는 창."""

    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("980x520")
        self.plans: list[RenamePlan] = []

        상단 = tk.Frame(self, padx=10, pady=8)
        상단.pack(fill="x")

        self.btn_select = tk.Button(상단, text="파일 선택", width=14, command=self.on_select)
        self.btn_select.pack(side="left")

        self.btn_apply = tk.Button(
            상단, text="이름 변경 실행", width=16, state="disabled", command=self.on_apply
        )
        self.btn_apply.pack(side="left", padx=(8, 0))

        self.lbl_status = tk.Label(상단, text="PDF 파일을 선택하세요.", anchor="w")
        self.lbl_status.pack(side="left", padx=(16, 0))

        self.tree = ttk.Treeview(self, columns=COLUMNS, show="headings")
        for 열, 폭 in zip(COLUMNS, (140, 220, 190, 230, 90)):
            self.tree.heading(열, text=열)
            self.tree.column(열, width=폭, anchor="w")
        self.tree.tag_configure("미인식", foreground="#c00000")
        self.tree.tag_configure("중복", foreground="#b06000")

        스크롤 = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=스크롤.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=(0, 10))
        스크롤.pack(side="right", fill="y", padx=(0, 10), pady=(0, 10))

        try:
            self.patterns = load_patterns(Path(__file__).parent / "config.ini")
        except ValueError as e:
            messagebox.showerror("설정 오류", f"{e}\n\n기본 규칙으로 실행합니다.")
            self.patterns = load_patterns(None)

    def on_select(self):
        """PDF를 고르고 계획을 세워 목록에 표시한다. 파일은 아직 바뀌지 않는다."""
        선택 = filedialog.askopenfilenames(
            title="이름을 바꿀 PDF를 선택하세요", filetypes=[("PDF 파일", "*.pdf")]
        )
        if not 선택:
            return

        경로들 = [Path(s) for s in 선택 if Path(s).suffix.lower() == ".pdf"]
        if not 경로들:
            messagebox.showinfo(APP_TITLE, "선택된 PDF가 없습니다.")
            return

        self.config(cursor="watch")
        self.update()
        try:
            self.plans = plan_renames(경로들, self.patterns)
        finally:
            self.config(cursor="")

        self.tree.delete(*self.tree.get_children())
        for c in self.plans:
            시각 = datetime.fromtimestamp(c.mtime).strftime("%Y-%m-%d %H:%M")
            self.tree.insert(
                "",
                "end",
                values=(시각, c.path.name, c.number or "(없음)", c.new_name or "—", c.status),
                tags=(c.status,),
            )

        바꿀것 = sum(1 for c in self.plans if c.new_name)
        미인식 = len(self.plans) - 바꿀것
        self.lbl_status.config(
            text=f"총 {len(self.plans)}건 · 변경 대상 {바꿀것}건 · 미인식 {미인식}건"
            + ("  (미인식 파일은 그대로 둡니다)" if 미인식 else "")
        )
        self.btn_apply.config(state="normal" if 바꿀것 else "disabled")

    def on_apply(self):
        """확인을 받은 뒤 실제로 이름을 바꾼다."""
        바꿀것 = sum(1 for c in self.plans if c.new_name)
        if not messagebox.askyesno(APP_TITLE, f"{바꿀것}건의 파일명을 변경합니다. 진행할까요?"):
            return

        결과 = apply_renames(self.plans)
        성공 = sum(1 for r in 결과 if r.ok)
        실패 = len(결과) - 성공
        로그 = self.plans[0].path.parent / LOG_NAME

        messagebox.showinfo(
            APP_TITLE,
            f"완료되었습니다.\n\n성공 {성공}건\n미변경·실패 {실패}건\n\n기록: {로그}",
        )

        self.tree.delete(*self.tree.get_children())
        self.plans = []
        self.btn_apply.config(state="disabled")
        self.lbl_status.config(text=f"완료: 성공 {성공}건, 미변경·실패 {실패}건")


def main() -> None:
    """프로그램 진입점."""
    App().mainloop()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 기존 테스트가 여전히 통과하는지 확인**

GUI 추가가 로직을 깨지 않았는지 본다.

Run: `python3 test_scan_organizer.py`
Expected: PASS — `24개 모두 통과`

- [ ] **Step 3: 모듈이 GUI를 띄우지 않고 import되는지 확인**

`if __name__ == "__main__"` 가드가 제대로 걸려 있어야 테스트가 창을 띄우지 않는다.

Run: `python3 -c "import scan_organizer; print('import OK, 창 안 뜸')"`
Expected: `import OK, 창 안 뜸`

- [ ] **Step 4: 창이 실제로 뜨는지 눈으로 확인**

Run: `python3 scan_organizer.py`

Expected: 창이 열리고 "파일 선택" / "이름 변경 실행"(비활성) 버튼과 5개 열 헤더가 보인다. PDF 몇 개를 골라 목록이 채워지는지, 미인식 행이 빨간색인지 확인한 뒤 창을 닫는다.

- [ ] **Step 5: 커밋**

```bash
git add scan_organizer.py
git commit -m "$(cat <<'EOF'
tkinter GUI 구현

파일 선택 → 목록 확인 → 실행 순서. 판단 로직은 모두 하위 함수에 있고
GUI는 호출과 표시만 담당한다. 미인식은 빨강, 중복은 주황으로 구분한다.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: 배포물 (실행 배치파일, README)

비개발자가 설치하고 쓸 수 있게 만든다. 설치 3단계 이내(NFR-04).

**Files:**
- Create: `스캔정리_실행.bat`
- Create: `README.md`

**Interfaces:**
- Consumes: Task 5의 `scan_organizer.py`
- Produces: 없음 (최종 산출물)

---

- [ ] **Step 1: 배치파일 작성**

`스캔정리_실행.bat`를 만든다. Windows 한글 환경에서 깨지지 않도록 `chcp 65001`로 UTF-8을 켠다.

```bat
@echo off
chcp 65001 > nul
cd /d "%~dp0"

python --version > nul 2>&1
if errorlevel 1 (
    echo Python이 설치되어 있지 않습니다.
    echo https://www.python.org 에서 설치한 뒤 다시 실행하세요.
    echo 설치할 때 "Add Python to PATH" 를 반드시 체크하세요.
    pause
    exit /b 1
)

python -c "import pypdf" > nul 2>&1
if errorlevel 1 (
    echo 처음 실행입니다. 필요한 부품을 설치합니다. 잠시 기다려 주세요.
    python -m pip install pypdf
    if errorlevel 1 (
        echo 설치에 실패했습니다. 인터넷 연결을 확인하세요.
        pause
        exit /b 1
    )
)

python scan_organizer.py
if errorlevel 1 pause
```

- [ ] **Step 2: 배치파일이 UTF-8로 저장됐는지 확인**

Run: `file 스캔정리_실행.bat && head -3 스캔정리_실행.bat`
Expected: 인코딩이 UTF-8로 표시되고 한글이 깨지지 않는다.

- [ ] **Step 3: README 작성**

`README.md`를 만든다.

```markdown
# 스캔 결의서 파일명 자동 변경

스캔한 결의서 PDF의 첫 페이지에서 결의번호를 읽어, 그 번호로 파일명을 바꿉니다.
**바꾸기 전에 결과를 보여드리니 확인한 뒤 실행하세요.**

파일을 지우거나 다른 폴더로 옮기지 않습니다. 이름만 바꿉니다.

## 설치 (처음 한 번만)

1. [python.org](https://www.python.org) 에서 Python을 설치합니다.
   설치 화면에서 **"Add Python to PATH"** 를 반드시 체크하세요.
2. `스캔정리_실행.bat` 을 더블클릭합니다.
   처음 실행할 때 필요한 부품을 자동으로 설치합니다 (인터넷 필요, 1분 정도).

## 사용법

1. `스캔정리_실행.bat` 을 더블클릭합니다.
2. **파일 선택** 을 눌러 스캔 폴더에서 이름을 바꿀 PDF들을 고릅니다.
   (Ctrl 또는 Shift로 여러 개 선택)
3. 목록에서 결과를 확인합니다.

   | 상태 | 색 | 뜻 |
   |---|---|---|
   | 정상 | 검정 | 결의번호를 찾았습니다. 이 이름으로 바뀝니다 |
   | 중복 | 주황 | 같은 번호가 이미 있어 `_2`, `_3` 이 붙습니다 |
   | 미인식 | 빨강 | 번호를 못 찾았습니다. **이 파일은 그대로 둡니다** |

4. 결과가 맞으면 **이름 변경 실행** 을 누릅니다.
5. 보관 폴더 정리는 직접 하시면 됩니다.

목록은 파일 수정 시각 순서, 즉 **스캔한 순서대로** 표시됩니다.

## 결과 기록

파일을 고른 폴더에 `정리기록.log` 가 만들어집니다. 메모장으로 열 수 있습니다.

```
2026-09-07 10:32:15  성공  Scan_0007.pdf  ->  20260315-0000012.pdf
2026-09-07 10:32:15  실패  Scan_0009.pdf  (사유: 결의번호 미인식 | 추출텍스트: 지출결의서 2026학년도 ...)
```

## 문제가 생겼을 때

### 전부 "미인식"으로 나옵니다

두 가지 원인이 있습니다.

**1. PDF에 텍스트가 없는 경우** — 로그에 `텍스트 없음` 이라고 적힙니다.
PDF를 열어 결의번호 위에서 마우스로 드래그해 보세요. 글자가 선택되지 않으면
스캐너의 OCR(문자 인식) 기능이 꺼져 있는 것입니다. 스캐너 설정에서 켜야 합니다.

**2. 번호 형식이 다른 경우** — 로그의 `추출텍스트:` 뒤를 보면 실제로 어떤 글자가
읽혔는지 나옵니다. 여기에 결의번호가 보이는데도 인식이 안 된다면 아래를 고칩니다.

### 인식 규칙 바꾸기

`config.ini` 를 메모장으로 열면 규칙이 있습니다. 파일 안에 설명이 적혀 있습니다.
고친 뒤 프로그램을 껐다 켜면 반영됩니다.

기본 규칙은 `20260315-0000005` (뒤 7자리) 와 `20260414-0001` (뒤 4자리) 두 가지를
인식합니다. 5자리나 6자리는 일부러 인식하지 않습니다 — 다른 숫자를 잘못 집는 것을
막기 위해서입니다.

### 잘못 바뀐 파일을 되돌리고 싶습니다

`정리기록.log` 에 `원래이름 -> 바뀐이름` 이 전부 남아 있습니다.
파일을 지우지 않으므로 이름만 되돌리면 됩니다.

## 개발자용

```bash
python test_scan_organizer.py
```

설계 문서: `docs/superpowers/specs/2026-09-07-scan-organizer-design.md`
```

- [ ] **Step 4: README의 링크와 파일명이 실제와 맞는지 확인**

Run: `ls -1 && ls docs/superpowers/specs/`
Expected: `scan_organizer.py`, `config.ini`, `스캔정리_실행.bat`, `README.md`, `test_scan_organizer.py`가 있고 설계 문서 경로가 맞다.

- [ ] **Step 5: 전체 테스트 최종 확인**

Run: `python3 test_scan_organizer.py`
Expected: PASS — `24개 모두 통과`

- [ ] **Step 6: 커밋**

```bash
git add 스캔정리_실행.bat README.md
git commit -m "$(cat <<'EOF'
실행 배치파일과 한글 사용자 안내서 추가

배치파일이 Python과 pypdf 설치 여부를 확인해 비개발자도 더블클릭으로
실행할 수 있게 한다. README에 미인식 원인별 대처법을 넣었다.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Windows 실기 검수

개발은 macOS에서 하지만 **최종 검증은 실제 Windows 업무용 PC에서 해야 한다.**
설계서 11.2의 항목이며, 실제 스캔 PDF로 수행한다.

| ID | 시나리오 | 기대 결과 |
|---|---|---|
| T-01 | 정상 결의서 여러 건 선택 | 각 결의번호로 이름 변경, 로그 성공 기록 |
| T-02 | 결의번호 없는 문서 포함 | 해당 건만 빨강 표시, 이름 그대로 유지 |
| T-03 | 같은 결의번호 2건 | 두 번째에 `_2`, 첫 파일 내용 보존 |
| T-04 | 100페이지 이상 PDF | 3초 이내 처리 |
| T-05 | 손상된 PDF 포함 | 프로그램 중단 없이 나머지 처리 완료 |
| T-06 | `config.ini` 정규식만 변경 | 코드 수정 없이 새 형식 인식 |
| T-07 | 한글 경로 (`C:\결의서\2026학년도\`) | 파일명·로그 깨짐 없음 |
| T-08 | 정렬 순서 | 수정 시각 오름차순으로 표시 |
| T-09 | 잘못된 정규식 입력 | 오류 안내 후 기본 규칙으로 계속 동작 |

**통과 기준:** T-01 ~ T-09 전부 통과, 실제 스캔 문서 30건 이상 시범 운영에서 파일 손실 0건.

### 실기 검수 전 확인할 것

설계서 12장의 미확정 사항이다. 실제 샘플이 없어 정규식은 구술 형식에만 근거한다.

1. **첫 실행은 복사본 폴더에서 한다.** 원본 스캔 폴더에 바로 돌리지 않는다.
2. 미인식이 나오면 `정리기록.log` 의 `추출텍스트:` 를 본다. 여기에 결의번호가
   어떤 모양으로 읽혔는지 그대로 나온다.
3. 특히 확인할 것: 라벨 표기(`결의번호` / `문서번호` / `지출결의번호`),
   하이픈이 다른 문자로 추출되는지(`‐`, `–`, 공백), 표 안에 있을 때 셀 경계가
   어떻게 나타나는지.
4. 필요하면 `config.ini` 의 정규식을 고친다. 코드는 건드리지 않는다.
