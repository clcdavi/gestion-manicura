// ── Theme switcher ────────────────────────────────────────────────────────────

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('salon-theme', theme);
  document.querySelectorAll('.theme-swatch').forEach(function(btn) {
    btn.classList.toggle('active', btn.dataset.theme === theme);
  });
}

function toggleThemePanel() {
  document.getElementById('themePanel').classList.toggle('open');
}

// Init: aplicar tema guardado y registrar eventos
(function() {
  var saved = localStorage.getItem('salon-theme') || 'indigo';
  applyTheme(saved);

  document.querySelectorAll('.theme-swatch').forEach(function(btn) {
    btn.addEventListener('click', function() {
      applyTheme(btn.dataset.theme);
      document.getElementById('themePanel').classList.remove('open');
    });
  });

  document.addEventListener('click', function(e) {
    var switcher = document.getElementById('themeSwitcher');
    if (switcher && !switcher.contains(e.target)) {
      var panel = document.getElementById('themePanel');
      if (panel) panel.classList.remove('open');
    }
  });
})();

// ── Toggle sidebar en mobile ──────────────────────────────────────────────────

function toggleSidebar() {
  document.getElementById('sidebar').classList.toggle('open');
}

document.addEventListener('click', function(e) {
  var sidebar = document.getElementById('sidebar');
  var toggle = document.querySelector('.menu-toggle');
  if (sidebar && sidebar.classList.contains('open')) {
    if (!sidebar.contains(e.target) && e.target !== toggle) {
      sidebar.classList.remove('open');
    }
  }
});
