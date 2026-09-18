document.querySelectorAll('[data-table-search]').forEach((input) => {
  input.addEventListener('input', () => {
    const term = input.value.trim().toLowerCase();
    document.querySelectorAll(input.dataset.tableSearch).forEach((row) => {
      row.hidden = term && !row.textContent.toLowerCase().includes(term);
    });
  });
});
