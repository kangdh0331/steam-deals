let deals = [];

const grid = document.getElementById('grid');
const empty = document.getElementById('empty');
const meta = document.getElementById('meta');
const search = document.getElementById('search');
const sortSelect = document.getElementById('sort');
const refreshBtn = document.getElementById('refresh');

function formatPrice(value, currency) {
  const formatted = new Intl.NumberFormat('ko-KR').format(Math.round(value));
  return currency === 'KRW' ? `${formatted}원` : `${formatted} ${currency}`;
}

function render() {
  const q = search.value.trim().toLowerCase();
  let list = deals.filter(d => d.name.toLowerCase().includes(q));

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

    const priceRow = document.createElement('div');
    priceRow.className = 'price-row';
    const discountEl = document.createElement('span');
    discountEl.className = 'discount';
    discountEl.textContent = `-${d.discount_percent}%`;
    const originalEl = document.createElement('span');
    originalEl.className = 'original';
    originalEl.textContent = formatPrice(d.original_price, d.currency);
    const finalEl = document.createElement('span');
    finalEl.className = 'final';
    finalEl.textContent = formatPrice(d.final_price, d.currency);

    priceRow.append(discountEl, originalEl, finalEl);
    body.append(title, priceRow);
    card.append(thumb, body);
    frag.appendChild(card);
  }
  grid.appendChild(frag);
}

async function load(forceRefresh) {
  meta.textContent = '불러오는 중...';
  try {
    const res = await fetch(forceRefresh ? '/api/refresh' : '/api/deals');
    const payload = await res.json();
    if (payload.error) throw new Error(payload.error);
    deals = payload.deals || [];
    const fetchedAt = payload.fetched_at
      ? new Date(payload.fetched_at * 1000).toLocaleString('ko-KR')
      : '알 수 없음';
    meta.textContent = `할인 중인 게임 ${deals.length}개 · 마지막 갱신: ${fetchedAt}`;
    render();
  } catch (err) {
    meta.textContent = `불러오기 실패: ${err.message}`;
  }
}

search.addEventListener('input', render);
sortSelect.addEventListener('change', render);
refreshBtn.addEventListener('click', () => load(true));

load(false);
