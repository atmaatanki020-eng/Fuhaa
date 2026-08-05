import telebot
import requests
import sqlite3
import time
import os
import urllib.parse
from fpdf import FPDF
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# 👇 Configuration
BOT_TOKEN = "8917941915:AAEEGwXRz0caxTwVUIP-havu5hhyiwlG5I8"
CHANNEL_USERNAME = "@Zerotrace_root" 
BOT_USERNAME = "ZeroTraceYTbot" # ⚠️ Dhyan rahe: Ye bilkul sahi hona chahiye
ADMIN_ID = 1746944997  # 👈 APNA TELEGRAM USER ID YAHAN DALEIN

# ⚙️ Settings
START_CREDITS = 1
REFERRAL_BONUS = 1   
SHORTLINK_BONUS = 2  
SEARCH_COST = 1
COOLDOWN_TIME = 5
DAILY_BONUS = 0

# 🔗 URL Shortener API (Arolinks)
SHORTENER_API_KEY = "ace7502b25fc2e46fccd077f7f246006cf422b09"
SHORTENER_BASE_URL = "https://arolinks.com/api"

MAINTENANCE_MODE = False
API_LIST = ["https://hi-teck-groop-in.vercel.app/?number={}"]

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
user_cooldowns = {}

# --- DATABASE SETUP & UPGRADES ---
def init_db():
    conn = sqlite3.connect('users.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, credits INTEGER)''')
    
    try: c.execute('ALTER TABLE users ADD COLUMN is_banned INTEGER DEFAULT 0')
    except: pass
    try: c.execute('ALTER TABLE users ADD COLUMN vip_until INTEGER DEFAULT 0')
    except: pass
    try: c.execute('ALTER TABLE users ADD COLUMN referral_count INTEGER DEFAULT 0')
    except: pass
    try: c.execute('ALTER TABLE users ADD COLUMN last_daily INTEGER DEFAULT 0')
    except: pass
    
    c.execute('''CREATE TABLE IF NOT EXISTS promo_codes (code TEXT PRIMARY KEY, reward INTEGER, max_uses INTEGER, current_uses INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS used_promos (user_id INTEGER, code TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS blacklist (number TEXT PRIMARY KEY)''')
    c.execute('''CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, query_data TEXT, timestamp INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS short_tasks (task_id TEXT PRIMARY KEY, user_id INTEGER, status TEXT)''')
    
    conn.commit()
    return conn

conn = init_db()

# --- DB HELPERS ---
def get_user_data(user_id):
    c = conn.cursor()
    c.execute("SELECT credits, is_banned, vip_until, last_daily, referral_count FROM users WHERE user_id=?", (user_id,))
    return c.fetchone()

def add_user(user_id, referrer_id=None):
    if get_user_data(user_id) is None:
        c = conn.cursor()
        c.execute("INSERT INTO users (user_id, credits, is_banned, vip_until, referral_count, last_daily) VALUES (?, ?, 0, 0, 0, 0)", (user_id, START_CREDITS))
        conn.commit()
        
        try: bot.send_message(ADMIN_ID, f"👤 <b>NEW USER:</b> <code>{user_id}</code>")
        except: pass
        
        if referrer_id and referrer_id != user_id:
            c.execute("UPDATE users SET credits = credits + ?, referral_count = referral_count + 1 WHERE user_id=?", (REFERRAL_BONUS, referrer_id))
            conn.commit()
            try: bot.send_message(referrer_id, f"🎉 <b>New Referral!</b> You received <code>{REFERRAL_BONUS}</code> credits.")
            except: pass
        return True
    return False

def update_credits(user_id, amount):
    c = conn.cursor()
    c.execute("UPDATE users SET credits = credits + ? WHERE user_id=?", (amount, user_id))
    conn.commit()

def is_vip(vip_until):
    return time.time() < vip_until

def is_subscribed(user_id):
    try:
        status = bot.get_chat_member(CHANNEL_USERNAME, user_id).status
        return status in ['member', 'administrator', 'creator']
    except: return False

