"""법령 PDF 디렉토리 → 문서별 JSON + 파싱 품질 리포트.

    python scripts/parse_pdfs.py                          # data/pdf → data/raw, results/
    python scripts/parse_pdfs.py --pdf-dir <폴더> --out data/raw

산출물
  data/raw/<law_id>.json        : 문서별 구조화 결과 (메타 + 조문 + 부칙)
  results/parse_report.csv      : 문서별 조문 수·본문 길이·메타 추출 여부
  results/parse_summary.md      : 전체 요약 (법령종류 분포, 메타 추출률, 이상 징후)
"""
import argparse
import csv
import json
import re
import sys
import time
from collections import Counter
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lawparser.pdf_parser import parse_pdf  # noqa: E402

# PDF 텍스트 추출 시 단어 중간에 공백이 끼는 현상(예: "시 행규칙") 탐지용
SPLIT_SUFFIX_RE = re.compile(r"(시\s+행\s*령|시\s*행\s+령|시\s+행\s*규\s*칙|시행\s+규칙|시\s*행\s*세\s+칙)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf-dir", default="data/pdf")
    ap.add_argument("--out", default="data/raw")
    ap.add_argument("--report-dir", default="results")
    ap.add_argument("--legacy", action="store_true",
                    help="v1.0 방식(조문 헤더 줄 버림)으로 파싱 — 졸업논문 데이터셋 v1.0 재현용")
    args = ap.parse_args()

    pdf_dir, out_dir, rep_dir = ROOT / args.pdf_dir, ROOT / args.out, ROOT / args.report_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    rep_dir.mkdir(parents=True, exist_ok=True)

    rows, t0 = [], time.time()
    pdfs = sorted(pdf_dir.glob("*.pdf"))
    for i, p in enumerate(pdfs, 1):
        doc = parse_pdf(p, legacy=args.legacy)
        legacy_doc = doc if args.legacy else parse_pdf(p, legacy=True)
        d = asdict(doc)
        raw_text = d.pop("raw_text")
        (out_dir / f"{doc.law_id}.json").write_text(
            json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        n_cite = sum(a["text"].count("「") for a in doc.articles)
        n_cite_legacy = sum(a["text"].count("「") for a in legacy_doc.articles)
        rows.append({
            "law_id": doc.law_id, "title": doc.title, "doc_type": doc.doc_type,
            "doc_type_raw": doc.doc_type_raw, "effective_date": doc.effective_date,
            "promulgation_date": doc.promulgation_date or "",
            "revision_type": doc.revision_type or "", "short_title": doc.short_title or "",
            "jurisdiction": "|".join(doc.jurisdiction),
            "n_articles": len(doc.articles), "n_addenda": len(doc.addenda),
            "n_chars": len(raw_text), "n_citation_marks": n_cite, "n_citation_marks_v1_0": n_cite_legacy,
            "n_articles_v1_0": len(legacy_doc.articles),
            "split_word_hits": len(SPLIT_SUFFIX_RE.findall(raw_text)),
        })
        print(f"[{i:2d}/{len(pdfs)}] {doc.doc_type:26s} 조문 {len(doc.articles):4d}  {doc.title}")

    with (rep_dir / "parse_report.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    n = len(rows)
    rate = lambda key: sum(1 for r in rows if r[key]) / n * 100  # noqa: E731
    types = Counter(r["doc_type"] for r in rows)
    orgs = Counter(o for r in rows for o in r["jurisdiction"].split("|") if o)
    lines = [
        "# 법령 PDF 파싱 요약", "",
        f"- 문서 수 : **{n}건**  (처리 시간 {time.time() - t0:.1f}s)",
        f"- 총 조문 수 : **{sum(r['n_articles'] for r in rows):,}개** "
        f"(문서당 평균 {sum(r['n_articles'] for r in rows) / n:.1f}, 최대 {max(r['n_articles'] for r in rows)})",
        f"- 총 텍스트 : {sum(r['n_chars'] for r in rows):,}자, 「」 인용 표기 {sum(r['n_citation_marks'] for r in rows):,}회",
        "", "## 메타데이터 추출률", "",
        "| 항목 | 추출률 |", "|---|---|",
        f"| 시행일 | {rate('effective_date'):.0f}% |",
        f"| 공포일 | {rate('promulgation_date'):.0f}% |",
        f"| 제·개정 구분 | {rate('revision_type'):.0f}% |",
        f"| 소관부처 | {rate('jurisdiction'):.0f}% |",
        f"| 약칭 | {rate('short_title'):.0f}% (약칭이 있는 법령만 해당) |",
        "", "## 법령 종류 분포", "", "| 클래스 | 문서 수 |", "|---|---|",
        *[f"| {k} | {v} |" for k, v in types.most_common()],
        "", "## 소관부처 분포", "", "| 기관 | 문서 수 |", "|---|---|",
        *[f"| {k} | {v} |" for k, v in orgs.most_common()],
        "", "## 조문 헤더 줄 처리 개선 (v1.0 → v1.1)", "",
        "v1.0 파서의 두 가지 문제를 수정했다.",
        "① `제N조(제목)` 헤더 줄을 통째로 버려, 같은 줄의 본문(특히 제1조 목적 조항의 「모법」 인용)이 누락됨",
        "② `제N조의M` 가지조문을 인식하지 못해 해당 조문 전체가 앞 조문 번호와 중복 처리되어 누락됨",
        "", "| 버전 | 조문 수 | 조문 본문 내 「」 인용 표기 수 |", "|---|---|---|",
        f"| v1.0 (legacy, 졸업논문 데이터셋) | {sum(r['n_articles_v1_0'] for r in rows):,} | {sum(r['n_citation_marks_v1_0'] for r in rows):,} |",
        f"| v1.1 (현재) | {sum(r['n_articles'] for r in rows):,} | {sum(r['n_citation_marks'] for r in rows):,} |",
        "", "## 이상 징후 (후속 정규화 대상)", "",
        f"- PDF 추출 공백 분리(예: `시 행규칙`) 의심 구간 : {sum(r['split_word_hits'] for r in rows)}회 "
        f"/ {sum(1 for r in rows if r['split_word_hits'])}개 문서",
        "- 조문 0개 문서 : " + (", ".join(r["title"] for r in rows if r["n_articles"] == 0) or "없음"),
    ]
    (rep_dir / "parse_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n→ {out_dir} ({n} JSON), {rep_dir / 'parse_summary.md'}")


if __name__ == "__main__":
    main()
