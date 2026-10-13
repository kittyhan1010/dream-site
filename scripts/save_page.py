#!/usr/bin/env python3
"""Claude가 쓴 원고 JSON을 품질 검사한 뒤 사이트에 저장합니다.

사용: python scripts/save_page.py 원고1.json [원고2.json ...]
- 통과: content/dreams/에 저장하고, 대기열에서 빼고, 관련 꿈을 대기열에 추가
- 불합격: 이유를 출력하고 저장하지 않음 (고쳐서 다시 실행)
종료 코드: 하나라도 불합격이면 1
"""
import json
import sys
from pathlib import Path

from common import (CONTENT_DIR, DRAFT_DIR, add_to_queue, compact, load_config, load_state,
                    normalize_keyword, save_state, today)
from generate import build_record, validate


def save_one(path: Path, state: dict, out_dir: Path) -> bool:
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"[불합격] {path.name}: JSON을 읽을 수 없음 ({e})")
        return False

    keyword = normalize_keyword(d.get("keyword", ""))
    if not keyword:
        print(f"[불합격] {path.name}: keyword가 'OO 꿈' 형식이 아님")
        return False
    if any(compact(x["keyword"]) == compact(keyword) for x in state["done"]):
        print(f"[건너뜀] {keyword}: 이미 있는 페이지")
        return True

    errors = validate(d, keyword)
    if errors:
        print(f"[불합격] {keyword}:")
        for e in errors:
            print(f"   - {e}")
        return False

    queued = next((x for x in state["queue"] if compact(x["keyword"]) == compact(keyword)), None)
    rec = build_record(d, keyword, queued["category"] if queued else "사물")
    (out_dir / f"{rec['slug']}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")

    if queued:
        state["queue"].remove(queued)
    state["done"].append({"keyword": keyword, "category": rec["category"], "date": today()})
    new = sum(add_to_queue(state, r, rec["category"], "related") for r in rec["related"])
    print(f"[저장] {keyword} → {out_dir.name}/{rec['slug']}.json (관련 꿈 {new}개 대기열 추가)")
    return True


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    out_dir = CONTENT_DIR if load_config()["generation"].get("auto_publish", True) else DRAFT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    state = load_state()
    results = [save_one(Path(p), state, out_dir) for p in sys.argv[1:]]
    save_state(state)
    print(f"\n합격 {sum(results)}개 / 불합격 {results.count(False)}개 · 남은 대기열 {len(state['queue'])}개")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
