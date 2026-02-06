import os
import re
import json
import argparse

from pydantic import BaseModel, conlist
from google import genai


# ----------------------------
# 1) PII 마스킹(이메일/전화번호/URL)
# ----------------------------
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
URL_RE = re.compile(r"\b(?:https?://|www\.)\S+\b", re.IGNORECASE)
PHONE_RE = re.compile(
    r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\(?0\d{1,2}\)?[-.\s]?)?\d{3,4}[-.\s]?\d{4}\b"
)

def mask_pii(text: str) -> str:
    text = EMAIL_RE.sub("[EMAIL]", text)
    text = URL_RE.sub("[URL]", text)
    text = PHONE_RE.sub("[PHONE]", text)
    return text


# ----------------------------
# 2) 입력 로드(.txt 또는 stdin)
# ----------------------------
def load_text(input_path: str | None) -> str:
    if not input_path or input_path == "-":
        import sys
        return sys.stdin.read().strip()

    with open(input_path, "r", encoding="utf-8") as f:
        return f.read().strip()


# ----------------------------
# 3) Gemini 구조화 출력 스키마 (keywords only)
# ----------------------------
class KeywordsOnlyResult(BaseModel):
    keywords: conlist(str, min_length=5, max_length=5)


def build_prompt(portfolio_text: str, target_role: str) -> str:
    return f"""
너는 채용 담당자/시니어 엔지니어 관점에서 '개발자 포트폴리오 텍스트'에서
가장 핵심적인 키워드 5개만 추출한다.

[목표 직무]
{target_role}

[출력 규칙]
- 반드시 JSON으로만 출력한다.
- JSON 형태는 정확히 다음 스키마를 따른다:
  {{ "keywords": ["키워드1","키워드2","키워드3","키워드4","키워드5"] }}
- keywords는 정확히 5개.
- 키워드는 짧고 명확한 명사구(2~6단어).
- 중복/동의어 반복 금지.
- 텍스트에 실제로 등장한 표현을 우선(추론 금지).

[선정 기준]
- 기술 스택(예: Spring Boot, PostgreSQL, AWS 등)
- 핵심 도메인/성과/문제 해결/배포 운영/협업 프로세스/기술 깊이를 대표하는 것

[포트폴리오 텍스트]
\"\"\"{portfolio_text}\"\"\"
""".strip()


def analyze_with_gemini(
    portfolio_text: str,
    target_role: str = "Backend",
    model: str = "gemini-3-flash-preview",
    max_chars: int = 35000,
) -> KeywordsOnlyResult:
    text = portfolio_text[:max_chars]

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise SystemExit(
            "API 키가 없습니다. PowerShell에서 예:\n"
            "$env:GEMINI_API_KEY=\"YOUR_KEY\" 후 다시 실행하세요."
        )

    client = genai.Client(api_key=api_key)
    prompt = build_prompt(text, target_role)

    resp = client.models.generate_content(
        model=model,
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "response_json_schema": KeywordsOnlyResult.model_json_schema(),
        },
    )

    return KeywordsOnlyResult.model_validate_json(resp.text)


def main():
    ap = argparse.ArgumentParser(description="포트폴리오 텍스트 -> Gemini로 핵심 키워드 5개만 추출(JSON)")
    ap.add_argument("input", nargs="?", default="-", help="입력 텍스트 파일(.txt). 없으면 stdin. stdin은 '-'")
    ap.add_argument("--role", default="Backend", help="목표 직무(Backend/Frontend/Mobile/Data 등)")
    ap.add_argument("--model", default="gemini-3-flash-preview", help="Gemini 모델명")
    ap.add_argument("--out", default="result.json", help="출력 파일명(result.json)")
    ap.add_argument("--no-mask", action="store_true", help="PII 마스킹 비활성화(기본은 마스킹 ON)")
    args = ap.parse_args()

    raw = load_text(args.input)
    if not raw:
        raise SystemExit("입력 텍스트가 비어 있습니다.")

    text = raw if args.no_mask else mask_pii(raw)

    result = analyze_with_gemini(
        portfolio_text=text,
        target_role=args.role,
        model=args.model,
    )

    # ✅ result.json에는 keywords 배열만 저장
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result.keywords, f, ensure_ascii=False, indent=2)

    print(f"✅ Saved: {args.out}")
    print("  keywords:", ", ".join(result.keywords))


if __name__ == "__main__":
    main()
