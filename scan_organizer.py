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
