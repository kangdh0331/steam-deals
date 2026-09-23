let deals = [];

// 우선 지원하는 대형 개발사/배급사 목록. 실제 데이터에 게임이 있는 곳만 드롭다운에 표시된다.
const MAJOR_PUBLISHERS = [
  { label: '반다이 남코', match: 'bandai namco' },
  { label: '스퀘어 에닉스', match: 'square enix' },
  { label: 'CD Projekt Red', match: 'cd projekt' },
  { label: '락스타 게임즈', match: 'rockstar' },
  { label: 'Take-Two Interactive', match: 'take-two' },
  { label: '일렉트로닉 아츠', match: 'electronic arts' },
  { label: '유비소프트', match: 'ubisoft' },
  { label: '세가', match: 'sega' },
  { label: '캡콤', match: 'capcom' },
  { label: '2K', match: '2k' },
  { label: '베데스다', match: 'bethesda' },
  { label: '액티비전', match: 'activision' },
  { label: '밸브', match: 'valve' },
  { label: '디볼버 디지털', match: 'devolver' },
];

const grid = document.getElementById('grid');
const empty = document.getElementById('empty');
const meta = document.getElementById('meta');
const search = document.getElementById('search');
const genreFilter = document.getElementById('genreFilter');
const publisherFilter = document.getElementById('publisherFilter');
const sortSelect = document.getElementById('sort');
const refreshBtn = document.getElementById('refresh');

function companyNames(d) {
  return [...(d.developers || []), ...(d.publishers || [])].join(' ').toLowerCase();
}

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

function populatePublisherFilter() {
  const current = publisherFilter.value;
  publisherFilter.innerHTML = '<option value="">전체 개발사/배급사</option>';
  for (const p of MAJOR_PUBLISHERS) {
    const has = deals.some(d => companyNames(d).includes(p.match));
    if (!has) continue;
    const opt = document.createElement('option');
    opt.value = p.match;
    opt.textContent = p.label;
    publisherFilter.appendChild(opt);
  }
  if ([...publisherFilter.options].some(o => o.value === current)) publisherFilter.value = current;
}

function render() {
  const q = search.value.trim().toLowerCase();
  const genre = genreFilter.value;
  const publisher = publisherFilter.value;
  // 검색어/장르/개발사 필터가 없으면 세일 중인 게임만, 있으면 세일 여부와 상관없이 전체에서 찾는다.
  let list = (q || genre || publisher) ? deals.slice() : deals.filter(d => d.on_sale);
  if (q) list = list.filter(d => d.name.toLowerCase().includes(q));
  if (genre) list = list.filter(d => (d.genres || []).includes(genre));
  if (publisher) list = list.filter(d => companyNames(d).includes(publisher));

  const sortKey = sortSelect.value;
  list = list.slice().sort((a, b) => {
    if (a.on_sale !== b.on_sale) return a.on_sale ? -1 : 1; // 할인 중인 게임을 우선 표시
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

    const studio = (d.publishers && d.publishers[0]) || (d.developers && d.developers[0]);
    let studioEl = null;
    if (studio) {
      studioEl = document.createElement('div');
      studioEl.className = 'studio';
      studioEl.textContent = studio;
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
    body.append(title, ...(studioEl ? [studioEl] : []), genres, priceRow);
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
    populatePublisherFilter();
    render();
  } catch (err) {
    meta.textContent = `불러오기 실패: ${err.message}`;
  }
}

search.addEventListener('input', render);
genreFilter.addEventListener('change', render);
publisherFilter.addEventListener('change', render);
sortSelect.addEventListener('change', render);
refreshBtn.addEventListener('click', () => load(true));

load(false);
