import json
import os
import secrets
import threading
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from lexicon import Lexicon
from service import CHAT_MODEL, EMBED_MODEL, Pharos, ProviderError

ROOT = Path(__file__).resolve().parent
evaluation_data = json.loads((ROOT / 'static' / 'data' / 'evaluation.json').read_text(encoding='utf-8'))
DICTIONARIES = Path(os.getenv('CULTURALMT_DICTIONARIES', str(ROOT.parent / 'dictionaries')))
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 64 * 1024
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.json.ensure_ascii = False
lexicon = Lexicon(DICTIONARIES)
pharos = Pharos(ROOT / '.cache')
gate = threading.BoundedSemaphore(2)
csrf_token = secrets.token_urlsafe(32)


@app.after_request
def headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"
    if request.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store'
    return response


VOCABULARY_NOTES = {
    'ekt_items_types': 'Types of cultural objects, artworks and documents, with hierarchical relationships and selected definitions.',
    'ekt-unesco': 'Cultural, educational, social and humanities concepts in the Greek adaptation of the UNESCO Thesaurus.',
    'thematic_tags': 'More specific cultural subjects linked to the UNESCO Thesaurus.',
    'historical-periods': 'Historical periods and chronological terminology, including descriptive notes where available.',
    'searchculture-persons': 'People associated with cultural heritage, with name variants and available biographical information.',
    'geonames-places-earth': 'Geographic names and variants for cities, regions and other places.',
    'geonames-supplementary-places': 'Additional place names supplementing the main geographic authority collection.',
}


@app.route('/')
@app.route('/vocabularies')
@app.route('/approach')
@app.route('/evaluation')
def index():
    view = {'/approach': 'approach', '/vocabularies': 'lexicon', '/evaluation': 'evaluation'}.get(request.path, 'studio')
    titles = {'studio': 'CulturalMT — Cultural heritage translation', 'lexicon': 'Vocabularies — CulturalMT', 'approach': 'Our approach — CulturalMT', 'evaluation': 'Evaluation — CulturalMT'}
    return render_template('index.html', csrf_token=csrf_token, initial_view=view, page_title=titles[view],
                           concept_count=f'{len(lexicon.concepts):,}', sources=lexicon.sources, vocabulary_notes=VOCABULARY_NOTES,
                           evaluation=evaluation_data)


@app.route('/api/status')
def status():
    return jsonify({**lexicon.stats(), 'configured': bool(os.getenv('PHAROS_API_KEY')), 'model': CHAT_MODEL, 'embedding_model': EMBED_MODEL})


@app.route('/api/lexicon')
def browse():
    try:
        page = max(1, min(10000, int(request.args.get('page', 1))))
    except (ValueError, TypeError):
        return jsonify(error='Invalid page number.'), 400
    return jsonify(lexicon.search(request.args.get('q', '')[:200], request.args.get('source', ''), page))


@app.route('/api/concepts/<cid>')
def concept(cid):
    if cid not in lexicon.concepts:
        return jsonify(error='Entry not found.'), 404
    return jsonify(lexicon.public(cid))


@app.route('/api/translate', methods=['POST'])
def translate():
    if not secrets.compare_digest(request.headers.get('X-Studio-Token', ''), csrf_token):
        return jsonify(error='Please refresh the page and try again.'), 403
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error='Invalid request.'), 400
    text = data.get('text', '')
    lang = data.get('source_lang', 'el')
    if not isinstance(text, str) or not text.strip():
        return jsonify(error='Please enter a text to translate.'), 400
    text = text.strip()
    if len(text) > 6000:
        return jsonify(error='Please keep each text within 6,000 characters.'), 400
    if lang not in ('el', 'en'):
        return jsonify(error='Only Greek and English are supported.'), 400
    if not gate.acquire(blocking=False):
        return jsonify(error='Other translations are in progress. Please try again shortly.'), 429
    try:
        return jsonify(pharos.translate(lexicon, text, lang))
    except ProviderError as exc:
        return jsonify(error=str(exc)), 502
    except Exception:
        app.logger.exception('Translation failed')
        return jsonify(error='The translation could not be completed. Please try again.'), 500
    finally:
        gate.release()


@app.errorhandler(413)
def too_large(error):
    return jsonify(error='The submitted text is too large.'), 413


if __name__ == '__main__':
    print('CulturalMT Studio — http://127.0.0.1:%s' % os.getenv('PORT', '5080'), flush=True)
    app.run(host='127.0.0.1', port=int(os.getenv('PORT', '5080')), debug=False, threaded=True)
