document.addEventListener('click', async (event) => {
  const button = event.target.closest('.catalog-delete');
  if (!button || button.disabled) return;

  const label = button.dataset.deleteLabel || 'data ini';
  if (!window.confirm(`Hapus ${label}?`)) return;

  button.disabled = true;
  const originalText = button.textContent;
  button.textContent = 'Menghapus...';

  try {
    const formData = new FormData();
    formData.set('csrf', document.body.dataset.csrf || '');
    const response = await fetch(button.dataset.deleteUrl, {
      method: 'POST',
      body: formData,
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
    });

    const contentType = response.headers.get('content-type') || '';
    const result = contentType.includes('application/json')
      ? await response.json()
      : null;

    if (!response.ok || !result?.success) {
      throw new Error(result?.error || `Server gagal menghapus data (HTTP ${response.status}).`);
    }

    window.location.reload();
  } catch (error) {
    window.alert(`Gagal menghapus ${label}. ${error.message}`);
    button.disabled = false;
    button.textContent = originalText;
  }
});
