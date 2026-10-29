'use strict';
(() => {
  const root = document.getElementById('evaluation-view');
  if (!root) return;
  const format = (value) => Number(value).toLocaleString('en-GB');

  root.querySelectorAll('[data-ev-population]').forEach((button) => {
    button.addEventListener('click', () => {
      const edited = button.dataset.evPopulation === 'edited';
      const total = edited ? 155 : 339;
      const maximum = edited ? 51 : 184;
      root.querySelectorAll('[data-ev-population]').forEach((item) => item.setAttribute('aria-pressed', String(item === button)));
      root.querySelectorAll('[data-ev-edit-count]').forEach((row) => {
        const count = Number(row.dataset.evEditCount);
        row.classList.toggle('hidden', edited && row.dataset.evEditBin === '0');
        row.querySelector('.ev-bar-track > span').style.setProperty('--bar', `${100 * count / maximum}%`);
        row.querySelector('[data-ev-edit-value]').textContent = format(count);
        row.querySelector('[data-ev-edit-percent]').textContent = `${(100 * count / total).toFixed(1)}%`;
      });
      document.getElementById('ev-edit-population').textContent = `${total} ${edited ? 'changed' : ''} pairs · minimum word edit operations`.replace('  ', ' ');
      document.getElementById('ev-edit-chart-note').textContent = edited
        ? 'Among the 155 changed texts, the median is 4 word edit operations and the mean is 5.77.'
        : '184 of 339 pairs are unchanged. Counts compare words in the generated and reviewer-submitted texts.';
    });
  });

  root.querySelectorAll('[data-ev-category-mode]').forEach((button) => {
    button.addEventListener('click', () => {
      const spans = button.dataset.evCategoryMode === 'spans';
      const maximum = spans ? 136 : 80;
      root.querySelectorAll('[data-ev-category-mode]').forEach((item) => item.setAttribute('aria-pressed', String(item === button)));
      root.querySelectorAll('[data-ev-category-texts]').forEach((row) => {
        const count = Number(spans ? row.dataset.evCategorySpans : row.dataset.evCategoryTexts);
        row.querySelector('.ev-bar-track > span').style.setProperty('--bar', `${100 * count / maximum}%`);
        row.querySelector('[data-ev-category-value]').textContent = format(count);
        row.querySelector('[data-ev-category-percent]').textContent = spans ? 'spans' : `${(100 * count / 341).toFixed(1)}%`;
      });
      document.getElementById('ev-category-axis').textContent = spans
        ? 'Highlight spans carrying each category · categories overlap'
        : 'Texts with at least one highlight in the category · out of 341';
      document.getElementById('ev-category-note').textContent = spans
        ? '390 highlight spans carry 431 category assignments. A span may carry several labels.'
        : 'A text or highlight can carry several categories. Category totals therefore overlap.';
    });
  });

  const tabs = [...root.querySelectorAll('[data-ev-case]')];
  function selectCase(button, focus = false) {
    tabs.forEach((tab) => {
      const selected = tab === button;
      tab.setAttribute('aria-selected', String(selected));
      tab.tabIndex = selected ? 0 : -1;
      document.getElementById(tab.getAttribute('aria-controls')).classList.toggle('hidden', !selected);
    });
    if (focus) button.focus();
  }
  tabs.forEach((button, index) => {
    button.addEventListener('click', () => selectCase(button));
    button.addEventListener('keydown', (event) => {
      let next;
      if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
      else if (event.key === 'ArrowLeft') next = (index + tabs.length - 1) % tabs.length;
      else if (event.key === 'Home') next = 0;
      else if (event.key === 'End') next = tabs.length - 1;
      else return;
      event.preventDefault();
      selectCase(tabs[next], true);
    });
  });

  function revealAnchor(hash, scroll = true) {
    if (!hash.startsWith('#ev-')) return;
    const target = document.getElementById(hash.slice(1));
    if (!target || !root.contains(target)) return;
    if (target.tagName === 'DETAILS') target.open = true;
    if (scroll && !root.classList.contains('hidden')) target.scrollIntoView({block:'start', behavior:'instant'});
  }
  root.querySelectorAll('a[href^="#ev-"]').forEach((link) => {
    link.addEventListener('click', (event) => {
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      const hash = link.getAttribute('href');
      history.replaceState({view:'evaluation'}, '', location.pathname + hash);
      revealAnchor(hash);
      const target = document.getElementById(hash.slice(1));
      if (target?.tagName === 'DETAILS') target.querySelector('summary').focus({preventScroll:true});
    });
  });
  window.addEventListener('popstate', () => revealAnchor(location.hash));
  revealAnchor(location.hash);
})();
