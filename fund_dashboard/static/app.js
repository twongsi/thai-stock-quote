/* Thai Fund Dashboard — ฝั่งหน้าเว็บ
   ไม่มี dependency ภายนอก กราฟทั้งหมดวาดด้วย SVG เอง เพื่อให้เปิดใช้งานแบบ offline ได้ */

// ---------------------------------------------------------------- ค่าคงที่
const SERIES_COLORS = [
  '#c98500', '#199e70', '#3987e5', '#d55181',
  '#008300', '#e66767', '#9085e9', '#d95926',
];
// ไล่สีระดับความเสี่ยง 1→8 (เขียว → เหลือง → แดง) ใช้กับแถบวัดระดับเท่านั้น ไม่ใช่สีของกราฟ
const RISK_RAMP = ['#199e70', '#3d9e5c', '#7a9b3c', '#a89228', '#c98500', '#d95926', '#dd4545', '#c4314b'];
const UP = '#34d399';
const DOWN = '#fb7185';
const TH_MONTHS = ['ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.', 'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.'];
const RANGE_DAYS = { '1M': 30, '3M': 91, '6M': 182, '1Y': 365, '3Y': 1095, '5Y': 1825, MAX: null };
const PERIOD_LABEL = {
  '1M': '1 เดือน', '3M': '3 เดือน', '6M': '6 เดือน', YTD: 'ตั้งแต่ต้นปี',
  '1Y': '1 ปี', '3Y': '3 ปี (ต่อปี)', '5Y': '5 ปี (ต่อปี)', MAX: 'ตั้งแต่เริ่มมีข้อมูล',
};
const TILE_PERIODS = ['1M', '3M', '6M', '1Y', '3Y', 'MAX'];

// ---------------------------------------------------------------- ตัวช่วยจัดรูปแบบ
const $ = (sel) => document.querySelector(sel);
const el = (tag, attrs = {}, html = '') => {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined) continue;
    if (k === 'class') node.className = v; else node.setAttribute(k, v);
  }
  if (html) node.innerHTML = html;
  return node;
};
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

function num(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
  return Number(value).toLocaleString('th-TH', { minimumFractionDigits: digits, maximumFractionDigits: digits });
}
function pct(fraction, digits = 2, signed = true) {
  if (fraction === null || fraction === undefined || Number.isNaN(Number(fraction))) return '—';
  const value = Number(fraction) * 100;
  const sign = signed && value > 0 ? '+' : '';
  return `${sign}${num(value, digits)}%`;
}
function pctRaw(value, digits = 2, signed = false) {
  if (value === null || value === undefined || value === '' || Number.isNaN(Number(value))) return '—';
  return pct(Number(value) / 100, digits, signed);
}
function money(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
  const v = Number(value);
  if (Math.abs(v) >= 1e9) return `฿${num(v / 1e6, 0)} <small>ล้าน</small>`;
  if (Math.abs(v) >= 1e6) return `฿${num(v / 1e6, 1)} <small>ล้าน</small>`;
  return `฿${num(v, 0)}`;
}
function thaiDate(iso) {
  if (!iso) return '—';
  const d = new Date(`${String(iso).slice(0, 10)}T00:00:00`);
  if (Number.isNaN(d.getTime())) return String(iso);
  return `${d.getDate()} ${TH_MONTHS[d.getMonth()]} ${d.getFullYear() + 543}`;
}
function thaiMonth(date) { return `${TH_MONTHS[date.getMonth()]} ${String(date.getFullYear() + 543).slice(2)}`; }
const signClass = (v) => (v === null || v === undefined ? 'muted' : (v > 0 ? 'up' : (v < 0 ? 'down' : 'muted')));
const toDate = (iso) => new Date(`${iso}T00:00:00`);

// ---------------------------------------------------------------- state
const state = {
  meta: null,
  fund: null,           // bundle ของกองหลัก
  compare: [],          // [{code, class_name, name_th, history}]
  range: '1Y',
  window: '1Y',
  showTable: false,
  browse: null,
};

async function api(path, params = {}) {
  const url = new URL(path, location.origin);
  Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, v); });
  const res = await fetch(url);
  const data = await res.json();
  if (data.error) throw new Error(data.error);
  return data;
}

function showAlert(message, kind = 'warn') {
  const box = $('#alert');
  box.className = `notice ${kind}`;
  box.innerHTML = message;
  box.classList.remove('hidden');
}
function hideAlert() { $('#alert').classList.add('hidden'); }

// ---------------------------------------------------------------- กราฟเส้น (SVG)
const SVG_NS = 'http://www.w3.org/2000/svg';
function svgEl(name, attrs = {}) {
  const node = document.createElementNS(SVG_NS, name);
  for (const [k, v] of Object.entries(attrs)) if (v !== null && v !== undefined) node.setAttribute(k, v);
  return node;
}
function niceTicks(min, max, count = 5) {
  if (!Number.isFinite(min) || !Number.isFinite(max) || min === max) return [min];
  const raw = (max - min) / count;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) || mag * 10;
  const out = [];
  for (let t = Math.ceil(min / step) * step; t <= max + 1e-9; t += step) out.push(Number(t.toFixed(10)));
  return out;
}

/** วาดกราฟเส้นหลายเส้นลงใน <svg>
 *  series: [{ name, color, points: [{t: Date, v: number, nav?: number}] }] */
