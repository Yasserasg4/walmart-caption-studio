"""
Authentic customer review photos — Reddit and DuckDuckGo review/blog sources only.
Aggressively excludes all commercial, professional, and stock photography domains.
"""
from __future__ import annotations
import asyncio
import urllib.parse
import httpx
from ddgs import DDGS

# Any URL containing these strings is a professional/commercial product image
_BLOCK = [
    'walmart.com', 'target.com', 'amazon.com', 'bestbuy.com', 'wayfair.com',
    'homedepot.com', 'lowes.com', 'costco.com', 'samsclub.com', 'ebay.com',
    'shutterstock', 'gettyimages', 'istockphoto', 'dreamstime', 'adobestock',
    'depositphotos', 'freepik', 'alamy', 'pond5', '123rf', 'vectorstock',
    'scene7.com', 'bbystatic', 'stanley1913', 'cdn.shopify',
    '/product-images/', '/catalog/', '/products/', '/item/', '/dp/',
    'walmartimages.com', 'tgtds.com', 'target.scene7',
    'media-amazon.com', 'images-amazon', 'ssl-images-amazon',
]

# Sources that produce authentic customer/lifestyle photos
_AUTHENTIC_DOMAINS = [
    'i.redd.it', 'preview.redd.it', 'i.imgur.com', 'imgur.com',
    'pinimg.com', 'blogspot.com', 'wordpress.com', 'wp.com',
    'squarespace.com', 'wix.com', 'weebly.com',
    'buzzfeed.com', 'thekrazycouponlady.com', 'hip2save.com',
    'slickdeals.net', 'dealnews.com',
]


def _is_authentic(url: str, width: int = 0, height: int = 0) -> bool:
    ul = url.lower()
    if ul.endswith(('.svg', '.gif', '.webp', '.ico')):
        return False
    if any(b in ul for b in _BLOCK):
        return False
    if width and height and (width < 180 or height < 180):
        return False
    return True


def _prefer_score(url: str) -> int:
    """Higher = more likely to be an authentic customer photo."""
    ul = url.lower()
    for i, domain in enumerate(_AUTHENTIC_DOMAINS):
        if domain in ul:
            return len(_AUTHENTIC_DOMAINS) - i
    return 0


async def search_reddit_images(product_name: str, num: int = 8) -> list[str]:
    """
    Hit Reddit's public JSON API for posts about this product.
    Reddit posts with photos are genuinely from real customers.
    """
    q = urllib.parse.quote(product_name)
    headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; ReviewFinder/1.0)',
        'Accept': 'application/json',
    }
    images: list[str] = []
    seen: set[str] = set()

    endpoints = [
        f'https://www.reddit.com/search.json?q={q}+review&type=link&sort=relevance&limit=25&t=year',
        f'https://www.reddit.com/search.json?q={q}+haul+bought&type=link&sort=new&limit=25',
        f'https://www.reddit.com/r/frugalfemalefashion+frugalmalefashion+walmartfinds+amazonfinds+buyitforlife/search.json?q={q}&restrict_sr=1&sort=new&limit=25',
    ]

    async with httpx.AsyncClient(headers=headers, timeout=15, follow_redirects=True) as client:
        for url in endpoints:
            if len(images) >= num:
                break
            try:
                resp = await client.get(url)
                if resp.status_code != 200:
                    continue
                posts = resp.json().get('data', {}).get('children', [])
                for post in posts:
                    p = post.get('data', {})

                    # Direct image link (i.redd.it, imgur)
                    direct = p.get('url_overridden_by_dest', '') or p.get('url', '')
                    if direct and any(direct.lower().endswith(e) for e in ['.jpg', '.jpeg', '.png']):
                        if any(d in direct for d in ['redd.it', 'imgur', 'i.imgur']):
                            if direct not in seen:
                                seen.add(direct)
                                images.append(direct)

                    # Reddit-hosted preview images (highest quality)
                    for img_obj in p.get('preview', {}).get('images', []):
                        src = img_obj.get('source', {}).get('url', '').replace('&amp;', '&')
                        if src and src.startswith('https') and src not in seen:
                            seen.add(src)
                            images.append(src)

                    if len(images) >= num:
                        break
            except Exception as e:
                print(f'[reddit] {e}')

    print(f'[images] Reddit raw: {len(images)}')
    return images[:num]


def search_ddg_review_photos(product_name: str, num: int = 8) -> list[str]:
    """
    DuckDuckGo image search with queries that target real customer/review photos.
    Scores results by authenticity and discards commercial domains.
    """
    queries = [
        f'{product_name} customer review photo real',
        f'{product_name} unboxing review bought 2024',
        f'{product_name} honest review blogger photo',
        f'{product_name} haul real photo reddit',
    ]
    seen: set[str] = set()
    scored: list[tuple[int, str]] = []

    with DDGS() as d:
        for q in queries:
            if len(scored) >= num * 3:
                break
            try:
                for h in d.images(q, max_results=25):
                    u = h.get('image', '')
                    w = h.get('width', 0)
                    ht = h.get('height', 0)
                    if u and u not in seen and _is_authentic(u, w, ht):
                        seen.add(u)
                        scored.append((_prefer_score(u), u))
            except Exception as e:
                print(f'[ddg] {e}')

    scored.sort(key=lambda x: x[0], reverse=True)
    return [u for _, u in scored[:num]]


async def get_authentic_review_images(product_name: str) -> list[str]:
    """
    Returns up to 8 authentic customer-style photo URLs.
    Reddit is the primary source (most authentic). DDG review sites fill the rest.
    """
    all_imgs: list[str] = []
    seen: set[str] = set()

    def add(imgs: list[str]):
        for u in imgs:
            if u and u not in seen:
                seen.add(u)
                all_imgs.append(u)

    reddit_imgs = await search_reddit_images(product_name, num=8)
    add(reddit_imgs)

    if len(all_imgs) < 6:
        try:
            ddg_imgs = await asyncio.get_event_loop().run_in_executor(
                None, search_ddg_review_photos, product_name, 8
            )
            add(ddg_imgs)
            print(f'[images] DDG: {len(ddg_imgs)}')
        except Exception as e:
            print(f'[images] DDG error: {e}')

    print(f'[images] Total unique: {len(all_imgs[:8])}')
    return all_imgs[:8]
