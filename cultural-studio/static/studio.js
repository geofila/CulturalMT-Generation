'use strict';
const $ = (id) => document.getElementById(id);
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const number = (value) => Number(value).toLocaleString('en-GB');
const show = (id, visible = true) => $(id).classList.toggle('hidden', !visible);
const safeUrl = (value) => { try { const u = new URL(value); return ['https:', 'http:'].includes(u.protocol) ? u.href : '#'; } catch { return '#'; } };
const arrow = '<svg class="pair-arrow" viewBox="0 0 32 12" aria-hidden="true"><path d="M1 6h28m-5-4 4 4-4 4"/></svg>';
const categories = {objects:'OBJECTS', themes:'SUBJECTS & THEMES', periods:'HISTORICAL PERIODS', people:'PEOPLE', places:'PLACES'};
const metadataNames = {dateOfBirth:'Born',dateOfDeath:'Died',gender:'Gender',professionOrOccupation:'Occupation',placeOfBirth:'Birthplace',placeOfDeath:'Place of death',begin:'Beginning',end:'End',lat:'Latitude',long:'Longitude'};
const examples = {
  "ceramics": {
    "el": "Στην ενότητα της κινεζικής κεραμικής, τα αγγεία τεχνοτροπίας qingbai εκτίθενται δίπλα σε δείγματα τεχνοτροπίας Ding και τεχνοτροπίας Jun. Ο κατάλογος διακρίνει την τεχνοτροπία Cizhou από την τεχνοτροπία διακόσμησης wucai και την τεχνοτροπία famille rose, διατηρώντας τις διαφορές ανάμεσα στις παραδόσεις παραγωγής και διακόσμησης.",
    "en": "In the Chinese ceramics section, vessels in the Qingbai style are displayed alongside examples in the Ding style and Jun style. The catalogue distinguishes the Cizhou style from the Wucai decoration style and the Famille rose style, preserving the differences between these traditions of production and decoration."
  },
  "excavation": {
    "el": "Στο δελτίο της ανασκαφής καταγράφονται ένα ενεπίγραφο όστρακο, ένας σφραγιδόλιθος και ένα σφράγισμα. Το λεπτό χάλκινο έλασμα φέρει επιγραφή, ενώ το αρχιτεκτονικό μέλος σώζει ανάγλυφο. Η μελέτη συνδυάζει επιγραφική και νομισματική για την ερμηνεία του συνόλου.",
    "en": "The excavation record lists an inscribed ostracon, a sealstone and an imprint. The thin bronze lamella bears an inscription, while the architectural element preserves a relief. The study draws on epigraphy and numismatics to interpret the assemblage."
  },
  "print": {
    "el": "Η συλλογή εφήμερων περιλαμβάνει ένα τυπογραφικό δοκίμιο, μια αφιερωματική κάρτα Αγίων και ένα πρόγραμμα θεατρικής παράστασης. Η καρτέλα ευρετηρίου διακρίνει το έργο χαρακτικής από τη λιθογραφία. Στο ίδιο αρχείο, το πρωτότυπο που χρησίμευσε ως υπόδειγμα για την παραγωγή αντιγράφων καταγράφεται χωριστά από ένα μεταγενέστερο αντίγραφο.",
    "en": "The ephemera collection includes a printing proof, a santino and a theatre programme. The card index distinguishes an engraving from a lithograph. In the same archive, the master used as the working model for producing copies is recorded separately from a later replica."
  }
};
const state = {lang:'el', result:null, selected:null, tab:'used', busy:false, view:'studio', stats:null, concepts:new Map(), browsePage:1, browseSeq:0, browseTimer:null, focusBeforeDrawer:null};

function toast(message) {
  $('toast').textContent = message; show('toast');
  clearTimeout(toast.timer); toast.timer = setTimeout(() => show('toast', false), 2800);
}
function updateCount() { $('char-count').textContent = `${number($('source-text').value.length)} / 6,000`; }
function remember(concept) { state.concepts.set(concept.id, concept); return concept; }
function plainDefinition(concept) { return concept.definitions.en[0] || (concept.definitions.el.length ? 'An original Greek note is available in the entry.' : ''); }