function drawLineChart(svg, series, opts = {}) {
  const tip = opts.tooltip;
  svg.innerHTML = '';
  const width = svg.clientWidth || svg.parentElement.clientWidth || 720;
  const height = Number(svg.getAttribute('height')) || 320;
  svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
  const pad = { t: 14, r: opts.labelWidth ?? 58, b: 26, l: 46 };

  const all = series.flatMap((s) => s.points);
  if (!all.length) {
    svg.appendChild(svgEl('rect', { x: 0, y: 0, width, height, fill: 'transparent' }));
    const text = svgEl('text', { x: width / 2, y: height / 2, 'text-anchor': 'middle', fill: 'var(--text-3)', 'font-size': 13 });
    text.textContent = 'ไม่มีข้อมูลในช่วงเวลานี้';
    svg.appendChild(text);
    return;
  }

  const tMin = Math.min(...all.map((p) => +p.t));
  const tMax = Math.max(...all.map((p) => +p.t));
  let vMin = Math.min(...all.map((p) => p.v));
  let vMax = Math.max(...all.map((p) => p.v));
  const span = (vMax - vMin) || Math.abs(vMax) * 0.1 || 1;
  vMin -= span * 0.08; vMax += span * 0.08;

  const x = (t) => pad.l + ((+t - tMin) / ((tMax - tMin) || 1)) * (width - pad.l - pad.r);
  const y = (v) => height - pad.b - ((v - vMin) / ((vMax - vMin) || 1)) * (height - pad.t - pad.b);

  // เส้นกริดแนวนอน + แกน y
  for (const tick of niceTicks(vMin, vMax, 4)) {
    const yy = y(tick);
    if (yy < pad.t - 2 || yy > height - pad.b + 2) continue;
    svg.appendChild(svgEl('line', { x1: pad.l, x2: width - pad.r, y1: yy, y2: yy, stroke: 'var(--grid)', 'stroke-width': 1 }));
    const label = svgEl('text', { x: pad.l - 8, y: yy + 4, 'text-anchor': 'end', fill: 'var(--text-3)', 'font-size': 11 });
    label.textContent = opts.yFormat ? opts.yFormat(tick) : num(tick, tick >= 100 ? 0 : 2);
    svg.appendChild(label);
  }

  // แกน x — ป้ายเดือนแบบไทย
  const ticks = 5;
  for (let i = 0; i < ticks; i += 1) {
    const t = tMin + ((tMax - tMin) / (ticks - 1)) * i;
    const label = svgEl('text', {
      x: x(t), y: height - 6, 'text-anchor': i === 0 ? 'start' : (i === ticks - 1 ? 'end' : 'middle'),
      fill: 'var(--text-3)', 'font-size': 11,
    });
    label.textContent = thaiMonth(new Date(t));
    svg.appendChild(label);
  }

  // เส้นข้อมูล
  series.forEach((s) => {
    if (!s.points.length) return;
    const path = s.points.map((p, i) => `${i ? 'L' : 'M'}${x(p.t).toFixed(1)},${y(p.v).toFixed(1)}`).join(' ');
    if (series.length === 1) {
      const area = `${path} L${x(s.points[s.points.length - 1].t).toFixed(1)},${height - pad.b} L${x(s.points[0].t).toFixed(1)},${height - pad.b} Z`;
      svg.appendChild(svgEl('path', { d: area, fill: s.color, 'fill-opacity': 0.1, stroke: 'none' }));
    }
    svg.appendChild(svgEl('path', { d: path, fill: 'none', stroke: s.color, 'stroke-width': 2, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }));

    const last = s.points[s.points.length - 1];
    svg.appendChild(svgEl('circle', { cx: x(last.t), cy: y(last.v), r: 4, fill: s.color, stroke: 'var(--surface)', 'stroke-width': 2 }));
    // ป้ายค่าล่าสุดติดปลายเส้น (direct label)
    const lx = Math.min(x(last.t) + 8, width - pad.r + 4);
    const ly = Math.max(pad.t + 9, Math.min(y(last.v), height - pad.b - 2));
    const text = opts.labelFormat ? opts.labelFormat(last.v) : num(last.v, 2);
    const box = svgEl('rect', { x: lx, y: ly - 11, width: Math.max(38, text.length * 7.2), height: 18, rx: 5, fill: s.color, 'fill-opacity': 0.16, stroke: s.color, 'stroke-opacity': 0.5 });
    svg.appendChild(box);
    const label = svgEl('text', { x: lx + 5, y: ly + 3, fill: 'var(--text)', 'font-size': 11, 'font-family': 'var(--mono)' });
    label.textContent = text;
    svg.appendChild(label);
  });

  // ---- เลเยอร์ hover: เส้นตั้ง + จุด + tooltip ----
  if (!tip) return;
  const hover = svgEl('g', { visibility: 'hidden' });
  const vline = svgEl('line', { y1: pad.t, y2: height - pad.b, stroke: 'var(--text-3)', 'stroke-width': 1 });
  hover.appendChild(vline);
  const dots = series.map((s) => {
    const dot = svgEl('circle', { r: 4.5, fill: s.color, stroke: 'var(--surface)', 'stroke-width': 2 });
    hover.appendChild(dot);
    return dot;
  });
  svg.appendChild(hover);

  const overlay = svgEl('rect', { x: pad.l, y: pad.t, width: Math.max(1, width - pad.l - pad.r), height: Math.max(1, height - pad.t - pad.b), fill: 'transparent' });
  svg.appendChild(overlay);

  const nearest = (points, t) => {
    let lo = 0; let hi = points.length - 1;
    while (lo < hi) { const mid = (lo + hi) >> 1; if (+points[mid].t < t) lo = mid + 1; else hi = mid; }
    const a = points[Math.max(0, lo - 1)]; const b = points[lo];
    return Math.abs(+a.t - t) <= Math.abs(+b.t - t) ? a : b;
  };

  const move = (event) => {
    const rect = svg.getBoundingClientRect();
    const px = ((event.touches ? event.touches[0].clientX : event.clientX) - rect.left) * (width / rect.width);
    const t = tMin + ((px - pad.l) / Math.max(1, width - pad.l - pad.r)) * (tMax - tMin);
    hover.setAttribute('visibility', 'visible');
    vline.setAttribute('x1', x(t)); vline.setAttribute('x2', x(t));
    const rows = [];
    series.forEach((s, i) => {
      if (!s.points.length) { dots[i].setAttribute('visibility', 'hidden'); return; }
      const point = nearest(s.points, t);
      dots[i].setAttribute('visibility', 'visible');
      dots[i].setAttribute('cx', x(point.t)); dots[i].setAttribute('cy', y(point.v));
      rows.push({ color: s.color, name: s.name, point });
    });
    if (!rows.length) return;
    const stamp = rows[0].point.t;
    tip.innerHTML = `<div class="t-date">${thaiDate(stamp.toISOString().slice(0, 10))}</div>` + rows.map((r) => `
      <div class="t-row"><span><span style="display:inline-block;width:9px;height:3px;border-radius:2px;background:${r.color};vertical-align:middle;margin-right:6px"></span>${esc(r.name)}</span>
      <b>${opts.tipFormat ? opts.tipFormat(r.point) : num(r.point.v, 4)}</b></div>`).join('');
    tip.hidden = false;
    const wrapRect = svg.parentElement.getBoundingClientRect();
    const left = (event.touches ? event.touches[0].clientX : event.clientX) - wrapRect.left;
    tip.style.left = `${Math.min(Math.max(left + 14, 4), wrapRect.width - tip.offsetWidth - 4)}px`;
    tip.style.top = `${Math.max(8, (event.touches ? event.touches[0].clientY : event.clientY) - wrapRect.top - 20)}px`;
  };
  const leave = () => { hover.setAttribute('visibility', 'hidden'); tip.hidden = true; };
  overlay.addEventListener('mousemove', move);
  overlay.addEventListener('mouseleave', leave);
  overlay.addEventListener('touchmove', move, { passive: true });
  overlay.addEventListener('touchend', leave);
}

