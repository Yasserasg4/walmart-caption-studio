import os
import asyncio
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from scraper import scrape_walmart_product
from caption_generator import generate_captions, generate_story_posts, improve_existing_caption

load_dotenv()

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/process', methods=['POST'])
def process():
    body = request.get_json(silent=True) or {}
    url = (body.get('url') or '').strip()

    if not url:
        return jsonify({'error': 'Please paste a Walmart product URL.'}), 400
    if 'walmart.com' not in url:
        return jsonify({'error': "That doesn't look like a Walmart URL."}), 400

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        product_data = loop.run_until_complete(scrape_walmart_product(url))
        loop.close()
    except Exception as e:
        return jsonify({'error': f'Scraping failed: {str(e)}'}), 500

    try:
        captions = generate_captions(product_data)
    except Exception as e:
        return jsonify({'error': f'Caption generation failed: {str(e)}'}), 500

    try:
        story_posts = generate_story_posts(product_data)
    except Exception as e:
        print(f'[story_posts] failed: {e}')
        story_posts = []

    return jsonify({
        'product': {
            'name':           product_data.get('name', ''),
            'price':          product_data.get('price', ''),
            'original_price': product_data.get('original_price', ''),
            'rating':         product_data.get('rating', ''),
            'review_count':   product_data.get('review_count', ''),
            'category':       product_data.get('category', ''),
        },
        'captions':      captions,
        'story_posts':   story_posts,
    })


@app.route('/api/improve-caption', methods=['POST'])
def improve_caption():
    body = request.get_json(silent=True) or {}
    caption      = (body.get('caption') or '').strip()
    product_name = (body.get('product_name') or '').strip()
    price        = (body.get('price') or '').strip()

    if not caption:
        return jsonify({'error': 'Paste a caption to improve.'}), 400

    try:
        improved = improve_existing_caption(caption, product_name, price)
    except Exception as e:
        return jsonify({'error': f'Improvement failed: {str(e)}'}), 500

    return jsonify({'improved': improved})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, port=port)
