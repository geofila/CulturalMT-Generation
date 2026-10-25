"""Read the project's RDF vocabularies without changing the original files."""
import hashlib
import html
import math
import re
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

LANG = '{http://www.w3.org/XML/1998/namespace}lang'
ABOUT = '{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about'
RESOURCE = '{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource'
SOURCES = {
    'ekt_items_types': ('Τύποι πολιτιστικών αντικειμένων', 'Object types', 'objects', '#a76c49'),
    'ekt-unesco': ('Θησαυρός UNESCO · ΕΚΤ', 'UNESCO thesaurus', 'themes', '#6d8573'),
    'thematic_tags': ('Θεματικές ετικέτες', 'Thematic tags', 'themes', '#9a885b'),
    'historical-periods': ('Ιστορικές περίοδοι', 'Historical periods', 'periods', '#98757c'),
    'searchculture-persons': ('Πρόσωπα SearchCulture', 'People', 'people', '#657b97'),
    'geonames-places-earth': ('Γεωγραφικοί τόποι', 'Places', 'places', '#738b80'),
    'geonames-supplementary-places': ('Συμπληρωματικοί τόποι', 'Supplementary places', 'places', '#ac8b69'),
}
STOP = set('και της των του την τον το τα οι ο η σε με για απο στη στην στο στον ενα μια ενος μιας που ειναι ως κατα μετα δε δεν εχει the a an and of in on at to from is was are with by for its it this that as or be has have into'.split())


def norm(value):
    value = ''.join(c for c in unicodedata.normalize('NFD', str(value).casefold()) if unicodedata.category(c) != 'Mn')
    return ' '.join(re.findall(r'[^\W_]+', value.replace('ς', 'σ'), re.UNICODE))


def local(tag):
    return tag.rsplit('}', 1)[-1]


def clean(element):
    text = ' '.join(element.itertext())
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', text)).strip()


def locate(text, phrase):
    """Return original character offsets, preserving accents and punctuation."""
    if not phrase or not phrase.strip():
        return []
    direct = list(re.finditer(r'(?<!\w)' + re.escape(phrase.strip()) + r'(?!\w)', text, re.I))
    if direct:
        return [{'start': m.start(), 'end': m.end(), 'text': m.group()} for m in direct]
    words = list(re.finditer(r'[^\W_]+', text, re.UNICODE))
    desired = norm(phrase).split()
    result = []
    for i in range(len(words) - len(desired) + 1):
        window = words[i:i + len(desired)]
        if [norm(w.group()) for w in window] == desired:
            start, end = window[0].start(), window[-1].end()
            result.append({'start': start, 'end': end, 'text': text[start:end]})
    return result