def get_premium_keyboard():
    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    markup.add(InlineKeyboardButton("💸 Earn Credits", callback_data="earn_menu"))
    markup.add(
        InlineKeyboardButton("🌐 Website", url="https://zerotrace.site.je/"),
        InlineKeyboardButton("👨‍💻 Support", url="https://youtube.com/@zerotraceroot")
    )
    return markup

# --- 💸 EARN MENU & AROLINKS SYSTEM ---
@bot.message_handler(commands=['earn'])
def earn_command(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("👥 Refer & Earn (+1 Credit)", callback_data="earn_referral"))
    markup.add(InlineKeyboardButton("🔗 Shortlink Task (+2 Credits)", callback_data="earn_shortlink"))
    text = "💸 <b>EARN FREE CREDITS</b>\n━━━━━━━━━━━━━━━━━━━━\nChoose a method below to earn credits:"
    bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("earn_") or call.data == "main_menu")
def earn_system_handler(call):
    user_id = call.from_user.id
    
    if call.data == "main_menu":
        data = get_user_data(user_id)
        if not data: return
        vip_status = "🟢 VIP" if is_vip(data[2]) else "🔴 Basic"
        text = f"💎 <b>ZERO TRACE ENGINE</b> 💎\nCredits: <code>{data[0]}</code> | Status: {vip_status}\n\nSend target number to search.\nCommands: /earn, /daily, /redeem, /history, /top\nDev ➜ ZeroTrace Team"
        bot.edit_message_text(text=text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=get_premium_keyboard(), parse_mode="HTML")
        
    elif call.data == "earn_menu":
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("👥 Refer & Earn (+1 Credit)", callback_data="earn_referral"))
        markup.add(InlineKeyboardButton("🔗 Shortlink Task (+2 Credits)", callback_data="earn_shortlink"))
        markup.add(InlineKeyboardButton("🔙 Back", callback_data="main_menu"))
        text = "💸 <b>EARN FREE CREDITS</b>\n━━━━━━━━━━━━━━━━━━━━\nChoose a method below to earn credits:"
        bot.edit_message_text(text=text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup, parse_mode="HTML")
        
    elif call.data == "earn_referral":
        ref_link = f"https://t.me/{BOT_USERNAME}?start={user_id}"
        text = f"👥 <b>REFERRAL SYSTEM</b>\n━━━━━━━━━━━━━━━━━━━━\nShare your link with friends. When they join, you get <b>+{REFERRAL_BONUS} Credit</b>!\n\n🔗 Your Link: <code>{ref_link}</code>"
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="earn_menu"))
        bot.edit_message_text(text=text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup, parse_mode="HTML")
        
    elif call.data == "earn_shortlink":
        bot.answer_callback_query(call.id, "Generating Task Link...")
        
        task_id = f"T{user_id}{int(time.time())}"
        target_url = f"https://t.me/{BOT_USERNAME}?start={task_id}"
        encoded_url = urllib.parse.quote(target_url)
        
        api_params = {
            "api": SHORTENER_API_KEY,
            "url": encoded_url
        }
        
        try:
            res = requests.get(SHORTENER_BASE_URL, params=api_params, timeout=10).json()
            if res.get("status") == "success" or "shortenedUrl" in res:
                short_url = res.get("shortenedUrl")
                c = conn.cursor()
                c.execute("INSERT INTO short_tasks (task_id, user_id, status) VALUES (?, ?, 'pending')", (task_id, user_id))
                conn.commit()
                text = f"🔗 <b>SHORTLINK TASK</b>\n━━━━━━━━━━━━━━━━━━━━\n1. Click the link below\n2. Verify Captcha / Skip Ads\n3. You will be redirected back\n4. Click 'Start' to claim <b>+{SHORTLINK_BONUS} Credits</b>!\n\n👉 <b>Link:</b> {short_url}"
            else:
                text = "⚠️ Failed to generate link from Arolinks. Try again later."
        except Exception as e:
            text = "⚠️ Network Error. Try again later."
            
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="earn_menu"))
        bot.edit_message_text(text=text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup, parse_mode="HTML")

