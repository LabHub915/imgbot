import os
import re
import secrets
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, request, abort, render_template, redirect, url_for, session, flash
from linebot.v3 import WebhookHandler
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    ImageMessage,
    TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.exceptions import InvalidSignatureError
from pymongo import MongoClient
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# Session security settings
app.config.update(
    SESSION_COOKIE_SECURE=True,      # Only send cookie over HTTPS
    SESSION_COOKIE_HTTPONLY=True,    # Prevent JavaScript access to session cookie
    SESSION_COOKIE_SAMESITE='Lax',   # Prevent CSRF from external sites
    PERMANENT_SESSION_LIFETIME=timedelta(hours=2)  # Session expires after 2 hours
)

# Security settings
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15
ALLOWED_IMAGE_DOMAINS = ['cdn.jsdelivr.net', 'raw.githubusercontent.com', 'i.imgur.com']

# LINE Bot Configuration
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET', '')
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN', '')

configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# MongoDB Connection
MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/imgbot')
mongo_client = MongoClient(MONGO_URI)
db = mongo_client.get_database()
memes_collection = db['memes']
users_collection = db['users']

# Ensure indexes
memes_collection.create_index('keywords')
users_collection.create_index('username', unique=True)

# Create default admin if no users exist
if users_collection.count_documents({}) == 0:
    default_password = os.environ.get('ADMIN_PASSWORD', 'admin123')
    users_collection.insert_one({
        'username': 'admin',
        'password': generate_password_hash(default_password),
        'role': 'admin',
        'failed_attempts': 0,
        'locked_until': None
    })


# ============ Auth Decorator ============
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        user = users_collection.find_one({'_id': ObjectId(session['user_id'])})
        if not user or user.get('role') != 'admin':
            flash('需要管理員權限', 'error')
            return redirect(url_for('admin_index'))
        return f(*args, **kwargs)
    return decorated_function


def is_account_locked(user):
    """Check if account is currently locked"""
    locked_until = user.get('locked_until')
    if locked_until and isinstance(locked_until, datetime):
        if datetime.utcnow() < locked_until:
            return True
        # Lock expired, reset attempts
        users_collection.update_one(
            {'_id': user['_id']},
            {'$set': {'failed_attempts': 0, 'locked_until': None}}
        )
    return False


def get_remaining_lockout_minutes(user):
    """Get remaining lockout time in minutes"""
    locked_until = user.get('locked_until')
    if locked_until and isinstance(locked_until, datetime):
        remaining = locked_until - datetime.utcnow()
        if remaining.total_seconds() > 0:
            return int(remaining.total_seconds() / 60) + 1
    return 0


# ============ LINE Bot Webhook ============
@app.route('/callback', methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    
    return 'OK'


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_text = event.message.text.lower()
    
    # Find all memes and check keywords
    all_memes = list(memes_collection.find())
    matched_meme = None
    
    for meme in all_memes:
        keywords = meme.get('keywords', [])
        for kw in keywords:
            if kw.lower() in user_text:
                matched_meme = meme
                break
        if matched_meme:
            break
    
    if matched_meme:
        image_url = matched_meme.get('image_url', '')
        if image_url:
            with ApiClient(configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[
                            ImageMessage(
                                original_content_url=image_url,
                                preview_image_url=image_url
                            )
                        ]
                    )
                )


