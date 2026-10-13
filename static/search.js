(() => {
  const input = document.getElementById('dream-search');
  const out = document.getElementById('search-results');
  if (!input || !out) return;

  const base = document.documentElement.dataset.base || '';
  let index = null;
  const norm = (s) => (s || '').replace(/\s+/g, '').replace(/(꿈해몽|해몽|꿈)/g, '');

  async function load() {
    if (index) return index;
    try {
      const res = await fetch(base + '/search-index.json');
      index = (await res.json()).map((d) => ({ ...d, nk: norm(d.k), na: norm(d.a) }));
    } catch (e) {
      index = [];
    }
    return index;
  }

  function render(items, q) {
    out.textContent = '';
    if (!q) return;
    if (!items.length) {
      const li = document.createElement('li');
      li.className = 'empty';
      li.textContent = '아직 풀이하지 않은 꿈이에요. 꿈에 나온 것 하나만 짧게 적어 보세요.';
      out.appendChild(li);
      return;
    }
    for (const d of items.slice(0, 20)) {
      const li = document.createElement('li');
      const a = document.createElement('a');
      a.href = d.u;
      const strong = document.createElement('strong');
      strong.textContent = d.k;
      const span = document.createElement('span');
      span.textContent = d.s;
      a.append(strong, span);
      li.appendChild(a);
      out.appendChild(li);
    }
  }

  async function search() {
    const raw = input.value.trim();
    const q = norm(raw);
    const list = await load();
    if (!q) return render([], '');
    const score = (d) => (d.nk === q ? 0 : d.nk.startsWith(q) ? 1 : d.nk.includes(q) ? 2 : d.na.includes(q) ? 3 : 9);
    const hits = list.map((d) => [score(d), d]).filter(([s]) => s < 9)
      .sort((a, b) => a[0] - b[0] || a[1].k.length - b[1].k.length).map(([, d]) => d);
    render(hits, q);
    if (window.gtag && raw.length > 1) {
      clearTimeout(search.t);
      search.t = setTimeout(() => window.gtag('event', 'search', { search_term: raw, results: hits.length }), 1200);
    }
  }

  input.addEventListener('focus', load, { once: true });
  input.addEventListener('input', search);

  const q = new URLSearchParams(location.search).get('q');
  if (q) { input.value = q; search(); }
})();
