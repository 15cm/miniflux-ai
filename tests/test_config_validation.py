import importlib.util
import os
import sys
import textwrap
import unittest

# Load config module directly to avoid triggering common/__init__.py logger setup.
_config_path = os.path.join(os.path.dirname(__file__), '..', 'common', 'config.py')
_spec = importlib.util.spec_from_file_location('config', _config_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
Config = _mod.Config


def _write_config(tmp_path, content):
    cfg = tmp_path / 'config.yml'
    cfg.write_text(textwrap.dedent(content))
    return str(tmp_path)


BASE_CONFIG = """\
    log_level: INFO
    miniflux:
      base_url: http://test
      api_key: test
    llm:
      base_url: http://test
      api_key: test
      model: test
    agents:
"""


class TestAgentInputValidation(unittest.TestCase):

    def test_missing_input_exits(self, tmp_path=None):
        """Config with agent missing input field → sys.exit(1)."""
        import tempfile, pathlib
        with tempfile.TemporaryDirectory() as d:
            cfg = pathlib.Path(d) / 'config.yml'
            cfg.write_text(textwrap.dedent(BASE_CONFIG + """\
              summary:
                title: 'Test'
                prompt: 'Summarize.'
                style_block: true
                deny_list:
                allow_list:
            """))
            orig = os.getcwd()
            os.chdir(d)
            try:
                with self.assertRaises(SystemExit) as ctx:
                    Config()
                self.assertEqual(ctx.exception.code, 1)
            finally:
                os.chdir(orig)

    def test_empty_input_exits(self):
        """Config with agent input set to empty string → sys.exit(1)."""
        import tempfile, pathlib
        with tempfile.TemporaryDirectory() as d:
            cfg = pathlib.Path(d) / 'config.yml'
            cfg.write_text(textwrap.dedent(BASE_CONFIG + """\
              summary:
                title: 'Test'
                input: ''
                prompt: 'Summarize.'
                style_block: true
                deny_list:
                allow_list:
            """))
            orig = os.getcwd()
            os.chdir(d)
            try:
                with self.assertRaises(SystemExit) as ctx:
                    Config()
                self.assertEqual(ctx.exception.code, 1)
            finally:
                os.chdir(orig)

    def test_valid_input_loads(self):
        """Config with all agent input fields present → loads successfully."""
        import tempfile, pathlib
        with tempfile.TemporaryDirectory() as d:
            cfg = pathlib.Path(d) / 'config.yml'
            cfg.write_text(textwrap.dedent(BASE_CONFIG + """\
              summary:
                title: 'Test'
                input: '{{ content }}'
                prompt: 'Summarize.'
                style_block: true
                deny_list:
                allow_list:
            """))
            orig = os.getcwd()
            os.chdir(d)
            try:
                config = Config()
                self.assertEqual(config.agents['summary']['input'], '{{ content }}')
            finally:
                os.chdir(orig)


if __name__ == '__main__':
    unittest.main()
