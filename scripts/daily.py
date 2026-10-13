#!/usr/bin/env python3
"""매일 실행: 키워드 확장 → 페이지 생성. (사이트 빌드는 build.py)"""
import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def run(script: str, *args: str) -> None:
    print(f"\n=== {script} {' '.join(args)} ===")
    subprocess.run([sys.executable, str(HERE / script), *args], check=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--pages", default="", help="오늘 만들 페이지 수 (비우면 config 값)")
    p.add_argument("--skip-expand", action="store_true")
    args = p.parse_args()

    if not args.skip_expand:
        run("expand_keywords.py")
    run("generate.py", *(["--pages", args.pages] if args.pages.strip() else []))


if __name__ == "__main__":
    main()