class Lexicon:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.concepts = {}
        self.sources = []
        self.exact = {'el': defaultdict(list), 'en': defaultdict(list)}
        self.prefix = {'el': defaultdict(set), 'en': defaultdict(set)}
        self.phrases = {'el': defaultdict(list), 'en': defaultdict(list)}
        self.tokens = defaultdict(set)
        self._load()

    def _load(self):
        files = sorted(self.folder.glob('*.rdf'))
        if not files:
            raise FileNotFoundError('Δεν βρέθηκαν RDF λεξικά στο ' + str(self.folder))
        self.fingerprint = hashlib.sha256(''.join(p.name + str(p.stat().st_mtime_ns) + str(p.stat().st_size) for p in files).encode()).hexdigest()[:16]
        for path in files:
            title, english, category, color = SOURCES.get(path.stem, (path.stem, path.stem, 'themes', '#738b80'))
            source = {'id': path.stem, 'title': title, 'title_en': english, 'category': category, 'color': color, 'file': path.name, 'count': 0, 'definitions': 0}
            raw = path.read_text(encoding='utf-8', errors='replace')
            raw = raw[raw.index('<rdf:RDF'):]
            # Several exports include browser headers and literal ampersands.
            raw = re.sub(r'&(?!#\d+;|#x[\da-fA-F]+;|amp;|lt;|gt;|quot;|apos;)', '&amp;', raw)
            raw = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', raw)
            root = ET.fromstring(raw)
            for elem in root.iter():
                uri = elem.get(ABOUT)
                if not uri or not any(local(c.tag) == 'prefLabel' for c in elem):
                    continue
                labels = {'el': [], 'en': []}
                preferred = {'el': '', 'en': ''}
                definitions = {'el': [], 'en': []}
                relationships, links, metadata = [], [], []
                for child in elem:
                    tag, lang = local(child.tag), child.get(LANG, '')[:2]
                    if tag in ('prefLabel', 'altLabel', 'hiddenLabel', 'prefLabelInPlural') and lang in labels:
                        text = clean(child)
                        if text and text not in labels[lang]:
                            labels[lang].append(text)
                        if tag == 'prefLabel' and not preferred[lang]:
                            preferred[lang] = text
                    elif tag in ('definition', 'scopeNote', 'note') and lang in definitions:
                        text = clean(child)
                        if text and text not in definitions[lang]:
                            definitions[lang].append(text)
                    elif tag in ('broader', 'narrower', 'related'):
                        if child.get(RESOURCE):
                            relationships.append({'type': tag, 'uri': child.get(RESOURCE)})
                    elif tag in ('exactMatch', 'closeMatch', 'sameAs', 'isPartOf'):
                        url = child.get(RESOURCE)
                        label = ''
                        for sub in child.iter():
                            url = url or sub.get(ABOUT) or sub.get(RESOURCE)
                            if local(sub.tag) == 'label' and sub.get(LANG) in ('en', 'el'):
                                label = clean(sub)
                        if url:
                            links.append({'url': url, 'label': label or url.split('/')[2]})
                    elif tag in ('dateOfBirth', 'dateOfDeath', 'gender', 'professionOrOccupation', 'placeOfBirth', 'placeOfDeath', 'begin', 'end', 'lat', 'long'):
                        text = clean(child)
                        if text:
                            metadata.append({'property': tag, 'value': text[:600]})
                if not any(preferred.values()):
                    continue
                cid = hashlib.sha1((path.stem + '|' + uri).encode()).hexdigest()[:12]
                self.concepts[cid] = {'id': cid, 'uri': uri, 'labels': labels, 'preferred': preferred, 'definitions': definitions,
                    'source': source, 'category': category, 'relations': relationships, 'links': links, 'metadata': metadata}
                source['count'] += 1
                source['definitions'] += bool(any(definitions.values()))
                for lang in ('el', 'en'):
                    for label in labels[lang]:
                        normalized = norm(label)
                        if not normalized:
                            continue
                        self.exact[lang][normalized].append(cid)
                        phrase_words = normalized.split()
                        if 2 <= len(phrase_words) <= 8 and len(phrase_words[0]) >= 3:
                            self.phrases[lang][(len(phrase_words), phrase_words[0][:3])].append((normalized, cid))
                        for word in normalized.split():
                            if len(word) > 2 and word not in STOP:
                                self.prefix[lang][word[:4]].add(cid)
                                self.tokens[word].add(cid)
                for text in definitions['el'] + definitions['en']:
                    for word in norm(text).split():
                        if len(word) > 3 and word not in STOP:
                            self.tokens[word].add(cid)
            self.sources.append(source)
        self.by_uri = {c['uri']: cid for cid, c in self.concepts.items()}

    def stats(self):
        return {'concepts': len(self.concepts), 'bilingual': sum(bool(c['preferred']['el'] and c['preferred']['en']) for c in self.concepts.values()),
                'definitions': sum(bool(any(c['definitions'].values())) for c in self.concepts.values()), 'sources': self.sources}

    def public(self, cid, related=True):
        c = self.concepts[cid]
        result = {k: c[k] for k in ('id', 'uri', 'labels', 'preferred', 'definitions', 'source', 'category', 'links', 'metadata')}
        result['relations'] = []
        if related:
            for relation in c['relations'][:18]:
                target = self.concepts.get(self.by_uri.get(relation['uri']))
                if target:
                    result['relations'].append({**relation, 'id': target['id'], 'label': target['preferred']['el'] or target['preferred']['en'], 'label_en': target['preferred']['en'] or target['preferred']['el']})
        return result

    def retrieve(self, text, lang, limit=70):
        words = list(re.finditer(r'[^\W_]+', text, re.UNICODE))
        matches = defaultdict(list)
        scores = Counter()
        for i in range(len(words)):
            for length in range(1, min(9, len(words) - i + 1)):
                window = words[i:i + length]
                phrase = text[window[0].start():window[-1].end()]
                normalized = norm(phrase)
                if normalized in STOP or len(normalized) < 3:
                    continue
                for cid in self.exact[lang].get(normalized, []):
                    if not self.concepts[cid]['preferred']['en' if lang == 'el' else 'el']:
                        continue
                    matches[cid].append({'start': window[0].start(), 'end': window[-1].end(), 'text': phrase, 'kind': 'exact', 'score': 1.0})
                    scores[cid] = max(scores[cid], 10 + length)
                if length >= 2 and len(normalized.split()[0]) >= 3:
                    pool = self.phrases[lang].get((length, normalized.split()[0][:3]), [])
                    for label, cid in pool[:150]:
                        if label == normalized or not self.concepts[cid]['preferred']['en' if lang == 'el' else 'el']:
                            continue
                        similarity = SequenceMatcher(None, normalized, label).ratio()
                        if similarity >= .86:
                            span = {'start': window[0].start(), 'end': window[-1].end(), 'text': phrase, 'kind': 'fuzzy', 'score': round(similarity, 3)}
                            if span not in matches[cid]:
                                matches[cid].append(span)
                            scores[cid] = max(scores[cid], 7 + length + similarity)
            word = norm(words[i].group())
            if len(word) < 4 or word in STOP:
                continue
            pool = self.prefix[lang].get(word[:4], set())
            # Avoid expanding common four-character prefixes without a bound.
            for cid in sorted(pool)[:350]:
                concept = self.concepts[cid]
                if not concept['preferred']['en' if lang == 'el' else 'el']:
                    continue
                best = max((SequenceMatcher(None, word, norm(label)).ratio() for label in concept['labels'][lang] if len(norm(label).split()) == 1), default=0)
                if best >= .82 and not matches[cid]:
                    matches[cid].append({'start': words[i].start(), 'end': words[i].end(), 'text': words[i].group(), 'kind': 'fuzzy', 'score': round(best, 3)})
                    scores[cid] = max(scores[cid], 5 + best)
            # Definition and label token search supplies additional candidates
            # for Harrier to rank; these are never asserted as literal matches.
            for cid in self.tokens.get(word, ()):
                if self.concepts[cid]['preferred']['en' if lang == 'el' else 'el']:
                    scores[cid] += min(1.8, math.log(1 + len(self.concepts) / (1 + len(self.tokens[word])))) * .12
        ranked = sorted(scores, key=lambda cid: (-scores[cid], cid))[:limit]
        return [{'id': cid, 'lexical_score': round(scores[cid], 3), 'matches': matches[cid]} for cid in ranked]

    def document(self, cid):
        c = self.concepts[cid]
        parts = [c['preferred']['el'], c['preferred']['en']]
        parts += [', '.join(c['labels'][lang][1:4]) for lang in ('el', 'en')]
        parts += [d[:800] for lang in ('el', 'en') for d in c['definitions'][lang][:1]]
        return ' | '.join(p for p in parts if p)[:2200]

    def search(self, query='', source='', page=1, per_page=24):
        needle = norm(query)
        if needle:
            tokens = needle.split()
            pool = set()
            for word in tokens:
                pool.update(self.tokens.get(word, set()))
                for lang in ('el', 'en'):
                    pool.update(self.prefix[lang].get(word[:4], set()))
            ids = sorted(pool, key=lambda cid: (0 if any(norm(l) == needle for ls in self.concepts[cid]['labels'].values() for l in ls) else 1,
                0 if any(needle in norm(l) for ls in self.concepts[cid]['labels'].values() for l in ls) else 1, self.concepts[cid]['preferred']['el']))
        else:
            ids = sorted(self.concepts, key=lambda cid: (not any(self.concepts[cid]['definitions'].values()), self.concepts[cid]['preferred']['el']))
        if source:
            ids = [cid for cid in ids if self.concepts[cid]['source']['id'] == source]
        total = len(ids)
        return {'items': [self.public(cid, False) for cid in ids[(page - 1) * per_page:page * per_page]], 'total': total, 'page': page, 'has_more': page * per_page < total}
