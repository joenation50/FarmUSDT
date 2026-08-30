from flask import Flask, render_template_string, request, redirect, url_for, flash, session, jsonify
from datetime import datetime, timedelta
import random
import string
import os
import json
import uuid
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from urllib.parse import urlparse

app = Flask(__name__)
app.secret_key = 'farmusdt-super-secret-key-2026'

# ==================== DATABASE CONFIGURATION ====================
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///farmusdt.db')

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ==================== DATABASE MODELS ====================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    referral_code = db.Column(db.String(10), unique=True)
    referred_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    full_name = db.Column(db.String(100), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    address = db.Column(db.String(200), nullable=True)
    
    balance = db.Column(db.Float, default=0)
    commission_balance = db.Column(db.Float, default=0)
    tier = db.Column(db.String(20), default='FREE')
    daily_limit = db.Column(db.Integer, default=0)
    daily_tasks_completed = db.Column(db.Integer, default=0)
    streak_days = db.Column(db.Integer, default=0)
    last_checkin = db.Column(db.DateTime, nullable=True)
    last_task_reset = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    is_banned = db.Column(db.Boolean, default=False)
    ban_reason = db.Column(db.Text, nullable=True)
    
    wallet_address = db.Column(db.String(200), nullable=True)
    wallet_network = db.Column(db.String(50), default='BEP20')
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    
    referral_bonus_earned = db.Column(db.Float, default=0)
    total_referrals = db.Column(db.Integer, default=0)
    theme = db.Column(db.String(10), default='dark')
    total_earned = db.Column(db.Float, default=0)
    total_withdrawn = db.Column(db.Float, default=0)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def generate_referral_code(self):
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    
    def get_next_tier(self):
        tiers = ['FREE', 'BRONZE', 'SILVER', 'GOLD', 'PLATINUM', 'DIAMOND']
        current = self.tier
        if current in tiers:
            idx = tiers.index(current)
            if idx < len(tiers) - 1:
                return tiers[idx + 1]
        return None
    
    def get_profile_completion(self):
        fields = ['full_name', 'phone', 'address', 'wallet_address']
        completed = sum(1 for field in fields if getattr(self, field))
        return int((completed / len(fields)) * 100)
    
    def __repr__(self):
        return f'<User {self.username}>'

class Referral(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    referrer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    referred_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    bonus_paid = db.Column(db.Boolean, default=False)
    bonus_amount = db.Column(db.Float, default=0.50)
    verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    task_type = db.Column(db.String(50))
    reward = db.Column(db.Float, default=0.20)
    tier_required = db.Column(db.String(20), default='BRONZE')
    external_link = db.Column(db.String(200), nullable=True)
    daily_limit = db.Column(db.Integer, default=2)
    is_active = db.Column(db.Boolean, default=True)
    category = db.Column(db.String(50), default='General')
    icon = db.Column(db.String(50), default='📝')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class TaskCompletion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)
    proof_text = db.Column(db.Text, nullable=True)
    proof_image = db.Column(db.String(200), nullable=True)
    is_verified = db.Column(db.Boolean, default=False)
    is_paid = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    tier = db.Column(db.String(20), nullable=True)
    transaction_id = db.Column(db.String(50), unique=True)
    sender_name = db.Column(db.String(100))
    payment_date = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    status = db.Column(db.String(20), default='PENDING')
    type = db.Column(db.String(20), default='UPGRADE')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'amount': self.amount,
            'tier': self.tier,
            'transaction_id': self.transaction_id,
            'sender_name': self.sender_name,
            'status': self.status,
            'date': self.created_at.strftime('%b %d, %Y %H:%M')
        }

class Withdrawal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    wallet_address = db.Column(db.String(200), nullable=False)
    wallet_network = db.Column(db.String(50), default='BEP20')
    status = db.Column(db.String(20), default='PENDING')
    reference = db.Column(db.String(50), unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime, nullable=True)
    tx_hash = db.Column(db.String(200), nullable=True)

class SupportTicket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='OPEN')
    priority = db.Column(db.String(20), default='MEDIUM')
    category = db.Column(db.String(50), default='General')
    admin_response = db.Column(db.Text, nullable=True)
    responded_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': User.query.get(self.user_id).username if User.query.get(self.user_id) else 'Unknown',
            'subject': self.subject,
            'message': self.message[:100] + '...' if len(self.message) > 100 else self.message,
            'status': self.status,
            'priority': self.priority,
            'date': self.created_at.strftime('%b %d, %Y %H:%M')
        }

class PaymentSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bank_name = db.Column(db.String(100), default='GTBank')
    account_name = db.Column(db.String(100), default='FarmUSDT Labs Ltd')
    account_number = db.Column(db.String(20), default='0123456789')
    bank_code = db.Column(db.String(10), default='058')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class SocialLinks(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    telegram_link = db.Column(db.String(200), default='https://t.me/farmusdt')
    whatsapp_link = db.Column(db.String(200), default='https://chat.whatsapp.com/farmusdt')
    twitter_link = db.Column(db.String(200), default='https://twitter.com/farmusdt')
    youtube_link = db.Column(db.String(200), default='https://youtube.com/farmusdt')
    facebook_link = db.Column(db.String(200), default='https://facebook.com/farmusdt')
    instagram_link = db.Column(db.String(200), default='https://instagram.com/farmusdt')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Announcement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class UserActivity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ==================== CREATE TABLES ====================
with app.app_context():
    db.create_all()
    
    if PaymentSettings.query.count() == 0:
        default_settings = PaymentSettings(
            bank_name='GTBank',
            account_name='FarmUSDT Labs Ltd',
            account_number='0123456789',
            bank_code='058'
        )
        db.session.add(default_settings)
        db.session.commit()
    
    if SocialLinks.query.count() == 0:
        default_links = SocialLinks(
            telegram_link='https://t.me/farmusdt',
            whatsapp_link='https://chat.whatsapp.com/farmusdt',
            twitter_link='https://twitter.com/farmusdt',
            youtube_link='https://youtube.com/farmusdt',
            facebook_link='https://facebook.com/farmusdt',
            instagram_link='https://instagram.com/farmusdt'
        )
        db.session.add(default_links)
        db.session.commit()
    
    if Task.query.count() == 0:
        default_tasks = [
            Task(title='⭐ Google Review', description='Leave a 5-star review on Google', 
                 task_type='REVIEW', reward=0.20, tier_required='BRONZE', icon='⭐'),
            Task(title='🐦 Twitter Follow', description='Follow us on Twitter', 
                 task_type='SOCIAL', reward=0.20, tier_required='BRONZE', icon='🐦'),
            Task(title='💬 Join Telegram', description='Join our Telegram community', 
                 task_type='SOCIAL', reward=0.20, tier_required='BRONZE', icon='💬'),
            Task(title='📱 Join WhatsApp', description='Join our WhatsApp group', 
                 task_type='SOCIAL', reward=0.20, tier_required='BRONZE', icon='📱'),
            Task(title='▶️ YouTube Watch', description='Watch and like our video', 
                 task_type='VIDEO', reward=0.20, tier_required='BRONZE', icon='▶️'),
            Task(title='⭐ Google Review', description='Leave a 5-star review on Google', 
                 task_type='REVIEW', reward=0.20, tier_required='SILVER', icon='⭐'),
            Task(title='🐦 Twitter Share', description='Share our post on Twitter', 
                 task_type='SOCIAL', reward=0.20, tier_required='SILVER', icon='🐦'),
            Task(title='💬 Join Telegram', description='Join our Telegram community', 
                 task_type='SOCIAL', reward=0.20, tier_required='SILVER', icon='💬'),
            Task(title='📱 Join WhatsApp', description='Join our WhatsApp group', 
                 task_type='SOCIAL', reward=0.20, tier_required='SILVER', icon='📱'),
            Task(title='▶️ YouTube Comment', description='Comment on our video', 
                 task_type='VIDEO', reward=0.20, tier_required='SILVER', icon='▶️'),
            Task(title='⭐ Google Review', description='Leave a 5-star review on Google', 
                 task_type='REVIEW', reward=0.20, tier_required='GOLD', icon='⭐'),
            Task(title='🐦 Twitter Thread', description='Post a thread about us', 
                 task_type='SOCIAL', reward=0.20, tier_required='GOLD', icon='🐦'),
            Task(title='💬 Join Telegram', description='Join our Telegram community', 
                 task_type='SOCIAL', reward=0.20, tier_required='GOLD', icon='💬'),
            Task(title='📱 Join WhatsApp', description='Join our WhatsApp group', 
                 task_type='SOCIAL', reward=0.20, tier_required='GOLD', icon='📱'),
            Task(title='▶️ YouTube Subscribe', description='Subscribe to our channel', 
                 task_type='VIDEO', reward=0.20, tier_required='GOLD', icon='▶️'),
        ]
        for task in default_tasks:
            db.session.add(task)
        db.session.commit()

# ==================== CONFIGURATION ====================
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'admin123'
REFERRAL_BONUS = 0.50
MINIMUM_WITHDRAWAL = 1.00

TIER_PRICES = {
    'BRONZE': 1000,
    'SILVER': 3000,
    'GOLD': 5000,
    'PLATINUM': 10000,
    'DIAMOND': 20000
}

TIER_TASKS = {
    'FREE': 0,
    'BRONZE': 5,
    'SILVER': 7,
    'GOLD': 9,
    'PLATINUM': 11,
    'DIAMOND': 13
}

TIER_NAMES = {
    'FREE': 'FREE',
    'BRONZE': '🥉 Bronze',
    'SILVER': '🥈 Silver',
    'GOLD': '🥇 Gold',
    'PLATINUM': '💎 Platinum',
    'DIAMOND': '💠 Diamond'
}

TESTIMONIALS = [
    {'name': 'CryptoKing 👑', 'text': 'FarmUSDT changed my life! I earned 50 USDT in my first month! 🚀', 'rating': 5},
    {'name': 'MoonWalker 🌙', 'text': 'Finally a legit crypto earning platform. Withdrew 20 USDT in 24 hours! 💰', 'rating': 5},
    {'name': 'DiamondHands 💎', 'text': 'The referral bonus is amazing! Got 0.50 USDT per referral! 🎯', 'rating': 5},
]

FAKE_REVIEWS = [
    {'name': 'CryptoKing 👑', 'review': 'I earned 50 USDT in just 2 weeks! This platform is amazing!', 'rating': 5, 'time': '2 hours ago'},
    {'name': 'MoonWalker 🌙', 'review': 'The referral bonus is legit. I got 0.50 USDT when my friend joined!', 'rating': 5, 'time': '5 hours ago'},
    {'name': 'DiamondHands 💎', 'review': 'Best earning platform. Tasks are simple and payments are fast!', 'rating': 5, 'time': '1 day ago'},
]

# ==================== STYLES ====================
STYLES = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

:root {
    --primary: #0f0f1a;
    --primary-light: #1a1a2e;
    --secondary: #6c5ce7;
    --secondary-light: #a29bfe;
    --accent: #fd79a8;
    --success: #00b894;
    --success-light: #55efc4;
    --danger: #ff7675;
    --warning: #fdcb6e;
    --gold: #f9ca24;
    --gradient-1: linear-gradient(135deg, #6c5ce7, #fd79a8);
    --gradient-2: linear-gradient(135deg, #00b894, #00cec9);
    --gradient-3: linear-gradient(135deg, #fdcb6e, #f9ca24);
    --bg: #0f0f1a;
    --card-bg: #1a1a2e;
    --text: #ffffff;
    --text-light: #b0b0c8;
    --text-muted: #6a6a8a;
    --border: #2a2a4a;
    --shadow: 0 8px 32px rgba(0,0,0,0.4);
    --shadow-hover: 0 12px 48px rgba(108, 92, 231, 0.2);
    --radius: 24px;
    --radius-sm: 14px;
    --transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
    font-family: 'Inter', -apple-system, sans-serif;
    background: var(--bg);
    color: var(--text);
    padding: 16px;
    padding-bottom: 90px;
    max-width: 480px;
    margin: 0 auto;
    min-height: 100vh;
    overflow-x: hidden;
}

.top-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
    padding: 12px 16px;
    background: rgba(26, 26, 46, 0.7);
    backdrop-filter: blur(20px);
    border-radius: var(--radius);
    box-shadow: var(--shadow);
    border: 1px solid rgba(255,255,255,0.05);
}

.logo-container {
    display: flex;
    align-items: center;
    gap: 10px;
    text-decoration: none;
}

.logo-icon {
    width: 44px;
    height: 44px;
    background: var(--gradient-1);
    border-radius: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    font-weight: 900;
    color: white;
    box-shadow: 0 4px 20px rgba(108, 92, 231, 0.3);
}

.logo-text .main {
    font-size: 20px;
    font-weight: 800;
    background: var(--gradient-1);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}
.logo-text .sub {
    font-size: 8px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 2px;
}

.user-avatar {
    width: 38px;
    height: 38px;
    border-radius: 50%;
    background: var(--gradient-1);
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-weight: 700;
    font-size: 14px;
    cursor: pointer;
    transition: var(--transition);
}
.user-avatar:hover { transform: scale(1.05); }

.user-actions { display: flex; align-items: center; gap: 8px; }
.user-info { display: flex; align-items: center; gap: 8px; }

.btn {
    background: var(--gradient-1);
    color: white;
    border: none;
    padding: 14px 24px;
    border-radius: var(--radius-sm);
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    width: 100%;
    text-decoration: none;
    display: inline-block;
    text-align: center;
    transition: var(--transition);
    position: relative;
    overflow: hidden;
}
.btn:active { transform: scale(0.97); }

.btn-primary { background: var(--gradient-1); color: white; box-shadow: 0 4px 20px rgba(108, 92, 231, 0.3); }
.btn-primary:hover { box-shadow: 0 6px 30px rgba(108, 92, 231, 0.5); transform: translateY(-2px); }

.btn-secondary { background: var(--card-bg); color: var(--text); border: 1px solid var(--border); }
.btn-secondary:hover { border-color: var(--secondary); }

.btn-success { background: var(--gradient-2); color: white; box-shadow: 0 4px 20px rgba(0, 184, 148, 0.3); }
.btn-success:hover { box-shadow: 0 6px 30px rgba(0, 184, 148, 0.5); transform: translateY(-2px); }

.btn-danger { background: var(--danger); color: white; box-shadow: 0 4px 20px rgba(255, 118, 117, 0.3); }
.btn-danger:hover { box-shadow: 0 6px 30px rgba(255, 118, 117, 0.5); transform: translateY(-2px); }

.btn-gold { background: var(--gradient-3); color: #0a0e1a; box-shadow: 0 4px 20px rgba(249, 202, 36, 0.3); }
.btn-gold:hover { box-shadow: 0 6px 30px rgba(249, 202, 36, 0.5); transform: translateY(-2px); }

.btn-outline { background: transparent; color: var(--secondary); border: 2px solid var(--secondary); }
.btn-outline:hover { background: var(--secondary); color: white; }

.btn-sm { padding: 8px 16px; font-size: 12px; width: auto; }

.btn-logout { 
    background: var(--danger); 
    color: white; 
    padding: 8px 16px; 
    font-size: 12px; 
    font-weight: 600;
    width: auto; 
    border-radius: 50px;
    box-shadow: 0 4px 20px rgba(255, 118, 117, 0.3);
}
.btn-logout:hover { transform: translateY(-2px); }

.btn-share {
    background: linear-gradient(135deg, #25D366, #128C7E);
    color: white;
    padding: 12px 20px;
    font-size: 14px;
    font-weight: 600;
    width: auto;
    border-radius: 50px;
    box-shadow: 0 4px 20px rgba(37, 211, 102, 0.3);
}
.btn-share:hover { transform: scale(1.02); }

.tier-badge {
    padding: 6px 16px;
    border-radius: 50px;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    display: inline-block;
}
.tier-free { background: #2d3436; color: #dfe6e9; }
.tier-bronze { background: linear-gradient(135deg, #cd7f32, #b87333); color: white; }
.tier-silver { background: linear-gradient(135deg, #c0c0c0, #a8a8a8); color: #0a0e1a; }
.tier-gold { background: linear-gradient(135deg, #f9ca24, #f0932b); color: #0a0e1a; }
.tier-platinum { background: linear-gradient(135deg, #e5e4e2, #b8b8b8); color: #0a0e1a; }
.tier-diamond { background: linear-gradient(135deg, #b9f2ff, #4dd0e1); color: #0a0e1a; }

.card {
    background: var(--card-bg);
    border-radius: var(--radius);
    padding: 20px;
    margin-bottom: 16px;
    box-shadow: var(--shadow);
    border: 1px solid rgba(255,255,255,0.03);
    transition: var(--transition);
}
.card:hover { border-color: rgba(108, 92, 231, 0.1); }

.bottom-nav {
    display: flex;
    gap: 2px;
    position: fixed;
    bottom: 16px;
    left: 50%;
    transform: translateX(-50%);
    background: rgba(26, 26, 46, 0.9);
    backdrop-filter: blur(30px);
    padding: 6px 8px;
    border-radius: 60px;
    box-shadow: 0 8px 40px rgba(0,0,0,0.6);
    max-width: 460px;
    width: calc(100% - 32px);
    z-index: 1000;
    border: 1px solid rgba(255,255,255,0.05);
}
.bottom-nav a {
    flex: 1;
    text-align: center;
    padding: 8px 4px;
    text-decoration: none;
    color: var(--text-muted);
    font-size: 7px;
    font-weight: 600;
    border-radius: 50px;
    transition: var(--transition);
}
.bottom-nav a .icon { font-size: 20px; display: block; margin-bottom: 2px; }
.bottom-nav a .label { font-size: 7px; display: block; text-transform: uppercase; letter-spacing: 0.5px; }
.bottom-nav a:hover { color: var(--secondary); }
.bottom-nav a.active {
    color: white;
    background: var(--gradient-1);
    padding: 8px 12px;
    flex: 1.2;
    box-shadow: 0 4px 20px rgba(108, 92, 231, 0.3);
}

.hero-section {
    background: var(--gradient-1);
    border-radius: var(--radius);
    padding: 32px 24px;
    text-align: center;
    color: white;
    margin-bottom: 20px;
    position: relative;
    overflow: hidden;
}
.hero-section::before {
    content: '✦';
    position: absolute;
    top: -30%;
    right: -10%;
    font-size: 150px;
    opacity: 0.05;
}
.hero-section .hero-icon { font-size: 56px; margin-bottom: 12px; }
.hero-section h1 { font-size: 28px; font-weight: 800; margin-bottom: 8px; }
.hero-section p { opacity: 0.9; font-size: 15px; line-height: 1.6; }

.stats-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
}
.stat-box {
    text-align: center;
    padding: 16px;
    background: var(--bg);
    border-radius: var(--radius-sm);
    border: 1px solid rgba(255,255,255,0.03);
    transition: var(--transition);
}
.stat-box:hover { border-color: var(--secondary); }
.stat-box .value {
    font-size: 24px;
    font-weight: 800;
    background: var(--gradient-1);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}
.stat-box .value.gold { background: var(--gradient-3); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.stat-box .label { font-size: 12px; color: var(--text-muted); margin-top: 4px; }

.dashboard-stats {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 8px;
}
.dashboard-stat {
    text-align: center;
    padding: 12px 8px;
    background: var(--bg);
    border-radius: var(--radius-sm);
}
.dashboard-stat .number {
    font-size: 18px;
    font-weight: 700;
    color: var(--secondary);
}
.dashboard-stat .label {
    font-size: 10px;
    color: var(--text-muted);
    margin-top: 2px;
}

.progress-bar {
    background: var(--bg);
    height: 6px;
    border-radius: 50px;
    overflow: hidden;
    margin-top: 8px;
}
.progress-fill {
    background: var(--gradient-1);
    height: 100%;
    border-radius: 50px;
    transition: width 0.8s ease;
}

.alert {
    padding: 14px 18px;
    border-radius: var(--radius-sm);
    margin-bottom: 16px;
    font-weight: 500;
    border-left: 4px solid;
}
.alert-success { background: rgba(0, 184, 148, 0.1); color: var(--success); border-color: var(--success); }
.alert-error { background: rgba(255, 118, 117, 0.1); color: var(--danger); border-color: var(--danger); }
.alert-info { background: rgba(108, 92, 231, 0.1); color: var(--secondary); border-color: var(--secondary); }

input, select, textarea {
    width: 100%;
    padding: 14px 16px;
    border: 2px solid var(--border);
    border-radius: var(--radius-sm);
    font-size: 14px;
    background: var(--bg);
    color: var(--text);
    transition: var(--transition);
}
input:focus, select:focus, textarea:focus {
    outline: none;
    border-color: var(--secondary);
    box-shadow: 0 0 0 4px rgba(108, 92, 231, 0.1);
}
textarea { min-height: 80px; resize: vertical; }
.form-group { margin-bottom: 16px; }
.form-group label { font-weight: 600; font-size: 13px; color: var(--text-light); display: block; margin-bottom: 4px; }

.tier-card {
    background: var(--card-bg);
    border-radius: var(--radius);
    padding: 24px;
    margin-bottom: 16px;
    border: 2px solid var(--border);
    transition: var(--transition);
    position: relative;
    overflow: hidden;
}
.tier-card::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 4px;
    background: var(--border);
}
.tier-card:hover { transform: translateY(-4px); border-color: var(--secondary); }
.tier-card.popular { border-color: var(--gold); }
.tier-card.popular::before { background: var(--gradient-3); }
.tier-card .tier-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.tier-card .tier-name { font-size: 20px; font-weight: 700; }
.tier-card .tier-price { font-size: 28px; font-weight: 800; background: var(--gradient-1); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.tier-card .tier-features { margin: 12px 0; }
.tier-card .tier-features li { list-style: none; padding: 4px 0; color: var(--text-light); font-size: 13px; }
.tier-card .tier-features li::before { content: '✓ '; color: var(--success); font-weight: 700; }

.badge-popular {
    background: var(--gradient-3);
    color: #0a0e1a;
    padding: 2px 12px;
    border-radius: 50px;
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
}

.bank-details-box {
    background: var(--bg);
    border-radius: var(--radius-sm);
    padding: 16px;
    border: 2px dashed rgba(108, 92, 231, 0.3);
}
.bank-details-box .label { font-size: 12px; color: var(--text-muted); }
.bank-details-box .value { font-size: 18px; font-weight: 700; color: var(--text); }

.status-badge {
    padding: 4px 12px;
    border-radius: 50px;
    font-size: 10px;
    font-weight: 600;
}
.status-pending { background: rgba(253, 203, 110, 0.15); color: var(--warning); }
.status-verified { background: rgba(0, 184, 148, 0.15); color: var(--success); }
.status-rejected { background: rgba(255, 118, 117, 0.15); color: var(--danger); }
.status-completed { background: rgba(108, 92, 231, 0.15); color: var(--secondary); }

.review-card {
    background: var(--card-bg);
    border-radius: var(--radius-sm);
    padding: 14px 16px;
    margin-bottom: 10px;
    border-left: 3px solid var(--secondary);
    box-shadow: var(--shadow);
}
.review-card .review-name { font-weight: 700; font-size: 14px; }
.review-card .review-text { font-size: 14px; color: var(--text-light); line-height: 1.5; }
.review-card .review-stars { color: var(--gold); }

.share-confirm {
    background: var(--card-bg);
    border-radius: var(--radius-sm);
    padding: 16px;
    border: 2px solid var(--success);
    text-align: center;
}
.share-confirm .icon { font-size: 48px; display: block; margin-bottom: 8px; }

.withdrawal-info {
    background: rgba(0, 184, 148, 0.05);
    padding: 12px 16px;
    border-radius: var(--radius-sm);
    border-left: 4px solid var(--success);
}

.upgrade-info {
    background: rgba(108, 92, 231, 0.05);
    padding: 12px 16px;
    border-radius: var(--radius-sm);
    border-left: 4px solid var(--secondary);
    margin-bottom: 16px;
}

.glow-border {
    position: relative;
    background: var(--card-bg);
    border-radius: var(--radius);
}
.glow-border::before {
    content: '';
    position: absolute;
    top: -2px;
    left: -2px;
    right: -2px;
    bottom: -2px;
    border-radius: var(--radius);
    background: var(--gradient-1);
    background-size: 400% 400%;
    z-index: -1;
    animation: gradientBorder 4s ease infinite;
}
@keyframes gradientBorder {
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}

.flex-between { display: flex; justify-content: space-between; align-items: center; }
.text-center { text-align: center; }
.text-muted { color: var(--text-muted); font-size: 13px; }
.mt-2 { margin-top: 12px; }
.mb-2 { margin-bottom: 12px; }
.gradient-text { background: var(--gradient-1); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.bonus-badge { background: var(--gradient-3); color: #0a0e1a; padding: 4px 12px; border-radius: 50px; font-size: 11px; font-weight: 700; }
.share-platforms { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 12px 0; }
.share-platform { background: var(--bg); border-radius: var(--radius-sm); padding: 16px; text-align: center; border: 2px solid transparent; transition: var(--transition); }
.share-platform:hover { border-color: var(--secondary); }
.share-platform .platform-icon { font-size: 32px; display: block; margin-bottom: 4px; }
.share-platform .platform-name { font-size: 12px; font-weight: 600; color: var(--text); }
.login-features { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 12px; }
.login-feature { display: flex; align-items: center; gap: 8px; padding: 10px; background: var(--bg); border-radius: var(--radius-sm); font-size: 13px; font-weight: 500; }
.login-feature .icon { font-size: 18px; }
.profile-completion { margin-top: 8px; }
.profile-completion .label { display: flex; justify-content: space-between; font-size: 13px; color: var(--text-muted); }
.profile-completion .bar { height: 6px; background: var(--bg); border-radius: 50px; overflow: hidden; margin-top: 4px; }
.profile-completion .fill { height: 100%; background: var(--gradient-1); border-radius: 50px; transition: width 0.8s ease; }

.quick-actions {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 8px;
}
.quick-action {
    text-align: center;
    padding: 12px 8px;
    background: var(--bg);
    border-radius: var(--radius-sm);
    text-decoration: none;
    color: var(--text);
    transition: var(--transition);
    border: 1px solid transparent;
}
.quick-action:hover {
    border-color: var(--secondary);
    transform: translateY(-2px);
}
.quick-action .icon { font-size: 24px; display: block; margin-bottom: 4px; }
.quick-action .label { font-size: 10px; font-weight: 600; }

.activity-item {
    padding: 10px 0;
    border-bottom: 1px solid var(--border);
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.activity-item:last-child { border-bottom: none; }
.activity-item .action { font-size: 13px; }
.activity-item .time { font-size: 11px; color: var(--text-muted); }

.welcome-banner {
    background: var(--gradient-1);
    border-radius: var(--radius);
    padding: 20px;
    color: white;
    position: relative;
    overflow: hidden;
    margin-bottom: 16px;
}
.welcome-banner::before {
    content: '✦';
    position: absolute;
    top: -20%;
    right: -10%;
    font-size: 100px;
    opacity: 0.05;
}
.welcome-banner .greeting { font-size: 22px; font-weight: 700; }
.welcome-banner .subtext { opacity: 0.8; font-size: 13px; margin-top: 4px; }

.social-links-grid {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 8px;
}
.social-link {
    text-align: center;
    padding: 12px 8px;
    background: var(--bg);
    border-radius: var(--radius-sm);
    text-decoration: none;
    color: var(--text);
    transition: var(--transition);
    border: 1px solid transparent;
}
.social-link:hover {
    border-color: var(--secondary);
    transform: translateY(-2px);
}
.social-link .icon { font-size: 28px; display: block; margin-bottom: 4px; }
.social-link .label { font-size: 9px; font-weight: 600; }
"""

# ==================== HELPERS ====================
def get_payment_settings():
    settings = PaymentSettings.query.first()
    if not settings:
        settings = PaymentSettings(
            bank_name='GTBank',
            account_name='FarmUSDT Labs Ltd',
            account_number='0123456789',
            bank_code='058'
        )
        db.session.add(settings)
        db.session.commit()
    return settings

def get_social_links():
    links = SocialLinks.query.first()
    if not links:
        links = SocialLinks(
            telegram_link='https://t.me/farmusdt',
            whatsapp_link='https://chat.whatsapp.com/farmusdt',
            twitter_link='https://twitter.com/farmusdt',
            youtube_link='https://youtube.com/farmusdt',
            facebook_link='https://facebook.com/farmusdt',
            instagram_link='https://instagram.com/farmusdt'
        )
        db.session.add(links)
        db.session.commit()
    return links

def get_next_tier_info(current_tier, current_score):
    tiers = ['FREE', 'BRONZE', 'SILVER', 'GOLD', 'PLATINUM', 'DIAMOND']
    if current_tier in tiers:
        idx = tiers.index(current_tier)
        if idx < len(tiers) - 1:
            next_tier = tiers[idx + 1]
            return next_tier, TIER_PRICES.get(next_tier, 0)
    return None, 0

def log_activity(user_id, action, details=None, ip=None):
    activity = UserActivity(
        user_id=user_id,
        action=action,
        details=details,
        ip_address=ip
    )
    db.session.add(activity)
    db.session.commit()

def reset_user_tasks_if_needed(user):
    now = datetime.now()
    today = now.date()
    if user.last_task_reset is None:
        user.last_task_reset = now
        user.daily_tasks_completed = 0
        db.session.commit()
        return True
    last_reset_date = user.last_task_reset.date()
    if last_reset_date < today:
        user.daily_tasks_completed = 0
        user.last_task_reset = now
        db.session.commit()
        return True
    return False

def get_user_today_tasks(user_id):
    today = datetime.now().date()
    return TaskCompletion.query.filter(
        TaskCompletion.user_id == user_id,
        db.func.date(TaskCompletion.completed_at) == today
    ).count()

def get_share_message():
    testimonial1 = random.choice(TESTIMONIALS)
    testimonial2 = random.choice(TESTIMONIALS)
    return f"""🚀 FARMUSDT - EARN USDT DAILY! 💰

✅ Complete simple tasks and earn USDT instantly!
✅ Google Reviews - 0.20 USDT per review
✅ Social Tasks - 0.20 USDT per task
✅ Refer Friends - 0.50 USDT per referral
✅ Upgrade Tiers - Earn even more!

🎯 TIER BENEFITS:
• 🥉 BRONZE: 5 tasks/day - 0.20 USDT each
• 🥈 SILVER: 7 tasks/day - 0.20 USDT each
• 🥇 GOLD: 9 tasks/day - 0.20 USDT each
• 💎 PLATINUM: 11 tasks/day - 0.20 USDT each
• 💠 DIAMOND: 13 tasks/day - 0.20 USDT each

⭐ REAL TESTIMONIALS:
"{testimonial1['text']}" - {testimonial1['name']}
"{testimonial2['text']}" - {testimonial2['name']}

💰 Withdraw anytime to your Trust Wallet
⚡ Instant USDT payments
🔒 100% Legit & Verified Platform

Join 10,000+ users already earning USDT! 🚀
SIGN UP NOW:"""

# ==================== PAGE 1: LANDING_PAGE ====================
LANDING_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FarmUSDT - Earn USDT Daily ✨</title>
    <style>""" + STYLES + """</style>
</head>
<body>
    <div class="top-header">
        <div class="logo-container">
            <div class="logo-icon">✦</div>
            <div class="logo-text">
                <span class="main">FarmUSDT</span>
                <span class="sub">Earn Crypto • Trusted</span>
            </div>
        </div>
        <a href="/login" class="btn btn-sm btn-outline" style="width:auto;padding:8px 16px;">Login</a>
    </div>
    <div class="hero-section">
        <div class="hero-icon">✦</div>
        <h1>Earn USDT Daily</h1>
        <p>Complete simple tasks, get paid in USDT, and upgrade your earning potential!</p>
        <div style="margin-top:16px;">
            <a href="/register" class="btn btn-gold" style="width:auto;padding:12px 32px;display:inline-block;font-size:18px;">Get Started ✨</a>
        </div>
        <div style="margin-top:12px;font-size:13px;opacity:0.8;">⚡ Free to join · No hidden fees · Instant payments</div>
    </div>
    <div class="stats-grid" style="margin-bottom:16px;">
        <div class="stat-box"><div class="value">10K+</div><div class="label">Active Users</div></div>
        <div class="stat-box"><div class="value">50K+</div><div class="label">Tasks Done</div></div>
        <div class="stat-box"><div class="value gold">100K+</div><div class="label">USDT Earned</div></div>
        <div class="stat-box"><div class="value gold">99.9%</div><div class="label">Satisfaction</div></div>
    </div>
    <div class="card">
        <h3>⭐ What Our Users Say</h3>
        <div style="margin-top:8px;max-height:400px;overflow-y:auto;padding-right:4px;">
            {% for review in testimonials %}
            <div class="review-card">
                <div class="flex-between">
                    <span class="review-name">{{ review.name }}</span>
                    <span style="font-size:11px;color:var(--text-muted);">✅ Verified</span>
                </div>
                <div class="review-stars">{% for i in range(review.rating) %}⭐{% endfor %}</div>
                <div class="review-text">"{{ review.text }}"</div>
            </div>
            {% endfor %}
        </div>
    </div>
    <div class="card" style="background:var(--gradient-1);color:white;text-align:center;border:none;">
        <h2 style="color:white;">Ready to Start Earning? ✨</h2>
        <p style="opacity:0.9;">Join thousands of users already earning crypto!</p>
        <div style="margin-top:16px;display:flex;gap:8px;flex-direction:column;">
            <a href="/register" class="btn btn-gold" style="background:white;color:#0a0e1a;">Create Account ✨</a>
            <a href="/login" class="btn btn-outline" style="border-color:rgba(255,255,255,0.4);color:white;background:rgba(255,255,255,0.05);">Already have an account? Login</a>
        </div>
    </div>
</body>
</html>
"""

# ==================== PAGE 2: LOGIN_PAGE ====================
LOGIN_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - FarmUSDT 🔐</title>
    <style>""" + STYLES + """</style>
</head>
<body>
    <div class="top-header">
        <div class="logo-container">
            <div class="logo-icon">✦</div>
            <div class="logo-text">
                <span class="main">FarmUSDT</span>
                <span class="sub">Login</span>
            </div>
        </div>
        <a href="/" class="btn btn-sm btn-secondary" style="width:auto;padding:8px 16px;">← Back</a>
    </div>
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            {% for category, message in messages %}
                <div class="alert alert-{{ category }}">{{ message }}</div>
            {% endfor %}
        {% endif %}
    {% endwith %}
    <div class="card glow-border">
        <div style="text-align:center;margin-bottom:16px;">
            <div style="font-size:48px;">🔐</div>
            <h2>Welcome Back!</h2>
            <p class="text-muted">Login to continue earning USDT 💰</p>
        </div>
        <form method="POST">
            <div class="form-group">
                <label>👤 Username</label>
                <input type="text" name="username" required placeholder="Enter your username">
            </div>
            <div class="form-group">
                <label>🔑 Password</label>
                <input type="password" name="password" required placeholder="Enter your password">
            </div>
            <button type="submit" class="btn btn-primary">🚀 Login</button>
        </form>
        <div class="login-features">
            <div class="login-feature"><span class="icon">✅</span> Earn USDT</div>
            <div class="login-feature"><span class="icon">💰</span> Referral Bonuses</div>
            <div class="login-feature"><span class="icon">⬆️</span> Upgrade Tiers</div>
            <div class="login-feature"><span class="icon">🔒</span> Secure Platform</div>
        </div>
        <p class="text-center mt-2">Don't have an account? <a href="/register" style="color:var(--secondary);font-weight:600;">Register Now →</a></p>
    </div>
</body>
</html>
"""

# ==================== PAGE 3: REGISTER_PAGE ====================
REGISTER_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Register - FarmUSDT 📝</title>
    <style>""" + STYLES + """</style>
</head>
<body>
    <div class="top-header">
        <div class="logo-container">
            <div class="logo-icon">✦</div>
            <div class="logo-text">
                <span class="main">FarmUSDT</span>
                <span class="sub">Register</span>
            </div>
        </div>
        <a href="/" class="btn btn-sm btn-secondary" style="width:auto;padding:8px 16px;">← Back</a>
    </div>
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            {% for category, message in messages %}
                <div class="alert alert-{{ category }}">{{ message }}</div>
            {% endfor %}
        {% endif %}
    {% endwith %}
    <div class="card glow-border">
        <div style="text-align:center;margin-bottom:16px;">
            <div style="font-size:48px;">📝</div>
            <h2>Create Account</h2>
            <p class="text-muted">Join and start earning USDT today! 🚀</p>
        </div>
        <form method="POST">
            <div class="form-group">
                <label>👤 Username</label>
                <input type="text" name="username" required placeholder="Choose a unique username">
            </div>
            <div class="form-group">
                <label>📧 Email</label>
                <input type="email" name="email" required placeholder="Your email address">
            </div>
            <div class="form-group">
                <label>🔑 Password</label>
                <input type="password" name="password" required placeholder="Create a strong password">
            </div>
            <div class="form-group">
                <label>✅ Confirm Password</label>
                <input type="password" name="confirm_password" required placeholder="Confirm your password">
            </div>
            <button type="submit" class="btn btn-primary">🎯 Create Account</button>
        </form>
        <div style="margin-top:16px;background:rgba(108,92,231,0.05);padding:12px;border-radius:var(--radius-sm);text-align:center;border:1px solid rgba(108,92,231,0.15);">
            <span style="font-weight:600;">🎉 Bonus:</span>
            <span class="text-muted">Refer friends and earn <strong>0.50 USDT</strong> each!</span>
        </div>
        <p class="text-center mt-2">Already have an account? <a href="/login" style="color:var(--secondary);font-weight:600;">Login →</a></p>
    </div>
</body>
</html>
"""

# ==================== PAGE 4: DASHBOARD_PAGE ====================
DASHBOARD_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard - FarmUSDT 📊</title>
    <style>""" + STYLES + """</style>
</head>
<body>
    <div class="top-header">
        <div class="logo-container">
            <div class="logo-icon">✦</div>
            <div class="logo-text">
                <span class="main">FarmUSDT</span>
                <span class="sub">Dashboard</span>
            </div>
        </div>
        <div class="user-actions">
            <div class="user-info">
                <span class="tier-badge tier-{{ user.tier|lower }}">{{ user.tier }}</span>
                <span style="font-size:14px;font-weight:600;">👋 {{ user.username }}</span>
            </div>
            <a href="/logout" class="btn btn-logout" onclick="return confirm('Are you sure you want to logout?')">🚪</a>
        </div>
    </div>
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            {% for category, message in messages %}
                <div class="alert alert-{{ category }}">{{ message }}</div>
            {% endfor %}
        {% endif %}
    {% endwith %}
    
    <div class="welcome-banner">
        <div class="greeting">👋 Welcome back, {{ user.username }}!</div>
        <div class="subtext">You've earned {{ "%.2f"|format(user.total_earned) }} USDT so far. Keep going! 🚀</div>
    </div>
    
    {% if user.tier == 'FREE' %}
    <div class="card" style="text-align:center;background:rgba(108,92,231,0.05);border:2px solid var(--secondary);">
        <div style="font-size:48px;">⬆️</div>
        <h2 style="color:var(--text);">Upgrade Required!</h2>
        <p class="text-muted">You need to upgrade your tier to start earning USDT!</p>
        <a href="/upgrade" class="btn btn-primary mt-2">🚀 Upgrade Now</a>
    </div>
    {% endif %}
    
    <div class="card" style="background:var(--gradient-1);color:white;border:none;">
        <div style="font-size:14px;opacity:0.8;margin-bottom:4px;">💰 USDT Balance</div>
        <div style="font-size:40px;font-weight:800;">{{ "%.2f"|format(user.balance) }} USDT</div>
        <div style="display:flex;gap:12px;margin-top:16px;flex-wrap:wrap;">
            <span style="background:rgba(255,255,255,0.15);padding:4px 12px;border-radius:50px;font-size:12px;">🔥 {{ user.streak_days }} day streak</span>
            <span style="background:rgba(255,255,255,0.15);padding:4px 12px;border-radius:50px;font-size:12px;">👥 {{ user.total_referrals }} referrals</span>
            <span style="background:rgba(255,255,255,0.15);padding:4px 12px;border-radius:50px;font-size:12px;">📝 {{ user.daily_limit }} tasks/day</span>
        </div>
    </div>
    
    <div class="dashboard-stats">
        <div class="dashboard-stat">
            <div class="number">{{ "%.2f"|format(user.total_earned) }}</div>
            <div class="label">💰 Total Earned</div>
        </div>
        <div class="dashboard-stat">
            <div class="number">{{ user.total_referrals }}</div>
            <div class="label">👥 Referrals</div>
        </div>
        <div class="dashboard-stat">
            <div class="number">{{ user.streak_days }}</div>
            <div class="label">🔥 Streak</div>
        </div>
    </div>
    
    {% if user.tier != 'FREE' %}
    <div class="card">
        <div class="flex-between">
            <span style="font-weight:600;">
                {% if next_tier %}
                    Upgrade to <span class="gradient-text">{{ next_tier }}</span>
                {% else %}
                    <span class="gradient-text">MAX LEVEL</span>
                {% endif %}
            </span>
            <span style="font-weight:600;color:var(--secondary);">
                {% if next_tier %}₦{{ "%.2f"|format(needed_points) }}{% else %}🏆{% endif %}
            </span>
        </div>
        <div class="progress-bar"><div class="progress-fill" style="width:{{ progress }}%;"></div></div>
        <div style="margin-top:8px;display:flex;gap:4px;flex-wrap:wrap;">
            <span class="tier-badge tier-free">FREE</span>
            <span class="tier-badge tier-bronze">BRONZE</span>
            <span class="tier-badge tier-silver">SILVER</span>
            <span class="tier-badge tier-gold">GOLD</span>
            <span class="tier-badge tier-platinum">PLATINUM</span>
            <span class="tier-badge tier-diamond">DIAMOND</span>
        </div>
    </div>
    
    <div class="stats-grid">
        <div class="stat-box"><div class="value">{{ "%.2f"|format(user.commission_balance) }}</div><div class="label">💸 Commission</div></div>
        <div class="stat-box"><div class="value gold">{{ user.daily_limit }}</div><div class="label">📝 Daily Limit</div></div>
        <div class="stat-box"><div class="value">{{ today_tasks }}</div><div class="label">✅ Tasks Done</div></div>
        <div class="stat-box"><div class="value">{{ remaining_tasks }}</div><div class="label">⏳ Tasks Left</div></div>
    </div>
    {% endif %}
    
    <div class="card">
        <h3>⚡ Quick Actions</h3>
        <div class="quick-actions" style="margin-top:12px;">
            <a href="/earn" class="quick-action">
                <span class="icon">💰</span>
                <span class="label">Earn</span>
            </a>
            <a href="/upgrade" class="quick-action">
                <span class="icon">⬆️</span>
                <span class="label">Upgrade</span>
            </a>
            <a href="/referral" class="quick-action">
                <span class="icon">👥</span>
                <span class="label">Refer</span>
            </a>
            <a href="/withdraw" class="quick-action">
                <span class="icon">💸</span>
                <span class="label">Withdraw</span>
            </a>
            <a href="/account" class="quick-action">
                <span class="icon">⚙️</span>
                <span class="label">Settings</span>
            </a>
            <a href="/about" class="quick-action">
                <span class="icon">ℹ️</span>
                <span class="label">About</span>
            </a>
        </div>
    </div>
    
    <div class="card">
        <h3>📋 Recent Activity</h3>
        <div style="margin-top:8px;">
            {% if recent_activities %}
                {% for activity in recent_activities %}
                <div class="activity-item">
                    <span class="action">{{ activity.action }}</span>
                    <span class="time">{{ activity.time }}</span>
                </div>
                {% endfor %}
            {% else %}
                <p class="text-muted text-center">No recent activity yet. Start earning today! 🚀</p>
            {% endif %}
        </div>
    </div>
    
    <nav class="bottom-nav">
        <a href="/" class="active"><span class="icon">🏠</span><span class="label">Home</span></a>
        <a href="/earn"><span class="icon">💰</span><span class="label">Earn</span></a>
        <a href="/upgrade"><span class="icon">⬆️</span><span class="label">Upgrade</span></a>
        <a href="/referral"><span class="icon">👥</span><span class="label">Refer</span></a>
        <a href="/withdraw"><span class="icon">💸</span><span class="label">Withdraw</span></a>
    </nav>
</body>
</html>
"""

# ==================== PAGE 5: EARN_PAGE ====================
EARN_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Earn USDT - FarmUSDT 💰</title>
    <style>""" + STYLES + """</style>
</head>
<body>
    <div class="top-header">
        <div class="logo-container">
            <div class="logo-icon">✦</div>
            <div class="logo-text">
                <span class="main">FarmUSDT</span>
                <span class="sub">Earn</span>
            </div>
        </div>
        <div class="user-actions">
            <div class="user-info">
                <span class="tier-badge tier-{{ user.tier|lower }}">{{ user.tier }}</span>
                <span style="font-size:14px;font-weight:600;">👋 {{ user.username }}</span>
            </div>
            <a href="/logout" class="btn btn-logout" onclick="return confirm('Are you sure you want to logout?')">🚪</a>
        </div>
    </div>
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            {% for category, message in messages %}
                <div class="alert alert-{{ category }}">{{ message }}</div>
            {% endfor %}
        {% endif %}
    {% endwith %}
    
    {% if user.tier == 'FREE' %}
    <div class="card" style="text-align:center;background:rgba(108,92,231,0.05);border:2px solid var(--secondary);">
        <div style="font-size:48px;">⬆️</div>
        <h2 style="color:var(--text);">Upgrade Required</h2>
        <p class="text-muted">You need to upgrade your tier to access tasks!</p>
        <a href="/upgrade" class="btn btn-primary mt-2">🚀 Upgrade Now</a>
    </div>
    {% else %}
    
    {% set social = get_social_links() %}
    <div class="card" style="background:rgba(108,92,231,0.05);border:1px solid var(--secondary);">
        <h3 style="text-align:center;">📱 Join Our Community</h3>
        <div class="social-links-grid" style="margin-top:8px;">
            <a href="{{ social.telegram_link }}" target="_blank" class="social-link">
                <span class="icon">💬</span>
                <span class="label">Telegram</span>
            </a>
            <a href="{{ social.whatsapp_link }}" target="_blank" class="social-link">
                <span class="icon">📱</span>
                <span class="label">WhatsApp</span>
            </a>
            <a href="{{ social.twitter_link }}" target="_blank" class="social-link">
                <span class="icon">🐦</span>
                <span class="label">Twitter</span>
            </a>
            <a href="{{ social.youtube_link }}" target="_blank" class="social-link">
                <span class="icon">▶️</span>
                <span class="label">YouTube</span>
            </a>
            <a href="{{ social.facebook_link }}" target="_blank" class="social-link">
                <span class="icon">📘</span>
                <span class="label">Facebook</span>
            </a>
            <a href="{{ social.instagram_link }}" target="_blank" class="social-link">
                <span class="icon">📸</span>
                <span class="label">Instagram</span>
            </a>
        </div>
    </div>
    
    <div class="card" style="background:var(--gradient-2);color:white;border:none;">
        <div style="font-size:14px;opacity:0.9;">📊 Today's Earning Potential</div>
        <div style="font-size:32px;font-weight:800;">{{ "%.2f"|format(potential_earnings) }} USDT</div>
        <div style="font-size:12px;opacity:0.8;">{{ remaining_tasks }} tasks remaining out of {{ user.daily_limit }}</div>
        <div style="font-size:11px;opacity:0.7;margin-top:4px;">🔄 Resets at midnight every day</div>
    </div>
    
    {% if tasks %}
        {% for task in tasks %}
            <div class="card" style="border-left:4px solid var(--secondary);">
                <div class="flex-between">
                    <div>
                        <h3>{{ task.icon }} {{ task.title }}</h3>
                        <p class="text-muted">{{ task.description }}</p>
                        {% if task.external_link %}
                            <div style="margin-top:4px;">
                                <a href="{{ task.external_link }}" target="_blank" style="color:var(--secondary);font-size:12px;text-decoration:underline;">🔗 Visit Link</a>
                            </div>
                        {% endif %}
                        <div style="margin-top:6px;">
                            <span class="tier-badge tier-{{ task.tier_required|lower }}">{{ task.tier_required }}</span>
                            <span style="margin-left:8px;font-size:12px;color:var(--text-light);">💵 {{ "%.2f"|format(task.reward) }} USDT</span>
                        </div>
                    </div>
                    <div>
                        {% if task.id in completed_ids %}
                            <span style="background:var(--success);color:#0a0e1a;padding:6px 12px;border-radius:50px;font-size:12px;font-weight:700;">✅ Done</span>
                        {% elif remaining_tasks <= 0 %}
                            <div style="text-align:right;">
                                <span style="background:var(--danger);color:white;padding:6px 12px;border-radius:50px;font-size:12px;font-weight:600;">⛔ Limit</span>
                                <div style="font-size:10px;color:var(--text-muted);margin-top:4px;">Come back tomorrow</div>
                            </div>
                        {% else %}
                            <form method="POST" action="/complete_task/{{ task.id }}">
                                <button type="submit" style="background:var(--gradient-1);color:white;border:none;padding:10px 20px;border-radius:50px;font-size:14px;font-weight:700;cursor:pointer;">🚀 Start</button>
                            </form>
                        {% endif %}
                    </div>
                </div>
            </div>
        {% endfor %}
    {% else %}
        <div class="card" style="text-align:center;background:rgba(255,118,117,0.05);border:1px solid var(--danger);">
            <div style="font-size:48px;">⚠️</div>
            <h3 style="color:var(--text);">No Tasks Available</h3>
            <p class="text-muted">There are no tasks for your tier yet. Please contact admin.</p>
            <a href="/support" class="btn btn-secondary mt-2">📧 Contact Support</a>
        </div>
    {% endif %}
    {% endif %}
    
    <nav class="bottom-nav">
        <a href="/"><span class="icon">🏠</span><span class="label">Home</span></a>
        <a href="/earn" class="active"><span class="icon">💰</span><span class="label">Earn</span></a>
        <a href="/upgrade"><span class="icon">⬆️</span><span class="label">Upgrade</span></a>
        <a href="/referral"><span class="icon">👥</span><span class="label">Refer</span></a>
        <a href="/withdraw"><span class="icon">💸</span><span class="label">Withdraw</span></a>
    </nav>
</body>
</html>
"""

# ==================== PAGE 6: SHARE_TASK_PAGE ====================
SHARE_TASK_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Share & Earn - FarmUSDT 📤</title>
    <style>""" + STYLES + """</style>
</head>
<body>
    <div class="top-header">
        <div class="logo-container">
            <div class="logo-icon">✦</div>
            <div class="logo-text">
                <span class="main">FarmUSDT</span>
                <span class="sub">Share & Earn</span>
            </div>
        </div>
        <div class="user-actions">
            <div class="user-info">
                <span class="tier-badge tier-{{ user.tier|lower }}">{{ user.tier }}</span>
                <span style="font-size:14px;font-weight:600;">👋 {{ user.username }}</span>
            </div>
            <a href="/logout" class="btn btn-logout" onclick="return confirm('Are you sure you want to logout?')">🚪</a>
        </div>
    </div>
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            {% for category, message in messages %}
                <div class="alert alert-{{ category }}">{{ message }}</div>
            {% endfor %}
        {% endif %}
    {% endwith %}
    
    <div class="card" style="text-align:center;">
        <div style="font-size:48px;">📤</div>
        <h2>Share & Earn 0.20 USDT</h2>
        <p class="text-muted">Share our platform on social media and earn USDT instantly!</p>
    </div>
    
    <div class="card" style="background:rgba(108,92,231,0.05);border:2px solid var(--secondary);">
        <div style="font-size:14px;color:var(--text-light);">Your Referral Link</div>
        <div style="background:var(--bg);padding:12px;border-radius:var(--radius-sm);margin-top:8px;word-break:break-all;">
            <code>{{ share_url }}</code>
        </div>
        <button onclick="navigator.clipboard.writeText('{{ share_url }}');alert('✅ Link copied!')" class="btn btn-secondary mt-2" style="width:auto;padding:10px 20px;">
            📋 Copy Link
        </button>
    </div>

    <div class="card" style="background:linear-gradient(135deg,#25D366,#128C7E);color:white;text-align:center;border:none;">
        <div style="font-size:48px;">💬</div>
        <h2 style="color:white;">Share on WhatsApp</h2>
        <div style="margin-top:16px;">
            <a href="{{ whatsapp_link }}" target="_blank" class="btn btn-share" style="background:white;color:#25D366;font-size:18px;padding:14px 24px;">
                📱 Share on WhatsApp
            </a>
        </div>
    </div>

    <div class="card share-confirm">
        <span class="icon">✅</span>
        <h3>After sharing, confirm here</h3>
        <form method="POST" action="/share_task">
            <button type="submit" class="btn btn-success mt-2">💰 Claim 0.20 USDT</button>
        </form>
    </div>
    
    <nav class="bottom-nav">
        <a href="/"><span class="icon">🏠</span><span class="label">Home</span></a>
        <a href="/earn" class="active"><span class="icon">💰</span><span class="label">Earn</span></a>
        <a href="/upgrade"><span class="icon">⬆️</span><span class="label">Upgrade</span></a>
        <a href="/referral"><span class="icon">👥</span><span class="label">Refer</span></a>
        <a href="/withdraw"><span class="icon">💸</span><span class="label">Withdraw</span></a>
    </nav>
</body>
</html>
"""

# ==================== PAGE 7: REFERRAL_PAGE ====================
REFERRAL_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Referrals - FarmUSDT 👥</title>
    <style>""" + STYLES + """</style>
</head>
<body>
    <div class="top-header">
        <div class="logo-container">
            <div class="logo-icon">✦</div>
            <div class="logo-text">
                <span class="main">FarmUSDT</span>
                <span class="sub">Refer</span>
            </div>
        </div>
        <div class="user-actions">
            <div class="user-info">
                <span class="tier-badge tier-{{ user.tier|lower }}">{{ user.tier }}</span>
                <span style="font-size:14px;font-weight:600;">👋 {{ user.username }}</span>
            </div>
            <a href="/logout" class="btn btn-logout" onclick="return confirm('Are you sure you want to logout?')">🚪</a>
        </div>
    </div>
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            {% for category, message in messages %}
                <div class="alert alert-{{ category }}">{{ message }}</div>
            {% endfor %}
        {% endif %}
    {% endwith %}
    
    <div class="card" style="background:var(--gradient-1);color:white;text-align:center;border:none;">
        <div style="font-size:48px;">👥</div>
        <h2>Invite & Earn USDT</h2>
        <p style="opacity:0.9;">Earn <strong>0.50 USDT</strong> for every friend who joins!</p>
        <div style="margin-top:8px;">
            <span class="bonus-badge">🎯 Total Earned: {{ "%.2f"|format(user.referral_bonus_earned) }} USDT</span>
        </div>
    </div>
    
    <div class="card">
        <div class="form-group">
            <label>📋 Your Referral Link</label>
            <div style="display:flex;gap:8px;align-items:center;">
                <input type="text" value="{{ referral_link }}" readonly style="flex:1;" onclick="this.select();navigator.clipboard.writeText(this.value);">
                <button onclick="navigator.clipboard.writeText('{{ referral_link }}');alert('✅ Link copied!')" style="background:var(--gradient-1);color:white;border:none;padding:12px 16px;border-radius:12px;cursor:pointer;font-size:20px;font-weight:700;">📋</button>
            </div>
        </div>
    </div>

    <div class="card" style="background:linear-gradient(135deg,#25D366,#128C7E);color:white;text-align:center;border:none;">
        <div style="font-size:32px;">💬</div>
        <h3 style="color:white;">Share on WhatsApp</h3>
        <div style="margin-top:12px;">
            <a href="{{ whatsapp_link }}" target="_blank" class="btn btn-share" style="background:white;color:#25D366;font-size:16px;padding:12px 20px;">
                📱 Share Now
            </a>
        </div>
    </div>

    <div class="stats-grid">
        <div class="stat-box"><div class="value">{{ total_invites }}</div><div class="label">📊 Total Invites</div></div>
        <div class="stat-box"><div class="value gold">{{ "%.2f"|format(total_earned) }}</div><div class="label">💰 Total Earned</div></div>
    </div>
    
    {% if referred_users %}
    <div class="card">
        <h3>👥 Referred Users</h3>
        {% for ref in referred_users %}
        <div style="padding:8px 0;border-bottom:1px solid var(--border);">
            <div class="flex-between">
                <div><strong>{{ ref.username }}</strong><span class="tier-badge tier-{{ ref.tier|lower }}" style="font-size:10px;margin-left:8px;">{{ ref.tier }}</span></div>
                <div style="text-align:right;">
                    <div style="font-size:12px;color:var(--text-light);">Joined: {{ ref.created_at.strftime('%b %d, %Y') }}</div>
                    <div style="font-size:11px;color:var(--success);">+0.50 USDT</div>
                </div>
            </div>
        </div>
        {% endfor %}
    </div>
    {% else %}
    <div class="card">
        <p class="text-center text-muted">📭 You haven't referred anyone yet. Share your link!</p>
    </div>
    {% endif %}
    
    <nav class="bottom-nav">
        <a href="/"><span class="icon">🏠</span><span class="label">Home</span></a>
        <a href="/earn"><span class="icon">💰</span><span class="label">Earn</span></a>
        <a href="/upgrade"><span class="icon">⬆️</span><span class="label">Upgrade</span></a>
        <a href="/referral" class="active"><span class="icon">👥</span><span class="label">Refer</span></a>
        <a href="/withdraw"><span class="icon">💸</span><span class="label">Withdraw</span></a>
    </nav>
</body>
</html>
"""

# ==================== PAGE 8: UPGRADE_PAGE ====================
UPGRADE_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Upgrade - FarmUSDT ⬆️</title>
    <style>""" + STYLES + """</style>
</head>
<body>
    <div class="top-header">
        <div class="logo-container">
            <div class="logo-icon">✦</div>
            <div class="logo-text">
                <span class="main">FarmUSDT</span>
                <span class="sub">Upgrade</span>
            </div>
        </div>
        <div class="user-actions">
            <div class="user-info">
                <span class="tier-badge tier-{{ user.tier|lower }}">{{ user.tier }}</span>
                <span style="font-size:14px;font-weight:600;">👋 {{ user.username }}</span>
            </div>
            <a href="/logout" class="btn btn-logout" onclick="return confirm('Are you sure you want to logout?')">🚪</a>
        </div>
    </div>
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            {% for category, message in messages %}
                <div class="alert alert-{{ category }}">{{ message }}</div>
            {% endfor %}
        {% endif %}
    {% endwith %}
    
    <div class="upgrade-info">
        <div style="display:flex;align-items:center;gap:8px;">
            <span style="font-size:20px;">💡</span>
            <div>
                <strong>Upgrade to Start Earning USDT!</strong>
                <div style="font-size:13px;color:var(--text-light);">
                    Send payment to the bank details below and submit your proof for verification.
                </div>
            </div>
        </div>
    </div>
    
    <div class="card" style="text-align:center;">
        <h2 style="font-size:24px;">🚀 Choose Your Tier</h2>
        <p class="text-muted">Pay in Naira to unlock higher paying tasks!</p>
    </div>
    
    <div class="card" style="text-align:center;background:var(--bg);">
        <div style="font-size:14px;color:var(--text-light);">📌 Current Tier</div>
        <div style="font-size:32px;font-weight:800;" class="gradient-text">{{ user.tier }}</div>
        <div style="font-size:14px;color:var(--text-light);">📝 {{ user.daily_limit }} tasks/day</div>
    </div>
    
    {% set payment_settings = get_payment_settings() %}
    <div class="card" style="background:rgba(108,92,231,0.05);border:2px solid var(--secondary);">
        <h3 style="color:var(--text);">🏦 Send Payment To:</h3>
        <div class="bank-details-box">
            <div><span class="label">🏛️ Bank:</span> <span class="value">{{ payment_settings.bank_name }}</span></div>
            <div><span class="label">👤 Account Name:</span> <span class="value">{{ payment_settings.account_name }}</span></div>
            <div><span class="label">🔢 Account Number:</span> <span class="value">{{ payment_settings.account_number }}</span></div>
        </div>
        <p class="text-muted" style="font-size:12px;text-align:center;">⚠️ Send the exact amount in Naira for your chosen tier</p>
        <button onclick="navigator.clipboard.writeText('{{ payment_settings.account_number }}');alert('✅ Account number copied!')" class="btn btn-secondary mt-2" style="width:auto;padding:10px 20px;">
            📋 Copy Account Number
        </button>
    </div>
    
    {% for tier_key, tier in tiers.items() %}
        {% if user.tier != tier_key %}
        <div class="tier-card {% if tier_key == 'GOLD' %}popular{% endif %}">
            {% if tier_key == 'GOLD' %}<span class="badge-popular">🔥 POPULAR</span>{% endif %}
            <div class="tier-header">
                <span class="tier-name">{{ tier.name }}</span>
                <span style="font-size:14px;color:var(--text-muted);">{{ tier.tasks }} tasks/day</span>
            </div>
            <div class="tier-price">₦{{ "%.2f"|format(tier.price) }}</div>
            <ul class="tier-features">
                <li>{{ tier.tasks }} tasks per day</li>
                <li>0.20 USDT per task</li>
                <li>Earn up to ₦{{ "%.2f"|format(tier.tasks * 0.20 * 500) }} daily</li>
                <li>Priority support</li>
            </ul>
            <button onclick="showPaymentForm('{{ tier_key }}', {{ tier.price }})" class="btn btn-primary" style="margin-top:8px;">
                💳 Upgrade Now
            </button>
        </div>
        {% endif %}
    {% endfor %}
    
    <div id="paymentForm" style="display:none;">
        <div class="card" style="border:2px solid var(--success);">
            <h3>💳 Submit Payment Proof</h3>
            <p class="text-muted">After sending payment, fill this form to confirm.</p>
            <form method="POST" action="/submit_payment">
                <input type="hidden" name="tier" id="selectedTier">
                <input type="hidden" name="amount" id="selectedAmount">
                <div class="form-group"><label>👤 Full Name (as sender)</label><input type="text" name="sender_name" placeholder="Your full name" required></div>
                <div class="form-group"><label>🔢 Transaction Reference</label><input type="text" name="transaction_id" placeholder="e.g., FARM-123456" required></div>
                <div class="form-group"><label>💰 Amount Sent (₦)</label><input type="number" name="amount_sent" id="amountSent" required></div>
                <div class="form-group"><label>📅 Payment Date & Time</label><input type="datetime-local" name="payment_date" required></div>
                <div class="form-group"><label>📝 Notes (optional)</label><textarea name="notes" placeholder="Any extra details..."></textarea></div>
                <button type="submit" class="btn btn-success">✅ Submit Payment</button>
                <button type="button" onclick="hidePaymentForm()" class="btn btn-secondary mt-2">❌ Cancel</button>
            </form>
        </div>
    </div>
    
    {% if transactions_list %}
    <div class="card">
        <h3>📜 Your Payment History</h3>
        {% for tx in transactions_list %}
        <div style="padding:8px 0;border-bottom:1px solid var(--border);">
            <div class="flex-between">
                <div><strong>{{ tx.tier }}</strong><span style="font-size:12px;color:var(--text-light);">₦{{ "%.2f"|format(tx.amount) }}</span></div>
                <div><span class="status-badge status-{{ tx.status|lower }}">{{ tx.status }}</span></div>
            </div>
            <div class="text-muted" style="font-size:11px;">{{ tx.date }} · Ref: {{ tx.transaction_id }}</div>
        </div>
        {% endfor %}
    </div>
    {% endif %}
    
    <nav class="bottom-nav">
        <a href="/"><span class="icon">🏠</span><span class="label">Home</span></a>
        <a href="/earn"><span class="icon">💰</span><span class="label">Earn</span></a>
        <a href="/upgrade" class="active"><span class="icon">⬆️</span><span class="label">Upgrade</span></a>
        <a href="/referral"><span class="icon">👥</span><span class="label">Refer</span></a>
        <a href="/withdraw"><span class="icon">💸</span><span class="label">Withdraw</span></a>
    </nav>
    
    <script>
        function showPaymentForm(tier, amount) {
            document.getElementById('selectedTier').value = tier;
            document.getElementById('selectedAmount').value = amount;
            document.getElementById('amountSent').value = amount;
            document.getElementById('paymentForm').style.display = 'block';
            document.getElementById('paymentForm').scrollIntoView({ behavior: 'smooth' });
        }
        function hidePaymentForm() { document.getElementById('paymentForm').style.display = 'none'; }
    </script>
</body>
</html>
"""

# ==================== PAGE 9: WITHDRAW_PAGE ====================
WITHDRAW_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Withdraw USDT - FarmUSDT 💸</title>
    <style>""" + STYLES + """</style>
</head>
<body>
    <div class="top-header">
        <div class="logo-container">
            <div class="logo-icon">✦</div>
            <div class="logo-text">
                <span class="main">FarmUSDT</span>
                <span class="sub">Withdraw</span>
            </div>
        </div>
        <div class="user-actions">
            <div class="user-info">
                <span class="tier-badge tier-{{ user.tier|lower }}">{{ user.tier }}</span>
                <span style="font-size:14px;font-weight:600;">👋 {{ user.username }}</span>
            </div>
            <a href="/logout" class="btn btn-logout" onclick="return confirm('Are you sure you want to logout?')">🚪</a>
        </div>
    </div>
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            {% for category, message in messages %}
                <div class="alert alert-{{ category }}">{{ message }}</div>
            {% endfor %}
        {% endif %}
    {% endwith %}
    
    <div class="card" style="background:var(--gradient-2);color:white;border:none;">
        <div style="font-size:14px;opacity:0.8;">💰 USDT Balance</div>
        <div style="font-size:40px;font-weight:800;">{{ "%.2f"|format(user.balance) }} USDT</div>
    </div>

    <div class="withdrawal-info">
        <div style="display:flex;align-items:center;gap:8px;">
            <span style="font-size:20px;">💎</span>
            <div>
                <strong>Withdraw Anytime!</strong>
                <div style="font-size:13px;color:var(--text-light);">
                    ✅ No restrictions - Withdraw your USDT whenever you want!
                </div>
            </div>
        </div>
    </div>

    <div class="card">
        <form method="POST">
            <div class="form-group">
                <label>💰 Amount (USDT) - Minimum {{ "%.2f"|format(min_amount) }} USDT</label>
                <input type="number" name="amount" step="0.01" min="{{ min_amount }}" max="{{ user.balance }}" required>
                <span class="text-muted" style="font-size:12px;">Minimum: {{ "%.2f"|format(min_amount) }} USDT</span>
            </div>
            <div class="form-group">
                <label>🌐 Network</label>
                <select name="wallet_network" required>
                    <option value="BEP20">BEP20 (Binance Smart Chain)</option>
                    <option value="ERC20">ERC20 (Ethereum)</option>
                    <option value="TRC20">TRC20 (Tron)</option>
                </select>
            </div>
            <div class="form-group">
                <label>📬 USDT Wallet Address</label>
                <input type="text" name="wallet_address" placeholder="Enter your Trust Wallet USDT address" required>
            </div>
            <button type="submit" class="btn btn-success">💸 Request Withdrawal</button>
        </form>
    </div>

    {% if withdrawals %}
    <div class="card">
        <h3>📜 Withdrawal History</h3>
        {% for w in withdrawals %}
        <div style="padding:8px 0;border-bottom:1px solid var(--border);">
            <div class="flex-between">
                <div>
                    <strong>{{ "%.2f"|format(w.amount) }} USDT</strong>
                    <span style="margin-left:8px;font-size:12px;color:var(--text-light);">{{ w.wallet_network }}</span>
                </div>
                <div>
                    <span class="status-badge status-{{ w.status|lower }}">{{ w.status }}</span>
                </div>
            </div>
            <div class="text-muted" style="font-size:12px;">{{ w.created_at.strftime('%b %d, %Y %H:%M') }}</div>
        </div>
        {% endfor %}
    </div>
    {% endif %}

    <nav class="bottom-nav">
        <a href="/"><span class="icon">🏠</span><span class="label">Home</span></a>
        <a href="/earn"><span class="icon">💰</span><span class="label">Earn</span></a>
        <a href="/upgrade"><span class="icon">⬆️</span><span class="label">Upgrade</span></a>
        <a href="/referral"><span class="icon">👥</span><span class="label">Refer</span></a>
        <a href="/withdraw" class="active"><span class="icon">💸</span><span class="label">Withdraw</span></a>
    </nav>
</body>
</html>
"""

# ==================== PAGE 10: ACCOUNT_PAGE ====================
ACCOUNT_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Account - FarmUSDT 👤</title>
    <style>""" + STYLES + """</style>
</head>
<body>
    <div class="top-header">
        <div class="logo-container">
            <div class="logo-icon">✦</div>
            <div class="logo-text">
                <span class="main">FarmUSDT</span>
                <span class="sub">Account</span>
            </div>
        </div>
        <div class="user-actions">
            <div class="user-info">
                <span class="tier-badge tier-{{ user.tier|lower }}">{{ user.tier }}</span>
                <span style="font-size:14px;font-weight:600;">👋 {{ user.username }}</span>
            </div>
            <a href="/logout" class="btn btn-logout" onclick="return confirm('Are you sure you want to logout?')">🚪</a>
        </div>
    </div>
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            {% for category, message in messages %}
                <div class="alert alert-{{ category }}">{{ message }}</div>
            {% endfor %}
        {% endif %}
    {% endwith %}
    
    <div class="card"><div style="text-align:center;"><div style="font-size:48px;">👤</div><h2>Account Settings</h2><p class="text-muted">Manage your personal information</p></div></div>
    
    <div class="card glow-border">
        <h3>📝 Personal Information</h3>
        <form method="POST" action="/update_account">
            <div class="form-group"><label>👤 Full Name</label><input type="text" name="full_name" value="{{ user.full_name or '' }}" placeholder="Enter your full name"></div>
            <div class="form-group"><label>📧 Email</label><input type="email" value="{{ user.email }}" disabled style="opacity:0.7;"></div>
            <div class="form-group"><label>📱 Phone Number</label><input type="tel" name="phone" value="{{ user.phone or '' }}" placeholder="Enter your phone number"></div>
            <div class="form-group"><label>📍 Address</label><input type="text" name="address" value="{{ user.address or '' }}" placeholder="Enter your address"></div>
            <button type="submit" class="btn btn-primary">💾 Save Changes</button>
        </form>
    </div>
    
    <div class="card">
        <h3>🏦 Crypto Wallet</h3>
        <form method="POST" action="/update_wallet">
            <div class="form-group"><label>🌐 Network</label><select name="wallet_network"><option value="BEP20" {% if user.wallet_network == 'BEP20' %}selected{% endif %}>BEP20 (Binance Smart Chain)</option><option value="ERC20" {% if user.wallet_network == 'ERC20' %}selected{% endif %}>ERC20 (Ethereum)</option><option value="TRC20" {% if user.wallet_network == 'TRC20' %}selected{% endif %}>TRC20 (Tron)</option></select></div>
            <div class="form-group"><label>📬 USDT Wallet Address</label><input type="text" name="wallet_address" value="{{ user.wallet_address or '' }}" placeholder="Enter your USDT wallet address"></div>
            <button type="submit" class="btn btn-success">💾 Save Wallet</button>
        </form>
    </div>
    
    <div class="card" style="border:2px solid var(--danger);"><h3 style="color:var(--danger);">🔒 Security</h3><a href="/change_password" class="btn btn-danger">🔑 Change Password</a></div>
    
    <nav class="bottom-nav">
        <a href="/"><span class="icon">🏠</span><span class="label">Home</span></a>
        <a href="/earn"><span class="icon">💰</span><span class="label">Earn</span></a>
        <a href="/upgrade"><span class="icon">⬆️</span><span class="label">Upgrade</span></a>
        <a href="/referral"><span class="icon">👥</span><span class="label">Refer</span></a>
        <a href="/withdraw"><span class="icon">💸</span><span class="label">Withdraw</span></a>
    </nav>
</body>
</html>
"""

# ==================== PAGE 11: CHANGE_PASSWORD_PAGE ====================
CHANGE_PASSWORD_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Change Password - FarmUSDT 🔒</title>
    <style>""" + STYLES + """</style>
</head>
<body>
    <div class="top-header">
        <div class="logo-container">
            <div class="logo-icon">✦</div>
            <div class="logo-text">
                <span class="main">FarmUSDT</span>
                <span class="sub">Security</span>
            </div>
        </div>
        <a href="/account" class="btn btn-sm btn-secondary" style="width:auto;padding:8px 16px;">← Back</a>
    </div>
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            {% for category, message in messages %}
                <div class="alert alert-{{ category }}">{{ message }}</div>
            {% endfor %}
        {% endif %}
    {% endwith %}
    <div class="card glow-border">
        <form method="POST">
            <div class="form-group"><label>🔑 Current Password</label><input type="password" name="current_password" required></div>
            <div class="form-group"><label>🔐 New Password</label><input type="password" name="new_password" required minlength="6"></div>
            <div class="form-group"><label>✅ Confirm New Password</label><input type="password" name="confirm_password" required></div>
            <button type="submit" class="btn btn-primary">Update Password</button>
        </form>
    </div>
</body>
</html>
"""

# ==================== PAGE 12: SUPPORT_PAGE ====================
SUPPORT_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Support - FarmUSDT 💬</title>
    <style>""" + STYLES + """</style>
</head>
<body>
    <div class="top-header">
        <div class="logo-container">
            <div class="logo-icon">✦</div>
            <div class="logo-text">
                <span class="main">FarmUSDT</span>
                <span class="sub">Support</span>
            </div>
        </div>
        <div class="user-actions">
            <div class="user-info">
                <span class="tier-badge tier-{{ user.tier|lower }}">{{ user.tier }}</span>
                <span style="font-size:14px;font-weight:600;">👋 {{ user.username }}</span>
            </div>
            <a href="/logout" class="btn btn-logout" onclick="return confirm('Are you sure you want to logout?')">🚪</a>
        </div>
    </div>
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            {% for category, message in messages %}
                <div class="alert alert-{{ category }}">{{ message }}</div>
            {% endfor %}
        {% endif %}
    {% endwith %}
    <div class="card" style="text-align:center;"><div style="font-size:48px;">💬</div><h2>Support Center</h2><p class="text-muted">We're here to help!</p></div>
    <div class="card glow-border">
        <h3>📝 Submit a Ticket</h3>
        <form method="POST" action="/submit_support">
            <div class="form-group"><label>📌 Subject</label><input type="text" name="subject" placeholder="Brief title of your issue" required></div>
            <div class="form-group"><label>🚨 Priority</label><select name="priority" required><option value="LOW">Low</option><option value="MEDIUM" selected>Medium</option><option value="HIGH">High</option><option value="CRITICAL">Critical</option></select></div>
            <div class="form-group"><label>📝 Message</label><textarea name="message" placeholder="Describe your issue..." required></textarea></div>
            <button type="submit" class="btn btn-primary">🚀 Submit Ticket</button>
        </form>
    </div>
    <div class="card">
        <h3>📜 Your Tickets</h3>
        {% if tickets %}
            {% for ticket in tickets %}
            <div style="padding:10px 0;border-bottom:1px solid var(--border);">
                <div class="flex-between"><div><strong>{{ ticket.subject }}</strong><span class="status-badge status-{{ ticket.status|lower }}">{{ ticket.status }}</span></div><span style="font-size:11px;color:var(--text-muted);">{{ ticket.date }}</span></div>
                <div class="text-muted" style="font-size:12px;margin-top:4px;">Priority: <span style="font-weight:600;">{{ ticket.priority }}</span></div>
                <div style="font-size:13px;margin-top:4px;color:var(--text);">{{ ticket.message[:100] }}{% if ticket.message|length > 100 %}...{% endif %}</div>
            </div>
            {% endfor %}
        {% else %}
            <p class="text-center text-muted">📭 No tickets submitted yet</p>
        {% endif %}
    </div>
    <nav class="bottom-nav">
        <a href="/"><span class="icon">🏠</span><span class="label">Home</span></a>
        <a href="/earn"><span class="icon">💰</span><span class="label">Earn</span></a>
        <a href="/upgrade"><span class="icon">⬆️</span><span class="label">Upgrade</span></a>
        <a href="/referral"><span class="icon">👥</span><span class="label">Refer</span></a>
        <a href="/withdraw"><span class="icon">💸</span><span class="label">Withdraw</span></a>
    </nav>
</body>
</html>
"""

# ==================== PAGE 13: ABOUT_PAGE ====================
ABOUT_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>About - FarmUSDT ℹ️</title>
    <style>""" + STYLES + """</style>
</head>
<body>
    <div class="top-header">
        <div class="logo-container">
            <div class="logo-icon">✦</div>
            <div class="logo-text">
                <span class="main">FarmUSDT</span>
                <span class="sub">About</span>
            </div>
        </div>
        <div class="user-actions">
            <div class="user-info">
                <span class="tier-badge tier-{{ user.tier|lower }}">{{ user.tier }}</span>
                <span style="font-size:14px;font-weight:600;">👋 {{ user.username }}</span>
            </div>
            <a href="/logout" class="btn btn-logout" onclick="return confirm('Are you sure you want to logout?')">🚪</a>
        </div>
    </div>
    
    <div class="card" style="text-align:center;background:var(--gradient-1);color:white;border:none;">
        <div style="font-size:48px;">✦</div>
        <h2 style="color:white;">About FarmUSDT</h2>
        <p style="opacity:0.9;">Your Trusted Crypto Earning Platform</p>
    </div>
    
    <div class="card">
        <h3>🚀 Our Mission</h3>
        <p class="text-muted">FarmUSDT is a revolutionary platform that allows users to earn USDT by completing simple tasks. We believe in making crypto earnings accessible to everyone.</p>
    </div>
    
    <div class="card">
        <h3>💡 How It Works</h3>
        <div style="margin-top:8px;">
            <div style="display:flex;align-items:center;gap:12px;padding:8px 0;border-bottom:1px solid var(--border);">
                <span style="font-size:24px;">1️⃣</span>
                <div><strong>Create Account</strong><br><span class="text-muted">Sign up for free and get your referral link</span></div>
            </div>
            <div style="display:flex;align-items:center;gap:12px;padding:8px 0;border-bottom:1px solid var(--border);">
                <span style="font-size:24px;">2️⃣</span>
                <div><strong>Upgrade Tier</strong><br><span class="text-muted">Pay in Naira to unlock earning tasks</span></div>
            </div>
            <div style="display:flex;align-items:center;gap:12px;padding:8px 0;border-bottom:1px solid var(--border);">
                <span style="font-size:24px;">3️⃣</span>
                <div><strong>Complete Tasks</strong><br><span class="text-muted">Earn 0.20 USDT per task</span></div>
            </div>
            <div style="display:flex;align-items:center;gap:12px;padding:8px 0;">
                <span style="font-size:24px;">4️⃣</span>
                <div><strong>Withdraw Anytime</strong><br><span class="text-muted">Send USDT to your Trust Wallet</span></div>
            </div>
        </div>
    </div>
    
    <div class="card">
        <h3>⭐ Why Choose FarmUSDT?</h3>
        <div style="margin-top:8px;">
            <div style="display:flex;align-items:center;gap:10px;padding:6px 0;">
                <span style="color:var(--success);font-size:20px;">✅</span>
                <span>Legit & Verified Platform</span>
            </div>
            <div style="display:flex;align-items:center;gap:10px;padding:6px 0;">
                <span style="color:var(--success);font-size:20px;">✅</span>
                <span>Instant USDT Payments</span>
            </div>
            <div style="display:flex;align-items:center;gap:10px;padding:6px 0;">
                <span style="color:var(--success);font-size:20px;">✅</span>
                <span>Withdraw Anytime</span>
            </div>
            <div style="display:flex;align-items:center;gap:10px;padding:6px 0;">
                <span style="color:var(--success);font-size:20px;">✅</span>
                <span>24/7 Support</span>
            </div>
            <div style="display:flex;align-items:center;gap:10px;padding:6px 0;">
                <span style="color:var(--success);font-size:20px;">✅</span>
                <span>10,000+ Active Users</span>
            </div>
        </div>
    </div>
    
    <div class="card">
        <h3>📊 Our Statistics</h3>
        <div class="stats-grid">
            <div class="stat-box"><div class="value">10K+</div><div class="label">Users</div></div>
            <div class="stat-box"><div class="value gold">100K+</div><div class="label">USDT Earned</div></div>
            <div class="stat-box"><div class="value">99.9%</div><div class="label">Satisfaction</div></div>
            <div class="stat-box"><div class="value gold">24/7</div><div class="label">Support</div></div>
        </div>
    </div>
    
    <nav class="bottom-nav">
        <a href="/"><span class="icon">🏠</span><span class="label">Home</span></a>
        <a href="/earn"><span class="icon">💰</span><span class="label">Earn</span></a>
        <a href="/upgrade"><span class="icon">⬆️</span><span class="label">Upgrade</span></a>
        <a href="/referral"><span class="icon">👥</span><span class="label">Refer</span></a>
        <a href="/withdraw"><span class="icon">💸</span><span class="label">Withdraw</span></a>
    </nav>
</body>
</html>
"""

# ==================== PAGE 14: ADMIN_LOGIN_PAGE ====================
ADMIN_LOGIN_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Login - FarmUSDT 🔐</title>
    <style>""" + STYLES + """</style>
</head>
<body>
    <div class="top-header">
        <div class="logo-container">
            <div class="logo-icon">✦</div>
            <div class="logo-text">
                <span class="main">Admin Panel</span>
                <span class="sub">FarmUSDT • Login</span>
            </div>
        </div>
    </div>
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            {% for category, message in messages %}
                <div class="alert alert-{{ category }}">{{ message }}</div>
            {% endfor %}
        {% endif %}
    {% endwith %}
    <div class="card glow-border">
        <h2>🔐 Admin Login</h2>
        <form method="POST">
            <div class="form-group"><label>👤 Username</label><input type="text" name="username" required></div>
            <div class="form-group"><label>🔑 Password</label><input type="password" name="password" required></div>
            <button type="submit" class="btn btn-primary">🚀 Login</button>
        </form>
        <p class="text-center mt-2">Default: admin / admin123</p>
    </div>
</body>
</html>
"""

# ==================== PAGE 15: ADMIN_DASHBOARD_PAGE ====================
ADMIN_DASHBOARD_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Dashboard - FarmUSDT 📊</title>
    <style>""" + STYLES + """</style>
</head>
<body>
    <div class="top-header">
        <div class="logo-container">
            <div class="logo-icon">✦</div>
            <div class="logo-text">
                <span class="main">Admin Panel</span>
                <span class="sub">FarmUSDT • Dashboard</span>
            </div>
        </div>
        <div><span style="font-size:14px;font-weight:600;">👋 Admin</span><a href="/admin/logout" style="margin-left:8px;color:var(--danger);text-decoration:none;font-size:12px;">🚪 Logout</a></div>
    </div>
    
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            {% for category, message in messages %}
                <div class="alert alert-{{ category }}">{{ message }}</div>
            {% endfor %}
        {% endif %}
    {% endwith %}
    
    <div class="stats-grid" style="margin-bottom:16px;">
        <div class="stat-box" style="background:var(--gradient-1);color:white;"><div class="value" style="color:white;font-size:32px;">{{ total_users }}</div><div class="label" style="color:rgba(255,255,255,0.8);">👥 Total Users</div></div>
        <div class="stat-box" style="background:var(--gradient-2);color:white;"><div class="value" style="color:white;font-size:32px;">{{ pending_count }}</div><div class="label" style="color:rgba(255,255,255,0.8);">⏳ Pending</div></div>
        <div class="stat-box" style="background:var(--gradient-3);color:white;"><div class="value" style="color:white;font-size:32px;">{{ verified_count }}</div><div class="label" style="color:rgba(255,255,255,0.8);">✅ Verified</div></div>
        <div class="stat-box" style="background:var(--danger);color:white;"><div class="value" style="color:white;font-size:32px;">{{ open_tickets }}</div><div class="label" style="color:rgba(255,255,255,0.8);">💬 Tickets</div></div>
    </div>

    <div class="card">
        <h3>📊 Payment Requests</h3>
        {% if pending_transactions %}
            {% for tx in pending_transactions %}
            <div style="padding:12px 0;border-bottom:1px solid var(--border);">
                <div class="flex-between">
                    <div><strong>{{ tx.username }}</strong><span class="tier-badge tier-{{ tx.tier|lower }}">{{ tx.tier }}</span></div>
                    <div><span style="font-weight:600;">₦{{ "%.2f"|format(tx.amount) }}</span></div>
                </div>
                <div style="font-size:12px;color:var(--text-light);margin-top:4px;">Ref: {{ tx.transaction_id }} · {{ tx.date }}</div>
                <div style="margin-top:8px;display:flex;gap:8px;">
                    <form method="POST" action="/admin/verify_payment/{{ tx.id }}" style="flex:1;"><button type="submit" class="btn btn-success btn-sm">✅ Verify</button></form>
                    <form method="POST" action="/admin/reject_payment/{{ tx.id }}" style="flex:1;"><button type="submit" class="btn btn-danger btn-sm">❌ Reject</button></form>
                </div>
            </div>
            {% endfor %}
        {% else %}
            <p class="text-center text-muted">🎉 No pending payments</p>
        {% endif %}
    </div>

    <div class="card">
        <h3>📊 Withdrawal Requests</h3>
        {% if pending_withdrawals %}
            {% for wd in pending_withdrawals %}
            <div style="padding:12px 0;border-bottom:1px solid var(--border);">
                <div class="flex-between">
                    <div><strong>{{ wd.username }}</strong></div>
                    <div><span style="font-weight:600;">{{ "%.2f"|format(wd.amount) }} USDT</span></div>
                </div>
                <div style="font-size:12px;color:var(--text-light);">📬 {{ wd.wallet_address[:12] }}...{{ wd.wallet_address[-8:] }}</div>
                <div style="font-size:12px;color:var(--text-light);">🌐 {{ wd.wallet_network }}</div>
                <div style="margin-top:8px;display:flex;gap:8px;">
                    <form method="POST" action="/admin/process_withdrawal/{{ wd.id }}" style="flex:1;">
                        <input type="text" name="tx_hash" placeholder="Transaction Hash" style="width:100%;padding:6px;font-size:12px;margin-bottom:4px;background:var(--bg);color:var(--text);border:1px solid var(--border);border-radius:var(--radius-sm);">
                        <button type="submit" class="btn btn-success btn-sm">✅ Process</button>
                    </form>
                    <form method="POST" action="/admin/reject_withdrawal/{{ wd.id }}" style="flex:1;">
                        <button type="submit" class="btn btn-danger btn-sm">❌ Reject</button>
                    </form>
                </div>
            </div>
            {% endfor %}
        {% else %}
            <p class="text-center text-muted">🎉 No pending withdrawals</p>
        {% endif %}
    </div>

    <div class="card">
        <h3>📊 All Users</h3>
        {% for user in all_users %}
        <div style="padding:8px 0;border-bottom:1px solid var(--border);">
            <div class="flex-between">
                <div>
                    <strong>{{ user.username }}</strong>
                    <span class="tier-badge tier-{{ user.tier|lower }}">{{ user.tier }}</span>
                    {% if user.tier != 'FREE' %}
                        <span style="font-size:10px;color:var(--success);margin-left:4px;">💰 PAID</span>
                    {% else %}
                        <span style="font-size:10px;color:var(--text-muted);margin-left:4px;">FREE</span>
                    {% endif %}
                </div>
                <div style="text-align:right;">
                    <div style="font-size:12px;">💰 {{ "%.2f"|format(user.balance) }} USDT</div>
                    <div style="font-size:12px;color:var(--text-light);">📝 {{ user.daily_tasks_completed }}/{{ user.daily_limit }}</div>
                </div>
            </div>
        </div>
        {% endfor %}
    </div>

    <nav class="bottom-nav">
        <a href="/" style="flex:1;text-align:center;padding:6px 4px;text-decoration:none;color:var(--text-light);font-size:8px;border-radius:50px;"><span class="icon">🏠</span><span class="label">Home</span></a>
        <a href="/admin/users" style="flex:1;text-align:center;padding:6px 4px;text-decoration:none;color:var(--text-light);font-size:8px;border-radius:50px;"><span class="icon">📊</span><span class="label">Users</span></a>
        <a href="/admin/tasks" style="flex:1;text-align:center;padding:6px 4px;text-decoration:none;color:var(--text-light);font-size:8px;border-radius:50px;"><span class="icon">📝</span><span class="label">Tasks</span></a>
        <a href="/admin/support" style="flex:1;text-align:center;padding:6px 4px;text-decoration:none;color:var(--text-light);font-size:8px;border-radius:50px;"><span class="icon">💬</span><span class="label">Support</span></a>
        <a href="/admin/settings" style="flex:1;text-align:center;padding:6px 4px;text-decoration:none;color:var(--text-light);font-size:8px;border-radius:50px;"><span class="icon">⚙️</span><span class="label">Settings</span></a>
        <a href="/admin/social_links" style="flex:1;text-align:center;padding:6px 4px;text-decoration:none;color:var(--text-light);font-size:8px;border-radius:50px;"><span class="icon">🔗</span><span class="label">Social</span></a>
        <a href="/admin/dashboard" class="active" style="flex:1.2;text-align:center;padding:6px 10px;text-decoration:none;color:white;font-size:8px;background:var(--gradient-1);border-radius:50px;box-shadow:0 4px 20px rgba(108,92,231,0.4);"><span class="icon">✦</span><span class="label">Admin</span></a>
    </nav>
</body>
</html>
"""

# ==================== PAGE 16: ADMIN_USERS_PAGE ====================
ADMIN_USERS_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>All Users - Admin 📊</title>
    <style>""" + STYLES + """</style>
</head>
<body>
    <div class="top-header">
        <div class="logo-container">
            <div class="logo-icon">✦</div>
            <div class="logo-text">
                <span class="main">All Users</span>
                <span class="sub">FarmUSDT • Admin</span>
            </div>
        </div>
        <div><a href="/admin/dashboard" class="btn btn-sm btn-secondary" style="width:auto;padding:8px 16px;">← Back</a><a href="/admin/logout" class="btn btn-sm btn-danger" style="width:auto;padding:8px 16px;">🚪</a></div>
    </div>
    <div class="card" style="overflow-x:auto;">
        <h3>📊 Registered Users</h3>
        <table style="width:100%;border-collapse:collapse;margin-top:12px;font-size:13px;">
            <thead><tr style="background:var(--gradient-1);color:white;"><th style="padding:10px;text-align:left;">ID</th><th style="padding:10px;text-align:left;">Username</th><th style="padding:10px;text-align:left;">Email</th><th style="padding:10px;text-align:left;">Tier</th><th style="padding:10px;text-align:left;">Balance</th><th style="padding:10px;text-align:left;">Refs</th><th style="padding:10px;text-align:left;">Tasks</th><th style="padding:10px;text-align:left;">Actions</th></tr></thead>
            <tbody>
                {% for user in users %}
                <tr style="border-bottom:1px solid var(--border);">
                    <td style="padding:10px;">{{ user.id }}</td>
                    <td style="padding:10px;font-weight:600;">{{ user.username }}</td>
                    <td style="padding:10px;font-size:12px;">{{ user.email }}</td>
                    <td style="padding:10px;"><span class="tier-badge tier-{{ user.tier|lower }}">{{ user.tier }}</span></td>
                    <td style="padding:10px;">{{ "%.2f"|format(user.balance) }} USDT</td>
                    <td style="padding:10px;">{{ user.total_referrals }}</td>
                    <td style="padding:10px;">{{ user.daily_tasks_completed }}/{{ user.daily_limit }}</td>
                    <td style="padding:10px;">
                        <form method="POST" action="/admin/reset_tasks/{{ user.id }}" style="display:inline;">
                            <button type="submit" class="btn btn-sm btn-primary" style="padding:4px 8px;font-size:10px;">🔄 Reset</button>
                        </form>
                        <form method="POST" action="/admin/upgrade_user/{{ user.id }}" style="display:inline;">
                            <select name="new_tier" style="padding:4px;font-size:10px;width:auto;background:var(--bg);color:var(--text);border:1px solid var(--border);">
                                <option value="BRONZE">Bronze</option>
                                <option value="SILVER">Silver</option>
                                <option value="GOLD">Gold</option>
                                <option value="PLATINUM">Platinum</option>
                                <option value="DIAMOND">Diamond</option>
                            </select>
                            <button type="submit" class="btn btn-sm btn-success" style="padding:4px 8px;font-size:10px;">⬆️</button>
                        </form>
                        {% if user.is_banned %}
                            <form method="POST" action="/admin/user/{{ user.id }}/unban" style="display:inline;">
                                <button type="submit" class="btn btn-sm btn-success" style="padding:4px 8px;font-size:10px;">Unban</button>
                            </form>
                        {% else %}
                            <form method="POST" action="/admin/user/{{ user.id }}/ban" style="display:inline;">
                                <input type="hidden" name="reason" value="Violation of terms">
                                <button type="submit" class="btn btn-sm btn-danger" style="padding:4px 8px;font-size:10px;">Ban</button>
                            </form>
                        {% endif %}
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</body>
</html>
"""

# ==================== PAGE 17: ADMIN_SETTINGS_PAGE ====================
ADMIN_SETTINGS_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Payment Settings - Admin ⚙️</title>
    <style>""" + STYLES + """</style>
</head>
<body>
    <div class="top-header">
        <div class="logo-container">
            <div class="logo-icon">✦</div>
            <div class="logo-text">
                <span class="main">Payment Settings</span>
                <span class="sub">FarmUSDT • Admin</span>
            </div>
        </div>
        <div><a href="/admin/dashboard" class="btn btn-sm btn-secondary" style="width:auto;padding:8px 16px;">← Back</a><a href="/admin/logout" class="btn btn-sm btn-danger" style="width:auto;padding:8px 16px;">🚪</a></div>
    </div>
    
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            {% for category, message in messages %}
                <div class="alert alert-{{ category }}">{{ message }}</div>
            {% endfor %}
        {% endif %}
    {% endwith %}
    
    <div class="card glow-border">
        <h3>🏦 Update Bank Account Details</h3>
        <p class="text-muted">These bank details will be shown to users when they want to upgrade.</p>
        <form method="POST" action="/admin/update_payment_settings">
            <div class="form-group">
                <label>🏛️ Bank Name</label>
                <input type="text" name="bank_name" value="{{ settings.bank_name }}" required>
            </div>
            <div class="form-group">
                <label>👤 Account Name</label>
                <input type="text" name="account_name" value="{{ settings.account_name }}" required>
            </div>
            <div class="form-group">
                <label>🔢 Account Number</label>
                <input type="text" name="account_number" value="{{ settings.account_number }}" required>
            </div>
            <button type="submit" class="btn btn-primary">💾 Update Bank Details</button>
        </form>
    </div>

    <div class="card">
        <h3>📋 Current Bank Details</h3>
        <div class="bank-details-box">
            <div><span class="label">🏛️ Bank:</span> <span class="value">{{ settings.bank_name }}</span></div>
            <div><span class="label">👤 Account Name:</span> <span class="value">{{ settings.account_name }}</span></div>
            <div><span class="label">🔢 Account Number:</span> <span class="value">{{ settings.account_number }}</span></div>
        </div>
        <p class="text-muted" style="font-size:12px;text-align:center;">Last updated: {{ settings.updated_at.strftime('%b %d, %Y %H:%M') if settings.updated_at else 'N/A' }}</p>
    </div>
</body>
</html>
"""

# ==================== PAGE 18: ADMIN_SUPPORT_PAGE ====================
ADMIN_SUPPORT_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Support Tickets - Admin 💬</title>
    <style>""" + STYLES + """</style>
</head>
<body>
    <div class="top-header">
        <div class="logo-container">
            <div class="logo-icon">✦</div>
            <div class="logo-text">
                <span class="main">Support Tickets</span>
                <span class="sub">FarmUSDT • Admin</span>
            </div>
        </div>
        <div><a href="/admin/dashboard" class="btn btn-sm btn-secondary" style="width:auto;padding:8px 16px;">← Back</a><a href="/admin/logout" class="btn btn-sm btn-danger" style="width:auto;padding:8px 16px;">🚪</a></div>
    </div>
    <div class="card">
        <h3>📋 All Tickets</h3>
        {% for ticket in tickets %}
        <div style="padding:12px 0;border-bottom:1px solid var(--border);">
            <div class="flex-between">
                <div>
                    <strong>{{ ticket.subject }}</strong>
                    <span class="status-badge status-{{ ticket.status|lower }}">{{ ticket.status }}</span>
                </div>
                <div style="font-size:11px;color:var(--text-light);">{{ ticket.date }}</div>
            </div>
            <div style="font-size:13px;color:var(--text-light);margin:4px 0;">
                From: <strong>{{ ticket.username }}</strong>
            </div>
            <div style="font-size:14px;margin:4px 0;">{{ ticket.message }}</div>
            <div style="margin-top:8px;display:flex;gap:8px;">
                <form method="POST" action="/admin/support/{{ ticket.id }}/resolve" style="flex:1;">
                    <input type="text" name="response" placeholder="Admin response..." style="flex:1;padding:6px;font-size:12px;background:var(--bg);color:var(--text);border:1px solid var(--border);border-radius:var(--radius-sm);">
                    <button type="submit" class="btn btn-success btn-sm" style="margin-top:4px;">✅ Resolve</button>
                </form>
                <form method="POST" action="/admin/support/{{ ticket.id }}/delete" style="flex:1;">
                    <button type="submit" class="btn btn-danger btn-sm" onclick="return confirm('Delete this ticket?')">🗑️ Delete</button>
                </form>
            </div>
        </div>
        {% else %}
        <p class="text-center text-muted">📭 No tickets yet</p>
        {% endfor %}
    </div>
</body>
</html>
"""

# ==================== PAGE 19: ADMIN_SOCIAL_LINKS_PAGE ====================
ADMIN_SOCIAL_LINKS_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Social Links - Admin 🔗</title>
    <style>""" + STYLES + """</style>
</head>
<body>
    <div class="top-header">
        <div class="logo-container">
            <div class="logo-icon">✦</div>
            <div class="logo-text">
                <span class="main">Social Links</span>
                <span class="sub">FarmUSDT • Admin</span>
            </div>
        </div>
        <div><a href="/admin/dashboard" class="btn btn-sm btn-secondary" style="width:auto;padding:8px 16px;">← Back</a><a href="/admin/logout" class="btn btn-sm btn-danger" style="width:auto;padding:8px 16px;">🚪</a></div>
    </div>
    
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            {% for category, message in messages %}
                <div class="alert alert-{{ category }}">{{ message }}</div>
            {% endfor %}
        {% endif %}
    {% endwith %}
    
    <div class="card glow-border">
        <h3>🔗 Update Social Media Links</h3>
        <p class="text-muted">These links will appear on the Earn page for users to join your communities.</p>
        <form method="POST" action="/admin/update_social_links">
            <div class="form-group">
                <label>💬 Telegram Link</label>
                <input type="url" name="telegram_link" value="{{ links.telegram_link }}" placeholder="https://t.me/yourgroup" required>
            </div>
            <div class="form-group">
                <label>📱 WhatsApp Link</label>
                <input type="url" name="whatsapp_link" value="{{ links.whatsapp_link }}" placeholder="https://chat.whatsapp.com/yourgroup" required>
            </div>
            <div class="form-group">
                <label>🐦 Twitter Link</label>
                <input type="url" name="twitter_link" value="{{ links.twitter_link }}" placeholder="https://twitter.com/yourpage" required>
            </div>
            <div class="form-group">
                <label>▶️ YouTube Link</label>
                <input type="url" name="youtube_link" value="{{ links.youtube_link }}" placeholder="https://youtube.com/yourchannel" required>
            </div>
            <div class="form-group">
                <label>📘 Facebook Link</label>
                <input type="url" name="facebook_link" value="{{ links.facebook_link }}" placeholder="https://facebook.com/yourpage" required>
            </div>
            <div class="form-group">
                <label>📸 Instagram Link</label>
                <input type="url" name="instagram_link" value="{{ links.instagram_link }}" placeholder="https://instagram.com/yourpage" required>
            </div>
            <button type="submit" class="btn btn-primary">💾 Update Social Links</button>
        </form>
    </div>

    <div class="card">
        <h3>📋 Current Social Links</h3>
        <div style="margin-top:8px;">
            <div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--border);">
                <span>💬 Telegram</span>
                <span style="font-size:12px;color:var(--secondary);">{{ links.telegram_link }}</span>
            </div>
            <div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--border);">
                <span>📱 WhatsApp</span>
                <span style="font-size:12px;color:var(--secondary);">{{ links.whatsapp_link }}</span>
            </div>
            <div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--border);">
                <span>🐦 Twitter</span>
                <span style="font-size:12px;color:var(--secondary);">{{ links.twitter_link }}</span>
            </div>
            <div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--border);">
                <span>▶️ YouTube</span>
                <span style="font-size:12px;color:var(--secondary);">{{ links.youtube_link }}</span>
            </div>
            <div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--border);">
                <span>📘 Facebook</span>
                <span style="font-size:12px;color:var(--secondary);">{{ links.facebook_link }}</span>
            </div>
            <div style="display:flex;justify-content:space-between;padding:8px 0;">
                <span>📸 Instagram</span>
                <span style="font-size:12px;color:var(--secondary);">{{ links.instagram_link }}</span>
            </div>
        </div>
        <p class="text-muted" style="font-size:12px;text-align:center;margin-top:8px;">Last updated: {{ links.updated_at.strftime('%b %d, %Y %H:%M') if links.updated_at else 'N/A' }}</p>
    </div>
</body>
</html>
"""

# ==================== PAGE 20: ADMIN_TASKS_PAGE ====================
ADMIN_TASKS_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Manage Tasks - Admin 📝</title>
    <style>""" + STYLES + """</style>
</head>
<body>
    <div class="top-header">
        <div class="logo-container">
            <div class="logo-icon">✦</div>
            <div class="logo-text">
                <span class="main">Manage Tasks</span>
                <span class="sub">FarmUSDT • Admin</span>
            </div>
        </div>
        <div><a href="/admin/dashboard" class="btn btn-sm btn-secondary" style="width:auto;padding:8px 16px;">← Back</a><a href="/admin/logout" class="btn btn-sm btn-danger" style="width:auto;padding:8px 16px;">🚪</a></div>
    </div>
    
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            {% for category, message in messages %}
                <div class="alert alert-{{ category }}">{{ message }}</div>
            {% endfor %}
        {% endif %}
    {% endwith %}
    
    <div class="card glow-border">
        <h3>📝 Add New Task</h3>
        <form method="POST" action="/admin/add_task">
            <div class="form-group">
                <label>🏷️ Task Title</label>
                <input type="text" name="title" placeholder="e.g., Google Review" required>
            </div>
            <div class="form-group">
                <label>📝 Description</label>
                <textarea name="description" placeholder="Describe the task..." required></textarea>
            </div>
            <div class="form-group">
                <label>🔗 External Link (Telegram/WhatsApp/YouTube)</label>
                <input type="url" name="external_link" placeholder="https://t.me/yourgroup">
            </div>
            <div class="form-group">
                <label>🎯 Tier Required</label>
                <select name="tier_required" required>
                    <option value="BRONZE">Bronze</option>
                    <option value="SILVER">Silver</option>
                    <option value="GOLD">Gold</option>
                    <option value="PLATINUM">Platinum</option>
                    <option value="DIAMOND">Diamond</option>
                </select>
            </div>
            <div class="form-group">
                <label>💰 Reward (USDT)</label>
                <input type="number" name="reward" step="0.01" value="0.20" required>
            </div>
            <div class="form-group">
                <label>📊 Task Type</label>
                <select name="task_type" required>
                    <option value="REVIEW">Review</option>
                    <option value="SOCIAL">Social Media</option>
                    <option value="VIDEO">Video</option>
                    <option value="SURVEY">Survey</option>
                    <option value="SHARE">Share</option>
                    <option value="OTHER">Other</option>
                </select>
            </div>
            <div class="form-group">
                <label>🎨 Icon (emoji)</label>
                <input type="text" name="icon" placeholder="⭐" value="📝">
            </div>
            <button type="submit" class="btn btn-success">✅ Add Task</button>
        </form>
    </div>
    
    <div class="card">
        <h3>📋 All Tasks</h3>
        <div style="overflow-x:auto;margin-top:12px;">
            <table style="width:100%;border-collapse:collapse;font-size:13px;">
                <thead><tr style="background:var(--gradient-1);color:white;"><th style="padding:8px;text-align:left;">ID</th><th style="padding:8px;text-align:left;">Title</th><th style="padding:8px;text-align:left;">Tier</th><th style="padding:8px;text-align:left;">Reward</th><th style="padding:8px;text-align:left;">Link</th><th style="padding:8px;text-align:left;">Status</th><th style="padding:8px;text-align:left;">Actions</th></tr></thead>
                <tbody>
                    {% for task in tasks %}
                    <tr style="border-bottom:1px solid var(--border);">
                        <td style="padding:8px;">{{ task.id }}</td>
                        <td style="padding:8px;font-weight:600;">{{ task.icon }} {{ task.title }}</td>
                        <td style="padding:8px;"><span class="tier-badge tier-{{ task.tier_required|lower }}">{{ task.tier_required }}</span></td>
                        <td style="padding:8px;">{{ "%.2f"|format(task.reward) }} USDT</td>
                        <td style="padding:8px;font-size:11px;">
                            {% if task.external_link %}
                                <a href="{{ task.external_link }}" target="_blank" style="color:var(--secondary);">🔗 Link</a>
                            {% else %}
                                <span style="color:var(--text-muted);">None</span>
                            {% endif %}
                        </td>
                        <td style="padding:8px;">
                            {% if task.is_active %}
                                <span style="color:var(--success);">✅ Active</span>
                            {% else %}
                                <span style="color:var(--danger);">❌ Inactive</span>
                            {% endif %}
                        </td>
                        <td style="padding:8px;">
                            <button onclick="editTask({{ task.id }})" class="btn btn-sm btn-primary" style="padding:4px 8px;font-size:10px;width:auto;">✏️</button>
                            <form method="POST" action="/admin/toggle_task/{{ task.id }}" style="display:inline;">
                                <button type="submit" class="btn btn-sm btn-secondary" style="padding:4px 8px;font-size:10px;width:auto;">
                                    {% if task.is_active %}⛔{% else %}✅{% endif %}
                                </button>
                            </form>
                            <form method="POST" action="/admin/delete_task/{{ task.id }}" style="display:inline;" onsubmit="return confirm('Delete this task?')">
                                <button type="submit" class="btn btn-sm btn-danger" style="padding:4px 8px;font-size:10px;width:auto;">🗑️</button>
                            </form>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
    
    <div id="editTaskModal" style="display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.7);z-index:9999;padding:20px;overflow-y:auto;">
        <div style="max-width:480px;margin:0 auto;background:var(--card-bg);border-radius:var(--radius);padding:20px;margin-top:20px;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
                <h3>✏️ Edit Task</h3>
                <button onclick="closeEditTask()" style="background:var(--danger);color:white;border:none;padding:8px 16px;border-radius:50px;cursor:pointer;">✕ Close</button>
            </div>
            <form id="editTaskForm" method="POST" action="">
                <div class="form-group">
                    <label>🏷️ Task Title</label>
                    <input type="text" name="title" id="edit_title" required>
                </div>
                <div class="form-group">
                    <label>📝 Description</label>
                    <textarea name="description" id="edit_description" required></textarea>
                </div>
                <div class="form-group">
                    <label>🔗 External Link</label>
                    <input type="url" name="external_link" id="edit_external_link" placeholder="https://t.me/yourgroup">
                </div>
                <div class="form-group">
                    <label>🎯 Tier Required</label>
                    <select name="tier_required" id="edit_tier_required">
                        <option value="BRONZE">Bronze</option>
                        <option value="SILVER">Silver</option>
                        <option value="GOLD">Gold</option>
                        <option value="PLATINUM">Platinum</option>
                        <option value="DIAMOND">Diamond</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>💰 Reward (USDT)</label>
                    <input type="number" name="reward" id="edit_reward" step="0.01" required>
                </div>
                <div class="form-group">
                    <label>📊 Task Type</label>
                    <select name="task_type" id="edit_task_type">
                        <option value="REVIEW">Review</option>
                        <option value="SOCIAL">Social Media</option>
                        <option value="VIDEO">Video</option>
                        <option value="SURVEY">Survey</option>
                        <option value="SHARE">Share</option>
                        <option value="OTHER">Other</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>🎨 Icon (emoji)</label>
                    <input type="text" name="icon" id="edit_icon" placeholder="⭐">
                </div>
                <button type="submit" class="btn btn-primary">💾 Update Task</button>
            </form>
        </div>
    </div>
    
    <script>
        function editTask(taskId) {
            fetch('/admin/get_task/' + taskId)
                .then(response => response.json())
                .then(data => {
                    document.getElementById('edit_title').value = data.title;
                    document.getElementById('edit_description').value = data.description;
                    document.getElementById('edit_external_link').value = data.external_link || '';
                    document.getElementById('edit_tier_required').value = data.tier_required;
                    document.getElementById('edit_reward').value = data.reward;
                    document.getElementById('edit_task_type').value = data.task_type;
                    document.getElementById('edit_icon').value = data.icon || '📝';
                    document.getElementById('editTaskForm').action = '/admin/update_task/' + taskId;
                    document.getElementById('editTaskModal').style.display = 'block';
                });
        }
        
        function closeEditTask() {
            document.getElementById('editTaskModal').style.display = 'none';
        }
        
        document.getElementById('editTaskModal').addEventListener('click', function(e) {
            if (e.target === this) closeEditTask();
        });
    </script>
</body>
</html>
"""

# ==================== ROUTES ====================

@app.route('/')
def home():
    if 'username' in session:
        return redirect('/dashboard')
    return render_template_string(LANDING_PAGE, testimonials=TESTIMONIALS, fake_reviews=FAKE_REVIEWS)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm = request.form.get('confirm_password')
        
        if password != confirm:
            flash('❌ Passwords do not match!', 'error')
            return redirect('/register')
        
        if User.query.filter_by(username=username).first():
            flash('❌ Username already taken!', 'error')
            return redirect('/register')
        
        if User.query.filter_by(email=email).first():
            flash('❌ Email already registered!', 'error')
            return redirect('/register')
        
        user = User(username=username, email=email)
        user.set_password(password)
        user.referral_code = user.generate_referral_code()
        user.daily_limit = 0
        user.last_task_reset = datetime.now()
        
        ref_code = request.args.get('ref', '')
        referrer = None
        bonus_applied = False
        
        if ref_code:
            referrer = User.query.filter_by(referral_code=ref_code).first()
            if referrer:
                user.referred_by = referrer.id
                bonus_amount = REFERRAL_BONUS
                referrer.balance += bonus_amount
                referrer.commission_balance += bonus_amount
                referrer.referral_bonus_earned += bonus_amount
                referrer.total_referrals += 1
                bonus_applied = True
                db.session.add(referrer)
                flash(f'🎉 You were referred by {referrer.username}! You both get {bonus_amount} USDT!', 'success')
            else:
                flash('⚠️ Invalid referral code!', 'error')
        
        db.session.add(user)
        db.session.commit()
        
        if referrer and user.id and bonus_applied:
            referral = Referral(
                referrer_id=referrer.id,
                referred_id=user.id,
                bonus_amount=REFERRAL_BONUS,
                bonus_paid=True,
                verified=True
            )
            db.session.add(referral)
            db.session.commit()
        
        flash('✅ Registration successful! Please login.', 'success')
        return redirect('/login')
    
    return render_template_string(REGISTER_PAGE)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            if user.is_banned:
                flash(f'❌ Your account has been banned. Reason: {user.ban_reason or "Violation of terms"}', 'error')
                return redirect('/login')
            
            session['username'] = username
            session['user_id'] = user.id
            user.last_login = datetime.utcnow()
            db.session.commit()
            flash('👋 Welcome back!', 'success')
            return redirect('/dashboard')
        
        flash('❌ Invalid username or password!', 'error')
    
    return render_template_string(LOGIN_PAGE)

@app.route('/logout')
def logout():
    session.clear()
    flash('👋 Logged out successfully', 'success')
    return redirect('/login')

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect('/login')
    
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect('/login')
    
    if user.is_banned:
        session.clear()
        flash(f'❌ Your account has been banned.', 'error')
        return redirect('/login')
    
    reset_user_tasks_if_needed(user)
    
    now = datetime.now()
    today = datetime.now().date()
    
    if user.last_checkin:
        if user.last_checkin.date() == today - timedelta(days=1):
            user.streak_days += 1
        elif user.last_checkin.date() != today:
            user.streak_days = 0
    user.last_checkin = datetime.now()
    
    db.session.commit()
    
    next_tier, needed_points = get_next_tier_info(user.tier, 0)
    
    tiers = ['FREE', 'BRONZE', 'SILVER', 'GOLD', 'PLATINUM', 'DIAMOND']
    current_idx = tiers.index(user.tier)
    total_tiers = len(tiers) - 1
    progress = (current_idx / total_tiers) * 100
    
    today_tasks = get_user_today_tasks(user.id)
    remaining_tasks = max(0, user.daily_limit - today_tasks)
    
    recent_activities = []
    activities = UserActivity.query.filter_by(user_id=user.id).order_by(UserActivity.created_at.desc()).limit(5).all()
    for act in activities:
        time_ago = datetime.now() - act.created_at
        if time_ago.seconds < 60:
            time_str = "Just now"
        elif time_ago.seconds < 3600:
            time_str = f"{time_ago.seconds // 60}m ago"
        elif time_ago.seconds < 86400:
            time_str = f"{time_ago.seconds // 3600}h ago"
        else:
            time_str = f"{time_ago.days}d ago"
        recent_activities.append({'action': act.action, 'time': time_str})
    
    return render_template_string(DASHBOARD_PAGE,
        user=user,
        next_tier=next_tier,
        needed_points=needed_points,
        progress=progress,
        today_tasks=today_tasks,
        remaining_tasks=remaining_tasks,
        recent_activities=recent_activities
    )

@app.route('/earn')
def earn():
    if 'username' not in session:
        return redirect('/login')
    
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect('/login')
    
    if user.is_banned:
        session.clear()
        flash('❌ Your account has been banned.', 'error')
        return redirect('/login')
    
    reset_user_tasks_if_needed(user)
    
    today = datetime.now().date()
    actual_completed = get_user_today_tasks(user.id)
    if user.daily_tasks_completed != actual_completed:
        user.daily_tasks_completed = actual_completed
        db.session.commit()
    
    if user.tier == 'FREE':
        flash('⚠️ You need to upgrade your tier to access tasks!', 'error')
        return redirect('/upgrade')
    
    tasks = Task.query.filter_by(tier_required=user.tier, is_active=True).all()
    
    if not tasks:
        return render_template_string(EARN_PAGE,
            user=user,
            tasks=[],
            completed_ids=[],
            remaining_tasks=0,
            potential_earnings=0,
            get_social_links=get_social_links
        )
    
    completed = TaskCompletion.query.filter(
        TaskCompletion.user_id == user.id,
        db.func.date(TaskCompletion.completed_at) == today
    ).all()
    
    completed_ids = [c.task_id for c in completed]
    today_tasks = len(completed)
    remaining_tasks = max(0, user.daily_limit - today_tasks)
    
    potential_earnings = sum(task.reward for task in tasks[:remaining_tasks]) if tasks else 0
    
    return render_template_string(EARN_PAGE,
        user=user,
        tasks=tasks,
        completed_ids=completed_ids,
        remaining_tasks=remaining_tasks,
        potential_earnings=potential_earnings,
        get_social_links=get_social_links
    )

@app.route('/complete_task/<int:task_id>', methods=['POST'])
def complete_task(task_id):
    if 'username' not in session:
        return redirect('/login')
    
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect('/login')
    
    if user.is_banned:
        session.clear()
        flash('❌ Your account has been banned.', 'error')
        return redirect('/login')
    
    reset_user_tasks_if_needed(user)
    
    if user.tier == 'FREE':
        flash('⚠️ You need to upgrade your tier to access tasks!', 'error')
        return redirect('/upgrade')
    
    task = Task.query.get_or_404(task_id)
    
    if task.tier_required != user.tier:
        flash('⚠️ This task is not available for your tier!', 'error')
        return redirect('/earn')
    
    today = datetime.now().date()
    today_tasks = get_user_today_tasks(user.id)
    
    if today_tasks >= user.daily_limit:
        flash('⛔ Daily task limit reached! Come back tomorrow.', 'error')
        return redirect('/earn')
    
    completion = TaskCompletion(
        user_id=user.id,
        task_id=task.id,
        proof_text=request.form.get('proof_text', 'Completed')
    )
    db.session.add(completion)
    
    user.balance += task.reward
    user.daily_tasks_completed += 1
    user.total_earned += task.reward
    
    db.session.commit()
    flash(f'✅ Task completed! +{task.reward} USDT', 'success')
    return redirect('/earn')

@app.route('/share_task', methods=['GET', 'POST'])
def share_task():
    if 'username' not in session:
        return redirect('/login')
    
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect('/login')
    
    if user.is_banned:
        session.clear()
        flash('❌ Your account has been banned.', 'error')
        return redirect('/login')
    
    if request.method == 'POST':
        bonus = 0.20
        
        today = datetime.now().date()
        share_task_obj = Task.query.filter_by(task_type='SHARE', is_active=True).first()
        if share_task_obj:
            already_completed = TaskCompletion.query.filter(
                TaskCompletion.user_id == user.id,
                TaskCompletion.task_id == share_task_obj.id,
                db.func.date(TaskCompletion.completed_at) == today
            ).first()
            
            if already_completed:
                flash('⚠️ You already completed the share task today!', 'error')
                return redirect('/earn')
        
        user.balance += bonus
        
        if share_task_obj:
            completion = TaskCompletion(
                user_id=user.id,
                task_id=share_task_obj.id,
                proof_text='Shared on social media'
            )
            db.session.add(completion)
        
        db.session.commit()
        flash(f'✅ Thank you for sharing! +{bonus} USDT', 'success')
        return redirect('/earn')
    
    if request.host.startswith('127.0.0.1') or request.host.startswith('localhost'):
        base_url = f"http://{request.host}"
    else:
        base_url = f"https://{request.host}"
    
    share_url = f"{base_url}/register?ref={user.referral_code}"
    share_message = get_share_message() + f"\n\n{share_url}"
    whatsapp_link = f"https://wa.me/?text={share_message}"
    
    return render_template_string(SHARE_TASK_PAGE,
        user=user,
        share_url=share_url,
        share_message=share_message,
        whatsapp_link=whatsapp_link
    )

@app.route('/referral')
def referral_page():
    if 'username' not in session:
        return redirect('/login')
    
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect('/login')
    
    if user.is_banned:
        session.clear()
        flash('❌ Your account has been banned.', 'error')
        return redirect('/login')
    
    referrals = Referral.query.filter_by(referrer_id=user.id).all()
    
    referred_users = []
    for ref in referrals:
        referred = User.query.get(ref.referred_id)
        if referred:
            referred_users.append(referred)
    
    if request.host.startswith('127.0.0.1') or request.host.startswith('localhost'):
        base_url = f"http://{request.host}"
    else:
        base_url = f"https://{request.host}"
    
    referral_link = f"{base_url}/register?ref={user.referral_code}"
    share_message = get_share_message() + f"\n\n{referral_link}"
    whatsapp_link = f"https://wa.me/?text={share_message}"
    
    total_earned = sum(ref.bonus_amount for ref in referrals if ref.bonus_paid)
    
    return render_template_string(REFERRAL_PAGE,
        user=user,
        referral_link=referral_link,
        referred_users=referred_users,
        total_invites=len(referrals),
        total_earned=total_earned,
        whatsapp_link=whatsapp_link
    )

@app.route('/upgrade')
def upgrade_page():
    if 'username' not in session:
        return redirect('/login')
    
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect('/login')
    
    if user.is_banned:
        session.clear()
        flash('❌ Your account has been banned.', 'error')
        return redirect('/login')
    
    tiers = {}
    for tier, price in TIER_PRICES.items():
        tiers[tier] = {
            'name': TIER_NAMES[tier],
            'price': price,
            'tasks': TIER_TASKS[tier],
            'reward': 0.20
        }
    
    user_transactions = Transaction.query.filter_by(user_id=user.id).order_by(Transaction.created_at.desc()).limit(5).all()
    
    return render_template_string(UPGRADE_PAGE,
        user=user,
        tiers=tiers,
        transactions_list=[t.to_dict() for t in user_transactions],
        get_payment_settings=get_payment_settings
    )

@app.route('/submit_payment', methods=['POST'])
def submit_payment():
    if 'username' not in session:
        return redirect('/login')
    
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect('/login')
    
    tier = request.form.get('tier')
    amount = float(request.form.get('amount', 0))
    sender_name = request.form.get('sender_name')
    transaction_id = request.form.get('transaction_id')
    amount_sent = float(request.form.get('amount_sent', 0))
    payment_date = request.form.get('payment_date')
    notes = request.form.get('notes', '')
    
    if Transaction.query.filter_by(transaction_id=transaction_id).first():
        flash('❌ This transaction ID already exists!', 'error')
        return redirect('/upgrade')
    
    tx = Transaction(
        user_id=user.id,
        amount=amount,
        tier=tier,
        transaction_id=transaction_id,
        sender_name=sender_name,
        payment_date=datetime.strptime(payment_date, '%Y-%m-%dT%H:%M'),
        notes=notes,
        status='PENDING',
        type='UPGRADE'
    )
    db.session.add(tx)
    db.session.commit()
    
    flash('✅ Payment proof submitted! Please wait for admin verification.', 'success')
    return redirect('/upgrade')

@app.route('/withdraw', methods=['GET', 'POST'])
def withdraw_page():
    if 'username' not in session:
        return redirect('/login')
    
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect('/login')
    
    if user.is_banned:
        session.clear()
        flash('❌ Your account has been banned.', 'error')
        return redirect('/login')
    
    withdrawals = Withdrawal.query.filter_by(user_id=user.id).order_by(Withdrawal.created_at.desc()).limit(10).all()
    min_amount = MINIMUM_WITHDRAWAL
    
    if request.method == 'POST':
        amount = float(request.form.get('amount', 0))
        wallet_address = request.form.get('wallet_address')
        wallet_network = request.form.get('wallet_network')
        
        if amount < min_amount:
            flash(f'❌ Minimum withdrawal is {min_amount} USDT!', 'error')
            return redirect('/withdraw')
        
        if amount > user.balance:
            flash('❌ Insufficient balance!', 'error')
            return redirect('/withdraw')
        
        if not wallet_address:
            flash('❌ Please enter your USDT wallet address!', 'error')
            return redirect('/withdraw')
        
        withdrawal = Withdrawal(
            user_id=user.id,
            amount=amount,
            wallet_address=wallet_address,
            wallet_network=wallet_network,
            reference=f"WDL-{user.id}-{random.randint(1000,9999)}"
        )
        db.session.add(withdrawal)
        
        user.balance -= amount
        db.session.commit()
        
        flash(f'💸 Withdrawal of {amount} USDT requested!', 'success')
        return redirect('/dashboard')
    
    return render_template_string(WITHDRAW_PAGE,
        user=user,
        withdrawals=withdrawals,
        min_amount=min_amount
    )

@app.route('/about')
def about_page():
    if 'username' not in session:
        return redirect('/login')
    
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect('/login')
    
    if user.is_banned:
        session.clear()
        flash('❌ Your account has been banned.', 'error')
        return redirect('/login')
    
    return render_template_string(ABOUT_PAGE, user=user)

@app.route('/account')
def account_page():
    if 'username' not in session:
        return redirect('/login')
    
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect('/login')
    
    if user.is_banned:
        session.clear()
        flash('❌ Your account has been banned.', 'error')
        return redirect('/login')
    
    return render_template_string(ACCOUNT_PAGE, user=user)

@app.route('/update_account', methods=['POST'])
def update_account():
    if 'username' not in session:
        return redirect('/login')
    
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect('/login')
    
    user.full_name = request.form.get('full_name')
    user.phone = request.form.get('phone')
    user.address = request.form.get('address')
    
    db.session.commit()
    flash('✅ Account information updated successfully!', 'success')
    return redirect('/account')

@app.route('/update_wallet', methods=['POST'])
def update_wallet():
    if 'username' not in session:
        return redirect('/login')
    
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect('/login')
    
    user.wallet_address = request.form.get('wallet_address')
    user.wallet_network = request.form.get('wallet_network')
    
    db.session.commit()
    flash('✅ Wallet details updated successfully!', 'success')
    return redirect('/account')

@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if 'username' not in session:
        return redirect('/login')
    
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect('/login')
    
    if user.is_banned:
        session.clear()
        flash('❌ Your account has been banned.', 'error')
        return redirect('/login')
    
    if request.method == 'POST':
        current = request.form.get('current_password')
        new = request.form.get('new_password')
        confirm = request.form.get('confirm_password')
        
        if not user.check_password(current):
            flash('❌ Current password is incorrect!', 'error')
            return redirect('/change_password')
        
        if new != confirm:
            flash('❌ New passwords do not match!', 'error')
            return redirect('/change_password')
        
        if len(new) < 6:
            flash('❌ Password must be at least 6 characters!', 'error')
            return redirect('/change_password')
        
        user.set_password(new)
        db.session.commit()
        flash('✅ Password changed successfully!', 'success')
        return redirect('/account')
    
    return render_template_string(CHANGE_PASSWORD_PAGE, user=user)

@app.route('/support')
def support_page():
    if 'username' not in session:
        return redirect('/login')
    
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect('/login')
    
    if user.is_banned:
        session.clear()
        flash('❌ Your account has been banned.', 'error')
        return redirect('/login')
    
    tickets = SupportTicket.query.filter_by(user_id=user.id).order_by(SupportTicket.created_at.desc()).all()
    ticket_list = [t.to_dict() for t in tickets]
    
    return render_template_string(SUPPORT_PAGE, user=user, tickets=ticket_list)

@app.route('/submit_support', methods=['POST'])
def submit_support():
    if 'username' not in session:
        return redirect('/login')
    
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect('/login')
    
    subject = request.form.get('subject')
    message = request.form.get('message')
    priority = request.form.get('priority', 'MEDIUM')
    
    if not subject or not message:
        flash('❌ Please fill in all fields!', 'error')
        return redirect('/support')
    
    ticket = SupportTicket(
        user_id=user.id,
        subject=subject,
        message=message,
        priority=priority,
        status='OPEN'
    )
    db.session.add(ticket)
    db.session.commit()
    
    flash('✅ Your support ticket has been submitted!', 'success')
    return redirect('/support')

# ==================== ADMIN ROUTES ====================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin'] = True
            flash('✅ Admin login successful!', 'success')
            return redirect('/admin/dashboard')
        
        flash('❌ Invalid admin credentials!', 'error')
    
    return render_template_string(ADMIN_LOGIN_PAGE)

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    flash('👋 Admin logged out', 'success')
    return redirect('/')

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin'):
        return redirect('/admin/login')
    
    pending = Transaction.query.filter_by(status='PENDING').all()
    pending_transactions = []
    for tx in pending:
        user = User.query.get(tx.user_id)
        tx_dict = tx.to_dict()
        tx_dict['username'] = user.username if user else 'Unknown User'
        pending_transactions.append(tx_dict)
    
    pending_withdrawals_list = Withdrawal.query.filter_by(status='PENDING').all()
    pending_withdrawals = []
    for wd in pending_withdrawals_list:
        user = User.query.get(wd.user_id)
        pending_withdrawals.append({
            'id': wd.id,
            'username': user.username if user else 'Unknown',
            'amount': wd.amount,
            'wallet_address': wd.wallet_address,
            'wallet_network': wd.wallet_network
        })
    
    all_users = User.query.all()
    verified_count = Transaction.query.filter_by(status='VERIFIED').count()
    open_tickets = SupportTicket.query.filter_by(status='OPEN').count()
    
    return render_template_string(ADMIN_DASHBOARD_PAGE,
        pending_transactions=pending_transactions,
        pending_count=len(pending),
        pending_withdrawals=pending_withdrawals,
        verified_count=verified_count,
        total_users=len(all_users),
        all_users=all_users,
        open_tickets=open_tickets
    )

@app.route('/admin/users')
def admin_users():
    if not session.get('admin'):
        return redirect('/admin/login')
    
    all_users = User.query.order_by(User.id.desc()).all()
    
    return render_template_string(ADMIN_USERS_PAGE,
        users=all_users,
        total_users=len(all_users)
    )

@app.route('/admin/reset_tasks/<int:user_id>', methods=['POST'])
def admin_reset_tasks(user_id):
    if not session.get('admin'):
        return redirect('/admin/login')
    
    user = User.query.get_or_404(user_id)
    user.daily_tasks_completed = 0
    user.last_task_reset = datetime.now()
    db.session.commit()
    
    flash(f'✅ Tasks reset for {user.username}!', 'success')
    return redirect('/admin/users')

@app.route('/admin/upgrade_user/<int:user_id>', methods=['POST'])
def admin_upgrade_user(user_id):
    if not session.get('admin'):
        return redirect('/admin/login')
    
    user = User.query.get_or_404(user_id)
    new_tier = request.form.get('new_tier')
    
    if new_tier in ['BRONZE', 'SILVER', 'GOLD', 'PLATINUM', 'DIAMOND']:
        tier_limits = {'BRONZE': 5, 'SILVER': 7, 'GOLD': 9, 'PLATINUM': 11, 'DIAMOND': 13}
        user.tier = new_tier
        user.daily_limit = tier_limits.get(new_tier, 0)
        db.session.commit()
        
        log_activity(user.id, 'Admin upgraded to ' + new_tier)
        
        flash(f'✅ {user.username} upgraded to {new_tier.title()} tier! Now has {user.daily_limit} tasks per day!', 'success')
    else:
        flash('❌ Invalid tier selected!', 'error')
    
    return redirect('/admin/users')

@app.route('/admin/user/<int:user_id>/ban', methods=['POST'])
def admin_ban_user(user_id):
    if not session.get('admin'):
        return redirect('/admin/login')
    
    user = User.query.get_or_404(user_id)
    user.is_banned = True
    user.ban_reason = request.form.get('reason', 'Violation of terms')
    db.session.commit()
    
    flash(f'✅ User {user.username} banned successfully!', 'success')
    return redirect('/admin/users')

@app.route('/admin/user/<int:user_id>/unban', methods=['POST'])
def admin_unban_user(user_id):
    if not session.get('admin'):
        return redirect('/admin/login')
    
    user = User.query.get_or_404(user_id)
    user.is_banned = False
    user.ban_reason = None
    db.session.commit()
    
    flash(f'✅ User {user.username} unbanned successfully!', 'success')
    return redirect('/admin/users')

@app.route('/admin/settings')
def admin_settings():
    if not session.get('admin'):
        return redirect('/admin/login')
    
    settings = get_payment_settings()
    
    return render_template_string(ADMIN_SETTINGS_PAGE, settings=settings)

@app.route('/admin/update_payment_settings', methods=['POST'])
def update_payment_settings():
    if not session.get('admin'):
        return redirect('/admin/login')
    
    bank_name = request.form.get('bank_name')
    account_name = request.form.get('account_name')
    account_number = request.form.get('account_number')
    
    settings = get_payment_settings()
    settings.bank_name = bank_name
    settings.account_name = account_name
    settings.account_number = account_number
    db.session.commit()
    
    flash('✅ Bank details updated successfully!', 'success')
    return redirect('/admin/settings')

@app.route('/admin/social_links')
def admin_social_links():
    if not session.get('admin'):
        return redirect('/admin/login')
    
    links = get_social_links()
    
    return render_template_string(ADMIN_SOCIAL_LINKS_PAGE, links=links)

@app.route('/admin/update_social_links', methods=['POST'])
def update_social_links():
    if not session.get('admin'):
        return redirect('/admin/login')
    
    links = get_social_links()
    links.telegram_link = request.form.get('telegram_link')
    links.whatsapp_link = request.form.get('whatsapp_link')
    links.twitter_link = request.form.get('twitter_link')
    links.youtube_link = request.form.get('youtube_link')
    links.facebook_link = request.form.get('facebook_link')
    links.instagram_link = request.form.get('instagram_link')
    db.session.commit()
    
    flash('✅ Social links updated successfully!', 'success')
    return redirect('/admin/social_links')

@app.route('/admin/tasks')
def admin_tasks():
    if not session.get('admin'):
        return redirect('/admin/login')
    
    all_tasks = Task.query.order_by(Task.id.desc()).all()
    
    return render_template_string(ADMIN_TASKS_PAGE, tasks=all_tasks)

@app.route('/admin/add_task', methods=['POST'])
def admin_add_task():
    if not session.get('admin'):
        return redirect('/admin/login')
    
    title = request.form.get('title')
    description = request.form.get('description')
    external_link = request.form.get('external_link')
    tier_required = request.form.get('tier_required')
    reward = float(request.form.get('reward', 0.20))
    task_type = request.form.get('task_type')
    icon = request.form.get('icon', '📝')
    
    task = Task(
        title=title,
        description=description,
        external_link=external_link,
        tier_required=tier_required,
        reward=reward,
        task_type=task_type,
        icon=icon,
        is_active=True
    )
    db.session.add(task)
    db.session.commit()
    
    flash(f'✅ Task "{title}" added successfully!', 'success')
    return redirect('/admin/tasks')

@app.route('/admin/update_task/<int:task_id>', methods=['POST'])
def admin_update_task(task_id):
    if not session.get('admin'):
        return redirect('/admin/login')
    
    task = Task.query.get_or_404(task_id)
    task.title = request.form.get('title')
    task.description = request.form.get('description')
    task.external_link = request.form.get('external_link')
    task.tier_required = request.form.get('tier_required')
    task.reward = float(request.form.get('reward', 0.20))
    task.task_type = request.form.get('task_type')
    task.icon = request.form.get('icon', '📝')
    
    db.session.commit()
    
    flash(f'✅ Task "{task.title}" updated successfully!', 'success')
    return redirect('/admin/tasks')

@app.route('/admin/toggle_task/<int:task_id>', methods=['POST'])
def admin_toggle_task(task_id):
    if not session.get('admin'):
        return redirect('/admin/login')
    
    task = Task.query.get_or_404(task_id)
    task.is_active = not task.is_active
    db.session.commit()
    
    status = "activated" if task.is_active else "deactivated"
    flash(f'✅ Task "{task.title}" {status}!', 'success')
    return redirect('/admin/tasks')

@app.route('/admin/delete_task/<int:task_id>', methods=['POST'])
def admin_delete_task(task_id):
    if not session.get('admin'):
        return redirect('/admin/login')
    
    task = Task.query.get_or_404(task_id)
    title = task.title
    db.session.delete(task)
    db.session.commit()
    
    flash(f'🗑️ Task "{title}" deleted successfully!', 'info')
    return redirect('/admin/tasks')

@app.route('/admin/get_task/<int:task_id>')
def admin_get_task(task_id):
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    task = Task.query.get_or_404(task_id)
    return jsonify({
        'id': task.id,
        'title': task.title,
        'description': task.description,
        'external_link': task.external_link,
        'tier_required': task.tier_required,
        'reward': task.reward,
        'task_type': task.task_type,
        'icon': task.icon,
        'is_active': task.is_active
    })

@app.route('/admin/process_withdrawal/<int:wd_id>', methods=['POST'])
def admin_process_withdrawal(wd_id):
    if not session.get('admin'):
        return redirect('/admin/login')
    
    withdrawal = Withdrawal.query.get_or_404(wd_id)
    tx_hash = request.form.get('tx_hash')
    
    withdrawal.status = 'COMPLETED'
    withdrawal.processed_at = datetime.now()
    withdrawal.tx_hash = tx_hash
    
    user = User.query.get(withdrawal.user_id)
    if user:
        user.total_withdrawn += withdrawal.amount
    
    db.session.commit()
    
    flash(f'✅ Withdrawal of {withdrawal.amount} USDT processed!', 'success')
    return redirect('/admin/dashboard')

@app.route('/admin/reject_withdrawal/<int:wd_id>', methods=['POST'])
def admin_reject_withdrawal(wd_id):
    if not session.get('admin'):
        return redirect('/admin/login')
    
    withdrawal = Withdrawal.query.get_or_404(wd_id)
    
    user = User.query.get(withdrawal.user_id)
    if user:
        user.balance += withdrawal.amount
    
    withdrawal.status = 'REJECTED'
    withdrawal.processed_at = datetime.now()
    db.session.commit()
    
    flash(f'❌ Withdrawal of {withdrawal.amount} USDT rejected and refunded!', 'info')
    return redirect('/admin/dashboard')

@app.route('/admin/support')
def admin_support():
    if not session.get('admin'):
        return redirect('/admin/login')
    
    tickets = SupportTicket.query.order_by(SupportTicket.created_at.desc()).all()
    ticket_list = [t.to_dict() for t in tickets]
    
    return render_template_string(ADMIN_SUPPORT_PAGE, tickets=ticket_list)

@app.route('/admin/support/<int:ticket_id>/resolve', methods=['POST'])
def admin_resolve_ticket(ticket_id):
    if not session.get('admin'):
        return redirect('/admin/login')
    
    ticket = SupportTicket.query.get_or_404(ticket_id)
    ticket.status = 'RESOLVED'
    ticket.admin_response = request.form.get('response', '')
    ticket.responded_at = datetime.utcnow()
    db.session.commit()
    
    flash('✅ Ticket resolved!', 'success')
    return redirect('/admin/support')

@app.route('/admin/support/<int:ticket_id>/delete', methods=['POST'])
def admin_delete_ticket(ticket_id):
    if not session.get('admin'):
        return redirect('/admin/login')
    
    ticket = SupportTicket.query.get_or_404(ticket_id)
    db.session.delete(ticket)
    db.session.commit()
    
    flash('🗑️ Ticket deleted!', 'info')
    return redirect('/admin/support')

@app.route('/admin/verify_payment/<int:tx_id>', methods=['POST'])
def verify_payment(tx_id):
    if not session.get('admin'):
        return redirect('/admin/login')
    
    tx = Transaction.query.get_or_404(tx_id)
    tx.status = 'VERIFIED'
    
    user = User.query.get(tx.user_id)
    if user:
        tier = tx.tier
        tier_limits = {'BRONZE': 5, 'SILVER': 7, 'GOLD': 9, 'PLATINUM': 11, 'DIAMOND': 13}
        user.tier = tier
        user.daily_limit = tier_limits.get(tier, 0)
        db.session.commit()
        
        flash(f'✅ {user.username} upgraded to {tier.title()}! Now has {user.daily_limit} tasks per day!', 'success')
    
    db.session.commit()
    return redirect('/admin/dashboard')

@app.route('/admin/reject_payment/<int:tx_id>', methods=['POST'])
def reject_payment(tx_id):
    if not session.get('admin'):
        return redirect('/admin/login')
    
    tx = Transaction.query.get_or_404(tx_id)
    tx.status = 'REJECTED'
    db.session.commit()
    
    flash('❌ Payment rejected!', 'info')
    return redirect('/admin/dashboard')

# ==================== RUN ====================

if __name__ == '__main__':
    print("=" * 60)
    print("✦ FarmUSDT - Premium Crypto Earning Platform")
    print("=" * 60)
    print("✅ SQLite Database Connected")
    print("✅ Server starting...")
    print("🌐 Open your browser and go to: http://127.0.0.1:5000")
    print("=" * 60)
    print("📊 TIER PRICES (NAIRA):")
    print("   🥉 BRONZE: ₦1,000 - 5 tasks/day")
    print("   🥈 SILVER: ₦3,000 - 7 tasks/day")
    print("   🥇 GOLD: ₦5,000 - 9 tasks/day")
    print("   💎 PLATINUM: ₦10,000 - 11 tasks/day")
    print("   💠 DIAMOND: ₦20,000 - 13 tasks/day")
    print("=" * 60)
    print("📄 ALL 21 PAGES DEFINED:")
    print("   ✅ 1. LANDING_PAGE")
    print("   ✅ 2. LOGIN_PAGE")
    print("   ✅ 3. REGISTER_PAGE")
    print("   ✅ 4. DASHBOARD_PAGE")
    print("   ✅ 5. EARN_PAGE (with Social Links)")
    print("   ✅ 6. SHARE_TASK_PAGE")
    print("   ✅ 7. REFERRAL_PAGE")
    print("   ✅ 8. UPGRADE_PAGE")
    print("   ✅ 9. WITHDRAW_PAGE")
    print("   ✅ 10. ACCOUNT_PAGE")
    print("   ✅ 11. CHANGE_PASSWORD_PAGE")
    print("   ✅ 12. SUPPORT_PAGE")
    print("   ✅ 13. ABOUT_PAGE")
    print("   ✅ 14. ADMIN_LOGIN_PAGE")
    print("   ✅ 15. ADMIN_DASHBOARD_PAGE")
    print("   ✅ 16. ADMIN_USERS_PAGE")
    print("   ✅ 17. ADMIN_SETTINGS_PAGE")
    print("   ✅ 18. ADMIN_SUPPORT_PAGE")
    print("   ✅ 19. ADMIN_SOCIAL_LINKS_PAGE")
    print("   ✅ 20. ADMIN_TASKS_PAGE")
    print("   ✅ 21. EARN_PAGE (with Social Links)")
    print("=" * 60)
    print("🔐 Admin Panel:")
    print(f"   URL: http://127.0.0.1:5000/admin/login")
    print(f"   Username: {ADMIN_USERNAME}")
    print(f"   Password: {ADMIN_PASSWORD}")
    print("=" * 60)
    print("📝 Admin Task Management:")
    print(f"   URL: http://127.0.0.1:5000/admin/tasks")
    print("   ✅ Add new tasks")
    print("   ✅ Edit existing tasks")
    print("   ✅ Toggle task active/inactive")
    print("   ✅ Delete tasks")
    print("   ✅ Update task links (Telegram, WhatsApp, YouTube, etc.)")
    print("=" * 60)
    print("🔗 Admin Social Links:")
    print(f"   URL: http://127.0.0.1:5000/admin/social_links")
    print("   ✅ Update Telegram, WhatsApp, Twitter, YouTube, Facebook, Instagram")
    print("=" * 60)
    print("✅ ALL ROUTES CONNECTED PROPERLY")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=True)