# --- 🎁 STANDARD COMMANDS (Start & Task Verification) ---
@bot.message_handler(commands=['start', 'adminhelp'])
def basic_commands(message):
    user_id = message.from_user.id
    if '/adminhelp' in message.text:
        if user_id != ADMIN_ID: return
        help_txt = (
            "👑 <b>ADMIN COMMANDS:</b>\n"
            "/addcredit, /remcredit [ID] [Amt]\n"
            "/addallcredit, /setallcredit [Amt]\n"
            "/addvip, /remvip [ID] [Days]\n"
            "/ban, /unban [ID]\n"
            "/broadcast [Msg]\n"
            "/createcode [Code] [Reward] [Max]\n"
            "/blacklist, /unblacklist [Number]\n"
            "/stats, /backup\n"
            "/maintenance [on/off]"
        )
        bot.send_message(message.chat.id, help_txt)
        return
        
    args = message.text.split()
    ref_id = None
    
    if len(args) > 1 and args[1].startswith('T') and len(args[1]) > 5:
        task_id = args[1]
        c = conn.cursor()
        c.execute("SELECT status FROM short_tasks WHERE task_id=? AND user_id=?", (task_id, user_id))
        task = c.fetchone()
        
        if task:
            if task[0] == 'pending':
                c.execute("UPDATE short_tasks SET status='completed' WHERE task_id=?", (task_id,))
                c.execute("UPDATE users SET credits = credits + ? WHERE user_id=?", (SHORTLINK_BONUS, user_id))
                conn.commit()
                bot.send_message(message.chat.id, f"🎉 <b>TASK COMPLETED!</b>\nYou successfully bypassed the link and received <b>+{SHORTLINK_BONUS} Credits</b>.")
            elif task[0] == 'completed':
                bot.send_message(message.chat.id, "⚠️ <b>You have already claimed credits for this task!</b> Generate a new one from /earn.")
        else:
            bot.send_message(message.chat.id, f"❌ <b>Invalid or Expired Task!</b>\n(System received: <code>{args[1]}</code>)\nPlease generate a new link from /earn.")
            
    elif len(args) > 1 and args[1].isdigit():
        ref_id = int(args[1])
        
    add_user(user_id, ref_id)
    
    if not is_subscribed(user_id):
        bot.send_message(message.chat.id, "⚠️ Join our channel first.", reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("📢 Join", url=f"https://t.me/{CHANNEL_USERNAME.replace('@','')}")))
        return
        
    data = get_user_data(user_id)
    vip_status = "🟢 VIP" if is_vip(data[2]) else "🔴 Basic"
    bot.send_message(message.chat.id, f"💎 <b>ZERO TRACE ENGINE</b> 💎\nCredits: <code>{data[0]}</code> | Status: {vip_status}\n\nSend target number to search.\nCommands: /earn, /daily, /redeem, /history, /top\nDev ➜ ZeroTrace Team", reply_markup=get_premium_keyboard())

# --- USER PRO FEATURES ---
@bot.message_handler(commands=['daily'])
def claim_daily(message):
    user_id = message.from_user.id
    data = get_user_data(user_id)
    if not data: return
    last_daily = data[3]
    current_time = int(time.time())
    if current_time - last_daily >= 86400:
        c = conn.cursor()
        c.execute("UPDATE users SET credits = credits + ?, last_daily = ? WHERE user_id=?", (DAILY_BONUS, current_time, user_id))
        conn.commit()
        bot.send_message(message.chat.id, f"🎁 <b>DAILY CLAIMED!</b>\nYou received <b>{DAILY_BONUS}</b> free credits.")
    else:
        left_seconds = 86400 - (current_time - last_daily)
        bot.send_message(message.chat.id, f"⏳ <b>ALREADY CLAIMED!</b>\nPlease wait {int(left_seconds//3600)}h {int((left_seconds%3600)//60)}m.")

