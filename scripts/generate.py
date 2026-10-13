#!/usr/bin/env python3
"""대기열에서 키워드를 꺼내 Claude API로 꿈해몽 페이지(JSON)를 만듭니다.

품질 기준(validate)을 통과한 글만 저장하고, 실패하면 오류를 알려주며 한 번 더 시도합니다.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

from common import (CATEGORIES, CONTENT_DIR, DRAFT_DIR, FORTUNES, add_to_queue, compact,
                    load_config, load_state, normalize_keyword, save_state, slugify, today)

API_URL = "https://api.anthropic.com/v1/messages"

SYSTEM = f"""당신은 한국 꿈해몽 사전의 전문 필자입니다. 전통 해몽 자료와 현대 심리학(프로이트, 융, 수면·기억 연구)의 관점을 구분해서, 검색으로 들어온 사람이 "내 꿈이 무슨 뜻인지" 바로 알 수 있게 씁니다.

반드시 아래 JSON 객체 하나만 출력하세요. 설명, 마크다운, 코드블록 없이 JSON만.

{{
  "keyword": "요청받은 키워드 그대로",
  "category": "{' | '.join(CATEGORIES)} 중 하나",
  "fortune": "길몽 | 흉몽 | 중립 (전체적인 경향)",
  "seo_title": "키워드를 포함한 40자 이내 제목. 예: 뱀 꿈 해몽, 물리는 꿈부터 큰 뱀까지 상황별 풀이",
  "meta_description": "80~150자. 검색 결과에 보일 요약",
  "summary": "20~70자 한 줄 풀이",
  "intro": "150~350자. 이 꿈이 대체로 무엇을 뜻하는지 결론부터",
  "situations": [
    {{"title": "구체적인 상황 꿈 (예: 뱀에게 물리는 꿈)", "fortune": "길몽 | 흉몽 | 중립", "meaning": "80~250자"}}
  ],
  "psychology": "200~450자. 심리학 관점",
  "tradition": "200~450자. 전통 해몽 관점",
  "advice": "80~250자. 이 꿈을 꾼 날 해볼 만한 일",
  "faq": [{{"q": "질문", "a": "60~200자 답"}}],
  "related": ["관련 꿈 키워드 6개, 모두 'OO 꿈' 형식"]
}}

