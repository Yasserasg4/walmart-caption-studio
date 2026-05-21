from __future__ import annotations
import re
import json
from curl_cffi.requests import AsyncSession

# ── Helpers ──────────────────────────────────────────────────────────────────

def parse_next_data(html: str) -> dict:
    """Pull product fields out of __NEXT_DATA__ embedded JSON."""
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return {}
    try:
        nj = json.loads(m.group(1))
        prod = (
            nj.get('props', {})
            .get('pageProps', {})
            .get('initialData', {})
            .get('data', {})
            .get('product', {})
        )
        if not prod:
            return {}
        pi = prod.get('priceInfo') or {}
        cat_path = (prod.get('category') or {}).get('path') or []
        return {
            'name':           prod.get('name', ''),
            'price':          str((pi.get('currentPrice') or {}).get('price', '') or (pi.get('priceRange') or {}).get('minPrice', '') or ''),
            'original_price': str((pi.get('wasPrice') or {}).get('price', '') or ''),
            'rating':         str(prod.get('averageRating', '')),
            'review_count':   str(prod.get('numberOfReviews', '')),
            'category':       cat_path[-1].get('name', '') if cat_path else '',
            'description':    (prod.get('shortDescription', '') or '')[:400],
        }
    except Exception as e:
        print(f'[parse] error: {e}')
        return {}


async def fetch_product_info(url: str) -> dict:
    """
    Fetches Walmart product page using curl_cffi to impersonate Chrome's TLS fingerprint,
    bypassing Walmart's CDN bot detection.
    """
    try:
        async with AsyncSession() as session:
            resp = await session.get(url, impersonate='chrome124', timeout=25, allow_redirects=True)
            if resp.status_code == 200:
                return parse_next_data(resp.text)
    except Exception as e:
        print(f'[fetch] error: {e}')
    return {}


def _fallback_name_from_url(url: str) -> str:
    m = re.search(r'/ip/([^/]+)/', url)
    if m:
        return m.group(1).replace('-', ' ')
    return ''


async def scrape_walmart_product(url: str) -> dict:
    product_data: dict = {
        'url': url,
        'name': '', 'price': '', 'original_price': '',
        'rating': '', 'review_count': '', 'category': '', 'description': '',
    }

    info = await fetch_product_info(url)

    # Reject bot/captcha pages
    _bad = ['robot', 'human', "couldn't find", 'not found', 'access denied', 'captcha']
    if any(b in (info.get('name') or '').lower() for b in _bad):
        info['name'] = ''

    product_data.update({k: v for k, v in info.items() if v})

    if not product_data.get('name'):
        slug = _fallback_name_from_url(url)
        if slug:
            product_data['name'] = slug

    return product_data