@bot.message_handler(commands=['redeem'])
def redeem_promo(message):
    user_id = message.from_user.id
    try:
        code = message.text.split()[1].upper()
        c = conn.cursor()
        c.execute("SELECT reward, max_uses, current_uses FROM promo_codes WHERE code=?", (code,))
        promo = c.fetchone()
        if not promo: return bot.send_message(message.chat.id, "❌ Invalid Promo Code.")
        c.execute("SELECT * FROM used_promos WHERE user_id=? AND code=?", (user_id, code))
        if c.fetchone(): return bot.send_message(message.chat.id, "⚠️ Already used.")
        reward, max_uses, current_uses = promo
        if current_uses >= max_uses: return bot.send_message(message.chat.id, "❌ Code expired.")
        c.execute("INSERT INTO used_promos VALUES (?, ?)", (user_id, code))
        c.execute("UPDATE promo_codes SET current_uses = current_uses + 1 WHERE code=?", (code,))
        c.execute("UPDATE users SET credits = credits + ? WHERE user_id=?", (reward, user_id))
        conn.commit()
        bot.send_message(message.chat.id, f"🎉 <b>PROMO REDEEMED!</b> +{reward} credits.")
    except: bot.send_message(message.chat.id, "⚠️ Usage: /redeem CODE")

@bot.message_handler(commands=['history'])
def show_history(message):
    c = conn.cursor()
    c.execute("SELECT query_data, timestamp FROM history WHERE user_id=? ORDER BY timestamp DESC LIMIT 5", (message.from_user.id,))
    history = c.fetchall()
    if not history: return bot.send_message(message.chat.id, "📂 No history.")
    text = "🗂️ <b>RECENT SEARCHES</b>\n━━━━━━━━━━━━━━━━━━━━\n"
    for q, t in history:
        text += f"▪️ <code>{q}</code> (<i>{time.strftime('%Y-%m-%d %H:%M', time.localtime(t))}</i>)\n"
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=['top'])
def show_leaderboard(message):
    c = conn.cursor()
    c.execute("SELECT user_id, referral_count FROM users ORDER BY referral_count DESC LIMIT 5")
    text = "🏆 <b>TOP REFERRERS</b>\n━━━━━━━━━━━━━━━━━━━━\n"
    for idx, (uid, count) in enumerate(c.fetchall(), 1): text += f"<b>{idx}.</b> ID: <code>{uid}</code> ➜ {count} Invites\n"
    bot.send_message(message.chat.id, text)

# --- 👑 ADMIN PRO FEATURES ---
@bot.message_handler(commands=['createcode', 'blacklist', 'unblacklist', 'stats', 'backup', 'addcredit', 'remcredit', 'addallcredit', 'setallcredit', 'addvip', 'remvip', 'ban', 'unban', 'broadcast', 'maintenance'])
def admin_controls(message):
    global MAINTENANCE_MODE
    if message.from_user.id != ADMIN_ID: return
    c = conn.cursor()
    cmd = message.text.split()[0]
    args = message.text.split()
    
    try:
        if cmd == '/createcode':
            c.execute("INSERT INTO promo_codes VALUES (?, ?, ?, 0)", (args[1].upper(), int(args[2]), int(args[3])))
            bot.send_message(message.chat.id, f"✅ Promo Created: {args[1].upper()}")
        elif cmd == '/blacklist':
            c.execute("INSERT OR IGNORE INTO blacklist VALUES (?)", (args[1],))
            bot.send_message(message.chat.id, f"✅ Blacklisted {args[1]}")
        elif cmd == '/unblacklist':
            c.execute("DELETE FROM blacklist WHERE number=?", (args[1],))
            bot.send_message(message.chat.id, "✅ Unblacklisted.")
        elif cmd == '/addcredit':
            update_credits(int(args[1]), int(args[2]))
            bot.send_message(message.chat.id, f"✅ Added {args[2]} credits to {args[1]}")
        elif cmd == '/remcredit':
            update_credits(int(args[1]), -int(args[2]))
            bot.send_message(message.chat.id, f"✅ Removed {args[2]} credits from {args[1]}")
        elif cmd == '/addallcredit':
            amt = int(args[1])
            c.execute("UPDATE users SET credits = credits + ?", (amt,))
            bot.send_message(message.chat.id, f"✅ Added {amt} credits to ALL users successfully!")
        elif cmd == '/setallcredit':
            amt = int(args[1])
            c.execute("UPDATE users SET credits = ?", (amt,))
            bot.send_message(message.chat.id, f"✅ Set credits to {amt} for ALL users successfully!")
        elif cmd == '/addvip':
            vip_time = time.time() + (int(args[2]) * 86400)
            c.execute("UPDATE users SET vip_until=? WHERE user_id=?", (vip_time, int(args[1])))
            bot.send_message(message.chat.id, f"✅ VIP given to {args[1]} for {args[2]} days")
        elif cmd == '/remvip':
            c.execute("UPDATE users SET vip_until=0 WHERE user_id=?", (int(args[1]),))
            bot.send_message(message.chat.id, f"✅ VIP removed from {args[1]}")
        elif cmd == '/ban':
            c.execute("UPDATE users SET is_banned=1 WHERE user_id=?", (int(args[1]),))
            bot.send_message(message.chat.id, f"✅ Banned {args[1]}")
        elif cmd == '/unban':
            c.execute("UPDATE users SET is_banned=0 WHERE user_id=?", (int(args[1]),))
            bot.send_message(message.chat.id, f"✅ Unbanned {args[1]}")
        elif cmd == '/stats':
            c.execute("SELECT COUNT(*) FROM users")
            u_count = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM history")
            h_count = c.fetchone()[0]
            bot.send_message(message.chat.id, f"📊 <b>Stats:</b>\nUsers: {u_count}\nSearches: {h_count}")
        elif cmd == '/backup':
            bot.send_document(message.chat.id, open('users.db', 'rb'), caption="📂 Database Backup")
        elif cmd == '/maintenance':
            MAINTENANCE_MODE = (args[1].lower() == 'on')
            bot.send_message(message.chat.id, f"✅ Maintenance Mode: {'ON' if MAINTENANCE_MODE else 'OFF'}")
        elif cmd == '/broadcast':
            text = message.text.replace("/broadcast", "").strip()
            c.execute("SELECT user_id FROM users")
            users = c.fetchall()
            for (uid,) in users:
                try: bot.send_message(uid, f"📢 <b>UPDATE:</b>\n{text}")
                except: pass
            bot.send_message(message.chat.id, "✅ Broadcast Complete.")
        conn.commit()
    except Exception as e: 
        bot.send_message(message.chat.id, f"⚠️ Error in {cmd}: {str(e)}")

