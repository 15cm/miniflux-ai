import os
import sys
from unittest.mock import MagicMock

# Change to tests/ dir at collection time so config.yml resolves correctly.
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Stub packages not available in the nix dev shell so app modules can import.
for _pkg in ('miniflux', 'openai', 'ratelimit', 'google', 'google.genai'):
    sys.modules.setdefault(_pkg, MagicMock())

# ratelimit decorators must be callable and return the original function.
_rl = sys.modules['ratelimit']
_rl.limits.return_value = lambda f: f
_rl.sleep_and_retry = lambda f: f
