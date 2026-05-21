import re
import unicodedata
import xml.etree.ElementTree as ET
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DICTIONARIES_DIR = PROJECT_DIR / "dictionaries"

GREEK_STOPWORDS = {
    "και",
    "της",
    "των",
    "τον",
    "την",
    "στο",
    "στη",
    "στην",
    "στον",
    "του",
    "το",
    "τα",
    "οι",
    "ο",
    "η",
    "σε",
    "με",
    "για",
    "που",
    "απο",
    "από",
    "ως",
    "ενα",
    "ένα",
    "μια",
    "ενος",
    "ενός",
    "μιας",
    "ειναι",
    "είναι",
    "η",
    "ή",
    "τις",
    "τους",
    "στοιχεια",
    "στοιχεία",
    "μεσα",
    "μέσα",
    "πανω",
    "πάνω",
    "κατω",
    "κάτω",
}

LABEL_TAGS = {"prefLabel", "altLabel", "hiddenLabel", "prefLabelInPlural"}
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
RDF_ABOUT = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about"


def strip_accents(text):
    text = text.replace("ς", "σ")
    normalized = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def normalize_greek(text):
    text = strip_accents((text or "").lower())
    text = re.sub(r"[^α-ω\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def greek_tokens(text):
    return re.findall(r"[Α-ΩΆ-Ώα-ωά-ώϊϋΐΰς]+", text or "")


def local_name(tag):
    return tag.split("}")[-1].split(":")[-1]


def clean_label(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()


def unique_terms(terms):
    unique = []
    seen = set()

    for term in terms:
        key = (term["greek_norm"], term["english"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(term)

    return unique


def make_terms(greek_terms, english_terms, source, uri=None):
    terms = []
    english_label = english_terms[0] if english_terms else ""

    for greek_term in greek_terms:
        greek_norm = normalize_greek(greek_term)
        if not greek_norm:
            continue

        terms.append(
            {
                "greek": greek_term,
                "english": english_label,
                "greek_norm": greek_norm,
                "token_count": len(greek_norm.split()),
                "uri": uri,
                "source": source,
            }
        )

    return terms


def load_rdf_terms(rdf_path, source=None):
    rdf_path = Path(rdf_path)
    source = source or rdf_path.stem
    raw_text = rdf_path.read_text(encoding="utf-8", errors="ignore")
    start = raw_text.find("<rdf:RDF")
    if start != -1:
        raw_text = raw_text[start:]

    try:
        root = ET.fromstring(raw_text)
    except ET.ParseError:
        return load_rdf_terms_with_regex(raw_text, source)

    terms = []
    for elem in root.iter():
        greek_terms = []
        english_terms = []

        for child in elem:
            if local_name(child.tag) not in LABEL_TAGS:
                continue

            text = clean_label(" ".join(child.itertext()))
            if not text:
                continue

            lang = child.attrib.get(XML_LANG)
            if lang == "el":
                greek_terms.append(text)
            elif lang == "en":
                english_terms.append(text)

        if greek_terms:
            terms.extend(make_terms(greek_terms, english_terms, source, elem.attrib.get(RDF_ABOUT)))

    return unique_terms(terms)


def load_rdf_terms_with_regex(raw_text, source):
    terms = []
    block_pattern = r"<(?P<tag>[\w:.-]+)\b[^>]*rdf:about=[\"'](?P<uri>[^\"']+)[\"'][^>]*>(?P<body>.*?)</(?P=tag)>"
    label_pattern = r"<(?P<tag>[\w:.-]+)\b[^>]*xml:lang=[\"'](?P<lang>el|en)[\"'][^>]*>(?P<text>.*?)</(?P=tag)>"

    for block in re.finditer(block_pattern, raw_text, re.DOTALL):
        greek_terms = []
        english_terms = []

        for label in re.finditer(label_pattern, block.group("body"), re.DOTALL):
            if local_name(label.group("tag")) not in LABEL_TAGS:
                continue

            text = clean_label(label.group("text"))
            if not text:
                continue

            if label.group("lang") == "el":
                greek_terms.append(text)
            else:
                english_terms.append(text)

        if greek_terms:
            terms.extend(make_terms(greek_terms, english_terms, source, block.group("uri")))

    return unique_terms(terms)


def load_all_rdf_terms(dictionaries_dir=DEFAULT_DICTIONARIES_DIR):
    dictionaries_path = Path(dictionaries_dir)
    rdf_paths = sorted(dictionaries_path.glob("*.rdf"))
    if not rdf_paths:
        raise FileNotFoundError(f"No .rdf files found in {dictionaries_path}")

    return {rdf_path.stem: load_rdf_terms(rdf_path, source=rdf_path.stem) for rdf_path in rdf_paths}


def flatten_vocabularies(vocabularies):
    return [term for terms in vocabularies.values() for term in terms if term.get("english")]


def term_keys(greek_norm):
    keys = set()

    for word in greek_norm.split():
        if word in GREEK_STOPWORDS:
            continue
        keys.add(word)
        if len(word) >= 4:
            keys.add(word[:4])

    return keys or set(greek_norm.split())


def build_indexes(terms):
    exact_index = defaultdict(list)
    candidates_by_token_count = defaultdict(list)
    key_index_by_token_count = defaultdict(lambda: defaultdict(list))
    max_tokens = max((term["token_count"] for term in terms), default=1)

    for order, term in enumerate(terms):
        term = dict(term)
        term["_order"] = order
        term["_keys"] = term_keys(term["greek_norm"])
        exact_index[term["greek_norm"]].append(term)

        for token_count in range(max(1, term["token_count"] - 1), term["token_count"] + 2):
            candidates_by_token_count[token_count].append(term)
            for key in term["_keys"]:
                key_index_by_token_count[token_count][key].append(term)

    return {
        "exact": exact_index,
        "by_token_count": candidates_by_token_count,
        "by_key": key_index_by_token_count,
        "max_tokens": max_tokens,
    }


def extract_candidate_phrases(description, max_tokens):
    tokens = greek_tokens(description)
    candidates = []

    for start in range(len(tokens)):
        for size in range(1, min(max_tokens, len(tokens) - start) + 1):
            phrase_tokens = tokens[start : start + size]
            normalized = normalize_greek(" ".join(phrase_tokens))
            if not normalized:
                continue
            if all(token in GREEK_STOPWORDS for token in normalized.split()):
                continue

            candidates.append(
                {
                    "phrase": " ".join(phrase_tokens),
                    "norm": normalized,
                    "token_count": size,
                    "start": start,
                    "end": start + size,
                }
            )

    return candidates


def score_phrase_against_vocab(phrase_norm, vocab_norm, min_score=0.0):
    matcher = SequenceMatcher(None, phrase_norm, vocab_norm)
    if matcher.real_quick_ratio() < min_score:
        return 0.0
    if matcher.quick_ratio() < min_score:
        return 0.0
    return matcher.ratio()


def get_vocab_candidates(candidate, indexes, full_scan=False):
    if full_scan:
        return indexes["by_token_count"].get(candidate["token_count"], [])

    candidates = {}
    key_index = indexes["by_key"].get(candidate["token_count"], {})

    for key in term_keys(candidate["norm"]):
        for term in key_index.get(key, []):
            candidates[term["_order"]] = term

    return [candidates[order] for order in sorted(candidates)]


def find_best_match(candidate, indexes, threshold, full_scan=False):
    exact_matches = indexes["exact"].get(candidate["norm"])
    if exact_matches and threshold <= 1.0:
        return exact_matches[0], 1.0

    best_match = None
    best_score = 0.0

    for item in get_vocab_candidates(candidate, indexes, full_scan=full_scan):
        score = score_phrase_against_vocab(candidate["norm"], item["greek_norm"], min_score=threshold)
        if score > best_score:
            best_score = score
            best_match = item

    return best_match, best_score


def find_dictionary_matches(description, dictionaries_dir=DEFAULT_DICTIONARIES_DIR, threshold=0.84, max_results=20):
    matcher = DictionaryMatcher(dictionaries_dir=dictionaries_dir)
    return matcher.find_matches(description=description, threshold=threshold, max_results=max_results)


class DictionaryMatcher:
    def __init__(self, dictionaries_dir=DEFAULT_DICTIONARIES_DIR):
        self.dictionaries_dir = Path(dictionaries_dir)
        self.vocabularies = load_all_rdf_terms(self.dictionaries_dir)
        self.terms = flatten_vocabularies(self.vocabularies)
        self.indexes = build_indexes(self.terms)

    def find_matches(self, description, threshold=0.84, max_results=20):
        return find_matches_with_indexes(
            description=description,
            indexes=self.indexes,
            threshold=threshold,
            max_results=max_results,
        )

    def build_terms_translation(self, description, threshold=0.84, max_results=20):
        matches = self.find_matches(
            description=description,
            threshold=threshold,
            max_results=max_results,
        )
        return format_terms_translation(matches), matches


def find_matches_with_indexes(description, indexes, threshold=0.84, max_results=20):
    candidates = extract_candidate_phrases(description, indexes["max_tokens"])
    matches = []

    for candidate in candidates:
        best_match, best_score = find_best_match(candidate, indexes, threshold)
        if best_match and best_score >= threshold:
            matches.append(
                {
                    "matched_text": candidate["phrase"],
                    "vocab_term": best_match["greek"],
                    "translation": best_match["english"],
                    "source": best_match["source"],
                    "score": round(best_score, 3),
                    "start": candidate["start"],
                    "end": candidate["end"],
                }
            )

    matches.sort(key=lambda x: (x["score"], len(x["matched_text"])), reverse=True)
    return filter_matches(matches, max_results=max_results)


def filter_matches(matches, max_results=20):
    filtered = []
    occupied_spans = []
    seen_pairs = set()

    for match in matches:
        pair_key = (normalize_greek(match["matched_text"]), match["translation"])
        if pair_key in seen_pairs:
            continue

        overlaps = any(not (match["end"] <= start or match["start"] >= end) for start, end in occupied_spans)
        if overlaps:
            continue

        seen_pairs.add(pair_key)
        occupied_spans.append((match["start"], match["end"]))
        filtered.append(match)

        if len(filtered) >= max_results:
            break

    return filtered


def format_terms_translation(matches):
    return "\n".join(
        f'{match["matched_text"]} -> {match["translation"]} '
        f'(vocab: {match["vocab_term"]}, source: {match["source"]}, score={match["score"]})'
        for match in matches
    )


def build_terms_translation_from_description(
    description,
    dictionaries_dir=DEFAULT_DICTIONARIES_DIR,
    threshold=0.84,
    max_results=20,
):
    matcher = DictionaryMatcher(dictionaries_dir=dictionaries_dir)
    return matcher.build_terms_translation(
        description=description,
        threshold=threshold,
        max_results=max_results,
    )