// ---------------------------------------------------------------- ส่วนแสดงผล
/** กองที่ไม่ได้แบ่ง class จะได้ fund_class_name = "main" ซึ่งไม่ควรเอาไปโชว์แทนรหัสกองทุน */
function displayCode(bundle) {
  const name = bundle.class_name || '';
  return (!name || name === 'main' || name === '-') ? bundle.code : name;
}

function renderFundHead(bundle) {
  const g = bundle.general;
  const risk = bundle.risk_spectrum || {};
  const chips = [];
  if (g.policy_desc) chips.push(`<span class="chip">${esc(g.policy_desc)}</span>`);
  if (g.feeder_master_fund) chips.push('<span class="chip">Feeder fund</span>');
  if (risk.level) chips.push(`<span class="chip ${risk.level >= 6 ? 'danger' : ''}">ความเสี่ยงระดับ ${risk.level} / 8</span>`);
  chips.push(`<span class="chip">${bundle.dividend_policy.label || 'ไม่ระบุนโยบายปันผล'}</span>`);
  if (g.fx_policy) chips.push(`<span class="chip">${esc(g.fx_policy.slice(0, 44))}</span>`);
  if (g.tax_incentive) chips.push(`<span class="chip">สิทธิลดหย่อนภาษี ${esc(g.tax_incentive)}</span>`);
  if (g.management_style) chips.push(`<span class="chip">${g.management_style === 'PM' ? 'บริหารเชิงรับ (Passive)' : 'บริหารเชิงรุก (Active)'}</span>`);
  chips.push(`<span class="chip ${String(g.status).toLowerCase() === 'registered' ? 'ok' : ''}">${g.status === 'Registered' ? 'เปิดดำเนินการ' : esc(g.status)}</span>`);

  const realClasses = (bundle.classes || []).filter((name) => name && name !== 'main' && name !== '-');
  const classChips = realClasses.length > 1 ? realClasses.map((name) => `
    <button class="chip mono ${name === bundle.class_name ? 'active' : ''}" data-class="${esc(name)}">${esc(name)}</button>`).join('') : '';

  const h = bundle.highlights || {};
  const mini = [
    ['ขนาดกองทุน', money(bundle.latest_nav.net_asset)],
    ['ค่าธรรมเนียมรวม', h.total_fee ? `${num(h.total_fee.value, 2)}<small>%/ปี</small>` : '—'],
    ['ซื้อขั้นต่ำ', h.minimum_sub !== null && h.minimum_sub !== undefined ? `฿${num(h.minimum_sub, 0)}` : '—'],
    ['รับเงินค่าขายคืน', h.settlement ? esc(h.settlement) : '—'],
  ];

  $('#fund-head').innerHTML = `
    <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">
      <span class="fund-code">${esc(displayCode(bundle))}</span>
      <h1 class="fund-name">${esc(g.name_th || bundle.code)}</h1>
    </div>
    <div class="fund-sub">${esc(g.name_en)} · ${esc(g.amc_th)} · <span class="muted">${esc(bundle.proj_id)}</span></div>
    <div class="chips">${chips.join('')}</div>
    ${classChips ? `<div class="chips" style="margin-top:10px">${classChips}</div>` : ''}
    <div class="mini-stats">
      ${mini.map(([k, v]) => `<div><div class="k">${k}</div><div class="v">${v}</div></div>`).join('')}
    </div>`;

  $('#fund-head').querySelectorAll('[data-class]').forEach((btn) => {
    btn.addEventListener('click', () => loadFund(bundle.code, btn.dataset.class));
  });
  document.title = `${displayCode(bundle)} — Thai Fund Dashboard`;
}

function renderNavCard(bundle) {
  const n = bundle.latest_nav;
  const changeValue = (n.nav !== null && n.previous_nav) ? n.nav - n.previous_nav : null;
  const arrow = n.daily_change > 0 ? '▲' : (n.daily_change < 0 ? '▼' : '•');
  $('#nav-card').innerHTML = `
    <div class="k">NAV ล่าสุด</div>
    <div class="hero">${num(n.nav, 4)}</div>
    <div class="delta ${signClass(n.daily_change)}">${arrow} ${changeValue === null ? '—' : num(changeValue, 4)} &nbsp; ${pct(n.daily_change)}</div>
    <div class="asof">ณ วันที่ ${thaiDate(n.nav_date)} · NAV ประกาศในวันทำการถัดไป</div>
    <div class="nav-prices">
      <div><div class="k">ราคาขาย (ซื้อหน่วย)</div><div class="v" style="font-family:var(--mono)">${num(n.sell_price, 4)}</div></div>
      <div><div class="k">ราคารับซื้อคืน</div><div class="v" style="font-family:var(--mono)">${num(n.buy_price, 4)}</div></div>
    </div>`;
}

function renderTiles(bundle) {
  const byPeriod = Object.fromEntries((bundle.summary.periods || []).map((p) => [p.period, p]));
  const peer = bundle.peer;
  $('#tiles').innerHTML = TILE_PERIODS.map((key) => {
    const p = byPeriod[key];
    const value = p && p.available ? (key === 'MAX' ? p.return : (p.annualized ?? p.return)) : null;
    const peerValue = peer && peer.median ? peer.median[key] : null;
    let note = '';
    if (peerValue !== null && peerValue !== undefined) {
      note = `กลุ่มเดียวกัน ${pct(peerValue)}`;
    } else if (key === 'MAX' && bundle.summary.first_date) {
      note = `สะสมตั้งแต่ ${thaiDate(bundle.summary.first_date)}`;
    } else if (p && p.available === false) {
      note = 'ข้อมูลไม่ครบช่วง';
    }
    return `<div class="tile">
      <div class="k">${PERIOD_LABEL[key]}</div>
      <div class="v ${signClass(value)}">${pct(value)}</div>
      <div class="peer">${note}</div>
    </div>`;
  }).join('');
}

function rangePoints(history, range) {
  const days = RANGE_DAYS[range];
  if (!days) return history;
  const last = toDate(history[history.length - 1].d);
  const cut = new Date(last.getTime() - days * 86400000);
  const sliced = history.filter((row) => toDate(row.d) >= cut);
  return sliced.length > 1 ? sliced : history;
}

