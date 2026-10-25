import os
import unittest
import tempfile
from unittest.mock import patch

from app import app, csrf_token, lexicon
from lexicon import locate
from service import Pharos, ProviderError, parse_translation, validate_alignments


class GroundingTests(unittest.TestCase):
    def test_real_collection(self):
        stats = lexicon.stats()
        self.assertEqual(len(stats['sources']), 7)
        self.assertGreater(stats['bilingual'], 10000)
        self.assertGreater(stats['definitions'], 100)
        self.assertTrue(all(s['count'] > 0 for s in stats['sources']))

    def test_two_way_lookup_and_original_offsets(self):
        for lang, text in [('el', 'Μια φορητή εικόνα.'), ('en', 'An icon in the museum.')]:
            candidates = lexicon.retrieve(text, lang)
            icons = [c for c in candidates if lexicon.concepts[c['id']]['preferred']['en'] == 'Icon']
            self.assertTrue(icons)
            for item in icons:
                for span in item['matches']:
                    self.assertEqual(text[span['start']:span['end']], span['text'])

    def test_accent_normalization_keeps_offsets_and_word_boundaries(self):
        self.assertEqual(locate('Η ΑΘΉΝΑ είναι πόλη.', 'αθηνα')[0], {'start': 2, 'end': 7, 'text': 'ΑΘΉΝΑ'})
        self.assertEqual(locate('The icons are here.', 'icon'), [])

    def test_inflected_greek_multiword_terms_are_retrieved(self):
        candidates = lexicon.retrieve('Αντικείμενα καθημερινής ζωής.', 'el')
        matches = [m for c in candidates if lexicon.concepts[c['id']]['preferred']['el'] == 'Καθημερινή ζωή' for m in c['matches']]
        self.assertTrue(any(m['text'] == 'καθημερινής ζωής' for m in matches))

    def test_rejects_hallucinated_alignment_evidence(self):
        text, target = 'Η φορητή εικόνα.', 'The icon.'
        candidates = {c['id']: c for c in lexicon.retrieve(text, 'el')}
        cid = next(cid for cid in candidates if lexicon.concepts[cid]['preferred']['en'] == 'Icon')
        alignments = [
            {'concept_id': 'invented', 'source_text': 'εικόνα', 'target_text': 'icon'},
            {'concept_id': cid, 'source_text': 'ανύπαρκτο', 'target_text': 'icon'},
            {'concept_id': cid, 'source_text': 'φορητή εικόνα', 'target_text': 'unseen'},
        ]
        self.assertEqual(validate_alignments(lexicon, text, target, alignments, candidates), [])
        alignments.append({'concept_id': cid, 'source_text': 'φορητή εικόνα', 'target_text': 'icon'})
        used = validate_alignments(lexicon, text, target, alignments, candidates)
        self.assertEqual(len(used), 1)
        self.assertEqual(used[0]['definitions'], lexicon.concepts[cid]['definitions'])

    def test_structured_output_failure_is_not_a_translation(self):
        for raw in ['not json', '{}', '{"translation":""}', '[]']:
            with self.assertRaises(ProviderError):
                parse_translation(raw)
        self.assertEqual(parse_translation('```json\n{"translation":"A museum.","alignments":[]}\n```')['translation'], 'A museum.')

    def test_user_queries_are_not_persisted_in_embedding_cache(self):
        def fake_embedding(route, payload, timeout):
            return {'data': [{'index': i, 'embedding': [3.0, 4.0]} for i in range(len(payload['input']))]}
        with tempfile.TemporaryDirectory() as folder:
            provider = Pharos(folder)
            with patch.object(provider, 'request', side_effect=fake_embedding) as request:
                vectors = provider.embeddings(['private user query', 'RDF document'])
                self.assertAlmostEqual(float((vectors[0] ** 2).sum()), 1)
                with provider.connection() as db:
                    self.assertEqual(db.execute('SELECT count(*) FROM embeddings').fetchone()[0], 1)
                provider.embeddings(['private user query', 'RDF document'])
                self.assertEqual(request.call_args.args[1]['input'], ['private user query'])

    def test_sense_check_can_reject_a_real_but_unrelated_rdf_record(self):
        terms = [{'source_spans':[{'text':'Παναγίας'}], 'target_spans':[{'text':'Virgin Mary'}], 'preferred':{'el':'Παναγία','en':'Panagia'}, 'category':'places', 'definitions':{'el':[],'en':[]}, 'uri':'https://example.com/place'}]
        with tempfile.TemporaryDirectory() as folder:
            provider = Pharos(folder)
            with patch.object(provider, 'request', return_value={'choices':[{'message':{'content':'{"translation":"Icon of the Virgin Mary","alignments":[]}'}}]}):
                self.assertEqual(provider.verify_senses('Εικόνα της Παναγίας', 'Icon of the Virgin Mary', terms)['alignments'], [])
            with patch.object(provider, 'request', return_value={'choices':[{'message':{'content':'unstructured response'}}]}):
                with self.assertRaises(ProviderError):
                    provider.verify_senses('source', 'translation', terms)


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.headers = {'X-Studio-Token': csrf_token}

    def test_page_and_status_no_credentials(self):
        page = self.client.get('/')
        self.assertEqual(page.status_code, 200)
        self.assertIn('frame-ancestors', page.headers['Content-Security-Policy'])
        status = self.client.get('/api/status')
        self.assertEqual(status.status_code, 200)
        key = os.getenv('PHAROS_API_KEY')
        if key:
            self.assertNotIn(key, status.get_data(as_text=True))
            self.assertNotIn(key, page.get_data(as_text=True))

    def test_no_model_call_for_invalid_inputs(self):
        self.assertEqual(self.client.post('/api/translate', json={'text':'hello'}).status_code, 403)
        for payload in [{'text':''}, {'text':123}, {'text':'x' * 6001}, {'text':'hello','source_lang':'fr'}, []]:
            self.assertEqual(self.client.post('/api/translate', json=payload, headers=self.headers).status_code, 400)

    def test_lexicon_search_and_missing_concept(self):
        result = self.client.get('/api/lexicon?q=εικόνα').get_json()
        self.assertGreater(result['total'], 0)
        self.assertIn('definitions', result['items'][0])
        self.assertEqual(self.client.get('/api/concepts/unknown').status_code, 404)
        self.assertEqual(self.client.get('/api/lexicon?page=invalid').status_code, 400)


if __name__ == '__main__':
    unittest.main()
