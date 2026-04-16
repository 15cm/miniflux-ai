import sys
from yaml import safe_load

class Config:
    def __init__(self):
        self.c = safe_load(open('config.yml', encoding='utf8'))
        self.log_level = self.c.get('log_level', 'INFO')

        self.miniflux_base_url = self.get_config_value('miniflux', 'base_url', None)
        self.miniflux_api_key = self.get_config_value('miniflux', 'api_key', None)
        self.miniflux_webhook_secret = self.get_config_value('miniflux', 'webhook_secret', None)
        self.miniflux_schedule_interval = self.get_config_value('miniflux', 'schedule_interval', None)

        self.llm_provider = self.get_config_value('llm', 'provider', 'openai')
        self.llm_base_url = self.get_config_value('llm', 'base_url', None)
        self.llm_api_key = self.get_config_value('llm', 'api_key', None)
        self.llm_model = self.get_config_value('llm', 'model', None)
        self.llm_max_length = self.get_config_value('llm', 'max_length', None)
        self.llm_timeout = self.get_config_value('llm', 'timeout', 60)
        self.llm_max_workers = self.get_config_value('llm', 'max_workers', 4)
        self.llm_RPM = self.get_config_value('llm', 'RPM', 1000)

        self.ai_news_url = self.get_config_value('ai_news', 'url', None)
        self.ai_news_schedule = self.get_config_value('ai_news', 'schedule', None)
        self.ai_news_prompts = self.get_config_value('ai_news', 'prompts', None)
        self.ai_news_input = self.get_config_value('ai_news', 'input', None) or "{{ entries | map(attribute='content') | join('\n') }}"
        self.ai_news_use_summary_block_as_summary_input = self.get_config_value('ai_news', 'use_summary_block_as_summary_input', False)

        self.agents = self.c.get('agents', {})
        self._validate_agents()

    def _validate_agents(self):
        for name, agent in self.agents.items():
            if not agent.get('input'):
                print(f"ERROR: agents.{name}.input is required but missing or empty in config.yml", file=sys.stderr)
                sys.exit(1)

    def get_config_value(self, section, key, default=None):
        return self.c.get(section, {}).get(key, default)