function resetResult() {
  state.result = null; state.selected = null; state.tab = 'used';
  show('source-text'); show('source-highlighted', false); show('edit-button', false);
  show('target-text', false); show('copy-button', false); show('download-button', false);
  show('empty-state'); show('error-message', false); show('warning-message', false);
  show('terms-section', false); show('term-tabs', false); show('term-total', false);
  $('result-status').textContent = ''; $('term-grid').replaceChildren(); $('terms-explainer').textContent = '';
}

function setExample(name) {
  if (state.busy) return;
  resetResult(); $('source-text').value = examples[name][state.lang]; updateCount();
}

function updateLanguages() {
  $('source-code').textContent = state.lang.toUpperCase(); $('target-code').textContent = state.lang === 'el' ? 'EN' : 'EL';
  $('source-language').textContent = state.lang === 'el' ? 'Greek' : 'English';
  $('target-language').textContent = state.lang === 'el' ? 'English' : 'Greek';
  $('source-text').lang = state.lang; $('source-highlighted').lang = state.lang;
  $('target-text').lang = state.lang === 'el' ? 'en' : 'el';
  $('source-text').placeholder = 'Enter a cultural heritage description…';
}

function highlightText(node, text, terms, side) {
  // Prefer the selected concept, then the longest phrase. Spans cannot overlap.
  const ranges = [];
  // Python offsets count Unicode code points; DOM strings count UTF-16 units.
  const offsets = [0]; for (const char of text) offsets.push(offsets[offsets.length - 1] + char.length);
  terms.forEach((term) => (term[`${side}_spans`] || []).forEach((span) => {
    const start = offsets[span.start], end = offsets[span.end];
    if (start !== undefined && end !== undefined && text.slice(start, end) === span.text) ranges.push({...span, start, end, term});
  }));
  ranges.sort((a,b) => (b.term.id === state.selected) - (a.term.id === state.selected) || (b.end - b.start) - (a.end - a.start) || a.start - b.start);
  const accepted = [];
  for (const range of ranges) if (!accepted.some((r) => range.start < r.end && range.end > r.start)) accepted.push(range);
  accepted.sort((a,b) => a.start - b.start);
  node.replaceChildren(); let last = 0;
  accepted.forEach((range) => {
    node.append(document.createTextNode(text.slice(last, range.start)));
    const mark = document.createElement('button'); mark.type = 'button'; mark.className = 'mark-term';
    mark.dataset.termId = range.term.id; mark.dataset.category = range.term.category; mark.textContent = text.slice(range.start, range.end);
    mark.classList.toggle('selected', range.term.id === state.selected);
    mark.setAttribute('aria-label', `${mark.textContent} — view entry for ${range.term.preferred.en || range.term.preferred.el}`);
    mark.title = `${range.term.preferred.el} ↔ ${range.term.preferred.en}`;
    node.append(mark); last = range.end;
  });
  node.append(document.createTextNode(text.slice(last)));
}

function renderHighlights() {
  if (!state.result) return;
  highlightText($('source-highlighted'), state.result.source_text, state.result.terms, 'source');
  highlightText($('target-text'), state.result.translation, state.result.terms, 'target');
}

