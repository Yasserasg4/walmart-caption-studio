import json
import os
import re
from groq import Groq


def build_discount_info(price, original_price) -> str:
    try:
        cur = float(re.sub(r'[^\d.]', '', str(price)))
        orig = float(re.sub(r'[^\d.]', '', str(original_price)))
        if orig > cur and cur > 0:
            pct = round((orig - cur) / orig * 100)
            saved = round(orig - cur, 2)
            return f"{pct}% off — was ${orig:.2f}, now ${cur:.2f}, saving ${saved:.2f}"
    except Exception:
        pass
    return ''


def _product_block(product_data: dict) -> str:
    name = product_data.get('name', 'this product') or 'this product'
    price = product_data.get('price', '')
    original_price = product_data.get('original_price', '')
    rating = product_data.get('rating', '')
    review_count = product_data.get('review_count', '')
    category = product_data.get('category', '')
    description = (product_data.get('description', '') or '')[:300]
    discount_info = build_discount_info(price, original_price)

    return '\n'.join(filter(None, [
        f"Product: {name}",
        f"Current price: ${price}" if price else '',
        f"Original price: ${original_price}" if original_price else '',
        f"Discount: {discount_info}" if discount_info else '',
        f"Rating: {rating}/5 ({review_count} reviews)" if rating else '',
        f"Category: {category}" if category else '',
        f"Description: {description}" if description else '',
    ]))


