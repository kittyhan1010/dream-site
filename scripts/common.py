"""공통 유틸: 경로, 설정, 키워드 정규화, 키워드 큐 관리."""
import datetime
import json
import re
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = ROOT / "content" / "dreams"
DRAFT_DIR = ROOT / "content" / "drafts"
DATA_DIR = ROOT / "data"
KEYWORDS_FILE = DATA_DIR / "keywords.json"
SEEDS_FILE = ROOT / "keywords" / "seeds.txt"
STATIC_DIR = ROOT / "static"
DIST = ROOT / "dist"

CATEGORIES = ["동물", "사람", "신체", "자연", "사물", "음식", "장소", "행동", "사건"]
FORTUNES = ["길몽", "흉몽", "중립"]
SOURCE_PRIORITY = {"suggest": 0, "seed": 1, "related": 2}

KST = datetime.timezone(datetime.timedelta(hours=9))


def today() -> str:
    return datetime.datetime.now(KST).date().isoformat()


def load_config() -> dict:
    return json.loads((ROOT / "config.json").read_text(encoding="utf-8"))


def compact(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def normalize_keyword(raw: str):
    """검색어를 'OO 꿈' 형태의 대표 키워드로 정리. 쓸 수 없으면 None."""
    k = re.sub(r"\s+", " ", str(raw)).strip()
    k = re.sub(r"(\s*(해몽|풀이|의미|뜻|로또|번호))+$", "", k).strip()
    idx = k.rfind("꿈")
    core = (k[:idx] if idx != -1 else k).strip()
    if not core or not re.fullmatch(r"[가-힣0-9 ]+", core):
        return None
    k = f"{core} 꿈"
    if not 3 <= len(k) <= 30:
        return None
    return k


def slugify(keyword: str) -> str:
    s = re.sub(r"\s+", "-", keyword.strip())
    return re.sub(r"[^가-힣0-9a-zA-Z-]", "", s)


def dream_path(slug: str) -> str:
    return f"/dream/{quote(slug)}/"


def category_path(cat: str) -> str:
    return f"/category/{quote(cat)}/"


def load_dreams(directory: Path = CONTENT_DIR) -> list:
    items = []
    for f in sorted(directory.glob("*.json")):
        try:
            items.append(json.loads(f.read_text(encoding="utf-8")))
        except json.JSONDecodeError as e:
            print(f"[경고] {f.name} 읽기 실패: {e}")
    return items


def read_seeds() -> list:
    """seeds.txt → [(키워드, 분류)]. '# 분류' 줄이 아래 키워드들의 분류가 됨."""
    seeds, cat = [], "사물"
    for line in SEEDS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            name = line.lstrip("#").strip()
            if name in CATEGORIES:
                cat = name
            continue
        seeds.append((line, cat))
    return seeds


# ---------- 키워드 큐 ----------

def load_state() -> dict:
    if KEYWORDS_FILE.exists():
        state = json.loads(KEYWORDS_FILE.read_text(encoding="utf-8"))
    else:
        state = {}
    for key in ("queue", "done", "failed", "expanded"):
        state.setdefault(key, [])
    # 이미 있는 페이지는 완료로 표시
    known = {compact(d["keyword"]) for d in state["done"]}
    for d in load_dreams() + load_dreams(DRAFT_DIR):
        if compact(d["keyword"]) not in known:
            state["done"].append({"keyword": d["keyword"], "category": d["category"], "date": d.get("created", today())})
    # 시드를 큐에 넣기 (처음 한 번, 이후 새로 추가한 시드도)
    for seed, cat in read_seeds():
        add_to_queue(state, f"{seed} 꿈", cat, "seed")
    return state


def save_state(state: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    state["queue"].sort(key=lambda x: (SOURCE_PRIORITY.get(x["source"], 9), x["added"]))
    KEYWORDS_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


def add_to_queue(state: dict, raw: str, category: str, source: str) -> bool:
    k = normalize_keyword(raw)
    if not k:
        return False
    c = compact(k)
    taken = {compact(x["keyword"]) for x in state["done"] + state["failed"]}
    if c in taken:
        return False
    for item in state["queue"]:
        if compact(item["keyword"]) == c:
            # 검색 제안에서 다시 발견되면 우선순위를 올림
            if SOURCE_PRIORITY.get(source, 9) < SOURCE_PRIORITY.get(item["source"], 9):
                item["source"] = source
            return False
    state["queue"].append({"keyword": k, "category": category if category in CATEGORIES else "사물",
                           "source": source, "added": today()})
    return True