function card(concept, mode = 'translation') {
  remember(concept);
  const sourceLang = mode === 'translation' ? state.lang : 'en';
  const targetLang = sourceLang === 'el' ? 'en' : 'el';
  const source = mode === 'translation' && concept.source_spans?.[0]?.text || concept.preferred[sourceLang] || concept.preferred[targetLang];
  const target = mode === 'translation' && concept.target_spans?.[0]?.text || concept.preferred[targetLang] || '—';
  const definition = plainDefinition(concept);
  const status = mode === 'browse' ? 'SOURCE ENTRY' : concept.status === 'used' ? 'USED IN TRANSLATION' : 'CANDIDATE';
  return `<button type="button" class="term-card ${state.selected === concept.id ? 'selected' : ''}" data-term-id="${esc(concept.id)}" style="--category-color:${esc(concept.source.color)}"><span class="card-top"><span><i class="category-dot"></i>${esc(categories[concept.category] || 'TERM')}</span><span aria-hidden="true">↗</span></span><span class="term-pair"><span class="term-source">${esc(source)}</span>${arrow}<span class="term-target">${esc(target)}</span></span><span class="term-definition ${definition ? '' : 'no-definition'}">${esc(definition || 'No definition in the source.')}</span><span class="card-footer"><span>${esc(concept.source.title_en)}</span><span>${status}</span></span></button>`;
}

function renderTerms() {
  if (!state.result) return;
  const {terms, candidates} = state.result;
  show('terms-section'); show('term-tabs'); show('term-total'); $('term-total').textContent = terms.length;
  $('used-tab').innerHTML = `Used in translation <span>${terms.length}</span>`;
  $('candidate-tab').innerHTML = `Other matches <span>${candidates.length}</span>`;
  for (const [id, name] of [['used-tab','used'],['candidate-tab','candidate']]) {
    $(id).classList.toggle('active', state.tab === name); $(id).setAttribute('aria-selected', String(state.tab === name));
  }
  const shown = state.tab === 'used' ? terms : candidates;
  $('term-grid').innerHTML = shown.length ? shown.map((c) => card(c)).join('') : `<div class="no-results">${state.tab === 'used' ? 'No supported term alignments were found in this passage.' : 'No additional matches.'}</div>`;
  $('terms-explainer').textContent = state.tab === 'used' ? '' : 'Suggestions only; these entries were not confirmed in the translation.';
}

function setBusy(busy) {
  state.busy = busy;
  for (const id of ['translate-button','swap-button','clear-button','edit-button']) $(id).disabled = busy;
  document.querySelectorAll('.example-button').forEach((b) => b.disabled = busy);
  $('source-text').readOnly = busy;
  $('translate-button').querySelector('span').textContent = busy ? 'Translating…' : 'Translate';
  $('translate-button').setAttribute('aria-busy', String(busy));
  show('loading-state', busy);
}

async function translate() {
  if (state.busy) return;
  const text = $('source-text').value.trim();
  if (!text) { $('source-text').focus(); toast('Enter a text to translate.'); return; }
  if (text.length > 6000) { toast('Please keep the text within 6,000 characters.'); return; }
  show('error-message', false); show('warning-message', false); show('empty-state', false); show('target-text', false);
  show('copy-button', false); show('download-button', false); $('result-status').textContent = '';
  setBusy(true);
  $('loading-title').textContent = 'Translating…'; $('loading-detail').textContent = 'Checking terminology and meaning.';
  const longTimer = setTimeout(() => { $('loading-title').textContent = 'Still translating…'; $('loading-detail').textContent = 'This is taking longer than usual. Please keep this page open.'; }, 45000);
  try {
    const response = await fetch('/api/translate', {method:'POST',headers:{'Content-Type':'application/json','X-Studio-Token':document.querySelector('meta[name="studio-token"]').content},body:JSON.stringify({text,source_lang:state.lang})});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'The translation could not be completed.');
    state.result = data; state.selected = null; state.tab = 'used';
    data.terms.forEach(remember); data.candidates.forEach(remember); renderHighlights(); renderTerms();
    show('source-text', false); show('source-highlighted'); show('edit-button'); show('target-text'); show('copy-button'); show('download-button');
    $('result-status').textContent = 'Ready';
    if (data.meta.embedding_warning) { $('warning-message').textContent = 'Some terminology could not be checked for context. Please review the suggested matches.'; show('warning-message'); }
    if (data.meta.verification_warning) { $('warning-message').textContent = 'The translation is available, but its terminology review could not be completed.'; show('warning-message'); }
  } catch (error) {
    $('error-message').textContent = error.message || 'Connection unavailable. Please try again.'; show('error-message');
    if (state.result) { show('target-text'); show('copy-button'); show('download-button'); } else show('empty-state');
  } finally { clearTimeout(longTimer); setBusy(false); }
}