function renderChart() {
  const bundle = state.fund;
  if (!bundle || !bundle.history.length) return;
  const svg = $('#nav-chart');
  const tip = $('#chart-tip');
  const indexed = state.compare.length > 0;

  const build = (history, name, color) => {
    const points = rangePoints(history, state.range);
    const base = points[0] ? points[0].nav : 1;
    return {
      name, color,
      points: points.map((row) => ({ t: toDate(row.d), v: indexed ? (row.nav / base) * 100 : row.nav, nav: row.nav })),
    };
  };

  const series = [build(bundle.history, displayCode(bundle), SERIES_COLORS[0])];
  state.compare.forEach((fund, i) => {
    series.push(build(fund.history, displayCode(fund), SERIES_COLORS[(i + 1) % SERIES_COLORS.length]));
  });

  drawLineChart(svg, series, {
    tooltip: tip,
    labelFormat: (v) => num(v, indexed ? 1 : 2),
    yFormat: (v) => num(v, indexed ? 0 : (v >= 100 ? 0 : 2)),
    tipFormat: (p) => (indexed ? `${num(p.v, 1)} (NAV ${num(p.nav, 4)})` : num(p.v, 4)),
  });

  const first = series[0].points[0];
  const last = series[0].points[series[0].points.length - 1];
  const change = first && last && first.nav ? last.nav / first.nav - 1 : null;
  $('#chart-sub').innerHTML = `ช่วง ${state.range === 'MAX' ? 'ทั้งหมด' : state.range} · ${esc(series[0].name)} <span class="${signClass(change)}">${pct(change)}</span>`;
  $('#chart-mode-note').textContent = indexed
    ? 'ปรับฐานเป็น 100 ที่จุดเริ่มต้น — เทียบผลตอบแทน (NAV หักค่าธรรมเนียมแล้ว)'
    : 'NAV ต่อหน่วย (บาท)';

  renderCompareChips();
  renderChartTable(series, indexed);
}

function renderCompareChips() {
  const bundle = state.fund;
  const chips = [`<span class="item"><span class="key" style="background:${SERIES_COLORS[0]}"></span>${esc(displayCode(bundle))}</span>`];
  state.compare.forEach((fund, i) => {
    chips.push(`<span class="item"><span class="key" style="background:${SERIES_COLORS[(i + 1) % SERIES_COLORS.length]}"></span>${esc(displayCode(fund))}
      <button class="btn" data-remove="${esc(fund.code)}" style="padding:1px 6px;font-size:11px;line-height:1.3">✕</button></span>`);
  });
  const box = $('#compare-chips');
  box.innerHTML = `<span class="sub" style="margin:0">เลือกกองที่จะเปรียบเทียบ</span>${chips.join('')}`
    + '<span class="item"><input id="chart-compare-input" class="chip mono" style="width:150px;padding:4px 10px" placeholder="+ เพิ่มรหัสกองทุน" aria-label="เพิ่มกองทุนที่จะเปรียบเทียบบนกราฟ"></span>';
  const input = $('#chart-compare-input');
  input.addEventListener('keydown', (event) => {
    if (event.key !== 'Enter') return;
    const value = input.value.trim();
    input.value = '';
    addCompare(value);
  });
  box.querySelectorAll('[data-remove]').forEach((btn) => btn.addEventListener('click', () => {
    state.compare = state.compare.filter((f) => f.code !== btn.dataset.remove);
    renderChart();
    loadCompareTable();
  }));
}

function renderChartTable(series, indexed) {
  if (!state.showTable) { $('#chart-table').classList.add('hidden'); return; }
  const box = $('#chart-table');
  box.classList.remove('hidden');
  // สรุปเป็นรายเดือน เพื่อให้ตารางอ่านได้จริง (ข้อมูลรายวันยาวเกินไป)
  const monthly = new Map();
  series.forEach((s, si) => {
    s.points.forEach((p) => {
      const key = `${p.t.getFullYear()}-${String(p.t.getMonth() + 1).padStart(2, '0')}`;
      if (!monthly.has(key)) monthly.set(key, {});
      monthly.get(key)[si] = p;
    });
  });
  const rows = [...monthly.entries()].slice(-36);
  box.innerHTML = `<table><thead><tr><th>เดือน</th>${series.map((s) => `<th class="num">${esc(s.name)}</th>`).join('')}</tr></thead>
    <tbody>${rows.map(([key, cells]) => {
      const [yy, mm] = key.split('-');
      return `<tr><td>${TH_MONTHS[Number(mm) - 1]} ${Number(yy) + 543}</td>${series.map((_, si) => {
        const point = cells[si];
        return `<td class="num">${point ? num(indexed ? point.v : point.nav, indexed ? 1 : 4) : '—'}</td>`;
      }).join('')}</tr>`;
    }).join('')}</tbody></table>`;
}

function renderCalculator() {
  const bundle = state.fund;
  const options = [
    ['1M', '1 เดือนก่อน'], ['6M', '6 เดือนก่อน'], ['1Y', '1 ปีก่อน'],
    ['3Y', '3 ปีก่อน'], ['5Y', '5 ปีก่อน'], ['MAX', 'วันแรกที่มีข้อมูล'],
  ];
  $('#calc-card').innerHTML = `
    <h2>ถ้าลงทุนไปแล้ว</h2>
    <div class="sub">คำนวณจากผลตอบแทนย้อนหลัง ไม่ใช่การรับประกันอนาคต</div>
    <div class="calc-row">
      <input id="calc-amount" type="number" min="0" step="1000" value="10000" aria-label="จำนวนเงินลงทุน">
      <select id="calc-period" aria-label="ช่วงเวลา">
        ${options.map(([v, label]) => `<option value="${v}" ${v === '3Y' ? 'selected' : ''}>เมื่อ ${label}</option>`).join('')}
      </select>
    </div>
    <div id="calc-result"></div>`;
  $('#calc-amount').addEventListener('input', updateCalculator);
  $('#calc-period').addEventListener('change', updateCalculator);
  updateCalculator();
}

function updateCalculator() {
  const bundle = state.fund;
  const amount = Number($('#calc-amount').value || 0);
  const key = $('#calc-period').value;
  const history = bundle.history;
  if (!history.length) return;
  const last = history[history.length - 1];
  const days = RANGE_DAYS[key];
  let start = history[0];
  if (days) {
    const cut = new Date(toDate(last.d).getTime() - days * 86400000);
    const candidates = history.filter((row) => toDate(row.d) <= cut);
    if (!candidates.length) {
      $('#calc-result').innerHTML = `<div class="notice">ข้อมูล NAV ย้อนหลังไม่ถึงช่วงเวลานี้ (เริ่มมีข้อมูล ${thaiDate(history[0].d)})</div>`;
      return;
    }
    start = candidates[candidates.length - 1];
  }
  const growth = last.nav / start.nav;
  const value = amount * growth;
  const gain = value - amount;
  $('#calc-result').innerHTML = `
    <div class="calc-out ${signClass(gain)}">฿${num(value, 0)}</div>
    <div class="${signClass(gain)}" style="font-family:var(--mono);font-size:14px">
      ${gain >= 0 ? '+' : '−'}฿${num(Math.abs(gain), 0)} (${pct(growth - 1)})
    </div>
    <div class="calc-note">
      ลงทุน ${thaiDate(start.d)} ถึง ${thaiDate(last.d)} · NAV หักค่าธรรมเนียมกองทุนแล้ว<br>
      ยังไม่รวมค่าธรรมเนียมขาย/รับซื้อคืน ภาษี และเงินปันผลที่จ่ายออก (ถ้ามี)
    </div>`;
}

