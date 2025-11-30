#!/usr/bin/env python3
#[790] Always Be Happy Nozani Sakurami
import os
import json
import httpx
import yt_dlp
import shutil
import requests
import asyncio
import tempfile
import feedparser
from pathlib import Path
from telegram import Update
from datetime import datetime, timedelta
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    filters
)
from gtts import gTTS
from langdetect import detect, LangDetectException

# ============ CONFIG ============
BOT_TOKEN = "8257565216:AAGZAn3KmRUfYFuzYWNyEyBEOeyeo4_pAvQ"
GEMINI_API_KEY = "AIzaSyA2vPIe8VhHuoBSbaIbIjTWooBxHZCBszo"
WEATHER_API_KEY = "a63df3434ffb45e895873111250202"
LOG_CHANNEL_ID = -1003149644391
ACTIVITY_CHANNEL_ID = -1003152237296
EXTRA_CHANNEL_ID = -1003451910926 
MODEL = "gemini-2.5-flash"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={GEMINI_API_KEY}"
PERSONALITY_FILE = "NozaniSakurami.txt"
HISTORY_FILE = "NozaniSakuramiConversation.json"
ADMIN_ID = 6343969439
ALLOWED_USERS_FILE = "allowed_users.json"
expecting_upload = {}

# ============ INITIAL FILE SETUP ============
def ensure_allowed_users_file():
    if not os.path.exists(ALLOWED_USERS_FILE):
        data = {"admin": ADMIN_ID, "allowed": [ADMIN_ID]}
        with open(ALLOWED_USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
def load_allowed_users():
    ensure_allowed_users_file()
    try:
        with open(ALLOWED_USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"admin": ADMIN_ID, "allowed": [ADMIN_ID]}
def save_allowed_users(data):
    with open(ALLOWED_USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
ensure_allowed_users_file()
allowed_users_data = load_allowed_users()

# ============ FILE SYSTEM ============
def load_personality():
    if not os.path.exists(PERSONALITY_FILE):
        return "You are a polite, friendly and helpful AI assistant."
    with open(PERSONALITY_FILE, "r", encoding="utf-8") as f:
        return f.read().strip()
def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    return []
def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
conversation_history = load_history()

# ============ LOGGING ============
async def log_message(update: Update, context: ContextTypes.DEFAULT_TYPE, reply=None):
    try:
        user = update.effective_user
        msg = ""
        if update.message:
            if update.message.text:
                msg = update.message.text
            elif update.message.caption:
                msg = update.message.caption
            else:
                msg = "Non-text message"
        else:
            msg = "Unknown"
        t = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_text = (
            "❏ Message Log \n"
            "────────────────────\n"
            f"➪ {user.first_name}\n"
            f"➪ {user.id}\n"
            f"➪ {t}\n\n"
            f"➪ User Message:\n{msg}"
        )
        if reply:
            log_text += f"\n\n➪ Bot Reply:\n{reply}"
        await context.bot.send_message(LOG_CHANNEL_ID, log_text)
    except Exception as e:
        print("Log error:", e)
async def log_activity(update: Update, context: ContextTypes.DEFAULT_TYPE, action="Message"):
    try:
        user = update.effective_user
        t = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        text = (
            "❏ Bot Activity\n"
            "────────────────────\n"
            f"➪ {user.first_name}\n"
            f"➪ {user.id}\n"
            f"➪ Action: {action}\n"
            f"➪ Time: {t}"
        )
        await context.bot.send_message(ACTIVITY_CHANNEL_ID, text)
    except Exception as e:
        print("Activity log error:", e)

# ============ PERMISSION HELPERS ============
def is_admin(user_id):
    return user_id == ADMIN_ID
def is_allowed_user_id(user_id):
    global allowed_users_data
    try:
        allowed_list = allowed_users_data.get("allowed", [])
        return user_id in allowed_list or user_id == ADMIN_ID
    except Exception:
        return user_id == ADMIN_ID
async def require_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("✖ Only the admin can use this command.")
        await log_activity(update, context, "Blocked non-admin attempt")
        return False
    return True
async def require_allowed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_admin(user.id):
        return True
    if not is_allowed_user_id(user.id):
        await update.message.reply_text("✖ You are not allowed to use this bot.")
        await log_activity(update, context, "Blocked unauthorized user")
        return False
    return True

# ============ GEMINI SYSTEM ============
def build_prompt(user_msg):
    personality = load_personality()
    history_text = ""
    for msg in conversation_history:
        history_text += f"{msg['role']}: {msg['text']}\n"
    history_text += f"User: {user_msg}\nAI:"
    return f"{personality}\n\n{history_text}"
def ask_gemini(prompt):
    data = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        r = requests.post(GEMINI_URL, json=data, headers={"Content-Type": "application/json"})
        r.raise_for_status()
        out = r.json()
        reply = out["candidates"][0]["content"]["parts"][0]["text"]
        return reply
    except Exception as e:
        try:
            return f"✖ Gemini Error:\n{r.json()}"
        except:
            return f"✖ Gemini Error:\n{e}"

# ============ /UID COMMAND ============
async def uid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_allowed(update, context):
        return
    await log_activity(update, context, "Used /UID")
    user = update.effective_user
    name = f"{user.first_name or 'Nobody'} {user.last_name or 'N/A'}"
    username = f"@{user.username}" if user.username else "N/A"
    uid = user.id
    reply = (
        "❏ USER INFORMATION\n"
        "────────────────────\n"
        f"➪ Name       : `{name}`\n"
        f"➪ Username: `{username}`\n"
        f"➪ ID              : `{uid}`"
    )
    await update.message.reply_text(reply, parse_mode="Markdown")
    await log_message(update, context, reply)

# ============ /AGE COMMAND ============
async def age_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_allowed(update, context):
        return
    await log_activity(update, context, "age")
    if not context.args:
        error_msg = "! Please provide your date of birth in YYYY-MM-DD format.\nExample: /age 2005-04-07"
        await update.message.reply_text(error_msg)
        await log_message(update, context, error_msg)
        return
    dob_str = context.args[0]
    try:
        dob = datetime.strptime(dob_str, '%Y-%m-%d')
        today = datetime.today()
        age_years = today.year - dob.year
        if (today.month, today.day) < (dob.month, dob.day):
            age_years -= 1
        delta = today - dob
        age_days = delta.days
        age_hours = age_days * 24
        age_minutes = age_hours * 60
        next_birthday = dob.replace(year=today.year)
        if next_birthday < today:
            next_birthday = next_birthday.replace(year=today.year + 1)
        days_until_next_birthday = (next_birthday - today).days
        weekday = dob.strftime('%A')
        is_today = today.month == dob.month and today.day == dob.day
        msg = (
            f"❏ Age Details\n"
            f"───────────────\n"
            f"➪ Date of Birth   : {dob.strftime('%B %d, %Y')} ({weekday})\n"
            f"➪ Current Age    : {age_years} years\n"
            f"➪ Next Birthday : {next_birthday.strftime('%Y-%m-%d')}\n"
            f"➪ Until Birthday : {days_until_next_birthday} days\n"
            f"➪ Lived Days      : {age_days} days\n"
            f"➪ Lived Hours    : {age_hours} hours\n"
            f"➪ Lived Minutes : {age_minutes} minutes\n"
        )
        if is_today:
            msg += "\n˚˖𓍢ִ໋HAPPY˚BIRTHDAY༘⋆"
        else:
            msg += f"\n➪ You will turn {age_years + 1} in {days_until_next_birthday} days."
        await update.message.reply_text(msg)
        await log_message(update, context, msg)
    except Exception:
        error_msg = "! Invalid date format. Use YYYY-MM-DD"
        await update.message.reply_text(error_msg)
        await log_message(update, context, error_msg)

# ============ TEXT-TO-SPEECH COMMAND ============
LANGUAGE_MAP = {
    'en': 'en', 'es': 'es', 'fr': 'fr', 'de': 'de', 'it': 'it', 'pt': 'pt',
    'ru': 'ru', 'ja': 'ja', 'ko': 'ko', 'zh-cn': 'zh-cn', 'zh-tw': 'zh-tw',
    'ar': 'ar', 'hi': 'hi', 'bn': 'bn', 'tr': 'tr', 'nl': 'nl', 'pl': 'pl',
    'uk': 'uk', 'el': 'el', 'he': 'he', 'th': 'th', 'vi': 'vi', 'id': 'id',
    'fa': 'fa', 'ur': 'ur',
}
LANGUAGE_NAMES = {code: code.upper() for code in LANGUAGE_MAP.keys()}
def detect_language(text):
    try:
        lang_code = detect(text)
        return LANGUAGE_MAP.get(lang_code, 'en')
    except LangDetectException:
        return 'en'
async def speak_and_send(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, lang='auto'):
    try:
        detected_lang = detect_language(text) if lang == 'auto' else LANGUAGE_MAP.get(lang, 'en')
        tts = gTTS(text=text, lang=detected_lang)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as mp3_file:
            tts.save(mp3_file.name)
        with open(mp3_file.name, "rb") as audio_file:
            await update.message.reply_audio(
                audio=audio_file,
                caption=f"⎆ Speaking ({LANGUAGE_NAMES.get(detected_lang, 'EN')})"
            )
        with open(mp3_file.name, "rb") as audio_file:
            await context.bot.send_audio(
                chat_id=LOG_CHANNEL_ID,
                audio=audio_file,
                caption=f"♅ TTS sent to user ({LANGUAGE_NAMES.get(detected_lang, 'EN')}): {text}"
            )
        os.remove(mp3_file.name)
        return detected_lang
    except Exception as e:
        await update.message.reply_text(f"! Voice error: {e}")
        return None
async def text_speak_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_allowed(update, context):
        return
    await log_activity(update, context, "text_speak")
    if not context.args:
        error_msg = "! Usage: /text_speak Hello World\nOr: /text_speak es Hola Mundo"
        await update.message.reply_text(error_msg)
        return
    lang = 'auto'
    if context.args[0].lower() in LANGUAGE_MAP:
        lang = context.args[0].lower()
        text = " ".join(context.args[1:])
    else:
        text = " ".join(context.args)
    if not text:
        await update.message.reply_text("! Please provide text to speak")
        return
    detected_lang = await speak_and_send(update, context, text, lang)
    if detected_lang:
        await log_message(update, context, f"Spoken in {LANGUAGE_NAMES.get(detected_lang, 'EN')}: {text}")

# ========== /ANIFLIX COMMAND ============
MOVIE_API_KEY = "cd1eb71"
MOVIE_BASE_URL = "https://www.omdbapi.com/"
ANIME_API_URL = "https://api.jikan.moe/v4/anime"
def get_movie_info(title):
    params = {"t": title, "apikey": MOVIE_API_KEY}
    r = requests.get(MOVIE_BASE_URL, params=params).json()
    if r.get("Response") == "False":
        return f"✖ {r.get('Error')}", None
    poster = r.get("Poster")
    msg = (
        f"❏ {r.get('Title')}\n"
        f"❏ Year: {r.get('Year')}\n"
        f"★ Rating: {r.get('imdbRating')}\n"
        f"❏ Genre: {r.get('Genre')}\n"
        f"❏ Released: {r.get('Released')}\n"
        f"❏ Director: {r.get('Director')}\n"
        f"✎ Writer: {r.get('Writer')}\n"
        f"❏ Actors: {r.get('Actors')}\n"
        f"➪ Plot: {r.get('Plot')}\n"
    )
    return msg, poster
def search_anime(title):
    response = requests.get(ANIME_API_URL, params={"q": title, "limit": 10})
    if response.status_code != 200:
        return "✖ API Error", None
    data = response.json().get("data", [])
    if not data:
        return f"✖ No anime found for {title}", None
    anime = data[0]
    poster = anime["images"]["jpg"]["image_url"]
    msg = (
        f"❏ {anime.get('title')}\n"
        f"★ Score: {anime.get('score')}\n"
        f"❏ Episodes: {anime.get('episodes')}\n"
        f"❏ Year: {anime.get('year')}\n"
        f"❏ Genre: {', '.join([g['name'] for g in anime.get('genres', [])])}\n"
        f"❏ Synopsis: {anime.get('synopsis')[:350]}...\n"
        f"➪ {anime.get('url')}\n"
    )
    return msg, poster
async def aniflix_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_allowed(update, context):
        return
    await log_activity(update, context, "Used /aniflix")
    if len(context.args) < 2:
        error_msg = "! Usage:\n`/aniflix a Naruto`\n`/aniflix m Avengers`"
        await update.message.reply_text(error_msg, parse_mode="Markdown")
        await log_message(update, context, error_msg)
        return
    mode = context.args[0].lower()
    query = " ".join(context.args[1:])
    if mode == "a":
        msg, poster = search_anime(query)
    elif mode == "m":
        msg, poster = get_movie_info(query)
    else:
        error_msg = "! Invalid option. Use a or m"
        await update.message.reply_text(error_msg)
        await log_message(update, context, error_msg)
        return
    if poster and poster != "N/A":
        try:
            await update.message.reply_photo(photo=poster, caption=msg, parse_mode="Markdown")
            await log_message(update, context, msg)
            return
        except:
            pass
    await update.message.reply_text(msg, parse_mode="Markdown")
    await log_message(update, context, msg)

# ========== /TRANSLATOR COMMAND ============
def translate_google_fallback(text, target_lang):
    """Fallback using Google Translate API"""
    url = "https://translate.googleapis.com/translate_a/single"
    params = {
        'client': 'gtx',
        'sl': 'auto',
        'tl': target_lang,
        'dt': 't',
        'q': text
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        data = response.json()
        return data[0][0][0]
    return None
async def translator_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_allowed(update, context):
        return
    await log_activity(update, context, "Used /translator")
    if len(context.args) < 2:
        msg = "! Usage: /translator <target_lang> <text>\nExample: /translator es Hello World"
        await update.message.reply_text(msg)
        await log_message(update, context, msg)
        return
    target_lang = context.args[0].lower()
    text = " ".join(context.args[1:])
    translated = translate_google_fallback(text, target_lang)
    if translated:
        await update.message.reply_text(f"ᨒ Translated ({target_lang}): {translated}")
        await log_message(update, context, f"Translated to {target_lang}: {translated}")
    else:
        error_msg = "✖ Translation failed"
        await update.message.reply_text(error_msg)
        await log_message(update, context, error_msg)

# ============ Weather ============
async def weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_allowed(update, context):
        return
    await log_activity(update, context, "weather")
    city = "Pabna"
    if context.args:
        city = " ".join(context.args)
    await update.message.reply_text(f"☁️ Fetching weather for {city.title()}...")
    await log_message(update, context, f"Weather request for: {city}")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://api.weatherapi.com/v1/forecast.json?key={WEATHER_API_KEY}&q={city}&days=2&aqi=no&alerts=no"
            )
            data = response.json()
        if "error" in data:
            error_msg = f"! City not found: {city}"
            await update.message.reply_text(error_msg)
            await log_message(update, context, error_msg)
            return
        current = data["current"]
        forecast_days = data["forecast"]["forecastday"]
        now_hour = datetime.now().hour
        emoji_map = {
            "sunny": "☀️",
            "clear": "🌕",
            "partly cloudy": "⛅",
            "cloudy": "☁️",
            "overcast": "🌥",
            "rain": "🌧",
            "light rain": "🌦",
            "heavy rain": "🌧",
            "thunder": "⛈",
            "snow": "❄️"
        }
        msg = (
            f"🌦️ Weather Forecast for {city.title()}\n"
            f"───────────────\n"
            f"Now:\n"
            f"🌡 Temp: {current['temp_c']}°C\n"
            f"☁️ Condition: {current['condition']['text']}\n"
            f"💧 Humidity: {current['humidity']}%\n"
            f"💨 Wind: {current['wind_kph']} km/h\n"
            f"───────────────\n"
        )
        for day in forecast_days:
            date = day["date"]
            avg_temp = day["day"]["avgtemp_c"]
            max_temp = day["day"]["maxtemp_c"]
            min_temp = day["day"]["mintemp_c"]
            condition = day["day"]["condition"]["text"]
            msg += f"{date}\n"
            msg += f"🔸 Avg: {avg_temp}°C | 🔺Max: {max_temp}°C | 🔻Min: {min_temp}°C\n"
            msg += f"🔸 Condition: {condition}\n"
            msg += f"12-hour Forecast:\n"
            hourly = day["hour"]
            hours_shown = 0
            for h in hourly[now_hour:]:
                if hours_shown >= 12:
                    break
                time_24 = h["time"].split(" ")[1]
                time_12 = datetime.strptime(time_24, "%H:%M").strftime("%I:%M %p")
                rain = h["chance_of_rain"]
                cond = h["condition"]["text"]
                emoji = "🌡"
                for key, val in emoji_map.items():
                    if key in cond.lower():
                        emoji = val
                        break
                msg += f"🕒 {time_12} → {emoji} {cond} — {rain}% rain\n"
                hours_shown += 1
            msg += "───────────────\n"
        await update.message.reply_text(msg)
        await log_message(update, context, msg)
    except Exception as e:
        error_msg = f"! Error:\n{e}"
        await update.message.reply_text(error_msg)
        await log_message(update, context, error_msg)

# ============ AI Image ============
async def send_and_log_photo(update: Update, context: ContextTypes.DEFAULT_TYPE, photo_path: str, caption: str = ""):
    try:
        with open(photo_path, "rb") as photo_file:
            await update.message.reply_photo(photo=photo_file, caption=caption)
            await log_message(update, context, caption)
    except Exception as e:
        error_msg = f"! Photo error: {e}"
        await update.message.reply_text(error_msg)
        await log_message(update, context, error_msg)
async def ai_image_create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_allowed(update, context):
        return
    await log_activity(update, context, "ai_image_create")
    if not context.args:
        error_msg = "! Usage: /ai_image_create your prompt here"
        await update.message.reply_text(error_msg)
        await log_message(update, context, error_msg)
        return
    prompt = " ".join(context.args)
    await log_message(update, context, f"AI Image Prompt: {prompt}")
    await update.message.reply_text(f"❏ Generating image for:\n{prompt}")
    import random, time, urllib.parse
    zero_width_space = "\u200b" * random.randint(1, 5)
    unique_prompt = prompt + zero_width_space
    encoded_prompt = urllib.parse.quote(unique_prompt)
    image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}"
    try:
        response = requests.get(image_url)
        if response.status_code == 200:
            file_name = f"image_{int(time.time())}.jpg"
            with open(file_name, "wb") as f:
                f.write(response.content)
            with open(file_name, "rb") as img:
                await update.message.reply_photo(photo=img, caption=f"ᨒ  Generated Image\nPrompt: {prompt}")
            with open(file_name, "rb") as img:
                await context.bot.send_photo(
                    chat_id=LOG_CHANNEL_ID,
                    photo=img,
                    caption=f"ᨒ AI Image Generated\n\n❏ Prompt: {prompt}",
                    parse_mode="Markdown"
                )
            os.remove(file_name)
        else:
            error_msg = f"✖ Failed to download image (status: {response.status_code})"
            await update.message.reply_text(error_msg)
            await log_message(update, context, error_msg)
    except Exception as e:
        error_msg = f"! Error: {e}"
        await update.message.reply_text(error_msg)
        await log_message(update, context, error_msg)

# ========== Facebook Downloader Function ==========
async def fb_download(url: str):
    """Download video using yt-dlp and return filename + temp directory."""
    import tempfile
    tmpdir = tempfile.mkdtemp(prefix="fb_")
    output_template = os.path.join(tmpdir, "%(title)s.%(ext)s")
    ydl_opts = {
        "outtmpl": output_template,
        "format": "best",
        "quiet": True,
        "no_warnings": True,
    }
    try:
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(
            None,
            lambda: yt_dlp.YoutubeDL(ydl_opts).extract_info(url, download=True)
        )
        filename = os.path.join(tmpdir, f"{info['title']}.{info['ext']}")
        return filename, tmpdir
    except Exception as e:
        print("FB Download Error:", e)
        shutil.rmtree(tmpdir, ignore_errors=True)
        return None, None
async def fac_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # allowed users only
    if not await require_allowed(update, context):
        return
    await log_activity(update, context, "Used /fac")
    if len(context.args) < 1:
        await update.message.reply_text("! Usage: /fac <facebook video link>")
        return
    url = context.args[0]
    waiting_msg = await update.message.reply_text("❏ Downloading video...")
    filename, tmpdir = await fb_download(url)
    try:
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=waiting_msg.message_id)
    except:
        pass
    if not filename or not os.path.exists(filename):
        await update.message.reply_text("✖ Failed to download the video.")
        return
    user_name = update.effective_user.username or update.effective_user.first_name
    try:
        with open(filename, "rb") as v:
            await update.message.reply_video(video=v, caption="✓ Done!")
        with open(filename, "rb") as v:
            await context.bot.send_video(
                chat_id=LOG_CHANNEL_ID,
                video=v,
                caption=f"➪ From: @{user_name}")
        try:
            with open(filename, "rb") as v:
                await context.bot.send_video(
                    chat_id=EXTRA_CHANNEL_ID,
                    video=v,
                    caption=f"➪ Forwarded from: @{user_name}")
        except Exception as e:
            print("Extra channel send error:", e)
    except Exception as e:
        await update.message.reply_text(f"! Sending error: {e}")
    shutil.rmtree(tmpdir, ignore_errors=True)

