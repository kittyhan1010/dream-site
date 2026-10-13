#!/usr/bin/env python3
"""구글·네이버 자동완성으로 실제로 검색되는 꿈 키워드를 찾아 큐에 넣습니다.

자동완성에 뜬다 = 사람들이 실제로 검색한다는 신호이므로
여기서 찾은 키워드(source=suggest)를 가장 먼저 페이지로 만듭니다.
"""
import argparse
import json
import time
import urllib.request
from urllib.parse import quote

from common import add_to_queue, load_config, load_state, read_seeds, save_state

UA = "Mozilla/5.0 (compatible; dream-dictionary-bot/1.0)"


def fetch_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.loads(r.read().decode("utf-8", errors="replace"))


def google_suggest(q: str) -> list:
    data = fetch_json(f"https://suggestqueries.google.com/complete/search?client=firefox&hl=ko&q={quote(q)}")
    return data[1] if isinstance(data, list) and len(data) > 1 else []


def naver_suggest(q: str) -> list:
    data = fetch_json(
        "https://ac.search.naver.com/nx/ac?con=0&frm=nx&ans=2&r_format=json&r_enc=UTF-8"
        f"&r_unicode=0&t_koreng=1&run=2&rev=4&q_enc=UTF-8&st=100&q={quote(q)}"
    )
    out = []
    for group in data.get("items", []):
        for item in group:
            if item and isinstance(item[0], str):
                out.append(item[0])
    return out


def expand(state: dict, limit: int) -> int:
    # 시드 먼저, 시드가 다 떨어지면 이미 만든 페이지 키워드로 한 단계 더 파고듦
    candidates = [(s, c) for s, c in read_seeds()]
    candidates += [(d["keyword"].removesuffix(" 꿈"), d["category"]) for d in state["done"]]
    expanded = set(state["expanded"])
    todo = list({s: c for s, c in candidates if s not in expanded}.items())[:limit]

    added = 0
    for seed, cat in todo:
        ok = False
        for q in (f"{seed} 꿈", f"{seed} 꿈해몽"):
            for provider in (google_suggest, naver_suggest):
                try:
                    suggestions = provider(q)
                except Exception as e:  # 네트워크 오류는 건너뜀
                    print(f"  [건너뜀] {provider.__name__}({q}): {e}")
                    continue
                ok = True
                for s in suggestions:
                    if "꿈" in s and add_to_queue(state, s, cat, "suggest"):
                        added += 1
                time.sleep(0.4)
        if ok:  # 요청이 모두 실패했으면 다음 실행 때 다시 시도
            state["expanded"].append(seed)
            print(f"  확장 완료: {seed}")
    return added


def main():
    cfg = load_config()
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=cfg["generation"]["expand_seeds_per_day"])
    args = p.parse_args()

    state = load_state()
    n = expand(state, args.limit)
    save_state(state)
    print(f"새 키워드 {n}개 추가 · 대기열 {len(state['queue'])}개")


if __name__ == "__main__":
    main()