function renderRiskCard() {
  const bundle = state.fund;
  const risk = bundle.risk_spectrum || {};
  const r1y = bundle.summary.risk_1y || {};
  const rall = bundle.summary.risk || {};
  const level = risk.level || 0;
  const meter = Array.from({ length: 8 }, (_, i) => {
    const step = i + 1;
    const state = step === level ? 'here' : (step < level ? 'on' : '');
    return `<i class="${state}" style="${step <= level ? `background:${RISK_RAMP[i]}` : ''}" title="ระดับความเสี่ยง ${step}"></i>`;
  }).join('');
  const recovery = rall.max_drawdown_recovery_days;
  $('#risk-card').innerHTML = `
    <h2>ความเสี่ยงแบบเข้าใจง่าย</h2>
    <div class="meter">${meter}</div>
    <div class="sub" style="margin-bottom:12px">${level ? `ระดับ ${level} จาก 8` : 'ไม่ระบุระดับความเสี่ยง'} — ${esc(risk.description || risk.label || '')}</div>
    <div class="kv"><span class="k">ความผันผวน <small>ต่อปี · 1 ปีล่าสุด</small></span><span class="v">${pct(r1y.volatility, 2, false)}</span></div>
    <div class="kv"><span class="k">ขาดทุนสูงสุดที่เคยเกิด <small>ช่วงข้อมูลทั้งหมด</small></span><span class="v down">${pct(rall.max_drawdown, 2, false)}</span></div>
    <div class="kv"><span class="k">Sharpe ratio <small>ผลตอบแทนต่อความเสี่ยง · 1 ปี</small></span><span class="v ${signClass(r1y.sharpe)}">${num(r1y.sharpe, 2)}</span></div>
    <div class="kv"><span class="k">ระยะเวลาฟื้นตัวจากจุดต่ำสุด</span><span class="v">${recovery ? `${Math.floor(recovery / 365) ? `${Math.floor(recovery / 365)} ปี ` : ''}${Math.round((recovery % 365) / 30)} เดือน` : 'ยังไม่ฟื้นกลับจุดเดิม'}</span></div>
    <div class="kv"><span class="k">วันที่ NAV เป็นบวก <small>สัดส่วนวันทำการ</small></span><span class="v">${pct(rall.positive_day_ratio, 1, false)}</span></div>`;
}

function renderPerfCard() {
  const perf = state.fund.sec_performance || { columns: [], rows: [] };
  const box = $('#perf-card');
  if (!perf.rows.length) {
    box.innerHTML = '<h2>ผลการดำเนินงานตาม factsheet</h2><div class="notice">ยังไม่มีข้อมูลผลการดำเนินงานจาก factsheet ของกองทุนนี้</div>';
    return;
  }
  const short = (label) => label.replace('ผลการดำเนินงานของ', '').replace('ความผันผวนของ', 'ผันผวน ').replace('กองทุนรวม', 'กองทุน').replace('ดัชนีชี้วัด', 'benchmark');
  box.innerHTML = `
    <h2>ผลการดำเนินงานตาม factsheet</h2>
    <div class="sub">ตัวเลขที่ บลจ. รายงานต่อ SEC · ข้อมูล ณ ${thaiDate(perf.as_of)} · หน่วย % ต่อปี</div>
    <div class="table-scroll"><table>
      <thead><tr><th>ช่วงเวลา</th>${perf.columns.map((c) => `<th class="num">${esc(short(c))}</th>`).join('')}</tr></thead>
      <tbody>${perf.rows.map((row) => `<tr><td>${esc(row.period)}</td>${perf.columns.map((c) => {
        const value = row.values[c];
        const isPerf = c.includes('ผลการดำเนินงาน');
        return `<td class="num ${isPerf ? signClass(Number(value)) : ''}">${pctRaw(value, 2, isPerf)}</td>`;
      }).join('')}</tr>`).join('')}</tbody>
    </table></div>`;
}

function renderStatCard() {
  const bundle = state.fund;
  const s = bundle.sec_statistics || {};
  const rall = bundle.summary.risk || {};
  const r1 = bundle.summary.risk_1y || {};
  const r3 = bundle.summary.risk_3y || {};
  $('#stat-card').innerHTML = `
    <h2>ค่าสถิติความเสี่ยง</h2>
    <div class="sub">ซ้าย = ตัวเลขที่ SEC เผยแพร่ (ณ ${thaiDate(s.as_of)}) · ขวา = คำนวณจาก NAV ย้อนหลังโดย dashboard นี้</div>
    <div class="table-scroll"><table>
      <thead><tr><th>ตัววัด</th><th class="num">จาก factsheet</th><th class="num">คำนวณเอง (1 ปี)</th><th class="num">คำนวณเอง (3 ปี)</th></tr></thead>
      <tbody>
        <tr><td>ความผันผวน (ต่อปี)</td><td class="num">—</td><td class="num">${pct(r1.volatility, 2, false)}</td><td class="num">${pct(r3.volatility, 2, false)}</td></tr>
        <tr><td>Sharpe ratio</td><td class="num">${num(s.sharpe_ratio, 2)}</td><td class="num">${num(r1.sharpe, 2)}</td><td class="num">${num(r3.sharpe, 2)}</td></tr>
        <tr><td>Sortino ratio</td><td class="num">—</td><td class="num">${num(r1.sortino, 2)}</td><td class="num">${num(r3.sortino, 2)}</td></tr>
        <tr><td>ขาดทุนสูงสุด (Max drawdown)</td><td class="num">${pctRaw(s.max_drawdown)}</td><td class="num down">${pct(r1.max_drawdown, 2, false)}</td><td class="num down">${pct(r3.max_drawdown, 2, false)}</td></tr>
        <tr><td>Beta เทียบ benchmark</td><td class="num">${num(s.beta, 2)}</td><td class="num">—</td><td class="num">—</td></tr>
        <tr><td>Alpha</td><td class="num">${num(s.alpha, 2)}</td><td class="num">—</td><td class="num">—</td></tr>
        <tr><td>Tracking error</td><td class="num">${pctRaw(s.tracking_error)}</td><td class="num">—</td><td class="num">—</td></tr>
        <tr><td>Portfolio turnover ratio</td><td class="num">${num(s.portfolio_turnover_ratio, 2)}</td><td class="num">—</td><td class="num">—</td></tr>
        <tr><td>ระยะเวลาฟื้นตัว (Recovering period)</td><td class="num">${esc(s.recovering_period || '—')}</td><td class="num">—</td><td class="num">—</td></tr>
      </tbody>
    </table></div>
    <div class="sub" style="margin:10px 0 0">คำนวณด้วยอัตราปราศจากความเสี่ยง ${pct(rall.risk_free_rate ?? 0.02, 2, false)} ต่อปี · ปรับได้ที่ RISK_FREE_RATE ในไฟล์ .env</div>`;
}