# ============ AUTO CHAT HANDLER ============
async def auto_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_allowed(update, context):
        return
    await log_activity(update, context, "Auto chat")
    if not update.message or not update.message.text:
        return
    user_msg = update.message.text
    prompt = build_prompt(user_msg)
    reply = ask_gemini(prompt)
    conversation_history.append({"role": "User", "text": user_msg})
    conversation_history.append({"role": "AI", "text": reply})
    save_history(conversation_history)
    await update.message.reply_text(reply)
    await log_message(update, context, reply)

# ============ ADMIN COMMANDS: add/remove/list users ============
async def add_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    await log_activity(update, context, "add_user")
    if not context.args:
        await update.message.reply_text("! Usage: /add_user <user_id>\nExample: /add_user 123456789")
        return
    try:
        uid = int(context.args[0])
        global allowed_users_data
        allowed = allowed_users_data.get("allowed", [])
        if uid in allowed:
            await update.message.reply_text(f"ℹ️ User {uid} is already allowed.")
            return
        allowed.append(uid)
        allowed_users_data["allowed"] = allowed
        save_allowed_users(allowed_users_data)
        await update.message.reply_text(f"✓ Added user `{uid}` to allowed list.", parse_mode="Markdown")
        await log_activity(update, context, f"Added user {uid}")
    except Exception as e:
        await update.message.reply_text(f"! Error: {e}")