async function openConcept(cid, relation = false) {
  const trigger = document.activeElement;
  let concept = state.concepts.get(cid);
  if (!concept || relation || !concept.status) {
    try {
      const response = await fetch('/api/concepts/' + encodeURIComponent(cid));
      if (!response.ok) throw new Error();
      concept = remember(await response.json());
    } catch { toast('This entry could not be loaded. Please try again.'); return; }
  }
  state.selected = cid;
  if (state.result) { renderHighlights(); renderTerms(); }
  document.querySelectorAll('.term-card').forEach((c) => c.classList.toggle('selected', c.dataset.termId === cid));
  const english = concept.definitions.en.map((d) => `<p class="definition-text" lang="en">${esc(d)}</p>`).join('');
  const greek = concept.definitions.el.length ? `<details class="original-note"><summary>Original Greek definition or note</summary>${concept.definitions.el.map((d) => `<p class="definition-text" lang="el">${esc(d)}</p>`).join('')}</details>` : '';
  const aliases = [...new Set([...concept.labels.en, ...concept.labels.el])].filter((l) => l !== concept.preferred.el && l !== concept.preferred.en);
  const relationships = concept.relations || [];
  const relationNames = {broader:'Broader',narrower:'Narrower',related:'Related'};
  $('drawer-content').innerHTML = `<div class="drawer-category"><i class="category-dot" style="--category-color:${esc(concept.source.color)}"></i>${esc(categories[concept.category])}</div><h2 id="drawer-title" class="drawer-title">${esc(concept.preferred.en || concept.preferred.el)}</h2><p class="drawer-target" lang="el">${esc(concept.preferred.el || '')}</p><span class="drawer-status">${concept.status === 'used' ? 'Linked to the translation' : concept.status === 'candidate' ? 'Candidate entry · check the sense' : 'Source vocabulary entry'}</span>${concept.source_spans?.length && concept.target_spans?.length ? `<div class="alignment-excerpt">${esc(concept.source_spans[0].text)}<span>↳ ${esc(concept.target_spans[0].text)}</span></div>` : ''}<section class="drawer-section"><h3>DEFINITION & NOTES</h3>${english || '<p class="drawer-empty-note">No English definition is provided in this source entry.</p>'}${greek}</section>${aliases.length ? `<section class="drawer-section"><h3>ALTERNATIVE NAMES</h3><div class="drawer-aliases">${aliases.map((a) => `<span>${esc(a)}</span>`).join('')}</div></section>` : ''}${relationships.length ? `<section class="drawer-section"><h3>RELATED CONCEPTS</h3>${relationships.map((r) => `<button class="relation-button" data-relation-id="${esc(r.id)}"><small>${relationNames[r.type] || esc(r.type)}</small>${esc(r.label_en || r.label)}<span>↗</span></button>`).join('')}</section>` : ''}${concept.metadata.length ? `<section class="drawer-section"><h3>ADDITIONAL INFORMATION</h3>${concept.metadata.map((m) => `<div class="metadata-row"><span>${esc(metadataNames[m.property] || m.property)}</span><span>${esc(m.value)}</span></div>`).join('')}</section>` : ''}<section class="provenance"><h3>SOURCE</h3><p>${esc(concept.source.title_en)}</p><p>National Documentation Centre · SearchCulture</p><a href="${esc(safeUrl(concept.uri))}" target="_blank" rel="noopener noreferrer">View source entry <span>↗</span></a></section>${concept.links.length ? `<section class="drawer-section"><h3>EXTERNAL REFERENCES</h3>${concept.links.map((l) => `<a class="external-link" href="${esc(safeUrl(l.url))}" target="_blank" rel="noopener noreferrer">${esc(l.label)} ↗</a>`).join('')}</section>` : ''}`;
  if ($('term-drawer').classList.contains('hidden')) state.focusBeforeDrawer = trigger;
  show('drawer-backdrop'); show('term-drawer'); document.body.style.overflow = 'hidden';
  document.querySelector('main').inert = true; document.querySelector('header').inert = true; document.querySelector('footer').inert = true;
  $('term-drawer').scrollTop = 0; $('close-drawer').focus();
}

