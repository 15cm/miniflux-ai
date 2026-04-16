import json
import unittest
from unittest.mock import MagicMock, patch

# myapp imports miniflux.Client at module level; patch before first import
# so no real network call is attempted.
_client_patcher = patch('miniflux.Client', return_value=MagicMock())
_client_patcher.start()

from myapp import app
import myapp.reprocess as reprocess_module
from myapp.reprocess import _parse_duration


def _make_entries(n=2):
    return {'entries': [{'id': i, 'content': 'c', 'feed': {'site_url': 'http://x.com', 'category': {'title': 'cat'}}, 'title': 't', 'url': 'http://x.com', 'created_at': '2024-01-01T00:00:00Z'} for i in range(n)], 'total': n}


class TestParseDuration(unittest.TestCase):
    def test_minutes(self):
        self.assertEqual(_parse_duration('30m'), 1800)

    def test_hours(self):
        self.assertEqual(_parse_duration('2h'), 7200)

    def test_days(self):
        self.assertEqual(_parse_duration('1d'), 86400)

    def test_whitespace(self):
        self.assertEqual(_parse_duration(' 5h '), 18000)

    def test_invalid_unit(self):
        self.assertIsNone(_parse_duration('10s'))

    def test_invalid_format(self):
        self.assertIsNone(_parse_duration('abc'))

    def test_empty(self):
        self.assertIsNone(_parse_duration(''))


class TestReprocessEndpoint(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()
        # Fresh mock for each test
        self.mock_mc = MagicMock()
        self.mock_mc.get_entries.return_value = _make_entries(3)
        self._mc_patch = patch.object(reprocess_module, 'miniflux_client', self.mock_mc)
        self._mc_patch.start()
        # Suppress background processing so threads don't outlive the test
        self._run_patch = patch.object(reprocess_module, '_run_process')
        self._run_patch.start()

    def tearDown(self):
        self._mc_patch.stop()
        self._run_patch.stop()

    def _post(self, body, headers=None):
        return self.client.post(
            '/api/reprocess',
            data=json.dumps(body),
            content_type='application/json',
            headers=headers or {},
        )

    # --- scope tests ---

    def test_scope_unread(self):
        resp = self._post({'scope': 'unread'})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['queued'], 3)
        self.mock_mc.get_entries.assert_called_once_with(status=['unread'], limit=10000)

    def test_scope_all(self):
        resp = self._post({'scope': 'all'})
        self.assertEqual(resp.status_code, 200)
        self.mock_mc.get_entries.assert_called_once_with(limit=10000)

    def test_scope_last_n(self):
        resp = self._post({'scope': 'last_n', 'n': 10})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()['queued'], 3)
        self.mock_mc.get_entries.assert_called_once_with(limit=10, order='published_at', direction='desc')

    def test_scope_duration(self):
        with patch('myapp.reprocess.time') as mock_time:
            mock_time.time.return_value = 10000
            resp = self._post({'scope': 'duration', 'duration': '1h'})
        self.assertEqual(resp.status_code, 200)
        self.mock_mc.get_entries.assert_called_once_with(limit=10000, after=10000 - 3600)

    def test_scope_invalid(self):
        resp = self._post({'scope': 'bogus'})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('scope', resp.get_json()['message'])

    def test_missing_scope(self):
        resp = self._post({})
        self.assertEqual(resp.status_code, 400)

    # --- last_n validation ---

    def test_last_n_missing_n(self):
        resp = self._post({'scope': 'last_n'})
        self.assertEqual(resp.status_code, 400)

    def test_last_n_zero(self):
        resp = self._post({'scope': 'last_n', 'n': 0})
        self.assertEqual(resp.status_code, 400)

    def test_last_n_negative(self):
        resp = self._post({'scope': 'last_n', 'n': -5})
        self.assertEqual(resp.status_code, 400)

    def test_last_n_string(self):
        resp = self._post({'scope': 'last_n', 'n': 'abc'})
        self.assertEqual(resp.status_code, 400)

    # --- duration validation ---

    def test_duration_invalid_unit(self):
        resp = self._post({'scope': 'duration', 'duration': '5s'})
        self.assertEqual(resp.status_code, 400)

    def test_duration_missing(self):
        resp = self._post({'scope': 'duration'})
        self.assertEqual(resp.status_code, 400)

    # --- empty result ---

    def test_empty_entries(self):
        self.mock_mc.get_entries.return_value = {'entries': [], 'total': 0}
        resp = self._post({'scope': 'unread'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()['queued'], 0)

    # --- auth ---

    def test_no_auth_required(self):
        # endpoint accessible without any Authorization header
        resp = self._post({'scope': 'unread'})
        self.assertEqual(resp.status_code, 200)


if __name__ == '__main__':
    unittest.main()