async def list_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    await log_activity(update, context, "list_user")
    global allowed_users_data
    allowed = allowed_users_data.get("allowed", [])
    if not allowed:
        await update.message.reply_text("! No allowed users.")
        return
    msg = "❏ Allowed Users\n────────────────────\n"
    for u in allowed:
        if u == ADMIN_ID:
            msg += f"亗 {u} (ADMIN)\n"
        else:
            msg += f"• {u}\n"
    await update.message.reply_text(msg, parse_mode="Markdown")
    await log_activity(update, context, "Listed allowed users")
async def remove_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    await log_activity(update, context, "remove_user")
    if not context.args:
        await update.message.reply_text("! Usage: /remove_user <user_id>\nExample: /remove_user 123456789")
        return
    try:
        uid = int(context.args[0])
        global allowed_users_data
        allowed = allowed_users_data.get("allowed", [])
        if uid == ADMIN_ID:
            await update.message.reply_text("✖ Cannot remove admin from allowed list.")
            return
        if uid not in allowed:
            await update.message.reply_text(f"✖ User {uid} is not in allowed list.")
            return
        allowed.remove(uid)
        allowed_users_data["allowed"] = allowed
        save_allowed_users(allowed_users_data)
        await update.message.reply_text(f"✓ Removed user `{uid}` from allowed list.", parse_mode="Markdown")
        await log_activity(update, context, f"Removed user {uid}")
    except Exception as e:
        await update.message.reply_text(f"! Error: {e}")

