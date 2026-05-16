import json
import threading
import requests
from gi.repository import GLib


class APIError(Exception):
    pass


class APIClient:
    def __init__(self, config):
        self.config = config

    def _headers(self):
        return {
            'Authorization': f'Bearer {self.config.api_key}',
            'Content-Type': 'application/json',
            'HTTP-Referer': self.config.get('site_url', ''),
            'X-Title': self.config.get('site_name', 'tuxscribe'),
        }

    def _url(self, path):
        return f"{self.config.base_url.rstrip('/')}/{path.lstrip('/')}"

    def complete(self, messages, system=None, model=None):
        if not self.config.api_key:
            raise APIError("No API key configured. Open Settings to add your OpenRouter API key.")
        payload = {
            'model': model or self.config.model,
            'messages': messages,
        }
        if system:
            payload['messages'] = [{'role': 'system', 'content': system}] + list(messages)
        try:
            resp = requests.post(
                self._url('/chat/completions'),
                headers=self._headers(),
                json=payload,
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
            return data['choices'][0]['message']['content']
        except requests.HTTPError as e:
            try:
                detail = e.response.json().get('error', {}).get('message', str(e))
            except Exception:
                detail = str(e)
            raise APIError(f"API error: {detail}")
        except requests.RequestException as e:
            raise APIError(f"Network error: {e}")

    def stream_complete(self, messages, system=None, model=None,
                        on_chunk=None, on_done=None, on_error=None):
        """Stream completion in a background thread. Callbacks are called on the GTK main thread."""
        def run():
            if not self.config.api_key:
                if on_error:
                    GLib.idle_add(on_error, "No API key configured. Open Settings to add your OpenRouter API key.")
                return

            payload = {
                'model': model or self.config.model,
                'messages': messages,
                'stream': True,
            }
            if system:
                payload['messages'] = [{'role': 'system', 'content': system}] + list(messages)

            try:
                resp = requests.post(
                    self._url('/chat/completions'),
                    headers=self._headers(),
                    json=payload,
                    stream=True,
                    timeout=180,
                )
                resp.raise_for_status()

                for line in resp.iter_lines():
                    if not line:
                        continue
                    if line.startswith(b'data: '):
                        data = line[6:]
                        if data.strip() == b'[DONE]':
                            break
                        try:
                            chunk = json.loads(data)
                            delta = chunk['choices'][0]['delta']
                            text = delta.get('content', '')
                            if text and on_chunk:
                                GLib.idle_add(on_chunk, text)
                        except (json.JSONDecodeError, KeyError, IndexError):
                            pass

                if on_done:
                    GLib.idle_add(on_done)

            except requests.HTTPError as e:
                try:
                    detail = e.response.json().get('error', {}).get('message', str(e))
                except Exception:
                    detail = str(e)
                if on_error:
                    GLib.idle_add(on_error, f"API error: {detail}")
            except requests.RequestException as e:
                if on_error:
                    GLib.idle_add(on_error, f"Network error: {e}")

        t = threading.Thread(target=run, daemon=True)
        t.start()
        return t

    def complete_async(self, messages, system=None, model=None,
                       on_done=None, on_error=None):
        """Non-streaming async completion."""
        def run():
            try:
                result = self.complete(messages, system=system, model=model)
                if on_done:
                    GLib.idle_add(on_done, result)
            except Exception as e:
                if on_error:
                    GLib.idle_add(on_error, str(e))

        t = threading.Thread(target=run, daemon=True)
        t.start()
        return t
