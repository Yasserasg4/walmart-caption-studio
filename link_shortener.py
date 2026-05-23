from __future__ import annotations
import re
import os
import requests

_session: requests.Session | None = None
_csrf_token: str = ''

# PythonAnywhere free plan requires their proxy for external HTTPS
_PA_PROXY = 'http://proxy.server:3128'
_PROXIES = {'http': _PA_PROXY, 'https': _PA_PROXY} if os.getenv('PYTHONANYWHERE_SITE') else {}

_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}


def _get_session() -> tuple[requests.Session, str]:
    global _session, _csrf_token
    s = requests.Session()
    s.headers.update(_HEADERS)

    r = s.get('https://mavlinks.com/user/login', proxies=_PROXIES, timeout=20, allow_redirects=True)
    m = re.search(r'name="_token"\s+value="([^"]+)"', r.text)
    if not m:
        raise RuntimeError('Could not extract CSRF token from mavlinks.com')
    token = m.group(1)

    r2 = s.post('https://mavlinks.com/user/login/auth', proxies=_PROXIES, timeout=20,
                allow_redirects=True, data={
                    'email': 'Mavlinkyasse',
                    'password': 'Mavlinkyasse10',
                    '_token': token,
                })
    if 'Dashboard' not in r2.text and '/user' not in r2.url:
        raise RuntimeError('mavlinks.com login failed')

    dash = s.get('https://mavlinks.com/user', proxies=_PROXIES, timeout=20)
    m2 = re.search(r'name="_token"\s+value="([^"]+)"', dash.text)
    _csrf_token = m2.group(1) if m2 else token
    _session = s
    return s, _csrf_token


def shorten_link(url: str) -> str:
    """Shortens a URL via mavlinks.com → returns a mavlink.to short URL."""
    global _session, _csrf_token

    for attempt in range(2):
        try:
            if _session is None or not _csrf_token:
                _session, _csrf_token = _get_session()

            r = _session.post('https://mavlinks.com/shorten', proxies=_PROXIES, timeout=20,
                              headers={**_HEADERS,
                                       'X-Requested-With': 'XMLHttpRequest',
                                       'Accept': 'application/json'},
                              data={
                                  'domain': 'https://mavlink.to',
                                  'url': url,
                                  '_token': _csrf_token,
                              })
            data = r.json()
            if data.get('error') is False:
                return data['data']['shorturl']

            if attempt == 0:
                _session = None
                _csrf_token = ''
                continue

            raise RuntimeError(data.get('message', 'Unknown error from mavlinks.com'))

        except RuntimeError:
            raise
        except Exception as e:
            if attempt == 0:
                _session = None
                _csrf_token = ''
                continue
            raise RuntimeError(f'mavlinks.com request failed: {e}')

    raise RuntimeError('mavlinks.com shorten failed after retry')
