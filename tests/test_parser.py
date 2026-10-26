"""lawparser 단위 테스트 (PDF 없이 문자열만으로 검증).

    python -m pytest -q
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lawparser.pdf_parser import (  # noqa: E402
    normalize_doc_type, parse_articles, parse_filename, parse_metadata_block,
    split_main_and_addenda,
)

SAMPLE = """방위사업법
[시행 2026. 1. 2.] [법률 제21065호, 2025. 10. 1., 타법개정]
국방부 (방위사업정책과) 02-748-0000
방위사업청 (방위사업정책과) 02-2079-0000
제1조(목적) 이 법은 「국방과학기술혁신 촉진법」에 따라
방위산업의 경쟁력 강화를 목적으로 한다.
제2조(정의) 이 법에서 사용하는 용어의 뜻은 다음과 같다.
제2조의2(다른 법률과의 관계) 「국가를 당사자로 하는 계약에 관한 법률」 제5조에 우선한다.
부 칙
제1조(시행일) 이 법은 공포한 날부터 시행한다.
"""


def test_parse_filename():
    m = parse_filename("방위사업법 시행령(대통령령)(제36332호)(20260519).pdf")
    assert m["title"] == "방위사업법 시행령"
    assert m["doc_type_raw"] == "대통령령"
    assert m["promulgation_no"] == "제36332호"
    assert m["effective_date"] == "20260519"


def test_parse_filename_issuing_org():
    m = parse_filename("군수품조달관리규정(방위사업청훈령)(제964호)(20260413).pdf")
    assert m["issuing_org"] == "방위사업청"
    assert normalize_doc_type(m["doc_type_raw"]) == "AdministrativeOrder"


def test_normalize_doc_type():
    assert normalize_doc_type("법률") == "Law"
    assert normalize_doc_type("대통령령") == "EnforcementOrdinance"
    assert normalize_doc_type("국방부령") == "EnforcementRule"
    assert normalize_doc_type("공동훈령") == "JointAdministrativeOrder"
    assert normalize_doc_type("") == "LegalDocument"


def test_metadata_block():
    meta = parse_metadata_block(SAMPLE)
    assert meta["effective_date_meta"] == "20260102"
    assert meta["promulgation_date"] == "20251001"      # v1.1 버그 수정 항목
    assert meta["revision_type"] == "타법개정"
    assert meta["jurisdiction"] == ["국방부", "방위사업청"]


def test_split_addenda():
    main, add = split_main_and_addenda(SAMPLE)
    assert "부 칙" not in main and add.strip().startswith("부 칙")


def test_parse_articles_keeps_header_line():
    main, _ = split_main_and_addenda(SAMPLE)
    arts = parse_articles(main)
    assert [a["no"] for a in arts] == ["1", "2", "2의2"]
    assert arts[0]["title"] == "목적"
    assert "「국방과학기술혁신 촉진법」" in arts[0]["text"]          # 헤더 줄 본문 보존
    assert "「국가를 당사자로 하는 계약에 관한 법률」" in arts[2]["text"]


def test_parse_articles_legacy_drops_header_line():
    main, _ = split_main_and_addenda(SAMPLE)
    arts = parse_articles(main, legacy=True)
    assert "「국방과학기술혁신 촉진법」" not in arts[0]["text"]       # v1.0 문제 ① 재현
    assert [a["no"] for a in arts] == ["1", "2"]                     # v1.0 문제 ② 재현 (2조의2 누락)
