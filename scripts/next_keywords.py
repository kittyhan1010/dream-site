#!/usr/bin/env python3
"""오늘 쓸 키워드와 이미 있는 페이지 목록을 보여줍니다. (Claude 예약 작업용)

사용: python scripts/next_keywords.py [개수]
"""
import sys

from common import load_config, load_state, save_state


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else load_config()["generation"]["pages_per_day"]
    state = load_state()
    save_state(state)  # seeds.txt에 새로 추가된 시드를 대기열에 반영
    print(f"# 오늘 쓸 키워드 {min(n, len(state['queue']))}개 (키워드 | 참고 분류 | 출처)")
    for item in state["queue"][:n]:
        print(f"{item['keyword']} | {item['category']} | {item['source']}")
    print(f"\n# 이미 있는 페이지 {len(state['done'])}개 (related에서 우선 골라 쓰세요)")
    print(", ".join(d["keyword"] for d in state["done"]))
    print(f"\n# 남은 대기열 {len(state['queue'])}개")


if __name__ == "__main__":
    main()
