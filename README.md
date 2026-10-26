# law_pdf_parser — 국방 법령 PDF 구조화 파서

> 졸업논문 「Graph Embedding을 활용한 온톨로지 기반 의미 관계 검색 최적화」 **Part 1 · 데이터셋 구축 (RQ1)** 의 첫 단계
> 국가법령정보센터에서 내려받은 국방·방위사업 법령 PDF 41건을 메타데이터와 조문 단위 JSON으로 바꿉니다.

## 1. 개요

| 항목 | 내용 |
|---|---|
| 입력 | 국가법령정보센터 법령 PDF 41건 (법률 2, 시행령 3, 시행규칙 5, 훈령·규정 31) |
| 출력 | 문서별 JSON (메타데이터 + 조문 + 부칙), 파싱 품질 리포트 |
| 핵심 기술 | `pypdf` 텍스트 추출, 정규식 기반 메타·조문 분할, 법령종류 → OWL 클래스 정규화 |
| 처리 시간 | 41건 약 11초 (CPU) |

이 파서의 출력은 [law_triple_extraction](https://github.com/Ikuuuu/law_triple_extraction)에서 트리플(지식그래프)로 바뀝니다.

## 2. 처리 흐름

```
PDF ──► ① 파일명 파싱 ──► ② 본문 메타 파싱 ──► ③ 본문/부칙 분리 ──► ④ 조문 분할 ──► JSON
        제목·종류·공포번호   [시행 …][법률 제N호,   "부 칙" 헤더        "제N조(제목)"
        시행일·발령기관      공포일, 개정구분]                          "제N조의M(제목)"
                             약칭, 소관부처
```

법령종류 문자열은 온톨로지 클래스로 바꿉니다.

| 원문 | 클래스 |
|---|---|
| 법률 | `Law` |
| 대통령령 | `EnforcementOrdinance` |
| 총리령·부령·국방부령 | `EnforcementRule` |
| 훈령·방위사업청훈령·국방부훈령 | `AdministrativeOrder` |
| 공동훈령 | `JointAdministrativeOrder` |

## 3. 폴더 구조

```
law_pdf_parser/
├── lawparser/
│   ├── __init__.py
│   └── pdf_parser.py      # 파서 본체 (LawDocument, parse_pdf, parse_directory)
├── scripts/
│   └── parse_pdfs.py      # 실행 스크립트 (JSON + 품질 리포트 생성)
├── tests/
│   └── test_parser.py     # 단위 테스트 7개 (PDF 없이 문자열로 검증)
├── data/
│   ├── pdf/               # 원본 법령 PDF 41건
│   └── raw/               # 파싱 결과 JSON (실행 시 재생성)
└── results/
    ├── parse_report.csv   # 문서별 조문 수·메타 추출 여부
    └── parse_summary.md   # 전체 요약
```

## 4. 설치 및 실행

```bash
# 1) 가상환경 (Windows: .venv\Scripts\activate)
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2) 파싱 실행 (data/pdf → data/raw, results/)
python scripts/parse_pdfs.py

# 3) 졸업논문 데이터셋 v1.0 과 동일한 결과가 필요할 때
python scripts/parse_pdfs.py --legacy --out data/raw_v1_0

# 4) 단위 테스트
python -m pytest -q
```

출력 JSON 예시 (`data/raw/방위사업법(법률)(제21065호)(20260102).json`)

```json
{
  "law_id": "방위사업법(법률)(제21065호)(20260102)",
  "title": "방위사업법",
  "doc_type": "Law",
  "promulgation_no": "제21065호",
  "promulgation_date": "20251001",
  "effective_date": "20260102",
  "revision_type": "타법개정",
  "jurisdiction": ["국방부", "방위사업청", "산업통상부"],
  "articles": [
    {"no": "1", "title": "목적", "text": "이 법은 자주국방의 기반을 마련하기 위한 …"}
  ]
}
```

## 5. 결과

`python scripts/parse_pdfs.py` 실행 결과 (`results/parse_summary.md`)

| 항목 | 값 |
|---|---|
| 문서 수 | 41건 |
| 조문 수 | 2,129개 (문서당 평균 51.9, 최대 246) |
| 본문 텍스트 | 1,234,368자 |
| 「」 인용 표기 | 1,367회 |
| 메타 추출률 | 시행일·공포일·제개정구분·소관부처 모두 100% |

### v1.0 → v1.1 개선 (이번 정리에서 찾아 수정한 버그 3건)

논문 데이터셋(v1.0)을 만든 파서를 다시 검토하면서 아래 문제를 찾아 고쳤습니다. 논문 결과를 재현할 수 있도록 `--legacy` 옵션으로 v1.0 동작을 그대로 남겨 두었습니다.

| # | 문제 (v1.0) | 영향 | 수정 (v1.1) |
|---|---|---|---|
| 1 | `제N조(제목)` 헤더 줄 전체를 버림 | 같은 줄의 본문, 특히 제1조 목적 조항의 「모법」 인용이 빠짐 | 헤더 뒤 텍스트를 본문에 포함 |
| 2 | `제2조의2` 형식을 `제2의2조`로 잘못 가정 | 가지조문 전체가 앞 조문과 번호가 겹쳐 버려짐 | `제N조의M` 정규식으로 수정 |
| 3 | 공포일 정규식 그룹 번호 오류 | 공포일 추출률 0% | 그룹 번호 수정 → 100% |

| 버전 | 조문 수 | 「」 인용 표기 수 | 공포일 추출률 |
|---|---|---|---|
| v1.0 (`--legacy`, 논문 데이터셋) | 1,936 | 970 | 0% |
| v1.1 (기본) | **2,129** (+193) | **1,367** (+41%) | **100%** |

`--legacy` 결과는 논문 저장소의 `data/raw/*.json` 과 공포일 필드를 빼고 41건 모두 일치합니다.

## 6. 알려진 한계

- **PDF 텍스트 추출 공백 오류** : `pypdf` 가 줄바꿈·자간 때문에 `방위사업법 시 행규칙` 처럼 단어 중간에 공백을 넣는 경우가 있습니다. 리포트의 "이상 징후"에서 개수를 확인할 수 있고, 엔티티 정규화는 [law_triple_extraction](https://github.com/Ikuuuu/law_triple_extraction)에서 처리합니다.
- **소관부처 줄바꿈 잘림** : 부처명이 줄 경계에서 잘리면 `위사업계약심의위원회` 처럼 앞 글자가 빠지는 경우가 1건 있습니다.
- 표·별표·서식은 파싱하지 않습니다.

## 7. 관련 저장소

| 순서 | 저장소 | 역할 |
|---|---|---|
| ① | **law_pdf_parser** (현재) | PDF → 구조화 JSON |
| ② | [owl_lite_schema](https://github.com/Ikuuuu/owl_lite_schema) | OWL Lite 온톨로지 스키마 |
| ③ | [law_triple_extraction](https://github.com/Ikuuuu/law_triple_extraction) | JSON → 트리플 |
| ④ | [defense_law_kg_dataset](https://github.com/Ikuuuu/defense_law_kg_dataset) | 최종 KG 데이터셋 |

---
송재익 · 충북대학교 산업인공지능학과 석사과정 (2025254013)
