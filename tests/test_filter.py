import unittest
from types import SimpleNamespace
from yaml import safe_load
from core.entry_filter import filter_entry


def _as_config(d):
    """Wrap a raw config dict so .agents works like a real Config object."""
    return SimpleNamespace(agents=d['agents'])

test_config = '''
{
  "test_style_block": {
    "agents": {
      "test": {
        "title": "🌐AI 翻译",
        "style_block": true,
        "allow_list": ,
        "deny_list": 
      }
    }
  },
  "test_allow_list": {
    "agents": {
      "test": {
        "title": "🌐AI 翻译",
        "style_block": false,
        "allow_list": [
          "https://9to5mac.com/",
          "https://home.kpmg/*"
        ],
        "deny_list": 
      }
    }
  },
  "test_deny_list": {
    "agents": {
      "test": {
        "title": "🌐AI 翻译",
        "style_block": false,
        "allow_list": ,
        "deny_list": [
          "https://9to5mac.com/",
          "https://home.kpmg/cn/zh/home/insights.html"
        ]
      }
    }
  },
  "test_None": {
    "agents": {
      "test": {
        "title": "🌐AI 翻译",
        "style_block": false,
        "allow_list": ,
        "deny_list": 
      }
    }
  }
}
'''

test_entries = '''
{
  "test_style_block":
    {
        "entry":
          {
            "content": '<blockquote>',
            "feed":
              {
                "site_url": "https://weibo.com/1906286443/OAih1wghK",
              },
          },
      "result": False,
    },
  "test_allow_list":
    {
        "entry":
          {
            "content": '123',
            "feed":
              {
                "site_url": "https://home.kpmg/cn/zh/home/insights.html",
              },
          },
      "result": True,
    },
  "test_deny_list":
    {
        "entry":
          {
            "content": '123',
            "feed":
              {
                "site_url": "https://weibo.com/1906286443/OAih1wghK",
              },
          },
      "result": True,
    },
  "test_None":
    {
        "entry":
          {
            "content": '123',
            "feed":
              {
                "site_url": "https://weibo.com/1906286443/OAih1wghK",
              },
          },
      "result": True,
    },
}

'''

configs = safe_load(test_config)
entries = safe_load(test_entries)

class MyTestCase(unittest.TestCase):
    def test_entry_filter(self):
        for key, cfg in configs.items():
            with self.subTest(scenario=key):
                config_obj = _as_config(cfg)
                agent = ('test', cfg['agents']['test'])
                entry = entries[key]
                result = filter_entry(config_obj, agent, entry['entry'])
                self.assertEqual(result, entry['result'])


if __name__ == '__main__':
    unittest.main()
