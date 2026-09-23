let deals = [];

const grid = document.getElementById('grid');
const empty = document.getElementById('empty');
const meta = document.getElementById('meta');
const search = document.getElementById('search');
const genreFilter = document.getElementById('genreFilter');
const sortSelect = document.getElementById('sort');
const refreshBtn = document.getElementById('refresh');

function formatPrice(value, currency) {
  const formatted = new Intl.NumberFormat('ko-KR').format(Math.round(value));
  return currency === 'KRW' ? `${formatted}원` : `${formatted} ${currency}`;
}

function populateGenreFilter() {
  const genres = new Set();
  for (const d of deals) {
    for (const g of d.genres || []) genres.add(g);
  }
  const current = genreFilter.value;
  genreFilter.innerHTML = '<option value="">전체 장르</option>';
  for (const g of [...genres].sort((a, b) => a.localeCompare(b, 'ko'))) {
    const opt = document.createElement('option');
    opt.value = g;
    opt.textContent = g;
    genreFilter.appendChild(opt);
  }
  if (genres.has(current)) genreFilter.value = current;
}

function render() {
  const q = search.value.trim().toLowerCase();
  // 검색어가 없으면 세일 중인 게임만, 검색 중이면 세일 여부와 상관없이 전체에서 찾는다.
  let list = q
    ? deals.filter(d => d.name.toLowerCase().includes(q))
    : deals.filter(d => d.on_sale);

  const genre = genreFilter.value;
  if (genre) list = list.filter(d => (d.genres || []).includes(genre));

  const sortKey = sortSelect.value;
  list = list.slice().sort((a, b) => {
    switch (sortKey) {
      case 'price_asc': return a.final_price - b.final_price;
      case 'price_desc': return b.final_price - a.final_price;
      case 'name_asc': return a.name.localeCompare(b.name, 'ko');
      default: return b.discount_percent - a.discount_percent;
    }
  });

  grid.innerHTML = '';
  empty.hidden = list.length > 0;

  const frag = document.createDocumentFragment();
  for (const d of list) {
    const card = document.createElement('a');
    card.className = 'card';
    card.href = d.url;
    card.target = '_blank';
    card.rel = 'noopener noreferrer';

    const thumb = document.createElement('div');
    thumb.className = 'thumb';
    const img = document.createElement('img');
    img.src = d.image || '';
    img.alt = d.name;
    img.loading = 'lazy';
    thumb.appendChild(img);

    const body = document.createElement('div');
    body.className = 'body';
    const title = document.createElement('h2');
    title.textContent = d.name;
    title.title = d.name;

    const genres = document.createElement('div');
    genres.className = 'genres';
    for (const g of d.genres || []) {
      const tag = document.createElement('span');
      tag.className = 'genre-tag';
      tag.textContent = g;
      genres.appendChild(tag);
    }

    const priceRow = document.createElement('div');
    priceRow.className = 'price-row';
    if (d.on_sale) {
      const discountEl = document.createElement('span');
      discountEl.className = 'discount';
      discountEl.textContent = `-${d.discount_percent}%`;
      const originalEl = document.createElement('span');
      originalEl.className = 'original';
      originalEl.textContent = formatPrice(d.original_price, d.currency);
      priceRow.append(discountEl, originalEl);
    }
    const finalEl = document.createElement('span');
    finalEl.className = 'final';
    finalEl.textContent = formatPrice(d.final_price, d.currency);
    priceRow.append(finalEl);
    body.append(title, genres, priceRow);
    card.append(thumb, body);
    frag.appendChild(card);
  }
  grid.appendChild(frag);
}

async function fetchDeals(forceRefresh) {
  if (forceRefresh) {
    try {
      const res = await fetch('/api/refresh');
      if (res.ok) return res;
    } catch (err) {
      // 백엔드 없는 정적 배포(GitHub Pages)에서는 무시하고 data.json으로 대체
    }
  }
  return fetch(`data.json?t=${Date.now()}`);
}

async function load(forceRefresh) {
  meta.textContent = '불러오는 중...';
  try {
    const res = await fetchDeals(forceRefresh);
    const payload = await res.json();
    if (payload.error) throw new Error(payload.error);
    deals = payload.deals || [];
    const saleCount = deals.filter(d => d.on_sale).length;
    const fetchedAt = payload.fetched_at
      ? new Date(payload.fetched_at * 1000).toLocaleString('ko-KR')
      : '알 수 없음';
    meta.textContent = `할인 중인 게임 ${saleCount}개 (검색 가능 ${deals.length}개) · 마지막 갱신: ${fetchedAt}`;
    populateGenreFilter();
    render();
  } catch (err) {
    meta.textContent = `불러오기 실패: ${err.message}`;
  }
}

search.addEventListener('input', render);
genreFilter.addEventListener('change', render);
sortSelect.addEventListener('change', render);
refreshBtn.addEventListener('click', () => load(true));

load(false);
