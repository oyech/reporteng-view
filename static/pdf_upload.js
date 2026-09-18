const $ = (id) => document.getElementById(id);
const uploadForm = $('pdf-upload-form');
const fileInput = $('pdf-file');
const uploadBtn = $('upload-btn');
const editor = $('editor-section');
const recordForm = $('record-form');
const rows = $('pdf-rows');
const notice = $('pdf-notice');
const fields = ['tanggal', 'no_wpr', 'deskripsi', 'type_budget', 'status', 'keterangan'];
const labels = ['Tanggal', 'No WPR', 'Deskripsi', 'Type Budget', 'Status', 'Keterangan'];
let records = [];
let editingId = null;
let pendingPdfFile = null;
let searchTerm = '';
const filterState = { start: '', end: '', budget: '', status: '' };

function dateForPicker(value) {
  const text = String(value || '').trim();
  let year, month, day;
  const iso = /^(\d{4})-(\d{1,2})-(\d{1,2})$/.exec(text);
  const local = /^(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})$/.exec(text);
  if (iso) {
    [, year, month, day] = iso;
  } else if (local) {
    [, day, month, year] = local;
    if (year.length === 2) year = `20${year}`;
  } else {
    return '';
  }
  const result = `${year.padStart(4, '0')}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`;
  const parsed = new Date(`${result}T00:00:00Z`);
  return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === result ? result : '';
}

function dateForStorage(value) {
  const [year, month, day] = value.split('-');
  return `${day}/${month}/${year}`;
}

function toast(message) {
  const el = $('toast');
  el.textContent = message;
  el.hidden = false;
  setTimeout(() => { el.hidden = true; }, 5000);
}

async function api(url, options = {}) {
  const response = await fetch(url, { ...options, redirect: 'manual' });
  const contentType = response.headers.get('content-type') || '';
  if (!contentType.includes('application/json')) {
    if (response.status === 401 || response.status === 302 || response.status === 0 || response.redirected) {
      throw new Error('Sesi berakhir. Muat ulang halaman dan login kembali.');
    }
    const error = new Error(`Server tidak mengirim JSON (HTTP ${response.status}). Muat ulang aplikasi atau restart server, lalu coba lagi.`);
    error.status = response.status;
    throw error;
  }
  const result = await response.json();
  if (!response.ok) {
    const error = new Error(result.error || `Permintaan gagal (HTTP ${response.status}).`);
    error.status = response.status;
    throw error;
  }
  return result;
}

function showError(message) {
  notice.textContent = message;
  notice.hidden = false;
  toast(message);
}

function openEditor(data, id = null) {
  editingId = id;
  fields.forEach((field) => {
    recordForm.elements[field].value = field === 'tanggal' ? dateForPicker(data[field]) : (data[field] || '');
  });
  $('editor-title').textContent = id === null ? 'Preview hasil ekstraksi' : 'Edit data Purchase Request';
  $('save-record').textContent = id === null ? 'Simpan Data' : 'Simpan Perubahan';
  $('parse-warning').hidden = true;
  $('pdf-replacement-field').hidden = id === null;
  recordForm.elements.pdf_file.value = '';
  $('source-pdf-name').textContent = id === null && pendingPdfFile ? `PDF yang akan disimpan: ${pendingPdfFile.name}` : '';
  $('source-pdf-name').hidden = id !== null || !pendingPdfFile;
  editor.hidden = false;
  editor.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function render() {
  rows.replaceChildren();
  const visibleRecords = records.filter((record) => {
    const date = dateForPicker(record.tanggal);
    return fields.some((field) => String(record[field] || '').toLowerCase().includes(searchTerm)) &&
      (!filterState.start || date >= filterState.start) && (!filterState.end || date <= filterState.end) &&
      (!filterState.budget || record.type_budget === filterState.budget) &&
      (!filterState.status || record.status === filterState.status);
  });
  $('pdf-count').textContent = visibleRecords.length;
  const empty = $('pdf-empty');
  empty.hidden = visibleRecords.length > 0;
  if (records.length && !visibleRecords.length) {
    $('pdf-empty-title').textContent = 'Data tidak ditemukan';
    $('pdf-empty-description').textContent = 'Ubah kata pencarian untuk melihat data lainnya.';
  } else {
    $('pdf-empty-title').textContent = 'Belum ada data';
    $('pdf-empty-description').textContent = 'Upload file PDF Purchase Request untuk mulai menyimpan data.';
  }
  visibleRecords.forEach((record) => {
    const tr = document.createElement('tr');
    fields.forEach((field) => {
      const td = document.createElement('td');
      td.textContent = record[field] || '—';
      tr.appendChild(td);
    });
    const actions = document.createElement('td');
    actions.className = 'pdf-actions';
    [['Preview', 'preview'], ['Edit', 'edit'], ['Hapus', 'delete']].forEach(([label, action]) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = label;
      button.dataset.action = action;
      button.dataset.id = record.id;
      actions.appendChild(button);
    });
    if (record.has_pdf) {
      const link = document.createElement('a');
      link.textContent = 'Lihat PDF';
      link.href = `/api/pdf-records/${record.id}/pdf`;
      link.target = '_blank';
      link.rel = 'noopener';
      link.className = 'pdf-file-link';
      link.setAttribute('aria-label', `Lihat PDF ${record.no_wpr}`);
      actions.appendChild(link);
    }
    tr.appendChild(actions);
    rows.appendChild(tr);
  });
}

const pdfSearchInput = $('pdf-search-input');
pdfSearchInput.addEventListener('input', () => {
  searchTerm = pdfSearchInput.value.trim().toLowerCase();
  render();
});

