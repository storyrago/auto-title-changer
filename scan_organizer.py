"""스캔된 결의서 PDF의 첫 페이지에서 결의번호를 읽어 파일명을 바꾼다."""

from __future__ import annotations

import configparser
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pypdf import PdfReader

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