작성 원칙
- situations는 6~8개. 사람들이 실제로 검색할 법한 구체적 변형(행동, 색, 크기, 장소, 등장인물)으로, 제목이 서로 겹치지 않게.
- faq는 3~4개.
- 결론을 먼저 말하고, 같은 표현을 반복하지 않습니다.
- 미래를 단정하는 예언, 공포를 주는 표현, 의료·투자·법률 조언은 쓰지 않습니다. 흉몽도 '조심할 점' 정도로 부드럽게.
- 반복되는 악몽이나 수면 문제가 언급될 만한 경우에만 전문가 상담을 가볍게 권합니다.
- 자연스러운 한국어 존댓말. 과장된 감탄사, 이모지 금지.
- related는 가능하면 '이미 있는 페이지' 목록에서 3개 이상 고르고, 나머지는 새로 만들 만한 꿈으로."""


def call_claude(api_key: str, model: str, messages: list) -> str:
    body = json.dumps({"model": model, "max_tokens": 6000, "system": SYSTEM, "messages": messages}).encode()
    req = urllib.request.Request(API_URL, data=body, method="POST", headers={
        "x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                data = json.loads(r.read())
            return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:300]
            if e.code in (429, 500, 502, 503, 529) and attempt < 3:
                wait = 20 * (attempt + 1)
                print(f"  API {e.code}, {wait}초 후 재시도")
                time.sleep(wait)
                continue
            raise RuntimeError(f"API 오류 {e.code}: {detail}") from e
    raise RuntimeError("API 재시도 초과")


def parse_json(text: str) -> dict:
    text = re.sub(r"```(?:json)?", "", text).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("JSON 객체를 찾지 못함")
    return json.loads(text[start:end + 1])


def length_ok(errors, name, value, lo, hi):
    n = len(value) if isinstance(value, str) else 0
    if not lo <= n <= hi:
        errors.append(f"{name} 길이 {n}자 (기준 {lo}~{hi}자)")


def validate(d: dict, keyword: str) -> list:
    """품질 기준. 통과하지 못하면 오류 목록을 돌려줍니다."""
    errors = []
    if compact(keyword) not in compact(d.get("seo_title", "")):
        errors.append("seo_title에 키워드가 없음")
    length_ok(errors, "seo_title", d.get("seo_title"), 8, 45)
    length_ok(errors, "meta_description", d.get("meta_description"), 60, 170)
    length_ok(errors, "summary", d.get("summary"), 15, 80)
    length_ok(errors, "intro", d.get("intro"), 130, 420)
    length_ok(errors, "psychology", d.get("psychology"), 180, 520)
    length_ok(errors, "tradition", d.get("tradition"), 180, 520)
    length_ok(errors, "advice", d.get("advice"), 70, 300)
    if d.get("fortune") not in FORTUNES:
        errors.append("fortune 값이 올바르지 않음")

    sits = d.get("situations") or []
    if not 5 <= len(sits) <= 10:
        errors.append(f"situations {len(sits)}개 (기준 6~8개)")
    titles = set()
    for i, s in enumerate(sits):
        if not isinstance(s, dict):
            errors.append(f"situations[{i}] 형식 오류")
            continue
        length_ok(errors, f"situations[{i}].meaning", s.get("meaning"), 70, 300)
        if s.get("fortune") not in FORTUNES:
            s["fortune"] = "중립"
        t = compact(s.get("title", ""))
        if not t or t in titles:
            errors.append(f"situations[{i}] 제목이 비었거나 중복")
        titles.add(t)

    faq = d.get("faq") or []
    if not 3 <= len(faq) <= 5:
        errors.append(f"faq {len(faq)}개 (기준 3~4개)")
    for i, f in enumerate(faq):
        if not isinstance(f, dict) or not f.get("q"):
            errors.append(f"faq[{i}] 형식 오류")
        else:
            length_ok(errors, f"faq[{i}].a", f.get("a"), 40, 260)

    total = sum(len(str(d.get(k, ""))) for k in ("intro", "psychology", "tradition", "advice"))
    total += sum(len(s.get("meaning", "")) for s in sits if isinstance(s, dict))
    if total < 1300:
        errors.append(f"본문 전체 {total}자 (최소 1300자)")
    return errors


def build_record(d: dict, keyword: str, category: str) -> dict:
    cat = d.get("category") if d.get("category") in CATEGORIES else category
    related = []
    for r in d.get("related", []):
        k = normalize_keyword(r)
        if k and compact(k) != compact(keyword) and k not in related:
            related.append(k)
    return {
        "keyword": keyword,
        "slug": slugify(keyword),
        "category": cat,
        "fortune": d["fortune"],
        "seo_title": d["seo_title"].strip(),
        "meta_description": d["meta_description"].strip(),
        "summary": d["summary"].strip(),
        "intro": d["intro"].strip(),
        "situations": [{"title": s["title"].strip(), "fortune": s["fortune"], "meaning": s["meaning"].strip()}
                       for s in d["situations"]],
        "psychology": d["psychology"].strip(),
        "tradition": d["tradition"].strip(),
        "advice": d["advice"].strip(),
        "faq": [{"q": f["q"].strip(), "a": f["a"].strip()} for f in d["faq"]],
        "related": related[:8],
        "created": today(),
        "updated": today(),
    }


def generate_one(api_key: str, model: str, keyword: str, category: str, existing: list) -> dict:
    sample = ", ".join(existing[-150:]) or "(아직 없음)"
    messages = [{"role": "user", "content":
                 f"키워드: {keyword}\n참고 분류: {category}\n이미 있는 페이지: {sample}"}]
    last_errors = []
    for attempt in range(2):
        text = call_claude(api_key, model, messages)
        try:
            d = parse_json(text)
            errors = validate(d, keyword)
        except (ValueError, json.JSONDecodeError) as e:
            errors = [f"JSON 파싱 실패: {e}"]
        if not errors:
            return build_record(d, keyword, category)
        last_errors = errors
        print(f"  품질 기준 미달({attempt + 1}회차): {'; '.join(errors[:4])}")
        messages += [{"role": "assistant", "content": text},
                     {"role": "user", "content": "다음 기준을 맞춰 JSON 전체를 다시 출력하세요:\n- " + "\n- ".join(errors)}]
    raise ValueError("; ".join(last_errors[:5]))


def main():
    cfg = load_config()
    gen = cfg["generation"]
    p = argparse.ArgumentParser()
    p.add_argument("--pages", type=int, default=gen["pages_per_day"])
    args = p.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("ANTHROPIC_API_KEY 환경 변수가 없습니다.")

    out_dir = CONTENT_DIR if gen.get("auto_publish", True) else DRAFT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    state = load_state()
    made = 0

    while made < args.pages and state["queue"]:
        item = state["queue"].pop(0)
        keyword, category = item["keyword"], item["category"]
        print(f"[{made + 1}/{args.pages}] {keyword} ({item['source']})")
        existing = [x["keyword"] for x in state["done"]]
        try:
            rec = generate_one(api_key, gen["model"], keyword, category, existing)
        except Exception as e:
            print(f"  실패: {e}")
            state["failed"].append({"keyword": keyword, "category": category, "date": today(), "reason": str(e)[:200]})
            save_state(state)
            continue
        (out_dir / f"{rec['slug']}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        state["done"].append({"keyword": keyword, "category": rec["category"], "date": today()})
        for r in rec["related"]:
            add_to_queue(state, r, rec["category"], "related")
        save_state(state)  # 중간에 끊겨도 진행분은 남도록 매번 저장
        made += 1

    print(f"완료: 새 페이지 {made}개 · 남은 대기열 {len(state['queue'])}개")


if __name__ == "__main__":
    main()
