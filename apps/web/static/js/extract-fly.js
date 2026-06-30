(function () {
  var reduce = window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function savedTab() { return document.getElementById('saved-tab'); }
  function badgeOf(tab) { return tab && tab.querySelector('[data-cookbook-badge]'); }

  function bumpBadge(badge, tab) {
    if (!badge) return;
    badge.classList.remove('nav-badge--empty');
    var n = parseInt(badge.textContent, 10) || 0;
    badge.textContent = String(n + 1);
    if (reduce) return;
    badge.animate(
      [
        { transform: 'scale(1)', background: 'var(--accent)', color: 'var(--on-accent)' },
        { transform: 'scale(1.5)', background: 'var(--accent)', color: 'var(--on-accent)' },
        { transform: 'scale(1)' }
      ],
      { duration: 520, easing: 'cubic-bezier(.34,1.56,.64,1)' }
    );
    if (tab) {
      var resting = getComputedStyle(tab).color;
      tab.animate(
        [{ color: 'var(--accent)' }, { color: 'var(--accent)' }, { color: resting }],
        { duration: 700, easing: 'ease-out' }
      );
    }
  }

  function fly(card, tab, badge) {
    var cardRect = card.getBoundingClientRect();
    var tgt = tab.getBoundingClientRect();

    var clone = card.cloneNode(true);
    var s = clone.style;
    s.position = 'fixed'; s.left = cardRect.left + 'px'; s.top = cardRect.top + 'px';
    s.width = cardRect.width + 'px'; s.height = cardRect.height + 'px'; s.margin = '0';
    s.zIndex = '99999'; s.pointerEvents = 'none'; s.boxShadow = 'var(--shadow-2)';
    s.borderRadius = '14px'; s.transformOrigin = 'center center';
    s.willChange = 'transform, opacity';
    document.body.appendChild(clone);

    var dx = tgt.left + tgt.width / 2 - (cardRect.left + cardRect.width / 2);
    var dy = tgt.top + tgt.height / 2 - (cardRect.top + cardRect.height / 2);
    var midX = dx * 0.45;
    var midY = dy * 0.45 - 130;

    card.animate(
      [{ transform: 'scale(1)' }, { transform: 'scale(1.015)' }, { transform: 'scale(1)' }],
      { duration: 260, easing: 'ease-out' }
    );

    var flight = clone.animate(
      [
        { transform: 'translate(0,0) scale(1) rotate(0deg)', opacity: 1, offset: 0 },
        { transform: 'translate(' + midX + 'px,' + midY + 'px) scale(0.46) rotate(-5deg)', opacity: 0.96, offset: 0.55 },
        { transform: 'translate(' + dx + 'px,' + dy + 'px) scale(0.06) rotate(8deg)', opacity: 0, offset: 1 }
      ],
      { duration: 880, easing: 'cubic-bezier(.55,0,.7,.25)' }
    );

    var done = false;
    function finish() {
      if (done) return;
      done = true;
      clone.remove();
      bumpBadge(badge, tab);
    }
    flight.onfinish = finish;
    setTimeout(finish, 940);
  }

  document.addEventListener('click', function (e) {
    var btn = e.target.closest && e.target.closest('.extract');
    if (!btn || btn.dataset.flying) return;
    var tab = savedTab();
    var badge = badgeOf(tab);
    var card = btn.closest('.rcard, .rrow');
    if (!tab || !card) return;        // let HTMX proceed unenhanced
    btn.dataset.flying = '1';         // guard double-fire; do NOT preventDefault
    if (reduce) { bumpBadge(badge, tab); return; }
    fly(card, tab, badge);
  }, true);
})();