function closeDrawer() {
  show('drawer-backdrop', false); show('term-drawer', false); document.body.style.overflow = '';
  document.querySelector('main').inert = false; document.querySelector('header').inert = false; document.querySelector('footer').inert = false;
  if (state.focusBeforeDrawer?.isConnected) state.focusBeforeDrawer.focus();
  else document.querySelector(`[data-term-id="${state.selected}"]`)?.focus();
}

function viewForPath() { return {'/approach':'approach','/vocabularies':'lexicon','/evaluation':'evaluation'}[location.pathname] || 'studio'; }
function setView(view, push = true) {
  if (!['studio','lexicon','approach','evaluation'].includes(view)) view = 'studio';
  state.view = view;
  for (const name of ['studio','lexicon','approach','evaluation']) show(name + '-view', view === name);
  document.querySelectorAll('[data-view]').forEach((b) => { b.classList.toggle('active', b.dataset.view === view); if (b.dataset.view === view) b.setAttribute('aria-current','page'); else b.removeAttribute('aria-current'); });
  const path = {studio:'/',lexicon:'/vocabularies',approach:'/approach',evaluation:'/evaluation'}[view];
  if (push && location.pathname !== path) history.pushState({view}, '', path);
  document.title = {studio:'CulturalMT — Cultural heritage translation',lexicon:'Vocabularies — CulturalMT',approach:'Our approach — CulturalMT',evaluation:'Evaluation — CulturalMT'}[view];
  if (view === 'lexicon') loadLexicon(true);
  window.scrollTo({top:0,behavior:'instant'});
}

async function loadLexicon(reset = false) {
  if (reset) state.browsePage = 1;
  const sequence = ++state.browseSeq;
  const params = new URLSearchParams({q:$('lexicon-search').value,source:$('source-filter').value,page:String(state.browsePage)});
  $('lexicon-count').textContent = 'Searching…'; $('load-more').disabled = true;
  if (reset) $('lexicon-grid').innerHTML = '<div class="no-results">Loading entries…</div>';
  try {
    const response = await fetch('/api/lexicon?' + params);
    if (!response.ok) throw new Error();
    const data = await response.json();
    if (sequence !== state.browseSeq) return;
    const markup = data.items.map((c) => card(c, 'browse')).join('');
    if (reset) $('lexicon-grid').innerHTML = markup || '<div class="no-results">No entries found. Try another term or vocabulary.</div>';
    else $('lexicon-grid').insertAdjacentHTML('beforeend', markup);
    $('lexicon-count').textContent = `${number(data.total)} entries`; show('load-more', data.has_more);
  } catch { if (sequence === state.browseSeq) { $('lexicon-count').textContent = 'Connection unavailable'; if (reset) $('lexicon-grid').innerHTML = '<div class="no-results">The vocabulary could not be loaded. Please try again.</div>'; } }
  finally { if (sequence === state.browseSeq) $('load-more').disabled = false; }
}

async function init() {
  updateLanguages(); setExample('ceramics'); setView(document.body.dataset.initialView || viewForPath(), false);
  try {
    const response = await fetch('/api/status'); if (!response.ok) throw new Error();
    state.stats = await response.json();
    state.stats.sources.forEach((source) => $('source-filter').add(new Option(source.title_en, source.id)));
    if (!state.stats.configured) { $('warning-message').textContent = 'Translation is unavailable. Please check the local service configuration.'; show('warning-message'); }
  } catch { $('warning-message').textContent = 'The local translation service is unavailable. Please try again.'; show('warning-message'); }
}