# --- PDF GENERATOR ---
def create_pdf(query, data_text):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt="ZERO TRACE VIP REPORT", ln=True, align='C')
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="--------------------------------------------------", ln=True, align='C')
    pdf.cell(200, 10, txt=f"TARGET NUMBER: {query}", ln=True, align='L')
    pdf.cell(200, 10, txt="--------------------------------------------------", ln=True, align='C')
    pdf.set_font("Arial", size=11)
    
    clean_data = data_text.replace("🟢", "").replace("🔴", "").replace("📂", "").replace("📊", "").replace("🔍", "")
    lines = clean_data.split("▪️")
    for line in lines:
        line = line.strip()
        if line:
            clean_line = line.replace("<b>", "").replace("</b>", "").replace("<code>", "").replace("</code>", "")
            safe_line = clean_line.encode('latin-1', 'replace').decode('latin-1')
            pdf.multi_cell(0, 10, txt=f"- {safe_line}")
            pdf.ln(2)
            
    pdf.set_y(-30)
    pdf.set_font("Arial", 'I', 8)
    pdf.cell(0, 10, "CONFIDENTIAL REPORT - GENERATED BY ZEROTRACE", 0, 0, 'C')
    filename = f"Report_{query}_{int(time.time())}.pdf"
    pdf.output(filename)
    return filename

@bot.callback_query_handler(func=lambda call: call.data.startswith("pdf_"))
def handle_pdf_download(call):
    bot.answer_callback_query(call.id, "Generating Secure PDF...")
    query = call.data.split("_")[1]
    msg_text = call.message.caption if call.message.caption else call.message.text
    try:
        data_part = msg_text.split("Extracted Data :")[1].split("━━━━━━━━━━━━━━━━━━━━")[0].strip() if "Extracted Data :" in msg_text else msg_text
        filename = create_pdf(query, data_part)
        with open(filename, 'rb') as doc:
            bot.send_document(call.message.chat.id, doc, caption=f"📄 <b>Report:</b> <code>{query}</code>")
        os.remove(filename) 
    except Exception as e:
        bot.send_message(call.message.chat.id, f"⚠️ PDF Error: <code>{str(e)[:50]}</code>")

