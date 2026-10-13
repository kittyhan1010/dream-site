(() => {
  const input = document.getElementById('dream-search');
  const out = document.getElementById('search-results');
  if (!input || !out) return;

  const base = document.documentElement.dataset.base || '';
  let index = null;

  // ---------- 한국어 문장 다듬기 ----------
  // "어금니가 빠졌을때" → "어금니가빠지을때"처럼 바꿔 "어금니가 빠지는 꿈"과 글자 조각이 겹치게 만든다.

  const SYNONYMS = [
    [/치아/g, '이빨'], [/이빨이|이빨을|이빨은/g, '이빨'],
    [/한테|에게서/g, '에게'],
    [/돌아가신|돌아가셨던|돌아가셨는데/g, '돌아가신'],
  ];
  // 혼자 쓰인 '이', '이가'는 이빨로 본다 (예: "이가 빠졌어")
  const TOOTH_WORDS = new Set(['이', '이가', '이를', '이는', '이도']);
  const DROP = /(꿈속에서|꿈에서|꿈속|꿈해몽|해몽|꿈풀이|풀이|의미|뜻|해석|꿈)/g;
  const STOP = new Set('이가은는을를의에도고하다요어아서때데면게했'.split(''));

  // 과거형 받침을 걷어낸다: 빠졌→빠지, 물렸→물리, 봤→보, 줬→주, 했→하
  function unpast(ch) {
    const code = ch.charCodeAt(0) - 0xac00;
    if (code < 0 || code > 11171 || code % 28 !== 20) return ch; // 받침 ㅆ이 아니면 그대로
    const cho = Math.floor(code / 588);
    let jung = Math.floor((code % 588) / 28);
    const map = { 6: 20, 9: 8, 14: 13, 10: 11, 1: 0 }; // ㅕ→ㅣ, ㅘ→ㅗ, ㅝ→ㅜ, ㅙ→ㅚ, ㅐ→ㅏ
    if (jung in map) jung = map[jung];
    return String.fromCharCode(0xac00 + cho * 588 + jung * 28);
  }

  function clean(text) {
    let t = (text || '').toLowerCase().replace(/[^가-힣0-9a-z\s]/g, ' ');
    t = t.split(/\s+/).map((w) => (TOOTH_WORDS.has(w) ? '이빨' : w)).join('');
    for (const [re, to] of SYNONYMS) t = t.replace(re, to);
    t = t.replace(DROP, '');
    return Array.from(t).map(unpast).join('');
  }

  function grams(t) {
    const bi = new Set();
    for (let i = 0; i < t.length - 1; i++) bi.add(t.slice(i, i + 2));
    const uni = new Set(Array.from(t).filter((c) => !STOP.has(c)));
    return { bi, uni };
  }

  function similarity(q, d) {
    let hit = 0;
    for (const g of q.bi) if (d.bi.has(g)) hit += 2;
    for (const c of q.uni) if (d.uni.has(c)) hit += 1;
    const total = q.bi.size * 2 + q.uni.size;
    return total ? hit / total : 0;
  }

  // ---------- 색인 ----------

  async function load() {
    if (index) return index;
    try {
      const res = await fetch(base + '/search-index.json');
      index = (await res.json()).map((d) => {
        const ck = clean(d.k);
        const sits = (Array.isArray(d.a) ? d.a : []).map((title, i) => {
          const c = clean(title);
          return { title, c, g: grams(c), anchor: `#s-${i + 1}` };
        });
        return { ...d, ck, g: grams(ck), sits };
      });
    } catch (e) {
      index = [];
    }
    return index;
  }

  function rank(list, q) {
    const qg = grams(q);
    const results = [];
    for (const d of list) {
      // 1) 꿈 이름과 바로 맞으면 가장 위로
      let best = null;
      if (d.ck === q) best = { score: 3 };
      else if (d.ck.startsWith(q)) best = { score: 2.5 };
      else if (q.length >= 2 && d.ck.includes(q)) best = { score: 2.2 };
      else if (q.includes(d.ck) && d.ck.length >= 1) best = { score: 0.55 }; // 문장 속에 꿈 이름이 있음: 상황이 더 잘 맞으면 그쪽으로

      // 2) 문장이면 꿈 이름·상황별 풀이와 글자 조각이 얼마나 겹치는지 본다
      const keyScore = similarity(qg, d.g) * 1.1; // 비슷하면 대표 페이지를 먼저
      if (!best || keyScore > best.score) best = keyScore > 0 ? { score: keyScore } : best;
      for (const s of d.sits) {
        if (s.c && (s.c.includes(q) || q.includes(s.c))) {
          const sc = 2.1;
          if (!best || sc > best.score) best = { score: sc, sit: s };
          continue;
        }
        const sc = similarity(qg, s.g);
        if (!best || sc > best.score) best = { score: sc, sit: s };
      }
      const minScore = q.length <= 2 ? 0.5 : 0.34;
      if (best && best.score >= minScore) results.push({ d, ...best });
    }
    return results.sort((a, b) => b.score - a.score || a.d.k.length - b.d.k.length);
  }

  // ---------- 화면 ----------

  function render(results, q) {
    out.textContent = '';
    if (!q) return;
    if (!results.length) {
      const li = document.createElement('li');
      li.className = 'empty';
      li.textContent = '아직 풀이하지 않은 꿈이에요. 꿈에 나온 것을 짧게 적어 보세요. 예: 뱀, 이빨, 돼지';
      out.appendChild(li);
      return;
    }
    for (const r of results.slice(0, 12)) {
      const li = document.createElement('li');
      const a = document.createElement('a');
      const strong = document.createElement('strong');
      const span = document.createElement('span');
      if (r.sit) {
        a.href = r.d.u + r.sit.anchor;
        strong.textContent = r.sit.title;
        span.textContent = `${r.d.k} 해몽에서 보기`;
      } else {
        a.href = r.d.u;
        strong.textContent = r.d.k;
        span.textContent = r.d.s;
      }
      a.append(strong, span);
      li.appendChild(a);
      out.appendChild(li);
    }
  }

  async function search() {
    const raw = input.value.trim();
    const q = clean(raw);
    const list = await load();
    if (!q) return render([], '');
    const results = rank(list, q);
    render(results, q);
    if (window.gtag && raw.length > 1) {
      clearTimeout(search.t);
      search.t = setTimeout(() => window.gtag('event', 'search', { search_term: raw, results: results.length }), 1200);
    }
  }

  input.addEventListener('focus', load, { once: true });
  input.addEventListener('input', search);

  const q = new URLSearchParams(location.search).get('q');
  if (q) { input.value = q; search(); }
})();