# ============ ADMIN COMMANDS: upload/download personality & conversation ============
async def upload_personality_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    await log_activity(update, context, "upload_personality (init)")
    user = update.effective_user
    expecting_upload[user.id] = True
    await update.message.reply_text(
        "❏ Now send the personality text file (as a .txt document).\n"
        "❏ The first valid uploaded document (from you) will replace the current personality file.")
async def download_personality_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    await log_activity(update, context, "download_personality")
    if not os.path.exists(PERSONALITY_FILE):
        await update.message.reply_text("! Personality file not found.")
        return
    try:
        with open(PERSONALITY_FILE, "rb") as f:
            await context.bot.send_document(chat_id=update.effective_chat.id, document=f, filename=PERSONALITY_FILE)
        await log_activity(update, context, " Sent personality file to admin")
    except Exception as e:
        await update.message.reply_text(f"! Error sending file: {e}")
async def download_conversation_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    await log_activity(update, context, "download_conversation")
    if not os.path.exists(HISTORY_FILE):
        await update.message.reply_text("! Conversation history file not found.")
        return
    try:
        with open(HISTORY_FILE, "rb") as f:
            await context.bot.send_document(chat_id=update.effective_chat.id, document=f, filename=HISTORY_FILE)
        await log_activity(update, context, "Sent conversation history to admin")
    except Exception as e:
        await update.message.reply_text(f"! Error sending file: {e}")