function barList(items, color) {
  if (!items.length) return '<div class="notice">ยังไม่มีข้อมูลส่วนนี้จาก SEC</div>';
  const max = Math.max(...items.map((i) => i.ratio)) || 100;
  return items.map((item) => `
    <div class="bar-row">
      <div>
        <div class="bar-label" title="${esc(item.name)}">${esc(item.name)}</div>
        <div class="bar-track"><div class="bar-fill" style="width:${Math.max(2, (item.ratio / max) * 100)}%;background:${color}"></div></div>
      </div>
      <div class="bar-val">${num(item.ratio, 2)}%</div>
    </div>`).join('');
}

function renderPortfolio() {
  const bundle = state.fund;
  const alloc = bundle.allocation || [];
  const top5 = bundle.top5 || [];
  $('#alloc-card').innerHTML = `
    <h2>สัดส่วนประเภททรัพย์สิน</h2>
    <div class="sub">${alloc.length ? `ข้อมูล ณ ${thaiDate(alloc[0].as_of)}` : ''}</div>
    ${barList(alloc, SERIES_COLORS[2])}`;
  $('#top5-card').innerHTML = `
    <h2>ทรัพย์สินที่ลงทุนสูงสุด 5 อันดับ</h2>
    <div class="sub">${top5.length ? `ข้อมูล ณ ${thaiDate(top5[0].as_of)}` : ''}</div>
    ${barList(top5, SERIES_COLORS[1])}`;
}

function renderFeesAndTerms() {
  const bundle = state.fund;
  const fees = bundle.fees || [];
  const amcFees = bundle.amc_fees || [];
  const sub = bundle.subscription || {};
  const dividends = bundle.dividend_history || [];

  $('#fee-card').innerHTML = `
    <h2>ค่าธรรมเนียม</h2>
    <div class="sub">อัตราที่เรียกเก็บจริง (actual) เทียบกับเพดานตามหนังสือชี้ชวน</div>
    <div class="table-scroll"><table>
      <thead><tr><th>รายการ</th><th class="num">เพดาน</th><th class="num">เก็บจริง</th></tr></thead>
      <tbody>${(fees.length ? fees : amcFees).slice(0, 10).map((f) => `
        <tr><td title="${esc(f.remark || '')}">${esc(f.type || '')}</td>
        <td class="num">${f.rate === null || f.rate === undefined ? '—' : `${num(f.rate, 2)}%`}</td>
        <td class="num">${f.actual === null || f.actual === undefined ? '—' : `${num(f.actual, 2)}%`}</td></tr>`).join('')}
      </tbody>
    </table></div>`;

  $('#terms-card').innerHTML = `
    <h2>เงื่อนไขการซื้อขาย</h2>
    <div class="sub">${sub.as_of ? `ข้อมูล ณ ${thaiDate(sub.as_of)}` : ''}</div>
    <div class="kv"><span class="k">ซื้อครั้งแรก / ครั้งถัดไป</span><span class="v">${sub.minimum_sub_ipo !== null ? `฿${num(sub.minimum_sub_ipo, 0)}` : '—'} / ${sub.minimum_sub !== null ? `฿${num(sub.minimum_sub, 0)}` : '—'}</span></div>
    <div class="kv"><span class="k">ขายคืนขั้นต่ำ</span><span class="v">${sub.minimum_redempt !== null ? `฿${num(sub.minimum_redempt, 0)}` : '—'}</span></div>
    <div class="kv"><span class="k">วันทำการซื้อ</span><span class="v" style="font-family:var(--font)">${esc(sub.subscription_period || '—')}</span></div>
    <div class="kv"><span class="k">วันทำการขายคืน</span><span class="v" style="font-family:var(--font)">${esc(sub.redemption_period || '—')}</span></div>
    <div class="kv"><span class="k">ระยะเวลารับเงินค่าขายคืน</span><span class="v">${esc(sub.settlement_period || '—')}</span></div>
    <div class="kv"><span class="k">นโยบายปันผล</span><span class="v" style="font-family:var(--font)">${esc(bundle.dividend_policy.label || '—')}</span></div>
    ${dividends.length ? `<div class="sub" style="margin:12px 0 4px">ปันผลล่าสุด</div>
      <div class="table-scroll"><table><thead><tr><th>วันจ่าย</th><th class="num">บาท/หน่วย</th></tr></thead>
      <tbody>${dividends.slice(0, 5).map((d) => `<tr><td>${thaiDate(d.dividend_date || d.book_close_date)}</td><td class="num">${num(d.value, 4)}</td></tr>`).join('')}</tbody></table></div>` : ''}`;

  const g = bundle.general;
  const benchmark = (bundle.benchmarks || [])[0];
  const links = (bundle.factsheet_urls || []);
  $('#profile-card').innerHTML = `
    <h2>ข้อมูลกองทุน</h2>
    <div class="kv"><span class="k">เลขที่โครงการ</span><span class="v">${esc(bundle.proj_id)}</span></div>
    <div class="kv"><span class="k">วันจดทะเบียนกองทุน</span><span class="v" style="font-family:var(--font)">${thaiDate(g.regis_date)}</span></div>
    <div class="kv"><span class="k">ISIN</span><span class="v">${esc(g.isin || '—')}</span></div>
    <div class="kv"><span class="k">ชนิดหน่วยลงทุน</span><span class="v" style="font-family:var(--font)">${esc(g.class_detail || bundle.class_name || '—')}</span></div>
    ${g.feeder_master_fund ? `<div class="kv"><span class="k">กองทุนหลัก (master fund)</span><span class="v" style="font-family:var(--font);text-align:right">${esc(g.feeder_master_fund)}${g.feeder_country ? `<br><small class="muted">${esc(g.feeder_country)}</small>` : ''}</span></div>` : ''}
    ${benchmark ? `<div class="sub" style="margin:12px 0 4px">ดัชนีชี้วัด (benchmark)</div><div style="font-size:12.5px;color:var(--text-2)">${esc(benchmark.benchmark)}</div>` : ''}
    ${g.investment_policy ? `<div class="sub" style="margin:12px 0 4px">นโยบายการลงทุน</div>
      <div style="font-size:12.5px;color:var(--text-2);max-height:150px;overflow:auto;white-space:pre-line">${esc(g.investment_policy)}</div>` : ''}
    ${links.length ? `<div style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap">
      ${links[0].pdf ? `<a class="btn" href="${esc(links[0].pdf)}" target="_blank" rel="noopener">Fund Factsheet (PDF)</a>` : ''}
      ${links[0].amc_url ? `<a class="btn" href="${esc(links[0].amc_url)}" target="_blank" rel="noopener">เว็บ บลจ.</a>` : ''}
    </div>` : ''}`;
}