def generate_captions(product_data: dict) -> list:
    client = Groq()

    prompt = f"""You write Facebook group posts for a page with 90% women aged 30-50. Study these REAL viral examples and copy their exact energy and format:

EXAMPLE 1: "THESE ARE USUALLY $80!! SAVE RIGHT NOWW!!"
EXAMPLE 2: "OMGGG blankets on clearance RUN before I buy the whole pile Link in Comment !!"
EXAMPLE 3: "RUNNNNNN!!! BEFORE IT'S GONEEEE!!! Link inment"
EXAMPLE 4: "Parents RUNNNNN!!! THIS IS CUTEEEE"
EXAMPLE 5: "WOW, THIS WILL DEFINITELY SELL OUT SOON‼️😱🏃‍♀️🏃‍♀️"

RULES — follow these exactly:
- MAX 1-2 sentences. Never more.
- Use ALL CAPS for most or all words
- Stretch letters for emphasis: RUNNNNNN, GONEEEE, NOWWW, OMGGGG, CUTEEEE, AMAZINGGG
- Typos are welcome and make it authentic (inment instead of in comments, dont instead of don't)
- Use 0 to 3 emojis MAX — high impact ones like ‼️ 😱 🏃‍♀️ 🔥 😍 — never more
- Sometimes say "Link in Comment" or "Link inment" or "dropping the link" at end
- Sometimes NO link mention at all — just pure reaction
- Call out the audience when relevant: "Ladies", "Girlies", "Moms", "Parents", "Girls"
- NEVER use hashtags
- NEVER write paragraphs
- NEVER sound like an ad or marketer
- Make it feel like a real person screaming in excitement

=== PRODUCT ===
{_product_block(product_data)}
===============

Write EXACTLY 4 captions. Each must be a different angle:
1. PRICE_SHOCK — lead with the price/savings ("THESE ARE USUALLY $X!!")
2. RUN — pure urgency, "BEFORE IT'S GONE" energy, link mention optional
3. REACTION — pure excitement/wow reaction, no link, audience callout
4. CLEARANCE — clearance/deal/stock running out angle, link mention at end

Return ONLY a JSON array, nothing else:
[
  {{"style": "PRICE_SHOCK", "caption": "..."}},
  {{"style": "RUN", "caption": "..."}},
  {{"style": "REACTION", "caption": "..."}},
  {{"style": "CLEARANCE", "caption": "..."}}
]"""

    response = client.chat.completions.create(
        model='llama-3.3-70b-versatile',
        max_tokens=800,
        messages=[
            {
                'role': 'system',
                'content': 'You write short viral Facebook captions. Output ONLY valid JSON arrays. No markdown. No explanations.',
            },
            {'role': 'user', 'content': prompt},
        ],
    )

    raw = response.choices[0].message.content.strip()
    raw = re.sub(r'^```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)

    try:
        start = raw.find('[')
        end = raw.rfind(']') + 1
        if start != -1 and end > 0:
            return json.loads(raw[start:end])
    except Exception as e:
        print(f'[captions] parse error: {e}\nRaw: {raw[:300]}')

    return [{'style': 'Generated', 'caption': raw}]


def generate_story_posts(product_data: dict) -> list:
    """
    Generates 4 Facebook posts short enough to show on a colored gradient background.
    Facebook's colored background cuts off at ~130 characters — after that it becomes
    a plain text post. Each caption must stay under 128 characters total.
    """
    client = Groq()

    prompt = f"""You are a 40-year-old American mom who shares deals in Facebook groups. Write 4 Facebook posts about this product for use with Facebook's COLORED GRADIENT BACKGROUND feature.

CRITICAL RULE: Every post MUST be under 128 characters total (including spaces and emojis). Facebook removes the colored background if text is longer. COUNT YOUR CHARACTERS.

=== PRODUCT ===
{_product_block(product_data)}
===============

STYLE EXAMPLES (notice how short and punchy they are):
- "I almost walked past this at Walmart... $14?? My jaw literally dropped 😭 Link in comments 👇"
- "UPDATE: been using it 3 weeks. Best purchase I made all year. Link dropping below 👇"
- "Ladies the price just dropped and stock is running low. Get it NOW 👇"
- "Found a deal so good I bought 2. You'll thank me later 👇"

POST STYLES — write one for each:
1. STORY: Mini discovery story ("I almost walked past..." or "Was just at Walmart and...")
2. URGENCY: FOMO/scarcity ("stock is low", "price going back up", "TODAY ONLY")
3. TESTIMONIAL: Social proof ("been using it X weeks", "best purchase this year")
4. DEAL_HUNTER: Deal finder voice ("found something rare", "never seen it this cheap")

RULES:
- UNDER 128 CHARACTERS. Non-negotiable. Count them.
- No hashtags
- 1 emoji max
- End with "Link in comments 👇" or "Link below 👇" or "👇" alone
- Natural imperfect grammar
- Mix of caps and lowercase — punchy but not screaming

Return ONLY a JSON array:
[
  {{"style": "STORY", "caption": "..."}},
  {{"style": "URGENCY", "caption": "..."}},
  {{"style": "TESTIMONIAL", "caption": "..."}},
  {{"style": "DEAL_HUNTER", "caption": "..."}}
]"""

    response = client.chat.completions.create(
        model='llama-3.3-70b-versatile',
        max_tokens=800,
        messages=[
            {
                'role': 'system',
                'content': 'You write short punchy Facebook posts for colored gradient backgrounds. Each must be under 128 characters. Output ONLY valid JSON arrays. No markdown. No explanations.',
            },
            {'role': 'user', 'content': prompt},
        ],
    )

    raw = response.choices[0].message.content.strip()
    raw = re.sub(r'^```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)

    try:
        start = raw.find('[')
        end = raw.rfind(']') + 1
        if start != -1 and end > 0:
            return json.loads(raw[start:end])
    except Exception as e:
        print(f'[story_posts] parse error: {e}\nRaw: {raw[:300]}')

    return []


def improve_existing_caption(caption: str, product_name: str = '', price: str = '') -> list[str]:
    """
    Returns 2 distinct improved variations of the caption.
    Each uses a different conversion angle/style.
    """
    client = Groq()

    context_lines = '\n'.join(filter(None, [
        f'Product: {product_name}' if product_name else '',
        f'Price: ${price}' if price else '',
    ]))

    char_count = len(caption)
    word_count = len(caption.split())

    prompt = f"""You are a Facebook group viral post expert. Improve this existing caption to get MORE reach and conversions:

ORIGINAL CAPTION:
"{caption}"

{f'CONTEXT:{chr(10)}{context_lines}' if context_lines else ''}

YOUR GOAL: Rewrite this with a DIFFERENT angle that hits harder and feels more human. No generic openers.

BANNED OPENERS — never start with these:
- "OMG" / "OMGG" / "OMGGG" (overused, ignored by scrollers)
- "WOW" alone
- "Ladies" alone
- "Check this out"
- Any variation of "I found this"

INSTEAD, open with something unexpected. High-performing openers that actually stop the scroll:
- A specific number or price dropped raw: "$9.97?? I had to triple check"
- A reaction that sounds personal: "my cart is embarrassing right now"
- A confession: "I told myself I wasn't buying anything today..."
- A comparison that creates instant value: "Target has this for $45. Walmart: $14."
- A direct callout with a twist: "if you have a [type of person] in your life, stop."
- Pure disbelief with no filler: "NO WAY this is still in stock‼️"
- A half-sentence that creates curiosity: "ok but why is nobody talking about this"

HIGH-CONVERTING STYLE SHIFTS (pick the best fit for this caption):
- Flip generic → specific: use the real price, real savings, real comparison store
- Flip soft → raw: shorter words, broken grammar, feels like a voice note typed out
- Flip calm → urgency: something is running out, ending, or about to go back up
- Flip passive → personal: make it sound like it already happened to her

RULES:
- Keep product name exactly as in the original
- PRICE RULE: only mention a price if the original caption already contains one. If no price in the original, do NOT add one.
- ALL CAPS on max 2-3 words — the ones that would make someone's thumb stop
- Stretched letters only when it sounds natural, not forced: RUNNNN, SOLDDD, SERIOUSLYYYY
- Zero hashtags. Zero marketing language. Zero "amazing quality."
- Sound like a real woman texting her sister, not writing a post
- LANGUAGE RULE: if the original caption is in French (or any non-English language), rewrite it in English — not a word-for-word translation, but a full reformulation that captures the same energy and intent in natural American English

ENDING: mirror the original exactly — if it has no link mention, write none. If it does, match or vary naturally. Never force "Link in Comments."

LENGTH + STRUCTURE — CRITICAL: Original is {char_count} characters, {word_count} words. Stay within 15%. Same number of lines. No adding or cutting lines.

Return ONLY the rewritten caption. No explanation, no quotes, no label."""

    variation_prompts = [
        prompt + "\n\nSTYLE FOR THIS VARIATION: Lead with urgency or scarcity. Make it feel like something is about to disappear.",
        prompt + "\n\nSTYLE FOR THIS VARIATION: Lead with a personal confession or reaction. Make it feel like she's talking to her best friend.",
    ]

    results = []
    for vp in variation_prompts:
        resp = client.chat.completions.create(
            model='llama-3.3-70b-versatile',
            max_tokens=300,
            temperature=0.9,
            messages=[
                {
                    'role': 'system',
                    'content': 'You are a viral Facebook content optimizer. Return ONLY the improved caption text, nothing else.',
                },
                {'role': 'user', 'content': vp},
            ],
        )
        results.append((resp.choices[0].message.content or '').strip().strip('"'))

    return results


STYLE_LABELS = {
    'PRICE_SHOCK': ('💲 Price Shock', '#e67e22'),
    'RUN':         ('🏃 Run Now',     '#e74c3c'),
    'REACTION':    ('😱 Pure React',  '#8e44ad'),
    'CLEARANCE':   ('🔥 Clearance',   '#27ae60'),
}

STORY_STYLE_LABELS = {
    'STORY':       ('🧵 Story Post',    '#3498db'),
    'URGENCY':     ('⚠️ Urgent Alert',  '#e74c3c'),
    'TESTIMONIAL': ('💬 Testimonial',   '#9b59b6'),
    'DEAL_HUNTER': ('🏷️ Deal Hunter',   '#27ae60'),
}
