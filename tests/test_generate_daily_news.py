import json
import unittest
from unittest.mock import MagicMock, patch, mock_open

_client_patcher = patch('miniflux.Client', return_value=MagicMock())
_client_patcher.start()

from myapp import app
import myapp.generate_daily_news as gdn_module


def _make_entries(n=2):
    return {'entries': [{'id': i, 'content': 'c', 'feed': {'site_url': 'http://x.com', 'category': {'title': 'cat'}}, 'title': 't', 'url': 'http://x.com', 'created_at': '2024-01-01T00:00:00Z', 'tags': []} for i in range(n)], 'total': n}


class TestGenerateDailyNewsEndpoint(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()
        self.mock_mc = MagicMock()
        self.mock_mc.get_entries.return_value = _make_entries(3)
        self._mc_patch = patch.object(gdn_module, 'miniflux_client', self.mock_mc)
        self._mc_patch.start()
        self._generate_patch = patch.object(gdn_module, 'generate_daily_news')
        self.mock_generate = self._generate_patch.start()
        self._executor_patch = patch('myapp.generate_daily_news.concurrent.futures.ThreadPoolExecutor')
        self.mock_executor_cls = self._executor_patch.start()
        # Make submit call the function synchronously for easier testing
        mock_executor = MagicMock()
        mock_executor.__enter__ = MagicMock(return_value=mock_executor)
        mock_executor.__exit__ = MagicMock(return_value=False)
        mock_executor.submit.side_effect = lambda fn, *args, **kwargs: fn(*args, **kwargs)
        self.mock_executor_cls.return_value = mock_executor
        # Patch file writes in _build_entries_json
        self._open_patch = patch('myapp.generate_daily_news.open', mock_open())
        self._open_patch.start()

    def tearDown(self):
        self._mc_patch.stop()
        self._generate_patch.stop()
        self._executor_patch.stop()
        self._open_patch.stop()

    def _post(self, body=None):
        kwargs = {'content_type': 'application/json'}
        if body is not None:
            kwargs['data'] = json.dumps(body)
        return self.client.post('/api/generate-daily-news', **kwargs)

    # --- no scope: just generate ---

    def test_no_body_triggers_generate(self):
        resp = self._post()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()['status'], 'ok')
        self.mock_generate.assert_called_once_with(self.mock_mc)

    def test_empty_body_triggers_generate(self):
        resp = self._post({})
        self.assertEqual(resp.status_code, 200)
        self.mock_generate.assert_called_once()

    # --- with scope: build entries.json then generate ---

    def test_scope_unread_builds_entries_and_generates(self):
        resp = self._post({'scope': 'unread'})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['queued'], 3)
        self.mock_mc.get_entries.assert_called_once_with(status=['unread'], limit=10000)
        self.mock_generate.assert_called_once_with(self.mock_mc)

    def test_scope_all(self):
        resp = self._post({'scope': 'all'})
        self.assertEqual(resp.status_code, 200)
        self.mock_mc.get_entries.assert_called_once_with(limit=10000)
        self.mock_generate.assert_called_once()

    def test_scope_last_n(self):
        resp = self._post({'scope': 'last_n', 'n': 5})
        self.assertEqual(resp.status_code, 200)
        self.mock_mc.get_entries.assert_called_once_with(limit=5, order='published_at', direction='desc')

    def test_scope_duration(self):
        with patch('core.reprocess_utils.time') as mock_time:
            mock_time.time.return_value = 10000
            resp = self._post({'scope': 'duration', 'duration': '2h'})
        self.assertEqual(resp.status_code, 200)
        self.mock_mc.get_entries.assert_called_once_with(limit=10000, after=10000 - 7200)

    # --- invalid scope ---

    def test_invalid_scope(self):
        resp = self._post({'scope': 'bogus'})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('scope', resp.get_json()['message'])

    def test_last_n_invalid(self):
        resp = self._post({'scope': 'last_n', 'n': -1})
        self.assertEqual(resp.status_code, 400)

    def test_duration_invalid(self):
        resp = self._post({'scope': 'duration', 'duration': '5s'})
        self.assertEqual(resp.status_code, 400)

    # --- empty entries ---

    def test_empty_entries_still_generates(self):
        self.mock_mc.get_entries.return_value = {'entries': [], 'total': 0}
        resp = self._post({'scope': 'unread'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()['queued'], 0)
        self.mock_generate.assert_called_once()


class TestBuildEntriesJson(unittest.TestCase):
    def test_builds_correct_format(self):
        entries = [
            {'id': 1, 'content': 'raw content', 'feed': {'category': {'title': 'Tech'}},
             'title': 'Test', 'url': 'http://x.com', 'created_at': '2024-01-01T00:00:00Z', 'tags': ['ai']},
        ]
        m = mock_open()
        with patch('myapp.generate_daily_news.open', m):
            gdn_module._build_entries_json(entries)

        written = m().write.call_args_list
        written_data = ''.join(call.args[0] for call in written)
        parsed = json.loads(written_data)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]['title'], 'Test')
        self.assertEqual(parsed[0]['content'], 'raw content')
        self.assertEqual(parsed[0]['category'], 'Tech')
        self.assertEqual(parsed[0]['tags'], ['ai'])


if __name__ == '__main__':
    unittest.main()
