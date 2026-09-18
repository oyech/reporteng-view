const feedback = document.getElementById('toast');
const copyDialog = document.getElementById('copy-dialog');
let feedbackTimer;
document.querySelectorAll('.copy-code').forEach(button => {
  button.addEventListener('click', async () => {
    const code = button.dataset.code;
    try {
      if (!navigator.clipboard || !window.isSecureContext) throw new Error('Clipboard unavailable');
      await navigator.clipboard.writeText(code);
      feedback.textContent = `Kode ${code} disalin.`;
      feedback.hidden = false;
      clearTimeout(feedbackTimer);
      feedbackTimer = setTimeout(() => { feedback.hidden = true; }, 3000);
    } catch {
      const input = document.getElementById('copy-value');
      input.value = code;
      copyDialog.showModal();
      input.focus();
      input.select();
    }
  });
});
document.getElementById('close-copy').onclick = () => copyDialog.close();
const itemSearch = document.getElementById('item-query');
let itemSearchTimer;
itemSearch.addEventListener('input', () => {
  clearTimeout(itemSearchTimer);
  itemSearchTimer = setTimeout(() => itemSearch.form.requestSubmit(), 450);
});
