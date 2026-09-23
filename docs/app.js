const CONFIG = window.SITE_CONFIG || {
  dataUrl: 'data.json',
  refreshUrl: '/api/steam/refresh',
  reviewTier: (rank) => (rank >= 6 ? 'good' : rank === 5 ? 'mixed' : 'bad'),
};

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
const discountFilter = document.getElementById('discountFilter');
const sortSelect = document.getElementById('sort');
const limitInput = document.getElementById('limitInput');
const refreshBtn = document.getElementById('refresh');
const homeLink = document.getElementById('homeLink');

function companyNames(d) {
  return [...(d.developers || []), ...(d.publishers || [])].join(' ').toLowerCase();
}

const CURRENCY_SYMBOLS = { USD: '$', EUR: '€', GBP: '£' };
let usdKrwRate = null;

function formatWon(value) {
  return `${new Intl.NumberFormat('ko-KR').format(Math.round(value))}원`;
}

function formatPrice(value, currency) {
  if (currency === 'KRW') {
    return formatWon(value);
  }
  const formatted = new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value);
  const symbol = CURRENCY_SYMBOLS[currency];
  const base = symbol ? `${symbol}${formatted}` : `${formatted} ${currency}`;
  if (currency === 'USD' && usdKrwRate) {
    return `${base} (약 ${formatWon(value * usdKrwRate)})`;
  }
  return base;
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

  const usedMatches = [];
  const majorGroup = document.createElement('optgroup');
  majorGroup.label = '주요 배급사';
  for (const p of MAJOR_PUBLISHERS) {
    if (!deals.some(d => companyNames(d).includes(p.match))) continue;
    const opt = document.createElement('option');
    opt.value = p.match;
    opt.textContent = p.label;
    majorGroup.appendChild(opt);
    usedMatches.push(p.match);
  }
  if (majorGroup.children.length) publisherFilter.appendChild(majorGroup);

  // 큐레이션 목록에 없는 플랫폼(예: GMG)은 선택지가 너무 적어지므로,
  // 데이터에 자주 나오는 개발사/배급사를 자동으로 뽑아 나머지 옵션으로 채운다.
  const counts = new Map();
  for (const d of deals) {
    for (const name of [...(d.publishers || []), ...(d.developers || [])]) {
      const trimmed = (name || '').trim();
      if (!trimmed) continue;
      const lower = trimmed.toLowerCase();
      if (usedMatches.some(m => lower.includes(m))) continue;
      counts.set(trimmed, (counts.get(trimmed) || 0) + 1);
    }
  }
  const others = [...counts.entries()]
    .filter(([, count]) => count >= 2)
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], 'ko'))
    .slice(0, 30);

  if (others.length) {
    const otherGroup = document.createElement('optgroup');
    otherGroup.label = '기타 배급사/개발사';
    for (const [name] of others) {
      const opt = document.createElement('option');
      opt.value = name.toLowerCase();
      opt.textContent = name;
      otherGroup.appendChild(opt);
    }
    publisherFilter.appendChild(otherGroup);
  }

  if ([...publisherFilter.querySelectorAll('option')].some(o => o.value === current)) {
    publisherFilter.value = current;
  }
}

function render() {
  const q = search.value.trim().toLowerCase();
  const genre = genreFilter.value;
  const publisher = publisherFilter.value;
  const minDiscount = parseInt(discountFilter.value, 10) || 0;
  // 검색어/장르/개발사 필터가 없으면 세일 중인 게임만, 있으면 세일 여부와 상관없이 전체에서 찾는다.
  let list = (q || genre || publisher) ? deals.slice() : deals.filter(d => d.on_sale);
  if (q) {
    list = list.filter(d =>
      d.name.toLowerCase().includes(q) ||
      companyNames(d).includes(q) ||
      (d.genres || []).some(g => g.toLowerCase().includes(q))
    );
  }
  if (minDiscount > 0) list = list.filter(d => d.discount_percent >= minDiscount);
  if (genre) list = list.filter(d => (d.genres || []).includes(genre));
  if (publisher) list = list.filter(d => companyNames(d).includes(publisher));

  const sortKey = sortSelect.value;
  list = list.slice().sort((a, b) => {
    if (a.on_sale !== b.on_sale) return a.on_sale ? -1 : 1; // 할인 중인 게임을 우선 표시
    switch (sortKey) {
      case 'price_asc': return a.final_price - b.final_price;
      case 'price_desc': return b.final_price - a.final_price;
      case 'name_asc': return a.name.localeCompare(b.name, 'ko');
      case 'review_desc': return b.review_rank - a.review_rank;
      default: return b.discount_percent - a.discount_percent;
    }
  });

  const limit = parseInt(limitInput.value, 10);
  const shown = limit > 0 ? list.slice(0, limit) : list;

  grid.innerHTML = '';
  empty.hidden = shown.length > 0;

  const frag = document.createDocumentFragment();
  for (const d of shown) {
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
    img.decoding = 'async';
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

    let reviewEl = null;
    if (d.review_desc) {
      reviewEl = document.createElement('div');
      const tier = CONFIG.reviewTier(d.review_rank);
      reviewEl.className = `review review-${tier}`;
      reviewEl.textContent = d.review_desc;
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
    body.append(title, ...(studioEl ? [studioEl] : []), genres, ...(reviewEl ? [reviewEl] : []), priceRow);
    card.append(thumb, body);
    frag.appendChild(card);
  }
  grid.appendChild(frag);
}

async function fetchDeals(forceRefresh) {
  if (forceRefresh) {
    try {
      const res = await fetch(CONFIG.refreshUrl);
      if (res.ok) return res;
    } catch (err) {
      // 백엔드 없는 정적 배포(GitHub Pages)에서는 무시하고 data.json으로 대체
    }
  }
  // 캐시 버스팅 없이 요청 -> 데이터는 6시간마다만 바뀌므로 브라우저/CDN 캐시를 그대로 활용한다.
  // (강제 새로고침은 위에서 이미 refreshUrl로 처리됨)
  return fetch(CONFIG.dataUrl);
}

async function load(forceRefresh) {
  meta.textContent = '불러오는 중...';
  try {
    const res = await fetchDeals(forceRefresh);
    const payload = await res.json();
    if (payload.error) throw new Error(payload.error);
    deals = payload.deals || [];
    usdKrwRate = payload.usd_krw_rate || null;
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

function debounce(fn, delayMs) {
  let timer = null;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delayMs);
  };
}

search.addEventListener('input', debounce(render, 150));
genreFilter.addEventListener('change', render);
publisherFilter.addEventListener('change', render);
discountFilter.addEventListener('change', render);
sortSelect.addEventListener('change', render);
limitInput.addEventListener('input', render);
refreshBtn.addEventListener('click', () => load(true));
homeLink.addEventListener('click', () => {
  search.value = '';
  genreFilter.value = '';
  publisherFilter.value = '';
  discountFilter.value = '0';
  sortSelect.value = 'discount_desc';
  limitInput.value = '';
  render();
});

load(false);
