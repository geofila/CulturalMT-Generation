# CulturalMT Studio

A standalone Flask application for **Greek ↔ English cultural heritage text**. This folder does not modify or import the older translation runner. It reads the existing seven RDF files in `../dictionaries/`.

The interface is in English. The translation page is kept minimal; research information is on `/approach`, and the searchable terminology collection is on `/vocabularies`. Original Greek text, term names and source notes retain their language. The approach page describes the 341 human-reviewed test translations and the project's approximately 80k silver training collection, while identifying the current public release as 62,460 training records. See the [published dataset card](https://huggingface.co/datasets/georgefilandr/culturalMT).

## Start locally

Python 3.9+:

```bash
cd cultural-studio
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python start.py
```

Enter the Pharos API key at the hidden prompt, then open **http://127.0.0.1:5080**. The key is held only in the process environment and never written to a file, sent to the browser, or embedded in source. Alternatively, provide `PHAROS_API_KEY` in your existing environment and run `python app.py`.

The local server binds only to `127.0.0.1`, with Flask debug disabled. Leave its terminal running while using the app. Stop with Ctrl+C. No login, deployment or Git push is involved.

Optional environment variables:

| Variable | Default |
| --- | --- |
| `PORT` | `5080` |
| `CULTURALMT_DICTIONARIES` | `../dictionaries` |
| `PHAROS_BASE_URL` | `https://pharos-api.ails.ece.ntua.gr:20000/v1` |
| `PHAROS_CHAT_MODEL` | `Qwen/Qwen3.5-122B-A10B` |
| `PHAROS_EMBED_MODEL` | `microsoft/harrier-oss-v1-0.6b` |

## Experience

- Two-way Greek/English translation, examples and keyboard shortcut.
- Aligned source/translation highlights, linked term cards and a keyboard accessible detail drawer.
- Actual RDF definitions, notes, aliases, broader/narrower/related concepts, external references and available metadata.
- Search and source filtering across the full local lexicon, independently of model availability.
- Copy the translated text or download a JSON record containing the translation, aligned terms and provenance.
- Responsive museum-inspired layout, system fonts, no external UI resources.

## Evaluation page

`/evaluation` presents the CulturalMT human-review study: 341 Greek-to-English descriptions assessed by five reviewers, with 339 unambiguous generated/post-edit pairs used for editing metrics. It includes the complete judgement distribution, exact-match rate, defined word minimality, TER against human post-edits, edit-size and highlight-category charts, six source-linked reviewer edits and expandable measurement details. Charts can switch between all/changed pairs and text/highlight category counts. All content and native interactive controls are available without an inference key.

The versioned aggregate results and curated excerpts live in `static/data/evaluation.json`; `static/data/evaluation-results.csv` is a compact metrics download. They contain no reviewer identities, private comments or draft annotations. The JSON retains the evaluated system identifier and metric signatures for provenance. Results describe this reviewed collection; wording preservation, editing distance and human quality judgements are reported as separate measures.

The published totals are checked against edit-operation identities, explicit token denominators and category assignments. The two records with conflicting submitted versions are excluded from the main post-edit metrics; one identical duplicate submission is counted once. The 95% intervals use 10,000 bootstrap resamples grouped by exact Greek source text. The page also includes a sensitivity check and the TER/chrF/BLEU metric definitions.

## Retrieval and translation

1. Normalize diacritics and Greek final sigma for lookup, while retaining original character offsets.
2. Gather exact phrases, conservative fuzzy word/phrase matches (including Greek inflections) and candidates from label/definition tokens across all seven vocabularies.
3. Rerank this candidate pool with Harrier embeddings. This is **candidate reranking, not exhaustive dense search over all 27k records**. The query receives an instruction prefix and vectors are L2-normalized, following the [Harrier model card](https://huggingface.co/microsoft/harrier-oss-v1-0.6b).
4. Give Qwen the passage, candidate labels and real definitions. The prompt explicitly rejects unrelated senses and treats the source and RDF content as data.
5. Ask for a structured translation and term alignments. Reject references to unknown concept IDs and quotes not present in the source or translation. Only explicitly selected alignments appear under “Στη μετάφραση”. Other matches are clearly marked as candidates.
6. Run a second Qwen editorial pass to proofread the translation and reject homonyms and mismatched geographic, religious or historical attributions. Verify the quoted spans again after editing. If this check fails, preserve the draft translation but withhold “used” attributions and explain the limit in the UI.

Both inference requests go directly to **Pharos**, using `requests` and the same key. There is no OpenAI SDK, OpenAI model or OpenAI service. If embeddings fail, the UI explicitly reports lexical-only retrieval; a chat failure produces an error, never a fabricated translation.

The original RDF exports contain browser headers and some unescaped ampersands. The loader sanitizes these **in memory**, never changes source RDF files, and preserves their actual labels, definitions and source URIs.

## Data and practical limits

The inspected RDF collection has 27,413 records, including 19,859 bilingual records and 5,199 records with definitions or notes. Counts are computed live, not hardcoded in the UI. Missing definitions are clearly identified. Spelling similarity and embedding similarity are not confidence percentages.

The text and candidate terminology are sent to Pharos. The application keeps no translation history or source passages on disk. Only **RDF-document embeddings** are cached in ignored `.cache/embeddings.sqlite3`; the user's query embedding is not persisted. Clear `.cache/` when needed. Credentials and caches are excluded by this folder's `.gitignore`.

Translations and sense choices still require editorial review, especially ambiguous names. Verified alignment means the ID and quoted spans are real, not that the interpretation has been independently certified. Texts are limited to 6,000 characters per request. Longer texts should be split. Requests have timeouts and at most two translations run concurrently.

## Checks

```bash
python -B -m unittest discover -s tests -v
```

The tests check genuine RDF loading, bilingual lookup, original-offset preservation, rejection of invented alignment evidence, malformed model output, and API validation/security boundaries without external calls.
