"""
AI image generation via Pollinations.ai (100% free, no API key needed).
Generates realistic phone-camera-style customer photos:
  - In-store (Walmart aisle, SALE tags)
  - Hand holding the product
  - Unboxing on a home surface
  - Product in use / lifestyle shot
"""
from __future__ import annotations
import asyncio
import hashlib
import urllib.parse
import httpx
from groq import Groq
import os

POLLINATIONS_BASE = 'https://image.pollinations.ai/prompt'


def _seed(text: str, offset: int = 0) -> int:
    """Deterministic seed from product name so same product = same images on retry."""
    return (int(hashlib.md5(text.encode()).hexdigest(), 16) + offset) % 999999


def _best_prompt(product_name: str, category: str = '', seed_offset: int = 0) -> dict:
    """
    Pick the single best-converting prompt style.
    Rotates between 4 scenes so "New AI Photo" gives variety.
    """
    scenes = [
        {
            'id': 'hand',
            'label': '✋ Customer Photo',
            'prompt': (
                f'close up candid phone photo of a woman\'s hand with red manicured nails holding {product_name}, '
                'blurred cozy living room background with plants, natural window light, '
                'slightly tilted casual angle like texting a friend, authentic iPhone photo, '
                'warm tones, real person photo, no filters, no studio'
            ),
        },
        {
            'id': 'instore',
            'label': '🏪 In-Store Find',
            'prompt': (
                f'candid phone photo of {product_name} on a Walmart store shelf, '
                'fluorescent store lighting, yellow clearance price tag visible, '
                'Walmart colors faintly in background, slightly tilted angle, '
                'authentic customer photo, raw phone camera quality, no filters'
            ),
        },
        {
            'id': 'unboxing',
            'label': '📦 Unboxing Photo',
            'prompt': (
                f'unboxing photo of {product_name} next to its open box on a kitchen counter, '
                'natural window light, tissue paper visible, casual home setting, '
                'authentic phone photo, warm tones, real customer unboxing style'
            ),
        },
        {
            'id': 'lifestyle',
            'label': '🏠 Home Photo',
            'prompt': (
                f'lifestyle iPhone photo of {product_name} in a cozy American home, '
                'natural soft lighting, lived-in home decor background, '
                'casual composition like shared in a Facebook moms group, '
                'authentic warm tones, no professional staging'
            ),
        },
    ]
    return scenes[seed_offset % len(scenes)]


async def generate_customer_photos(product_name: str, category: str = '', seed_offset: int = 0) -> list[dict]:
    """
    Generate a single authentic customer-style photo. Fast (~15s).
    seed_offset rotates the scene style so "New AI Photo" shows a different angle.
    Returns a list with one item for API compatibility.
    """
    import base64
    scene = _best_prompt(product_name, category, seed_offset)
    seed  = _seed(product_name, seed_offset)

    encoded = urllib.parse.quote(scene['prompt'])
    url = f'{POLLINATIONS_BASE}/{encoded}?width=1080&height=1080&model=flux&seed={seed}&nologo=true'

    img_bytes = None
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=60) as client:
            resp = await client.get(url)
            if resp.status_code == 200 and 'image' in resp.headers.get('content-type', ''):
                img_bytes = resp.content
    except Exception as e:
        print(f'[pollinations] error: {e}')

    data_url = ('data:image/jpeg;base64,' + base64.b64encode(img_bytes).decode()) if img_bytes else None

    return [{'id': scene['id'], 'label': scene['label'], 'data_url': data_url}]
