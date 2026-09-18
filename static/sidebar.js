const sidebarToggle = document.getElementById('sidebar-toggle');

function applySidebarVisibility() {
  const hidden = localStorage.getItem('sidebar-hidden') === '1';
  document.body.classList.toggle('hide-sidebar', hidden);
  sidebarToggle.setAttribute('aria-label', hidden ? 'Tampilkan bilah sisi' : 'Sembunyikan bilah sisi');
  sidebarToggle.setAttribute('title', hidden ? 'Tampilkan bilah sisi' : 'Sembunyikan bilah sisi');
  sidebarToggle.setAttribute('aria-expanded', String(!hidden));
}

if (sidebarToggle) {
  applySidebarVisibility();
  sidebarToggle.addEventListener('click', () => {
    localStorage.setItem('sidebar-hidden', document.body.classList.contains('hide-sidebar') ? '0' : '1');
    applySidebarVisibility();
  });
}