// ---------------------------------------------------------------- ตารางเปรียบเทียบ
/** ช่วงที่ยาวกว่า 1 ปีให้ใช้ผลตอบแทนต่อปี เพื่อให้เทียบกันได้จริง */
function periodValue(fund, key) {
  const cell = (fund.periods || {})[key];
  if (!cell) return null;
  return cell.annualized ?? cell.return ?? null;
}
async function loadCompareTable() {
  const codes = [displayCode(state.fund), ...state.compare.map(displayCode)];
  const box = $('#compare-table');
  box.innerHTML = '<div class="skeleton" style="height:120px"></div>';
  try {
    const data = await api('/api/compare', { codes: codes.join(','), window: state.window });
    const rows = data.funds || [];
    if (!rows.length) { box.innerHTML = '<div class="notice">ยังไม่มีข้อมูลเปรียบเทียบ</div>'; return; }
    $('#compare-sub').innerHTML = `เทียบในหน้าต่างเดียวกัน ${thaiDate(data.start_date)} – ${thaiDate(data.end_date)} · เรียงตามผลตอบแทนในหน้าต่างนี้`
      + (data.errors && data.errors.length ? ` · <span class="down">${data.errors.map((e) => esc(`${e.code}: ${e.error}`)).join(' | ')}</span>` : '');
    box.innerHTML = `<table>
      <thead><tr>
        <th>กองทุน</th><th class="num">ผลตอบแทนในช่วง</th><th class="num">1 ปี</th><th class="num">3 ปี (ต่อปี)</th>
        <th class="num">ความผันผวน</th><th class="num">Max drawdown</th><th class="num">Sharpe</th><th class="num">NAV ล่าสุด</th>
      </tr></thead>
      <tbody>${rows.map((f, i) => `<tr>
        <td><span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:${SERIES_COLORS[i % SERIES_COLORS.length]};margin-right:8px"></span>
          <b>${esc(displayCode(f))}</b><br><small class="muted">${esc(f.name_th)}</small></td>
        <td class="num ${signClass(f.window_return)}">${pct(f.window_return)}</td>
        <td class="num ${signClass(periodValue(f, '1Y'))}">${pct(periodValue(f, '1Y'))}</td>
        <td class="num ${signClass(periodValue(f, '3Y'))}">${pct(periodValue(f, '3Y'))}</td>
        <td class="num">${pct(f.risk.volatility, 2, false)}</td>
        <td class="num down">${pct(f.risk.max_drawdown, 2, false)}</td>
        <td class="num ${signClass(f.risk.sharpe)}">${num(f.risk.sharpe, 2)}</td>
        <td class="num">${num(f.latest_nav, 4)}</td>
      </tr>`).join('')}</tbody></table>`;
  } catch (err) {
    box.innerHTML = `<div class="notice err">${esc(err.message)}</div>`;
  }
}

async function addCompare(code) {
  code = (code || '').trim();
  if (!code) return;
  if (state.compare.length >= 7) { showAlert('เปรียบเทียบได้สูงสุด 8 กองทุนพร้อมกัน'); return; }
  const primary = displayCode(state.fund).toUpperCase();
  if (code.toUpperCase() === primary || state.compare.some((f) => f.code.toUpperCase() === code.toUpperCase())) return;
  try {
    const data = await api('/api/fund', { code });
    state.compare.push({ code: data.code, class_name: data.class_name, name_th: data.general.name_th, history: data.history });
    renderChart();
    loadCompareTable();
    hideAlert();
  } catch (err) {
    showAlert(esc(err.message), 'err');
  }
}

// ---------------------------------------------------------------- โหลดกองทุน
function setRecent(code) {
  let list = [];
  try { list = JSON.parse(localStorage.getItem('tfd-recent') || '[]'); } catch { list = []; }
  list = [code, ...list.filter((c) => c !== code)].slice(0, 6);
  localStorage.setItem('tfd-recent', JSON.stringify(list));
  renderRecent(list);
}
function renderRecent(list) {
  if (!list || !list.length) { $('#recent').innerHTML = ''; return; }
  $('#recent').innerHTML = '<span>ดูล่าสุด</span>' + list.map((c) => `<button class="chip mono" data-code="${esc(c)}">${esc(c)}</button>`).join('');
  $('#recent').querySelectorAll('[data-code]').forEach((b) => b.addEventListener('click', () => loadFund(b.dataset.code)));
}

async function loadFund(code, className) {
  hideAlert();
  $('#fund-head').innerHTML = '<div class="skeleton" style="width:160px;height:28px"></div><div class="skeleton" style="width:65%;height:26px;margin-top:12px"></div><div class="skeleton" style="width:45%;height:14px;margin-top:10px"></div>';
  $('#nav-card').innerHTML = '<div class="k">NAV ล่าสุด</div><div class="skeleton" style="width:70%;height:40px;margin-top:10px"></div>';
  try {
    const bundle = await api('/api/fund', { code, class: className });
    state.fund = bundle;
    state.compare = [];
    if (!bundle.history.length) showAlert('กองทุนนี้ยังไม่มีข้อมูล NAV ย้อนหลังในช่วงที่ดึงมา — ตัวเลขผลตอบแทนและความเสี่ยงจะแสดงไม่ครบ');
    renderFundHead(bundle);
    renderNavCard(bundle);
    renderTiles(bundle);
    renderChart();
    renderCalculator();
    renderRiskCard();
    renderPerfCard();
    renderStatCard();
    renderPortfolio();
    renderFeesAndTerms();
    loadCompareTable();
    setRecent(displayCode(bundle));
    location.hash = encodeURIComponent(displayCode(bundle));
  } catch (err) {
    showAlert(`โหลดข้อมูลไม่สำเร็จ: ${esc(err.message)}`, 'err');
    $('#fund-head').innerHTML = `<div class="notice err">${esc(err.message)}</div>`;
    $('#nav-card').innerHTML = '';
  }
}

