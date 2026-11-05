/* JOAN · JavaScript mínimo: menú móvil, filtro de proyectos y formulario. */
(function () {
  'use strict';
  var d = document;

  /* Menú móvil */
  var toggle = d.querySelector('[data-menu-toggle]');
  var nav = d.getElementById('site-nav');
  function setMenu(open) {
    if (!toggle) return;
    toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    d.body.classList.toggle('menu-open', open);
  }
  if (toggle && nav) {
    toggle.addEventListener('click', function () {
      setMenu(toggle.getAttribute('aria-expanded') !== 'true');
    });
    nav.addEventListener('click', function (e) {
      if (e.target.closest('a')) setMenu(false);
    });
    d.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') { setMenu(false); toggle.focus(); }
    });
  }

  /* Filtro de proyectos por categoría */
  var filters = d.querySelector('[data-filters]');
  var grid = d.querySelector('[data-grid]');
  if (filters && grid) {
    var buttons = filters.querySelectorAll('.filter-btn');
    var cards = grid.querySelectorAll('.card');

    var apply = function (cat, updateHash) {
      var visible = 0;
      cards.forEach(function (card) {
        var show = cat === 'all' || card.getAttribute('data-category') === cat;
        card.hidden = !show;
        card.classList.toggle('offset', show && visible % 2 === 1);
        if (show) visible += 1;
      });
      buttons.forEach(function (b) {
        b.setAttribute('aria-pressed', b.getAttribute('data-filter') === cat ? 'true' : 'false');
      });
      if (updateHash && window.history && history.replaceState) {
        history.replaceState(null, '', cat === 'all' ? location.pathname + location.search : '#' + cat);
      }
    };

    filters.addEventListener('click', function (e) {
      var btn = e.target.closest('.filter-btn');
      if (btn) apply(btn.getAttribute('data-filter'), true);
    });

    var fromHash = decodeURIComponent(location.hash.replace('#', ''));
    if (fromHash && filters.querySelector('[data-filter="' + fromHash + '"]')) apply(fromHash, false);
  }

  /* Formulario de contacto (Web3Forms) */
  var form = d.getElementById('contact-form');
  if (form && window.fetch) {
    var status = form.querySelector('.form-status');
    var submit = form.querySelector('button[type="submit"]');
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var label = submit.textContent;
      submit.disabled = true;
      submit.textContent = form.getAttribute('data-msg-sending');
      status.textContent = '';
      var payload = {};
      new FormData(form).forEach(function (value, key) { payload[key] = value; });
      fetch(form.action, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: JSON.stringify(payload)
      })
        .then(function (r) { return r.json(); })
        .then(function (res) {
          if (res && res.success) {
            status.textContent = form.getAttribute('data-msg-ok');
            form.reset();
          } else {
            status.textContent = form.getAttribute('data-msg-err');
          }
        })
        .catch(function () { status.textContent = form.getAttribute('data-msg-err'); })
        .then(function () { submit.disabled = false; submit.textContent = label; });
    });
  }
})();