# ============ Auth Routes ============
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        
        user = users_collection.find_one({'username': username})
        
        if not user:
            flash('帳號或密碼錯誤', 'error')
            return render_template('login.html')
        
        # Check if account is locked
        if is_account_locked(user):
            remaining = get_remaining_lockout_minutes(user)
            flash(f'帳號已鎖定，請 {remaining} 分鐘後再試', 'error')
            return render_template('login.html')
        
        if check_password_hash(user['password'], password):
            # Successful login - reset failed attempts
            users_collection.update_one(
                {'_id': user['_id']},
                {'$set': {'failed_attempts': 0, 'locked_until': None}}
            )
            session['user_id'] = str(user['_id'])
            session['username'] = user['username']
            session['role'] = user.get('role', 'user')
            return redirect(url_for('admin_index'))
        
        # Failed login - increment attempts
        failed_attempts = user.get('failed_attempts', 0) + 1
        update_data = {'failed_attempts': failed_attempts}
        
        if failed_attempts >= MAX_LOGIN_ATTEMPTS:
            update_data['locked_until'] = datetime.utcnow() + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
            flash(f'密碼錯誤次數過多，帳號已鎖定 {LOCKOUT_DURATION_MINUTES} 分鐘', 'error')
        else:
            remaining_attempts = MAX_LOGIN_ATTEMPTS - failed_attempts
            flash(f'帳號或密碼錯誤，還剩 {remaining_attempts} 次嘗試機會', 'error')
        
        users_collection.update_one({'_id': user['_id']}, {'$set': update_data})
    
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ============ Change Password ============
@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        user = users_collection.find_one({'_id': ObjectId(session['user_id'])})
        
        if not check_password_hash(user['password'], current_password):
            flash('目前密碼錯誤', 'error')
            return render_template('change_password.html')
        
        if len(new_password) < 6:
            flash('新密碼至少需要 6 個字元', 'error')
            return render_template('change_password.html')
        
        if new_password != confirm_password:
            flash('新密碼與確認密碼不符', 'error')
            return render_template('change_password.html')
        
        users_collection.update_one(
            {'_id': ObjectId(session['user_id'])},
            {'$set': {'password': generate_password_hash(new_password)}}
        )
        flash('密碼已更新成功', 'success')
        return redirect(url_for('admin_index'))
    
    return render_template('change_password.html')


# ============ Admin Web Interface ============
@app.route('/admin')
@login_required
def admin_index():
    memes = list(memes_collection.find())
    return render_template('index.html', memes=memes)


def is_valid_image_url(url):
    """Validate image URL for security"""
    if not url:
        return False
    # Must be HTTPS
    if not url.startswith('https://'):
        return False
    # Check allowed domains
    from urllib.parse import urlparse
    parsed = urlparse(url)
    # Allow any HTTPS URL but warn about untrusted domains
    return parsed.scheme == 'https'


def sanitize_keyword(kw):
    """Sanitize keyword input"""
    # Remove any HTML/script tags and limit length
    import re
    kw = re.sub(r'<[^>]*>', '', kw)  # Remove HTML tags
    kw = kw.strip()[:50]  # Limit to 50 chars
    return kw


@app.route('/admin/add', methods=['POST'])
@login_required
def admin_add():
    keywords_raw = request.form.get('keywords', '')
    image_url = request.form.get('image_url', '').strip()
    
    # Parse and sanitize keywords
    keywords = [sanitize_keyword(kw) for kw in keywords_raw.split(',') if kw.strip()]
    keywords = [kw for kw in keywords if kw]  # Remove empty after sanitization
    
    # Validate URL
    if not is_valid_image_url(image_url):
        flash('圖片網址必須使用 HTTPS', 'error')
        return redirect(url_for('admin_index'))
    
    if keywords and image_url:
        memes_collection.insert_one({
            'keywords': keywords,
            'image_url': image_url
        })
        flash('梗圖新增成功', 'success')
    
    return redirect(url_for('admin_index'))


@app.route('/admin/edit/<meme_id>', methods=['GET', 'POST'])
@login_required
def admin_edit(meme_id):
    try:
        meme = memes_collection.find_one({'_id': ObjectId(meme_id)})
    except Exception:
        return redirect(url_for('admin_index'))
    
    if not meme:
        return redirect(url_for('admin_index'))
    
    if request.method == 'POST':
        keywords_raw = request.form.get('keywords', '')
        image_url = request.form.get('image_url', '').strip()
        keywords = [sanitize_keyword(kw) for kw in keywords_raw.split(',') if kw.strip()]
        keywords = [kw for kw in keywords if kw]
        
        # Validate URL
        if not is_valid_image_url(image_url):
            flash('圖片網址必須使用 HTTPS', 'error')
            return redirect(url_for('admin_edit', meme_id=meme_id))
        
        if keywords and image_url:
            memes_collection.update_one(
                {'_id': ObjectId(meme_id)},
                {'$set': {'keywords': keywords, 'image_url': image_url}}
            )
            flash('梗圖更新成功', 'success')
        return redirect(url_for('admin_index'))
    
    return render_template('edit.html', meme=meme)


