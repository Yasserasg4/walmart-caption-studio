import os
import json
import asyncio
import functools
from datetime import timedelta
from flask import (Flask, render_template, request, jsonify,
                   session, redirect, url_for, make_response)
from dotenv import load_dotenv

from scraper import scrape_walmart_product
from caption_generator import generate_captions, generate_story_posts, improve_existing_caption
from link_shortener import shorten_link as _shorten_link
from database import (init_db, log_shortening, today_count,
                      weekly_total, all_time_total, best_day, daily_stats,
                      count_for_date, session_counts_for_date)

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'wcs-secret-k9x-2024')
app.config['JSON_SORT_KEYS'] = False
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

# ── Auth config ───────────────────────────────────────────
DAILY_TARGET = 300

USERS = {
    'safaa':   {'pin': '0105',                               'role': 'employee', 'display': 'Safaa'},
    'kaoutar': {'pin': '5304',                               'role': 'employee', 'display': 'Kaoutar'},
    'youssef': {'pin': 'xK9!mV3@rL7#qN',                    'role': 'employee', 'display': 'Youssef'},
    'admin':   {'pin': os.environ.get('ADMIN_PIN', '5304'),  'role': 'admin',    'display': 'Admin'},
}

EMPLOYEES = ['safaa']  # only Safaa is tracked in admin

init_db()


# ── Helpers ───────────────────────────────────────────────

def _no_cache(resp):
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


def _get_rating(pct, tc):
    if tc == 0:      return ('Not started yet',    '😴', '#8a8ea8')
    if pct < 25:     return ('Just warming up',    '🌱', '#e74c3c')
    if pct < 50:     return ('Building momentum',  '📈', '#e67e22')
    if pct < 75:     return ('Getting there!',     '💪', '#f1c40f')
    if pct < 90:     return ('Almost there!',      '🚀', '#2ecc71')
    if pct < 100:    return ('SO close!!',         '🔥', '#27ae60')
    return           ('TARGET REACHED!',           '🏆', '#ffd700')


def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'admin':
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated


# ── Auth routes ───────────────────────────────────────────

@app.route('/')
def root():
    if 'user' not in session:
        return redirect(url_for('login_page'))
    return redirect(url_for('admin_page') if session['role'] == 'admin' else url_for('dashboard'))


@app.route('/login', methods=['GET'])
def login_page():
    if 'user' in session:
        return redirect(url_for('root'))
    return _no_cache(make_response(render_template('login.html')))


@app.route('/login', methods=['POST'])
def do_login():
    data     = request.get_json(silent=True) or {}
    username = (data.get('username') or '').lower().strip()
    pin      = (data.get('pin') or '').strip()

    user = USERS.get(username)
    if not user or user['pin'] != pin:
        return jsonify({'error': 'Wrong PIN. Try again.'}), 401

    session.permanent = True
    session['user']    = username
    session['display'] = user['display']
    session['role']    = user['role']

    dest = url_for('admin_page') if user['role'] == 'admin' else url_for('dashboard')
    return jsonify({'redirect': dest})


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))


# ── Dashboard routes ──────────────────────────────────────

@app.route('/dashboard')
@login_required
def dashboard():
    if session['role'] == 'admin':
        return redirect(url_for('admin_page'))
    from datetime import date as _date
    today_str     = _date.today().isoformat()
    yesterday_str = (_date.today() - timedelta(days=1)).isoformat()
    count         = today_count(session['user'])
    pct           = min(round(count / DAILY_TARGET * 100), 100)
    rating        = _get_rating(pct, count)
    sess_today    = session_counts_for_date(session['user'], today_str)
    sess_yest     = session_counts_for_date(session['user'], yesterday_str)
    count_yest    = count_for_date(session['user'], yesterday_str)
    return _no_cache(make_response(render_template('index.html',
        today_count=count,
        daily_target=DAILY_TARGET,
        pct=pct,
        rating=rating,
        display_name=session['display'],
        sess_today=sess_today,
        sess_yest=sess_yest,
        count_yest=count_yest,
        yesterday_str=yesterday_str,
    )))


@app.route('/api/session-stats')
@login_required
def api_session_stats():
    from datetime import date as _date
    today_str     = _date.today().isoformat()
    yesterday_str = (_date.today() - timedelta(days=1)).isoformat()
    sess_today    = session_counts_for_date(session['user'], today_str)
    sess_yest     = session_counts_for_date(session['user'], yesterday_str)
    count_today   = today_count(session['user'])
    count_yest    = count_for_date(session['user'], yesterday_str)
    return jsonify({
        'today':     {'total': count_today,  'sessions': sess_today},
        'yesterday': {'total': count_yest,   'sessions': sess_yest},
    })


@app.route('/admin')
@login_required
@admin_required
def admin_page():
    user = 'safaa'
    tc   = today_count(user)
    wt   = weekly_total(user)
    at   = all_time_total(user)
    bd   = best_day(user)
    pct  = min(round(tc / DAILY_TARGET * 100), 100)
    rating = _get_rating(pct, tc)
    stats  = daily_stats(user, days=30)

    return _no_cache(make_response(render_template('admin.html',
        today_count=tc,
        weekly_total=wt,
        all_time=at,
        best_day=bd,
        daily_target=DAILY_TARGET,
        pct=pct,
        rating=rating,
        stats_json=json.dumps(stats),
        display_name=session['display'],
    )))


# ── API ───────────────────────────────────────────────────

@app.route('/api/process', methods=['POST'])
@login_required
def process():
    body = request.get_json(silent=True) or {}
    url  = (body.get('url') or '').strip()

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
        'captions':    captions,
        'story_posts': story_posts,
    })


@app.route('/api/improve-caption', methods=['POST'])
@login_required
def improve_caption():
    body         = request.get_json(silent=True) or {}
    caption      = (body.get('caption') or '').strip()
    product_name = (body.get('product_name') or '').strip()
    price        = (body.get('price') or '').strip()

    if not caption:
        return jsonify({'error': 'Paste a caption to improve.'}), 400

    try:
        improved = improve_existing_caption(caption, product_name, price)
    except Exception as e:
        return jsonify({'error': f'Improvement failed: {str(e)}'}), 500

    return jsonify({'variations': improved})


@app.route('/api/shorten-link', methods=['POST'])
@login_required
def shorten_link_route():
    body = request.get_json(silent=True) or {}
    url  = (body.get('url') or '').strip()

    if not url:
        return jsonify({'error': 'Please paste a link to shorten.'}), 400

    try:
        short = _shorten_link(url)
    except Exception as e:
        msg = str(e)
        if 'proxy' in msg.lower() or '403' in msg:
            msg = ('Link shortener is blocked by the server\'s network policy. '
                   'Contact PythonAnywhere support to whitelist mavlinks.com.')
        return jsonify({'error': msg}), 500

    log_shortening(session['user'], url, short)
    return jsonify({'short_url': short})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, port=port)