# --- CORE SEARCH LOGIC WITH SMART DATA EXTRACTOR ---
@bot.message_handler(func=lambda message: True)
def process_query(message):
    user_id = message.from_user.id
    query_data = message.text.strip()
    
    if MAINTENANCE_MODE and user_id != ADMIN_ID:
        return bot.send_message(message.chat.id, "⚙️ System is under maintenance. Please try again later.")
    
    c = conn.cursor()
    c.execute("SELECT * FROM blacklist WHERE number=?", (query_data,))
    if c.fetchone(): return bot.send_message(message.chat.id, "⚠️ <b>ACCESS DENIED:</b> Target is protected.")

    data = get_user_data(user_id)
    if not data: 
        add_user(user_id)
        data = get_user_data(user_id)
        
    current_credits, is_banned, vip_until = data[0], data[1], data[2]
    has_vip = is_vip(vip_until)

    if is_banned: return bot.send_message(message.chat.id, "🚫 <b>YOU ARE BANNED</b>")

    if not has_vip:
        current_time = time.time()
        if user_id in user_cooldowns and (current_time - user_cooldowns[user_id]) < COOLDOWN_TIME:
            return bot.send_message(message.chat.id, f"⏳ <b>Wait {int(COOLDOWN_TIME - (current_time - user_cooldowns[user_id]))} seconds.</b>")
        user_cooldowns[user_id] = current_time 
        
        if current_credits < SEARCH_COST:
            return bot.send_message(message.chat.id, f"❌ <b>INSUFFICIENT CREDITS</b>\nUse /earn to get more credits.")

    loading_msg = bot.send_message(message.chat.id, "🔄 <i>Processing securely...</i>")
    
    extracted_data = {}
    for api_endpoint in API_LIST:
        try:
            response = requests.get(api_endpoint.format(query_data), timeout=10)
            if response.status_code == 200:
                api_data = response.json() 
                
                # 🛠️ SMART EXTRACTOR (Sirf in kachre wale words ko hide karega aur baaki sab print karega)
                ignore_keys = ['developer', 'status', 'response_time_ms', 'query', 'title']
                
                def find_keys(d):
                    if isinstance(d, dict):
                        for k, v in d.items():
                            if isinstance(v, (dict, list)):
                                find_keys(v)
                            else:
                                k_lower = str(k).lower()
                                if k_lower not in ignore_keys and not k_lower.startswith('source'):
                                    if v is not None and str(v).strip() != "":
                                        extracted_data[str(k).title()] = v
                    elif isinstance(d, list):
                        for item in d:
                            find_keys(item)
                            
                find_keys(api_data)
                break
        except: continue

    if extracted_data:
        api_status = "SUCCESS 🟢"
        result_data = "".join([f"▪️ <b>{k}</b> : <code>{v}</code>\n" for k, v in extracted_data.items()])
        
        c.execute("INSERT INTO history (user_id, query_data, timestamp) VALUES (?, ?, ?)", (user_id, query_data, int(time.time())))
        conn.commit()
        if not has_vip:
            update_credits(user_id, -SEARCH_COST)
            current_credits -= SEARCH_COST
    else:
        api_status = "FAILED 🔴"
        result_data = "<code>NO DATA FOUND</code>"

    markup = InlineKeyboardMarkup()
    if extracted_data: markup.add(InlineKeyboardButton("📥 Download PDF Report", callback_data=f"pdf_{query_data}"))
    markup.add(InlineKeyboardButton("🌐 Website", url="https://zerotrace.site.je/"))

    response_text = (
        "<b>✦ SYSTEM RESPONSE ✦</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔍 <b>Query :</b> <code>{query_data}</code>\n"
        f"📊 <b>Status :</b> <b>{api_status}</b>\n\n"
        f"📂 <b>Extracted Data :</b>\n{result_data}\n━━━━━━━━━━━━━━━━━━━━\n"
        f"💳 <b>Credits Left :</b> <code>{'Unlimited 👑' if has_vip else current_credits}</code>\n"
        "⚡️ <i>Powered by ZeroTrace Team</i>"
    )
    
    bot.delete_message(message.chat.id, loading_msg.message_id) 
    bot.send_message(message.chat.id, response_text, reply_markup=markup)

print("💎 ZeroTrace ULTIMATE PRO is running...")
bot.infinity_polling()