[['wpr-filter-start', 'start'], ['wpr-filter-end', 'end'], ['wpr-filter-budget', 'budget'], ['wpr-filter-status', 'status']].forEach(([id, key]) => {
  $(id).addEventListener('change', () => { filterState[key] = $(id).value; render(); });
});
$('wpr-filter-reset').addEventListener('click', () => {
  Object.keys(filterState).forEach((key) => { filterState[key] = ''; });
  ['wpr-filter-start', 'wpr-filter-end', 'wpr-filter-budget', 'wpr-filter-status'].forEach((id) => { $(id).value = ''; });
  render();
});

async function refresh() {
  const result = await api('/api/pdf-upload');
  records = result.data;
  const budget = $('wpr-filter-budget');
  const selected = budget.value;
  const values = [...new Set(records.map((record) => record.type_budget).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'id'));
  budget.replaceChildren(new Option('Semua', ''), ...values.map((value) => new Option(value, value)));
  budget.value = values.includes(selected) ? selected : '';
  render();
}

fileInput.addEventListener('change', () => {
  uploadBtn.disabled = !fileInput.files.length;
  if (editingId === null) { pendingPdfFile = null; editor.hidden = true; }
});
const uploadArea = document.querySelector('.upload-area');
uploadArea.addEventListener('dragover', (event) => { event.preventDefault(); uploadArea.classList.add('drag-over'); });
uploadArea.addEventListener('dragleave', () => uploadArea.classList.remove('drag-over'));
uploadArea.addEventListener('drop', (event) => {
  event.preventDefault();
  uploadArea.classList.remove('drag-over');
  if (event.dataTransfer.files.length) {
    fileInput.files = event.dataTransfer.files;
    uploadBtn.disabled = false;
    if (editingId === null) { pendingPdfFile = null; editor.hidden = true; }
  }
});

uploadForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!fileInput.files.length) return;
  uploadBtn.disabled = true;
  uploadBtn.textContent = 'Memproses...';
  notice.hidden = true;
  try {
    const result = await api('/api/pdf-upload', { method: 'POST', body: new FormData(uploadForm) });
    pendingPdfFile = fileInput.files[0];
    openEditor(result.data);
    if (result.missing && result.missing.length) {
      const missingLabels = result.missing.map((field) => labels[fields.indexOf(field)]);
      $('parse-warning').textContent = `Tidak terbaca dari PDF: ${missingLabels.join(', ')}. Isi kolom tersebut sebelum menyimpan.`;
      $('parse-warning').hidden = false;
    }
    toast('Hasil ekstraksi siap diperiksa. Data belum disimpan.');
  } catch (error) {
    notice.textContent = error.message;
    notice.hidden = false;
    toast(error.message);
  } finally {
    uploadBtn.disabled = false;
    uploadBtn.textContent = 'Preview PDF →';
  }
});

recordForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const data = new FormData(recordForm);
  data.set('tanggal', dateForStorage(recordForm.elements.tanggal.value));
  if (editingId === null) {
    if (!pendingPdfFile) { showError('Preview PDF terlebih dahulu sebelum menyimpan.'); return; }
    data.set('pdf_file', pendingPdfFile);
  }
  data.set('csrf', uploadForm.elements.csrf.value);
  const id = editingId;
  const button = $('save-record');
  button.disabled = true;
  try {
    await api(id === null ? '/api/pdf-records' : `/api/pdf-records/${id}/edit`, {
      method: 'POST', body: data
    });
    await refresh();
    editor.hidden = true;
    recordForm.reset();
    editingId = null;
    pendingPdfFile = null;
    toast(id === null ? 'Data berhasil disimpan.' : 'Perubahan berhasil disimpan.');
  } catch (error) {
    showError(error.message);
  } finally {
    button.disabled = false;
  }
});

$('cancel-edit').addEventListener('click', () => { editor.hidden = true; editingId = null; });
rows.addEventListener('click', async (event) => {
  const button = event.target.closest('button[data-action]');
  if (!button) return;
  const record = records.find((item) => item.id === Number(button.dataset.id));
  if (!record) return;
  if (button.dataset.action === 'preview') {
    const container = $('preview-fields');
    container.replaceChildren();
    fields.forEach((field, index) => {
      const p = document.createElement('p');
      const strong = document.createElement('strong');
      strong.textContent = `${labels[index]}: `;
      p.append(strong, document.createTextNode(record[field] || '—'));
      container.appendChild(p);
    });
    $('record-preview').showModal();
  } else if (button.dataset.action === 'edit') {
    openEditor(record, record.id);
  } else if (button.dataset.action === 'delete' && confirm(`Hapus data WPR ${record.no_wpr}?`)) {
    const data = new FormData();
    data.set('csrf', uploadForm.elements.csrf.value);
    button.disabled = true;
    notice.hidden = true;
    try {
      try {
        await api(`/api/pdf-records/${record.id}/delete`, { method: 'POST', body: data });
      } catch (error) {
        if (error.status !== 404 && error.status !== 405) throw error;
        await api(`/api/pdf-records/${record.id}`, { method: 'DELETE', body: data });
      }
      await refresh();
      if (records.some((item) => item.id === record.id)) {
        throw new Error('Server menerima perintah hapus, tetapi data masih ada di SQLite. Coba muat ulang halaman.');
      }
      if (editingId === record.id) { editor.hidden = true; editingId = null; }
      toast('Data berhasil dihapus.');
    } catch (error) { showError(`Gagal menghapus WPR ${record.no_wpr}: ${error.message}`); }
    finally { button.disabled = false; }
  }
});
$('close-preview').addEventListener('click', () => $('record-preview').close());
refresh().catch((error) => { notice.textContent = error.message; notice.hidden = false; });
$('today').textContent = new Intl.DateTimeFormat('id-ID', { weekday: 'short', day: 'numeric', month: 'long', year: 'numeric' }).format(new Date());
