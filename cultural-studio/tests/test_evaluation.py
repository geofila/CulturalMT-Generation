"""Protect published research totals and the evaluation's navigation contract."""
import json
import unittest
from html.parser import HTMLParser

from app import ROOT, app, evaluation_data


class PageIds(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.references = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if values.get('id'):
            self.ids.append(values['id'])
        if values.get('href', '').startswith('#ev-'):
            self.references.append(values['href'][1:])
        if values.get('aria-controls', '').startswith('ev-'):
            self.references.append(values['aria-controls'])


class EvaluationTests(unittest.TestCase):
    def test_published_counts_and_weighted_scores_are_consistent(self):
        data = evaluation_data
        study, edits, highlights = data['study'], data['postediting'], data['highlights']
        self.assertEqual(sum(r['count'] for r in data['judgements']), study['reviewed_texts'])
        self.assertEqual(data['without_major']['count'], sum(r['count'] for r in data['judgements'][:2]))
        self.assertEqual(sum(b['count'] for b in edits['bins']), study['valid_postedit_pairs'])
        self.assertEqual(edits['unchanged'] + edits['changed'], edits['pairs'])
        self.assertEqual(edits['substitutions'] + edits['insertions'] + edits['deletions'], edits['word_edits'])
        self.assertEqual(edits['generated_words'] + edits['insertions'] - edits['deletions'], edits['postedit_words'])
        self.assertAlmostEqual(edits['word_edit_rate_percent'], 100 * edits['word_edits'] / edits['postedit_words'])
        self.assertAlmostEqual(edits['word_minimality_percent'], 100 * (1 - edits['word_edits'] / edits['max_pair_word_tokens']))
        self.assertAlmostEqual(edits['ter'], 100 * edits['ter_edits'] / edits['ter_reference_tokens'])
        self.assertEqual(sum(c['spans'] for c in highlights['categories']), highlights['label_assignments'])
        for category in highlights['categories']:
            self.assertAlmostEqual(category['document_percent'], 100 * category['documents'] / study['reviewed_texts'])

    def test_direct_route_has_unique_working_section_and_tab_targets(self):
        response = app.test_client().get('/evaluation')
        self.assertEqual(response.status_code, 200)
        text = response.get_data(as_text=True)
        self.assertIn('data-initial-view="evaluation"', text)
        self.assertIn('<title>Evaluation — CulturalMT</title>', text)
        self.assertIn('href="/evaluation" data-view="evaluation" aria-current="page"', text)
        ids = PageIds()
        ids.feed(text)
        self.assertEqual(len(ids.ids), len(set(ids.ids)))
        self.assertTrue(all(target in ids.ids for target in ids.references))
        self.assertEqual(sum(value.startswith('ev-case-tab-') for value in ids.ids), 6)

    def test_public_download_contains_aggregates_and_curated_examples(self):
        client = app.test_client()
        response = client.get('/static/data/evaluation.json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.get_data(as_text=True))
        self.assertEqual(data['study']['reviewed_texts'], 341)
        self.assertEqual(len(data['case_studies']), 6)
        self.assertNotIn('completed_by', response.get_data(as_text=True))
        self.assertNotIn('optional_comment', response.get_data(as_text=True))
        for case in data['case_studies']:
            self.assertTrue(case['source_url'].startswith('https://www.searchculture.gr/'))
            self.assertNotEqual(case['generated']['term'], case['reviewed']['term'])
        csv_response = client.get('/static/data/evaluation-results.csv')
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn('denominator', csv_response.get_data(as_text=True).splitlines()[0])


if __name__ == '__main__':
    unittest.main()
