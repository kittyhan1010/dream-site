#!/usr/bin/env python3
"""content/dreams/*.json → dist/ 정적 사이트 (의존성 없음)."""
import hashlib
import html
import json
import re
import shutil
from collections import defaultdict
from urllib.parse import unquote, urlparse

from common import (CATEGORIES, CONTENT_DIR, DIST, STATIC_DIR, category_path, compact,
                    dream_path, load_config, load_dreams, today)

E = html.escape

CHOSUNG = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
CHOSUNG_BASE = {"ㄲ": "ㄱ", "ㄸ": "ㄷ", "ㅃ": "ㅂ", "ㅆ": "ㅅ", "ㅉ": "ㅈ"}

FORTUNE_LABEL = {"길몽": "좋은 기운의 꿈", "흉몽": "조심하라는 꿈", "중립": "상황에 따라 달라지는 꿈"}


def moon(fortune: str, size: int = 40) -> str:
    """길몽=보름달, 흉몽=그믐달(빈 달), 중립=반달."""
    r, c = 15, 20
    ring = f'<circle cx="{c}" cy="{c}" r="{r}" class="moon-ring"/>'
    if fortune == "길몽":
        shape = f'<circle cx="{c}" cy="{c}" r="{r}" class="moon-lit"/>'
    elif fortune == "흉몽":
        shape = ""
    else:
        shape = f'<path d="M{c} {c - r} A{r} {r} 0 0 1 {c} {c + r} Z" class="moon-lit"/>'
    return (f'<svg class="moon" width="{size}" height="{size}" viewBox="0 0 40 40" aria-hidden="true">'
            f'{ring}{shape}</svg>')