$('translate-button').addEventListener('click', translate);
$('source-text').addEventListener('input', () => { updateCount(); if (state.result) resetResult(); });
$('source-text').addEventListener('keydown', (e) => { if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') { e.preventDefault(); translate(); } });
$('clear-button').addEventListener('click', () => { resetResult(); $('source-text').value = ''; updateCount(); $('source-text').focus(); });
$('edit-button').addEventListener('click', () => { show('source-text'); show('source-highlighted', false); show('edit-button', false); $('source-text').focus(); });
$('swap-button').addEventListener('click', () => { if (state.busy) return; const text = state.result?.translation; state.lang = state.lang === 'el' ? 'en' : 'el'; resetResult(); if (text) $('source-text').value = text; updateLanguages(); updateCount(); toast(state.lang === 'el' ? 'Greek → English' : 'English → Greek'); });
document.querySelectorAll('[data-example]').forEach((b) => b.addEventListener('click', () => setExample(b.dataset.example)));
document.querySelectorAll('[data-view]').forEach((b) => b.addEventListener('click', (e) => { if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return; e.preventDefault(); setView(b.dataset.view); }));
window.addEventListener('popstate', () => setView(viewForPath(), false));
$('used-tab').addEventListener('click', () => { state.tab = 'used'; renderTerms(); });
$('candidate-tab').addEventListener('click', () => { state.tab = 'candidate'; renderTerms(); });
$('copy-button').addEventListener('click', async () => { if (!state.result) return; try { await navigator.clipboard.writeText(state.result.translation); toast('Translation copied.'); } catch { toast('Copy is unavailable. Please select the text to copy it.'); } });
$('download-button').addEventListener('click', () => {
  if (!state.result) return;
  const data = {application:'CulturalMT Studio', ...state.result};
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], {type:'application/json;charset=utf-8'}));
  const link = document.createElement('a'); link.href = url; link.download = 'culturalmt-translation.json'; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1500); toast('Translation and sources downloaded.');
});
$('close-drawer').addEventListener('click', closeDrawer); $('drawer-backdrop').addEventListener('click', closeDrawer);
document.addEventListener('click', (e) => {
  const term = e.target.closest('[data-term-id]'); if (term) { openConcept(term.dataset.termId); return; }
  const relation = e.target.closest('[data-relation-id]'); if (relation) { openConcept(relation.dataset.relationId, true); return; }
  const source = e.target.closest('[data-source-id]'); if (source) { $('source-filter').value = source.dataset.sourceId; $('lexicon-search').value = ''; setView('lexicon'); }
});
document.addEventListener('pointerover', (e) => { const item = e.target.closest('[data-term-id]'); if (item) document.querySelectorAll(`[data-term-id="${item.dataset.termId}"]`).forEach((el) => el.classList.add('selected')); });
document.addEventListener('pointerout', (e) => { const item = e.target.closest('[data-term-id]'); if (item && item.dataset.termId !== state.selected) document.querySelectorAll(`[data-term-id="${item.dataset.termId}"]`).forEach((el) => el.classList.remove('selected')); });
document.addEventListener('keydown', (e) => {
  if ($('term-drawer').classList.contains('hidden')) return;
  if (e.key === 'Escape') closeDrawer();
  if (e.key === 'Tab') {
    const focusables = [...$('term-drawer').querySelectorAll('button,a[href]')]; const first = focusables[0], last = focusables[focusables.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  }
});
$('lexicon-search').addEventListener('input', () => { clearTimeout(state.browseTimer); state.browseSeq++; state.browseTimer = setTimeout(() => loadLexicon(true), 250); });
$('source-filter').addEventListener('change', () => loadLexicon(true));
$('load-more').addEventListener('click', () => { state.browsePage++; loadLexicon(); });
init();
