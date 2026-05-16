import json
import os

CONFIG_DIR = os.path.expanduser('~/.config/tuxscribe')
CONFIG_FILE = os.path.join(CONFIG_DIR, 'config.json')

DEFAULTS = {
    'api_key': '',
    'model': 'anthropic/claude-3.5-sonnet',
    'base_url': 'https://openrouter.ai/api/v1',
    'site_url': 'https://tuxscribe.app',
    'site_name': 'tuxscribe',
}


class Config:
    def __init__(self):
        self._data = dict(DEFAULTS)
        self._load()

    def _load(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    stored = json.load(f)
                self._data.update(stored)
            except (json.JSONDecodeError, OSError):
                pass

    def save(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self._data, f, indent=2)

    def get(self, key, fallback=None):
        return self._data.get(key, fallback)

    def set(self, key, value):
        self._data[key] = value

    @property
    def api_key(self):
        return self._data.get('api_key', '')

    @api_key.setter
    def api_key(self, value):
        self._data['api_key'] = value

    @property
    def model(self):
        return self._data.get('model', DEFAULTS['model'])

    @model.setter
    def model(self, value):
        self._data['model'] = value

    @property
    def base_url(self):
        return self._data.get('base_url', DEFAULTS['base_url'])