// ---------------------------------------------------------------- ค้นหา
let searchTimer = null;
function initSearch() {
  const input = $('#search');
  const box = $('#suggest');
  let items = [];
  let cursor = -1;

  const close = () => { box.hidden = true; cursor = -1; };
  const render = () => {
    if (!items.length) { close(); return; }
    box.innerHTML = items.map((f, i) => `
      <button role="option" data-code="${esc(f.classes && f.classes.length ? f.classes[0] : f.code)}" aria-selected="${i === cursor}">
        <span class="code">${esc(f.code)}</span>${esc(f.name_th)}
        <span class="sub">${esc(f.amc_th)}${f.classes && f.classes.length > 1 ? ` · ${f.classes.length} ชนิดหน่วย` : ''}</span>
      </button>`).join('');
    box.hidden = false;
    box.querySelectorAll('[data-code]').forEach((btn) => btn.addEventListener('mousedown', (e) => {
      e.preventDefault();
      input.value = '';
      close();
      loadFund(btn.dataset.code);
    }));
  };

  input.addEventListener('input', () => {
    clearTimeout(searchTimer);
    const q = input.value.trim();
    if (q.length < 2) { close(); return; }
    searchTimer = setTimeout(async () => {
      try {
        const data = await api('/api/search', { q });
        items = data.results || [];
        cursor = -1;
        render();
      } catch { close(); }
    }, 220);
  });

  input.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') { close(); return; }
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      if (box.hidden || !items.length) return;
      event.preventDefault();
      cursor = (cursor + (event.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length;
      render();
      return;
    }
    if (event.key === 'Enter') {
      const chosen = cursor >= 0 ? items[cursor] : null;
      const code = chosen ? (chosen.classes && chosen.classes.length ? chosen.classes[0] : chosen.code) : input.value.trim();
      if (!code) return;
      input.value = '';
      close();
      loadFund(code);
    }
  });
  input.addEventListener('blur', () => setTimeout(close, 120));
}

// ---------------------------------------------------------------- รายชื่อกองทุน (modal)
async function openBrowse() {
  const modal = $('#browse');
  modal.hidden = false;
  const body = $('#browse-body');
  body.innerHTML = '<div class="skeleton" style="height:200px"></div>';
  const data = await api('/api/funds', {
    q: $('#browse-q').value.trim(), amc: $('#browse-amc').value, policy: $('#browse-policy').value, limit: 400,
  });
  state.browse = data;
  if (!data.available) {
    body.innerHTML = `<div class="notice warn">ยังไม่ได้สร้างรายชื่อกองทุนในเครื่อง — รันคำสั่ง
      <code>python3 catalog.py --build</code> หนึ่งครั้ง แล้วรายชื่อกองทุนทั้งหมดจะขึ้นที่นี่</div>`
      + (data.funds && data.funds.length ? renderBrowseTable(data.funds) : '');
  } else {
    if ($('#browse-amc').options.length <= 1) {
      data.amcs.forEach((a) => $('#browse-amc').appendChild(el('option', { value: a }, esc(a))));
      data.policies.forEach((p) => $('#browse-policy').appendChild(el('option', { value: p }, esc(p))));
    }
    body.innerHTML = `<div class="sub" style="margin:10px 0">พบ ${num(data.total, 0)} กองทุน (แสดง ${data.funds.length} รายการแรก) · ข้อมูล ณ ${thaiDate(data.generated_at)}</div>`
      + renderBrowseTable(data.funds);
  }
  body.querySelectorAll('[data-code]').forEach((btn) => btn.addEventListener('click', () => {
    modal.hidden = true;
    loadFund(btn.dataset.code);
  }));
}
function renderBrowseTable(funds) {
  return `<div class="table-scroll"><table>
    <thead><tr><th>รหัส</th><th>ชื่อกองทุน</th><th>บลจ.</th><th>นโยบาย</th><th></th></tr></thead>
    <tbody>${funds.map((f) => `<tr>
      <td class="num"><b>${esc(f.code)}</b></td>
      <td>${esc(f.name_th)}</td>
      <td style="white-space:normal">${esc(f.amc_th)}</td>
      <td>${esc(f.policy || '')}</td>
      <td><button class="btn" data-code="${esc(f.classes && f.classes.length ? f.classes[0] : f.code)}">ดู</button></td>
    </tr>`).join('')}</tbody></table></div>`;
}

// ---------------------------------------------------------------- init
async function init() {
  initSearch();
  try { renderRecent(JSON.parse(localStorage.getItem('tfd-recent') || '[]')); } catch { /* ไม่มีก็ไม่เป็นไร */ }

  $('#range').addEventListener('click', (event) => {
    const btn = event.target.closest('button[data-range]');
    if (!btn) return;
    state.range = btn.dataset.range;
    $('#range').querySelectorAll('button').forEach((b) => b.classList.toggle('active', b === btn));
    renderChart();
  });
  $('#compare-range').addEventListener('click', (event) => {
    const btn = event.target.closest('button[data-window]');
    if (!btn) return;
    state.window = btn.dataset.window;
    $('#compare-range').querySelectorAll('button').forEach((b) => b.classList.toggle('active', b === btn));
    loadCompareTable();
  });
  $('#toggle-table').addEventListener('click', () => {
    state.showTable = !state.showTable;
    $('#toggle-table').textContent = state.showTable ? 'ซ่อนตาราง' : 'ดูเป็นตาราง';
    renderChart();
  });
  $('#compare-add').addEventListener('click', () => { addCompare($('#compare-input').value); $('#compare-input').value = ''; });
  $('#compare-input').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') { addCompare($('#compare-input').value); $('#compare-input').value = ''; }
  });
  $('#browse-btn').addEventListener('click', openBrowse);
  $('#browse-close').addEventListener('click', () => { $('#browse').hidden = true; });
  $('#browse').addEventListener('click', (e) => { if (e.target.id === 'browse') $('#browse').hidden = true; });
  let browseTimer = null;
  ['#browse-q', '#browse-amc', '#browse-policy'].forEach((sel) => {
    $(sel).addEventListener('input', () => { clearTimeout(browseTimer); browseTimer = setTimeout(openBrowse, 250); });
  });
  window.addEventListener('resize', () => { clearTimeout(window.__rz); window.__rz = setTimeout(renderChart, 150); });

  try {
    state.meta = await api('/api/meta');
    const m = state.meta;
    $('#meta-line').innerHTML = `ข้อมูล NAV ย้อนหลัง ${m.history_years} ปี · `
      + (m.catalog.available ? `รายชื่อกองทุนในเครื่อง ${num(m.catalog.count, 0)} กอง (${thaiDate(m.catalog.generated_at)})` : 'ยังไม่ได้สร้างรายชื่อกองทุนในเครื่อง — รัน python3 catalog.py --build')
      + (m.peers.available ? ` · ค่ากลางกลุ่มเดียวกัน ${m.peers.groups} กลุ่ม` : '');
    if (m.demo) {
      showAlert('<b>โหมดสาธิต</b> — ตัวเลขทั้งหมดเป็นข้อมูลจำลอง ไม่ใช่ข้อมูลจริงของกองทุน ใส่ SEC_API_KEY ในไฟล์ .env แล้วรัน <code>python3 server.py</code> เพื่อดูข้อมูลจริง');
    }
  } catch (err) {
    showAlert(`เชื่อมต่อ backend ไม่ได้: ${esc(err.message)}`, 'err');
  }

  const initial = decodeURIComponent((location.hash || '').replace('#', '')) || 'SCBNDQ';
  loadFund(initial);
}

init();