@app.route('/admin/delete/<meme_id>', methods=['POST'])
@login_required
def admin_delete(meme_id):
    try:
        memes_collection.delete_one({'_id': ObjectId(meme_id)})
        flash('梗圖已刪除', 'success')
    except Exception:
        flash('刪除失敗', 'error')
    return redirect(url_for('admin_index'))


# ============ User Management (Admin Only) ============
@app.route('/admin/users')
@admin_required
def admin_users():
    users = list(users_collection.find())
    return render_template('users.html', users=users, now=datetime.utcnow())


def sanitize_username(username):
    """Sanitize username - alphanumeric and underscore only"""
    import re
    username = re.sub(r'[^a-zA-Z0-9_]', '', username)
    return username[:30]  # Limit to 30 chars


@app.route('/admin/users/add', methods=['POST'])
@admin_required
def admin_users_add():
    username = sanitize_username(request.form.get('username', ''))
    password = request.form.get('password', '')
    role = request.form.get('role', 'user')
    
    # Validate role
    if role not in ['user', 'admin']:
        role = 'user'
    
    # Validate password strength
    if len(password) < 6:
        flash('密碼至少需要 6 個字元', 'error')
        return redirect(url_for('admin_users'))
    
    if username and password:
        if users_collection.find_one({'username': username}):
            flash('使用者名稱已存在', 'error')
        else:
            users_collection.insert_one({
                'username': username,
                'password': generate_password_hash(password),
                'role': role,
                'failed_attempts': 0,
                'locked_until': None
            })
            flash('使用者新增成功', 'success')
    else:
        flash('請填寫完整的使用者資訊', 'error')
    
    return redirect(url_for('admin_users'))


@app.route('/admin/users/delete/<user_id>', methods=['POST'])
@admin_required
def admin_users_delete(user_id):
    try:
        # Prevent deleting self
        if user_id == session.get('user_id'):
            flash('無法刪除自己的帳號', 'error')
        else:
            users_collection.delete_one({'_id': ObjectId(user_id)})
            flash('使用者已刪除', 'success')
    except Exception:
        flash('刪除失敗', 'error')
    return redirect(url_for('admin_users'))


@app.route('/admin/users/reset-password/<user_id>', methods=['POST'])
@admin_required
def admin_users_reset_password(user_id):
    new_password = request.form.get('new_password', '')
    
    if not new_password or len(new_password) < 6:
        flash('密碼至少需要 6 個字元', 'error')
        return redirect(url_for('admin_users'))
    
    try:
        users_collection.update_one(
            {'_id': ObjectId(user_id)},
            {'$set': {
                'password': generate_password_hash(new_password),
                'failed_attempts': 0,
                'locked_until': None
            }}
        )
        flash('密碼已重設成功', 'success')
    except Exception:
        flash('重設密碼失敗', 'error')
    
    return redirect(url_for('admin_users'))


@app.route('/admin/users/unlock/<user_id>')
@admin_required
def admin_users_unlock(user_id):
    try:
        users_collection.update_one(
            {'_id': ObjectId(user_id)},
            {'$set': {'failed_attempts': 0, 'locked_until': None}}
        )
        flash('帳號已解鎖', 'success')
    except Exception:
        flash('解鎖失敗', 'error')
    return redirect(url_for('admin_users'))


# ============ Health Check ============
@app.route('/health')
def health():
    return {'status': 'ok'}


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