def chosung(word: str) -> str:
    ch = word[0]
    code = ord(ch) - 0xAC00
    if 0 <= code < 11172:
        c = CHOSUNG[code // 588]
        return CHOSUNG_BASE.get(c, c)
    return "기타"


class Site:
    def __init__(self):
        self.cfg = load_config()
        self.url = self.cfg["site_url"].rstrip("/")
        # 사이트가 하위 경로(예: github.io/dream-site)에 있으면 내부 링크 앞에 붙임
        self.base = urlparse(self.url).path.rstrip("/")
        self.name = self.cfg["site_name"]
        self.dreams = sorted(load_dreams(), key=lambda d: d["keyword"])
        self.by_compact = {compact(d["keyword"]): d for d in self.dreams}
        self.by_cat = defaultdict(list)
        for d in self.dreams:
            self.by_cat[d["category"]].append(d)
        self.urls = []  # (path, lastmod)
        css = (STATIC_DIR / "style.css").read_bytes() + (STATIC_DIR / "search.js").read_bytes()
        self.ver = hashlib.md5(css).hexdigest()[:8]

    # ---------- 공통 ----------

    def fix_links(self, html_text: str) -> str:
        """사이트 안쪽 링크(/로 시작)에 하위 경로를 붙임. 외부 링크(//, https://)는 그대로."""
        if not self.base:
            return html_text
        for attr in ('href="', 'src="'):
            html_text = re.sub(rf'{attr}/(?!/)', f'{attr}{self.base}/', html_text)
        return html_text

    def write(self, rel: str, content: str, lastmod: str = None, sitemap: bool = True):
        path = DIST / unquote(rel).lstrip("/")  # 디스크에는 한글 그대로 저장
        if rel.endswith("/"):
            path = path / "index.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.fix_links(content), encoding="utf-8")
        if sitemap and rel.endswith("/"):
            self.urls.append((rel, lastmod or today()))

    def ad(self, slot_key: str) -> str:
        client, slot = self.cfg.get("adsense_client"), self.cfg.get("ad_slots", {}).get(slot_key)
        if not (client and slot):
            return ""  # 슬롯 ID가 없으면 자동 광고에 맡김
        return (f'<div class="ad"><ins class="adsbygoogle" style="display:block" data-ad-client="{E(client)}" '
                f'data-ad-slot="{E(slot)}" data-ad-format="auto" data-full-width-responsive="true"></ins>'
                '<script>(adsbygoogle=window.adsbygoogle||[]).push({});</script></div>')

    def head_extras(self) -> str:
        c, out = self.cfg, []
        if c.get("google_site_verification"):
            out.append(f'<meta name="google-site-verification" content="{E(c["google_site_verification"])}">')
        if c.get("naver_site_verification"):
            out.append(f'<meta name="naver-site-verification" content="{E(c["naver_site_verification"])}">')
        if c.get("adsense_client"):
            out.append(f'<meta name="google-adsense-account" content="{E(c["adsense_client"])}">')
            out.append('<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js'
                       f'?client={E(c["adsense_client"])}" crossorigin="anonymous"></script>')
        if c.get("ga4_id"):
            g = E(c["ga4_id"])
            out.append(f'<script async src="https://www.googletagmanager.com/gtag/js?id={g}"></script>'
                       "<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments)}"
                       f"gtag('js',new Date());gtag('config','{g}');</script>")
        return "\n".join(out)

    def page(self, *, path, title, description, body, jsonld=None, og_type="website", noindex=False):
        canonical = self.url + path
        ld = ""
        if jsonld:
            ld = f'<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>'
        robots = '<meta name="robots" content="noindex">' if noindex else ""
        return f"""<!doctype html>
<html lang="ko" data-base="{E(self.base)}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(title)}</title>
<meta name="description" content="{E(description)}">
<link rel="canonical" href="{E(canonical)}">
{robots}
<meta property="og:type" content="{og_type}">
<meta property="og:site_name" content="{E(self.name)}">
<meta property="og:title" content="{E(title)}">
<meta property="og:description" content="{E(description)}">
<meta property="og:url" content="{E(canonical)}">
<meta property="og:locale" content="ko_KR">
<meta name="theme-color" content="#ECE9F1" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#16182C" media="(prefers-color-scheme: dark)">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="alternate" type="application/rss+xml" title="{E(self.name)}" href="/rss.xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Gowun+Batang:wght@400;700&family=Gowun+Dodum&display=swap">
<link rel="stylesheet" href="/assets/style.css?v={self.ver}">
{self.head_extras()}
{ld}
</head>
<body>
<a class="skip" href="#main">본문으로 건너뛰기</a>
<header class="site-head">
  <a class="brand" href="/">{moon("길몽", 26)}<span>{E(self.name)}</span></a>
  <nav aria-label="주요 메뉴"><a href="/#find">꿈 찾기</a><a href="/#index">가나다 사전</a></nav>
</header>
<main id="main">
{body}
</main>
<footer class="site-foot">
  <p>꿈풀이는 전통 해몽과 심리학 관점을 참고한 읽을거리입니다. 중요한 결정은 꿈이 아닌 현실의 정보로 내려 주세요.</p>
  <nav aria-label="사이트 정보"><a href="/about/">사이트 소개</a><a href="/privacy/">개인정보처리방침</a><a href="/contact/">문의</a></nav>
  <p class="copy">© {today()[:4]} {E(self.name)}</p>
</footer>
<script src="/assets/search.js?v={self.ver}" defer></script>
</body>
</html>
"""

    def dream_list(self, items, show_summary=True) -> str:
        lis = []
        for d in items:
            summary = f'<span class="dl-sum">{E(d["summary"])}</span>' if show_summary else ""
            lis.append(f'<li><a href="{dream_path(d["slug"])}">{moon(d["fortune"], 18)}'
                       f'<span class="dl-kw">{E(d["keyword"])}</span>{summary}</a></li>')
        return f'<ul class="dream-list">{"".join(lis)}</ul>'

    # ---------- 꿈 상세 ----------

    def build_dream(self, d):
        path = dream_path(d["slug"])
        kw = d["keyword"]
        cat = d["category"]

        sit_html = []
        for i, s in enumerate(d["situations"]):
            sit_html.append(
                f'<section class="situation" id="s-{i + 1}"><h3>{moon(s["fortune"], 20)}{E(s["title"])}'
                f'<span class="tag">{E(s["fortune"])}</span></h3><p>{E(s["meaning"])}</p></section>')
            if i == 2:
                sit_html.append(self.ad("article_mid"))

        faq_html = "".join(f"<dt>{E(f['q'])}</dt><dd>{E(f['a'])}</dd>" for f in d["faq"])

        related = [self.by_compact[compact(r)] for r in d.get("related", []) if compact(r) in self.by_compact]
        seen = {compact(kw)} | {compact(r["keyword"]) for r in related}
        for other in self.by_cat[cat]:
            if len(related) >= 8:
                break
            if compact(other["keyword"]) not in seen:
                related.append(other)
                seen.add(compact(other["keyword"]))
        related_html = (f'<section class="related"><h2>함께 찾아본 꿈</h2>{self.dream_list(related, False)}</section>'
                        if related else "")

        body = f"""
<article class="dream">
  <nav class="crumbs" aria-label="현재 위치"><a href="/">홈</a> / <a href="{category_path(cat)}">{E(cat)} 꿈</a></nav>
  <header class="dream-head">
    {moon(d["fortune"], 64)}
    <h1>{E(kw)} 해몽</h1>
    <p class="verdict">{E(d["summary"])}</p>
    <p class="fortune-label">{E(FORTUNE_LABEL[d["fortune"]])}</p>
  </header>
  {self.ad("article_top")}
  <p class="lead">{E(d["intro"])}</p>
  <h2>상황별 {E(kw)} 풀이</h2>
  {"".join(sit_html)}
  <h2>심리학으로 보면</h2>
  <p>{E(d["psychology"])}</p>
  <h2>전통 해몽에서는</h2>
  <p>{E(d["tradition"])}</p>
  <h2>이 꿈을 꾼 날에는</h2>
  <p>{E(d["advice"])}</p>
  <h2>자주 묻는 질문</h2>
  <dl class="faq">{faq_html}</dl>
  {self.ad("article_bottom")}
  {related_html}
  <p class="dates">처음 쓴 날 {E(d["created"])}{' · 고친 날 ' + E(d["updated"]) if d.get("updated", d["created"]) != d["created"] else ''}</p>
</article>"""

        full = self.url + path
        jsonld = [
            {"@context": "https://schema.org", "@type": "Article", "headline": d["seo_title"],
             "description": d["meta_description"], "inLanguage": "ko-KR", "mainEntityOfPage": full,
             "datePublished": d["created"], "dateModified": d.get("updated", d["created"]),
             "author": {"@type": "Organization", "name": self.name},
             "publisher": {"@type": "Organization", "name": self.name}},
            {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "홈", "item": self.url + "/"},
                {"@type": "ListItem", "position": 2, "name": f"{cat} 꿈", "item": self.url + category_path(cat)},
                {"@type": "ListItem", "position": 3, "name": f"{kw} 해몽", "item": full}]},
            {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
                {"@type": "Question", "name": f["q"], "acceptedAnswer": {"@type": "Answer", "text": f["a"]}}
                for f in d["faq"]]},
        ]
        self.write(path, self.page(path=path, title=f'{d["seo_title"]} | {self.name}',
                                   description=d["meta_description"], body=body, jsonld=jsonld,
                                   og_type="article"), lastmod=d.get("updated", d["created"]))

    # ---------- 홈 / 분류 ----------

    def build_home(self):
        recent = sorted(self.dreams, key=lambda d: (d["created"], d["keyword"]), reverse=True)[:8]
        cats = "".join(f'<li><a href="{category_path(c)}">{E(c)} 꿈<span class="count">{len(self.by_cat[c])}</span></a></li>'
                       for c in CATEGORIES if self.by_cat[c])
        groups = defaultdict(list)
        for d in self.dreams:
            groups[chosung(d["keyword"])].append(d)
        order = [c for c in "ㄱㄴㄷㄹㅁㅂㅅㅇㅈㅊㅋㅌㅍㅎ" if c in groups] + (["기타"] if "기타" in groups else [])
        jump = "".join(f'<a href="#g-{c}">{c}</a>' for c in order)
        index = "".join(
            f'<section class="index-group" id="g-{c}"><h3>{c}</h3><div>'
            + "".join(f'<a href="{dream_path(d["slug"])}">{E(d["keyword"])}</a>' for d in groups[c])
            + "</div></section>" for c in order)

        body = f"""
<section class="hero" id="find">
  <h1>어젯밤 꾼 꿈,<br>무슨 뜻이었을까요</h1>
  <form class="search" role="search" action="/" onsubmit="return false">
    <label for="dream-search" class="sr">꿈에 나온 것 입력</label>
    <input id="dream-search" type="search" name="q" autocomplete="off"
      placeholder="꿈에 나온 것을 적어 보세요. 뱀, 이빨, 돼지…">
  </form>
  <p class="hint">지금까지 {len(self.dreams)}가지 꿈을 풀었어요.</p>
  <ol id="search-results" class="results" aria-live="polite"></ol>
</section>
<section class="block">
  <h2>분류로 찾기</h2>
  <ul class="cats">{cats}</ul>
</section>
<section class="block">
  <h2>새로 풀이한 꿈</h2>
  {self.dream_list(recent)}
</section>
<section class="block" id="index">
  <h2>가나다 꿈 사전</h2>
  <nav class="jump" aria-label="초성으로 이동">{jump}</nav>
  {index}
</section>"""
        jsonld = {"@context": "https://schema.org", "@type": "WebSite", "name": self.name, "url": self.url + "/",
                  "inLanguage": "ko-KR",
                  "potentialAction": {"@type": "SearchAction", "target": self.url + "/?q={search_term_string}",
                                      "query-input": "required name=search_term_string"}}
        self.write("/", self.page(path="/", title=f"{self.name} - 상황별 꿈해몽 풀이",
                                  description=self.cfg["site_description"], body=body, jsonld=jsonld))

    def build_categories(self):
        for c in CATEGORIES:
            items = self.by_cat[c]
            if not items:
                continue
            path = category_path(c)
            body = f"""
<section class="block cat-page">
  <nav class="crumbs" aria-label="현재 위치"><a href="/">홈</a></nav>
  <h1>{E(c)} 꿈 해몽</h1>
  <p class="lead">{E(c)}이(가) 나온 꿈 {len(items)}가지를 모았어요. 달 모양은 꿈의 기운을 뜻해요. 차 있을수록 좋은 꿈이에요.</p>
  {self.dream_list(items)}
</section>"""
            self.write(path, self.page(path=path, title=f"{c} 꿈 해몽 모음 | {self.name}",
                                       description=f"{c}이(가) 나온 꿈 {len(items)}가지의 상황별 해몽을 모았습니다.",
                                       body=body))

    # ---------- 정보 페이지 ----------

    def build_static_pages(self):
        email = E(self.cfg.get("contact_email", ""))
        pages = {
            "/about/": ("사이트 소개", f"""
<h1>사이트 소개</h1>
<p>{E(self.name)}은 꿈에서 본 장면이 무슨 뜻인지 궁금한 분들을 위한 꿈해몽 사전입니다. 같은 뱀 꿈이라도 물렸는지, 쫓겼는지, 잡았는지에 따라 풀이가 달라지기 때문에 상황별로 나누어 설명합니다.</p>
<p>각 풀이는 한국의 전통 해몽 자료와 현대 심리학의 꿈 연구를 바탕으로 AI 글쓰기 도구의 도움을 받아 작성합니다. 두 관점을 섞지 않고 구분해서 보여 드리는 것이 원칙입니다.</p>
<p>꿈풀이는 재미와 자기 성찰을 위한 읽을거리입니다. 건강, 돈, 법률처럼 중요한 결정은 꿈이 아닌 전문가와 현실의 정보를 바탕으로 내려 주세요. 같은 악몽이 반복되어 잠을 설친다면 수면 전문의와 상담해 보시길 권합니다.</p>
<p>잘못된 내용이나 풀이해 줬으면 하는 꿈이 있다면 <a href="/contact/">문의</a>로 알려 주세요.</p>"""),
            "/privacy/": ("개인정보처리방침", f"""
<h1>개인정보처리방침</h1>
<p>{E(self.name)}(이하 '사이트')은 회원가입 없이 이용할 수 있으며, 이용자의 이름·연락처 같은 개인정보를 직접 수집하지 않습니다.</p>
<h2>쿠키와 광고</h2>
<p>사이트는 Google AdSense를 통해 광고를 게재합니다. Google을 포함한 제3자 광고 사업자는 쿠키를 사용해 이용자의 이전 방문 기록을 바탕으로 광고를 보여줄 수 있습니다. Google은 광고 쿠키를 사용해 이 사이트와 다른 사이트 방문 기록에 기반한 광고를 제공합니다.</p>
<p>맞춤 광고는 <a href="https://adssettings.google.com" rel="nofollow">Google 광고 설정</a>에서 끌 수 있으며, 제3자 광고 쿠키는 <a href="https://www.aboutads.info/choices" rel="nofollow">aboutads.info</a>에서 거부할 수 있습니다.</p>
<h2>방문 통계</h2>
<p>사이트는 방문 통계를 위해 Google Analytics를 사용할 수 있습니다. 수집되는 정보는 방문 페이지, 체류 시간, 기기 종류 같은 익명 통계이며 개인을 식별하는 데 쓰지 않습니다.</p>
<h2>문의</h2>
<p>개인정보 관련 문의는 {email}로 보내 주세요.</p>
<p>시행일: 2026년 10월 1일</p>"""),
            "/contact/": ("문의", f"""
<h1>문의</h1>
<p>잘못된 풀이, 새로 풀어 줬으면 하는 꿈, 광고·제휴 문의는 아래 메일로 보내 주세요.</p>
<p class="mail"><a href="mailto:{email}">{email}</a></p>"""),
        }
        for path, (title, inner) in pages.items():
            self.write(path, self.page(path=path, title=f"{title} | {self.name}",
                                       description=f"{self.name} {title}",
                                       body=f'<article class="plain">{inner}</article>'))

        body = """<section class="block plain"><h1>찾는 페이지가 없어요</h1>
<p>주소가 바뀌었거나 아직 풀이하지 않은 꿈이에요. <a href="/#find">꿈 찾기</a>에서 다른 단어로 찾아 보세요.</p></section>"""
        (DIST / "404.html").write_text(self.fix_links(self.page(path="/404.html", title=f"페이지 없음 | {self.name}",
                                                 description="페이지를 찾을 수 없습니다.", body=body,
                                                 noindex=True)), encoding="utf-8")

    # ---------- 부가 파일 ----------

    def build_files(self):
        index = [{"k": d["keyword"], "u": self.base + dream_path(d["slug"]), "s": d["summary"], "f": d["fortune"],
                  "a": [s["title"] for s in d["situations"]]} for d in self.dreams]
        (DIST / "search-index.json").write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")

        urls = "".join(f"<url><loc>{E(self.url + p)}</loc><lastmod>{m}</lastmod></url>" for p, m in self.urls)
        (DIST / "sitemap.xml").write_text(
            f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>',
            encoding="utf-8")

        (DIST / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {self.url}/sitemap.xml\n", encoding="utf-8")

        client = self.cfg.get("adsense_client", "")
        if client:
            pub = client.replace("ca-", "")
            (DIST / "ads.txt").write_text(f"google.com, {pub}, DIRECT, f08c47fec0942fa0\n", encoding="utf-8")

        latest = sorted(self.dreams, key=lambda d: d["created"], reverse=True)[:30]
        items = "".join(
            f"<item><title>{E(d['seo_title'])}</title><link>{E(self.url + dream_path(d['slug']))}</link>"
            f"<guid>{E(self.url + dream_path(d['slug']))}</guid><description>{E(d['meta_description'])}</description>"
            f"<pubDate>{d['created']}T06:00:00+09:00</pubDate></item>" for d in latest)
        (DIST / "rss.xml").write_text(
            f'<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel><title>{E(self.name)}</title>'
            f"<link>{E(self.url)}/</link><description>{E(self.cfg['site_description'])}</description>"
            f"<language>ko</language>{items}</channel></rss>", encoding="utf-8")

        host = self.url.split("://", 1)[-1].split("/")[0]
        if host and "example.com" not in host and not host.endswith("github.io"):
            (DIST / "CNAME").write_text(host + "\n", encoding="utf-8")

    def build(self):
        if DIST.exists():
            shutil.rmtree(DIST)
        (DIST / "assets").mkdir(parents=True)
        for f in ("style.css", "search.js"):
            shutil.copy(STATIC_DIR / f, DIST / "assets" / f)
        shutil.copy(STATIC_DIR / "favicon.svg", DIST / "favicon.svg")

        self.build_home()
        for d in self.dreams:
            self.build_dream(d)
        self.build_categories()
        self.build_static_pages()
        self.build_files()
        print(f"빌드 완료: 꿈 페이지 {len(self.dreams)}개, 전체 URL {len(self.urls)}개 → {DIST}")


if __name__ == "__main__":
    if not CONTENT_DIR.exists():
        CONTENT_DIR.mkdir(parents=True)
    Site().build()
