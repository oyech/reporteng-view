const reportsUrl = document.body.dataset.reportsUrl || '/api/reports';
const exportUrl = document.body.dataset.exportUrl || '/export';
const exportPrefix = document.body.dataset.exportPrefix || 'laporan';
const $ = (id) => document.getElementById(id);
const form = $('filters');
const state = { rows: [], page: 1, size: 10, params: new URLSearchParams(), controller: null, loaded: false, autoRefreshInterval: null, autoRefreshEnabled: true, presenting: false };
const names = { area_kerja: 'Semua area', unit_area: 'Semua unit', status: 'Semua status', pic: 'Semua PIC' };
const reportTimezone = 'Asia/Jakarta'; // UTC+7 (WIB) timezone
const dateFormat = new Intl.DateTimeFormat('id-ID', { day: '2-digit', month: 'short', year: 'numeric', timeZone: reportTimezone });
const AUTO_REFRESH_INTERVAL = 5000; // Poll for changes every 5 seconds, including presentations.
function isoLocal(d) { return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`; }
function defaultDates() {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  $('start').value = `${year}-${month}-01`;
  $('end').value = `${year}-${month}-${day}`;
}
function periodDateLabel(value) { 
  if (!value) return '';
  const date = new Date(value + 'T12:00:00Z');
  return dateFormat.format(date);
}
function statusType(value) {
  const s = (value || '').replace(/^ProgressStatus\./, '').trim().toLowerCase().replace(/[_-]/g, ' ');
  if (['selesai', 'done', 'completed', 'complete', 'closed', 'finish', 'finished'].includes(s)) return 'done';
  if (['proses', 'dalam proses', 'in progress', 'progress', 'on progress', 'ongoing', 'sedang dikerjakan'].includes(s)) return 'progress';
  return 'pending';
}
function element(tag, text, className) { const node = document.createElement(tag); if (text !== undefined) node.textContent = text; if (className) node.className = className; return node; }
function dateLabel(value) {
  if (!value) return '—';
  // Legacy timestamp values without an offset are also stored as UTC.
  const timestamp = String(value).trim().replace(' ', 'T');
  const withZone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(timestamp) || !timestamp.includes('T') ? timestamp : timestamp + 'Z';
  const date = new Date(withZone);
  if (isNaN(date)) return String(value);
  // Format in Asia/Jakarta timezone (UTC+7)
  return new Intl.DateTimeFormat('id-ID', {
    day: '2-digit',
    month: 'short', 
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
    timeZone: reportTimezone
  }).format(date);
}
function toast(message) { $('toast').textContent = message; $('toast').hidden = false; clearTimeout(toast.timer); toast.timer = setTimeout(() => $('toast').hidden = true, 6000); }
function preview(urls) {
  $('photos').replaceChildren();
  urls.forEach(url => {
    const wrap = element('div'); const img = element('img'); img.src = url; img.alt = 'Foto dokumentasi pekerjaan';
    img.onerror = () => { img.replaceWith(element('p', 'Foto tidak dapat dimuat. Tautan mungkin kedaluwarsa atau membutuhkan akses.')); };
    const link = element('a', 'Buka foto asli ↗'); link.href = url; link.target = '_blank'; link.rel = 'noopener noreferrer';
    wrap.append(img, link); $('photos').append(wrap);
  });
  $('photo-dialog').showModal();
}
function formatUnitArea(value) {
  const text = String(value || '').trim();
  const unit = /^([a-z]{1,8})[\s-]*(\d+[a-z]?)$/i.exec(text);
  if (unit) return `${unit[1].toUpperCase()}-${unit[2].toUpperCase()}`;
  return text.toLocaleLowerCase('id-ID').replace(/(^|[\s/()-])([a-z])/g, (_, separator, letter) => separator + letter.toLocaleUpperCase('id-ID')) || '—';
}
function viewReport(report) {
  const detail = $('report-detail');
  detail.replaceChildren();
  const line = element('p', undefined, 'report-summary-line');
  const description = String(report.pekerjaan || '—').trim();
  const capitalizedDescription = description ? description[0].toLocaleUpperCase('id-ID') + description.slice(1) : '—';
  line.append(element('strong', formatUnitArea(report.unit_area || report.area_kerja)));
  line.append(document.createTextNode(` ${capitalizedDescription}`));
  if (report.status) line.append(document.createTextNode(` (${String(report.status).replace(/^ProgressStatus\./, '')})`));
  detail.append(line);
  $('report-dialog').showModal();
}
function render() {
  const total = state.rows.length;
  const pages = Math.max(1, Math.ceil(total/state.size)); state.page = Math.min(state.page, pages);
  const from = (state.page-1)*state.size;
  $('rows').replaceChildren();
  state.rows.slice(from, from+state.size).forEach(r => {
    const tr = element('tr');
    const dateCell = element('td', dateLabel(r.tanggal));
    dateCell.setAttribute('title', `Nilai tanggal dari server: ${r.tanggal || '—'}`);
    tr.append(dateCell, element('td', r.area_kerja || '—'), element('td', r.unit_area || '—'), element('td', r.pekerjaan || '—', 'job-cell'));
    const status = element('td'); 
    let statusText = r.status || 'Tanpa status';
    if (statusText.startsWith('ProgressStatus.')) {
      statusText = statusText.replace('ProgressStatus.', '');
    }
    status.append(element('span', statusText, `badge ${statusType(statusText)}`)); tr.append(status);
    const pic = element('td'); const person = element('div', undefined, 'pic-cell');
    const picNames = (r.pic || '').split('|').map(name => name.trim()).filter(name => name);
    const initials = picNames.length > 0 ? picNames[0].split(/\s+/).slice(0,2).map(p => p[0] || '').join('').toUpperCase() : '–';
    const displayPic = picNames.length > 0 ? picNames.join(' | ') : (r.pic || '—');
    person.append(element('span', initials || '–', 'pic-avatar'), element('span', displayPic)); pic.append(person); tr.append(pic);
    const photo = element('td');
    try {
      if (r.foto && Array.isArray(r.foto) && r.foto.length > 0) {
        const button = element('button', undefined, 'photo-button'); button.type = 'button'; button.setAttribute('aria-label', `Lihat ${r.foto.length} foto: ${r.pekerjaan}`);
        const img = element('img'); img.src = r.foto[0]; img.alt = ''; img.loading = 'lazy'; img.onerror = () => img.replaceWith(element('span', '▧'));
        button.append(img, element('span', r.foto.length > 1 ? `+${r.foto.length-1}` : 'Lihat')); button.onclick = () => preview(r.foto); photo.append(button);
      } else {
        photo.textContent = '—';
      }
    } catch (e) {
      console.error('Error rendering photo:', e);
      photo.textContent = '—';
    }
    tr.append(photo);
    const action = element('td');
    const view = element('button', 'View', 'button report-view-button');
    view.type = 'button'; view.onclick = () => viewReport(r); action.append(view);
    tr.append(action); $('rows').append(tr);
  });
  $('empty').hidden = total > 0;
  $('count').textContent = total.toLocaleString('id-ID');
  $('pagination-info').textContent = total ? `Menampilkan ${from+1}–${Math.min(from+state.size,total)} dari ${total.toLocaleString('id-ID')} pekerjaan` : '0 pekerjaan ditampilkan';
  $('page-number').textContent = `${state.page} / ${pages}`;
  $('prev').disabled = state.page <= 1; $('next').disabled = state.page >= pages;
  $('export').disabled = !state.loaded || total === 0;
  updatePresentationSummary();
  ['total','done','progress','pending'].forEach(id => { $(''+id).textContent = state.loaded ? (id === 'total' ? total : state.rows.filter(r => statusType(r.status) === id).length).toLocaleString('id-ID') : '—'; });
}
function getParams() { const params = new URLSearchParams(new FormData(form)); params.set('q', $('search').value.trim()); return params; }
function startAutoRefresh() {
  stopAutoRefresh(); // Clear any existing interval
  if (!state.autoRefreshEnabled || document.visibilityState !== 'visible') return; // Only start if enabled
  
  state.autoRefreshInterval = setInterval(() => {
    if (document.visibilityState === 'visible' && state.autoRefreshEnabled) {
      // Only auto-refresh if not currently loading and feature is enabled
      if (!state.controller) {
        load({ background: true }); // Refresh the applied period without moving pages
      }
    }
  }, AUTO_REFRESH_INTERVAL);
  
  // Show auto-refresh indicator
  $('auto-refresh-indicator').hidden = false;
  $('auto-refresh-indicator').textContent = 'Update otomatis • 5 detik';
}
function stopAutoRefresh() {
  if (state.autoRefreshInterval) {
    clearInterval(state.autoRefreshInterval);
    state.autoRefreshInterval = null;
  }
  // Hide auto-refresh indicator
  $('auto-refresh-indicator').hidden = true;
}
async function load({ background = false } = {}) {
  hideSearchSuggestions();
  if (!background && !form.reportValidity()) return;
  if (!background && $('start').value && $('end').value && $('start').value > $('end').value) { toast('Tanggal mulai tidak boleh melewati tanggal akhir.'); return; }
  state.controller?.abort(); const controller = new AbortController(); state.controller = controller;
  const params = background ? new URLSearchParams(state.params) : getParams();
  if (!background) { state.params = params; state.loaded = false; state.rows = []; state.page = 1; render(); }
  if (!background) { $('empty-title').textContent = 'Memuat laporan…'; $('empty-description').textContent = 'Mengambil data terbaru dari Supabase.'; }
  $('notice').hidden = true; $('refresh').disabled = true;
  const timeout = setTimeout(() => controller.abort(), 45000);
  try {
    const response = await fetch(reportsUrl + '?' + params, { signal: controller.signal, cache: 'no-store' });
    if (response.status === 401) { throw new Error('Sesi belum dapat diverifikasi. Coba muat ulang; jika tetap gagal, buka /login untuk masuk kembali.'); }
    
    // Check if response is JSON before parsing
    const contentType = response.headers.get('content-type');
    if (!contentType || !contentType.includes('application/json')) {
      throw new Error('Server mengembalikan respons tidak valid. Silakan coba lagi.');
    }
    
    const data = await response.json();
    if (state.controller !== controller) return;
    if (!response.ok) throw new Error(data.error || 'Gagal memuat laporan.');
    const changed = !state.loaded || JSON.stringify(state.rows) !== JSON.stringify(data.rows);
    state.rows = data.rows; state.loaded = true; state.params = params;
    Object.entries(names).forEach(([id, title]) => {
      const selected = (background ? $(id).value : params.get(id)) || ''; $(id).replaceChildren(new Option(title, ''));
      const values = data.options[id]; if (selected && !values.includes(selected)) values.push(selected);
      values.forEach(value => $(id).add(new Option(value, value))); $(id).value = selected;
    });
    $('empty-title').textContent = 'Tidak ada pekerjaan ditemukan'; $('empty-description').textContent = 'Coba ubah filter atau periode tanggal. Jika data seharusnya tersedia, periksa izin baca / RLS di Supabase.';
    $('updated').textContent = 'Diperbarui ' + new Intl.DateTimeFormat('id-ID', {hour:'2-digit',minute:'2-digit',second:'2-digit',timeZone:reportTimezone}).format(new Date());
    $('period-caption').textContent = `${params.get('start') ? periodDateLabel(params.get('start')) : 'Seluruh tanggal'} → ${params.get('end') ? periodDateLabel(params.get('end')) : 'Terbaru'} (UTC+7, tanggal akhir termasuk) • Filter aktif juga digunakan untuk export Excel`;
    if (!background || changed) render();
    
    // Update auto-refresh toggle state
    const autoRefreshToggle = $('auto-refresh-toggle');
    if (autoRefreshToggle) {
      autoRefreshToggle.classList.toggle('active', state.autoRefreshEnabled);
    }
    
  } catch(error) {
    if (state.controller !== controller) return;
    $('notice').textContent = error.name === 'AbortError' ? 'Koneksi melewati batas waktu. Akan mencoba kembali otomatis.' : error.message; $('notice').hidden = false;
    if (!state.loaded) { $('empty-title').textContent = 'Data belum dapat ditampilkan'; $('empty-description').textContent = 'Aplikasi akan mencoba memuat kembali secara otomatis.'; render(); }
    $('updated').textContent = state.loaded ? 'Menampilkan data terakhir • mencoba kembali otomatis' : 'Menunggu koneksi • mencoba kembali otomatis';
  } finally {
    clearTimeout(timeout);
    if (state.controller === controller) { state.controller = null; $('refresh').disabled = false; startAutoRefresh(); }
  }
}
form.addEventListener('submit', e => { e.preventDefault(); clearTimeout(searchTimer); load(); });
$('reset').onclick = () => { form.reset(); $('search').value = ''; defaultDates(); load(); };
$('refresh').onclick = () => load();
['start', 'end'].forEach(id => $(id).addEventListener('change', () => {
  clearTimeout(searchTimer);
  load();
}));
let searchTimer; $('search').addEventListener('input', () => { $('export').disabled = true; clearTimeout(searchTimer); searchTimer = setTimeout(load, 400); renderSearchSuggestions($('search').value); });
$('search').addEventListener('focus', () => { if ($('search').value.trim()) renderSearchSuggestions($('search').value); });
$('search').addEventListener('blur', () => { setTimeout(hideSearchSuggestions, 150); });
$('search').addEventListener('keydown', (e) => {
  const items = searchSuggestions ? searchSuggestions.querySelectorAll('.search-suggestion-item') : [];
  if (!items.length) return;
  if (e.key === 'ArrowDown') { e.preventDefault(); activeSuggestionIndex = Math.min(activeSuggestionIndex + 1, items.length - 1); updateActiveSuggestion(items); }
  else if (e.key === 'ArrowUp') { e.preventDefault(); activeSuggestionIndex = Math.max(activeSuggestionIndex - 1, 0); updateActiveSuggestion(items); }
  else if (e.key === 'Enter') { if (activeSuggestionIndex >= 0 && activeSuggestionIndex < items.length) { e.preventDefault(); items[activeSuggestionIndex].dispatchEvent(new Event('mousedown', { cancelable: true })); } }
  else if (e.key === 'Escape') { hideSearchSuggestions(); }
});
document.addEventListener('mousedown', (e) => { if (searchSuggestions && !searchSuggestions.contains(e.target) && e.target !== $('search')) hideSearchSuggestions(); });
function renderSearchSuggestions(query) {
  if (!searchSuggestions) return;
  const q = (query || '').trim().toLowerCase();
  if (!q) { hideSearchSuggestions(); return; }
  const matches = []; const seen = new Set();
  for (const row of state.rows) {
    const fields = ['pekerjaan', 'area_kerja', 'unit_area', 'status', 'pic'];
    for (const field of fields) {
      const value = String(row[field] || '').toLowerCase();
      if (value.includes(q)) {
        const key = `${field}:${value}`;
        if (!seen.has(key)) { seen.add(key); matches.push({ field, value: row[field], row }); }
        break;
      }
    }
    if (matches.length >= 50) break;
  }
  if (!matches.length) { hideSearchSuggestions(); return; }
  searchSuggestions.innerHTML = '';
  matches.forEach((match, index) => {
    const item = document.createElement('div');
    item.className = 'search-suggestion-item';
    item.setAttribute('role', 'option');
    item.setAttribute('aria-selected', 'false');
    const title = document.createElement('div');
    title.className = 'suggestion-title';
    title.textContent = match.value || '—';
    item.appendChild(title);
    const meta = document.createElement('div');
    meta.className = 'suggestion-meta';
    const label = match.field === 'pic' ? 'PIC' : match.field === 'status' ? 'Status' : match.field === 'area_kerja' ? 'Area kerja' : match.field === 'unit_area' ? 'Unit/Area' : 'Pekerjaan';
    const parts = [label];
    if (match.row.area_kerja && match.field !== 'area_kerja') parts.push(match.row.area_kerja);
    if (match.row.status && match.field !== 'status') parts.push(match.row.status);
    meta.innerHTML = parts.map(part => `<span>${escapeHtml(part)}</span>`).join('');
    item.appendChild(meta);
    item.addEventListener('mousedown', (e) => { e.preventDefault(); $('search').value = match.value; hideSearchSuggestions(); load(); });
    searchSuggestions.appendChild(item);
  });
  searchSuggestions.hidden = false;
  activeSuggestionIndex = -1;
}
function hideSearchSuggestions() { if (searchSuggestions) searchSuggestions.hidden = true; activeSuggestionIndex = -1; }
function updateActiveSuggestion(items) { items.forEach((item, idx) => { item.classList.toggle('active', idx === activeSuggestionIndex); item.setAttribute('aria-selected', String(idx === activeSuggestionIndex)); }); }
function escapeHtml(text) { const div = document.createElement('div'); div.textContent = text; return div.innerHTML; }
const searchInput = $('search');
const searchSuggestions = $('search-suggestions');
let activeSuggestionIndex = -1;
$('prev').onclick = () => { state.page--; render(); }; $('next').onclick = () => { state.page++; render(); };

// Auto-refresh toggle functionality
const autoRefreshToggle = $('auto-refresh-toggle');
if (autoRefreshToggle) {
  // Set initial state
  autoRefreshToggle.classList.toggle('active', state.autoRefreshEnabled);
  
  autoRefreshToggle.onclick = () => {
    state.autoRefreshEnabled = !state.autoRefreshEnabled;
    autoRefreshToggle.classList.toggle('active', state.autoRefreshEnabled);
    
    if (state.autoRefreshEnabled) {
      startAutoRefresh();
      toast('Auto-refresh diaktifkan');
    } else {
      stopAutoRefresh();
      toast('Auto-refresh dinonaktifkan');
    }
  };
}
$('page-size').onchange = () => { state.size = Number($('page-size').value); state.page = 1; render(); };
$('close-photo').onclick = () => $('photo-dialog').close();
$('photo-dialog').addEventListener('click', e => { if (e.target === $('photo-dialog')) $('photo-dialog').close(); });
$('close-report').onclick = () => $('report-dialog').close();
$('report-dialog').addEventListener('click', e => { if (e.target === $('report-dialog')) $('report-dialog').close(); });
$('export').onclick = async () => {
  const button = $('export'); button.disabled = true; button.querySelector('span').textContent = 'Menyiapkan…';
  try {
    const response = await fetch(exportUrl + '?' + state.params);
    if (response.status === 401) { throw new Error('Sesi belum dapat diverifikasi. Coba lagi atau buka /login untuk masuk kembali.'); }
    if (!response.ok) { 
      const contentType = response.headers.get('content-type');
      if (contentType && contentType.includes('application/json')) {
        const data = await response.json(); 
        throw new Error(data.error || 'Ekspor gagal.');
      }
      throw new Error('Ekspor gagal. Server mengembalikan respons tidak valid.');
    }
    const blob = await response.blob(); const url = URL.createObjectURL(blob); const link = element('a');
    link.href = url; link.download = `${exportPrefix}_${state.params.get('start') || 'semua'}_${state.params.get('end') || 'terbaru'}.xlsx`;
    document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    toast('Laporan Excel berhasil diunduh.');
  } catch(error) { toast(error.message); }
  finally { button.querySelector('span').textContent = 'Export Excel'; button.disabled = !state.loaded || state.rows.length === 0; }
};
$('today').textContent = new Intl.DateTimeFormat('id-ID', {weekday:'short',day:'numeric',month:'long',year:'numeric',timeZone:reportTimezone}).format(new Date());
// Handle visibility changes - pause auto-refresh when tab is hidden
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible' && state.autoRefreshEnabled) {
    if (!state.controller) load({ background: true });
    startAutoRefresh();
  } else {
    stopAutoRefresh();
  }
});
// Clean up auto-refresh when page is unloaded
window.addEventListener('beforeunload', () => {
  stopAutoRefresh();
});
function updatePresentationSummary() {
  const params = state.params;
  const period = [params.get('start') || 'Semua tanggal', params.get('end') || 'Terbaru'].join(' → ');
  const filters = ['area_kerja', 'unit_area', 'status', 'pic', 'q'].map(key => params.get(key)).filter(Boolean);
  $('presentation-summary').textContent = [period, ...filters].join(' • ');
}
function setPresentation(enabled) {
  state.presenting = enabled;
  document.body.classList.toggle('presenting', enabled);
  $('presentation-toggle').setAttribute('aria-pressed', String(enabled));
  $('presentation-toggle').textContent = enabled ? 'Keluar presentasi' : 'Mode presentasi';
  $('presentation-context').hidden = !enabled;
  startAutoRefresh();
  updatePresentationSummary();
}
$('presentation-toggle').onclick = () => setPresentation(!state.presenting);
document.addEventListener('keydown', event => {
  if (!state.presenting || $('photo-dialog').open || $('report-dialog').open || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey || event.target.closest('input, select, textarea, [contenteditable]')) return;
  if (event.key === 'Escape') setPresentation(false);
  if (event.key === 'ArrowRight' && !$('next').disabled) { event.preventDefault(); $('next').click(); }
  if (event.key === 'ArrowLeft' && !$('prev').disabled) { event.preventDefault(); $('prev').click(); }
});
defaultDates(); load();