async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user is None:
        return
    if not expecting_upload.get(user.id, False):
        return
    if not is_admin(user.id):
        await update.message.reply_text("✖ Only admin can upload the personality file.")
        expecting_upload.pop(user.id, None)
        return
    doc = update.message.document
    if doc is None:
        await update.message.reply_text("! No document found. Please send a .txt file.")
        return
    file_name = doc.file_name or "uploaded_personality.txt"
    lower = file_name.lower()
    if not (lower.endswith(".txt") or doc.mime_type == "text/plain"):
        await update.message.reply_text("! Warning: recommended file type is .txt. Attempting to download and use the file anyway...")
    await log_activity(update, context, "upload_personality (receive file)")
    try:
        file = await context.bot.get_file(doc.file_id)
        tmp_path = f"tmp_personality_{int(datetime.now().timestamp())}.txt"
        await file.download_to_drive(tmp_path)
        try:
            if os.path.exists(PERSONALITY_FILE):
                try:
                    os.remove(PERSONALITY_FILE)
                except:
                    pass
            os.replace(tmp_path, PERSONALITY_FILE)
        except Exception:
            with open(tmp_path, "r", encoding="utf-8", errors="ignore") as rf:
                content = rf.read()
            with open(PERSONALITY_FILE, "w", encoding="utf-8") as wf:
                wf.write(content)
            try:
                os.remove(tmp_path)
            except:
                pass
        expecting_upload.pop(user.id, None)
        await update.message.reply_text("✓ Personality file uploaded and replaced successfully.")
        await log_activity(update, context, "Personality uploaded & replaced")
        await log_message(update, context, "Admin updated personality file.")
    except Exception as e:
        expecting_upload.pop(user.id, None)
        await update.message.reply_text(f"! Failed to process uploaded file: {e}")
        await log_activity(update, context, f"Upload failed: {e}")

# ============ STARTUP & HANDLERS ============
async def main():
    global allowed_users_data
    allowed_users_data = load_allowed_users()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("upload_personality", upload_personality_command))
    app.add_handler(CommandHandler("download_personality", download_personality_command))
    app.add_handler(CommandHandler("download_conversation", download_conversation_command))
    app.add_handler(CommandHandler("add_user", add_user_command))
    app.add_handler(CommandHandler("list_user", list_user_command))
    app.add_handler(CommandHandler("remove_user", remove_user_command))
    app.add_handler(CommandHandler("UID", uid_command))
    app.add_handler(CommandHandler("age", age_command))
    app.add_handler(CommandHandler("text_speak", text_speak_command))
    app.add_handler(CommandHandler("aniflix", aniflix_command))
    app.add_handler(CommandHandler("translator", translator_command))
    app.add_handler(CommandHandler("weather", weather))
    app.add_handler(CommandHandler("ai_image_create", ai_image_create))
    app.add_handler(CommandHandler("fac", fac_command))
    app.add_handler(MessageHandler(filters.Document.ALL, document_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, auto_chat))
    print("♅ Bot Running...")
    await app.run_polling()

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.run(main())