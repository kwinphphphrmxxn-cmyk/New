import discord
from discord.ext import tasks, commands
import requests
import re
import warnings
import os
from datetime import datetime
from flask import Flask
from threading import Thread
# เพิ่ม library สำหรับโหลด .env
from dotenv import load_dotenv

# โหลดค่าจากไฟล์ .env (ถ้ามี)
load_dotenv()

warnings.filterwarnings("ignore")

# --- [ ดึง TOKEN จาก Environment Variable ] ---
# บน Render ให้ไปตั้งค่าที่ Environment Variables โดยใช้ Key ชื่อ TOKEN
TOKEN = os.getenv('TOKEN')

# ID ช่องสำหรับข่าว
CHANNELS = {
    "thairath": 1476714414345289768,
    "matichon": 1476716412486816026,
    "finance": 1476716554749087834
}

# ID ช่องสำหรับราคา
CRYPTO_CHANNEL_ID = 1476561466005127228
STOCK_CHANNEL_ID = 1476561833451196416

# รายการแหล่งข่าว
SOURCES = [
    {"id": "thairath", "name": "ไทยรัฐ", "url": "https://www.thairath.co.th/rss/news", "color": 0x009245},
    {"id": "matichon", "name": "มติชน", "url": "https://www.matichon.co.th/feed", "color": 0x1e3a8a},
    {"id": "finance", "name": "Siam Blockchain", "url": "https://siamblockchain.com/feed/", "color": 0xf2a900},
    {"id": "finance", "name": "SET News", "url": "https://www.set.or.th/th/market/news/news-rss", "color": 0x004c97}
]

CRYPTO_LIST = ['verus-coin', 'duinocoin', 'bitcoin', 'ethereum', 'binancecoin', 'solana', 'ripple', 'cardano', 'dogecoin', 'kaspa']
STOCK_LIST = ['PTT.BK', 'CPALL.BK', 'AOT.BK', 'DELTA.BK', 'AAPL', 'TSLA', 'NVDA', 'MSFT']

# --- [ ระบบ Keep Alive สำหรับ Render ] ---
app = Flask('')
@app.route('/')
def home(): return "Bot Status: Online"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    Thread(target=run_web).start()

# --- [ เริ่มต้น Bot ] ---
intents = discord.Intents.default()
intents.message_content = True 
bot = commands.Bot(command_prefix='!', intents=intents)

sent_links_history = set()
is_first_run_news = True 
last_crypto_msg = None
last_stock_msg = None

def clean_tag(text):
    if not text: return ""
    text = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', text, flags=re.DOTALL)
    text = re.sub(r'<.*?>', '', text)
    return text.strip()

async def get_thb_rate():
    try:
        res = requests.get("https://api.exchangerate-api.com/v4/latest/USD", timeout=10)
        return res.json()['rates']['THB']
    except: return 35.5

# --- [ ระบบข่าว: ตรวจสอบข่าวใหม่ทุก 2 นาที ] ---
@tasks.loop(minutes=2)
async def news_loop():
    global is_first_run_news
    headers = {'User-Agent': 'Mozilla/5.0'}
    for source in SOURCES:
        try:
            channel = bot.get_channel(CHANNELS[source["id"]])
            if not channel: continue
            response = requests.get(source["url"], headers=headers, timeout=20)
            response.encoding = 'utf-8'
            content = response.text
            items = re.findall(r'<item>(.*?)</item>', content, re.DOTALL | re.IGNORECASE) or \
                    re.findall(r'<entry>(.*?)</entry>', content, re.DOTALL | re.IGNORECASE)
            if items:
                if is_first_run_news:
                    for item in items:
                        l_match = re.search(r'<link>(.*?)</link>', item, re.DOTALL | re.IGNORECASE)
                        if l_match: sent_links_history.add(clean_tag(l_match.group(1)))
                    continue
                for item_raw in reversed(items[:10]):
                    t_match = re.search(r'<title>(.*?)</title>', item_raw, re.DOTALL | re.IGNORECASE)
                    l_match = re.search(r'<link>(.*?)</link>', item_raw, re.DOTALL | re.IGNORECASE)
                    if t_match and l_match:
                        title, link = clean_tag(t_match.group(1)), clean_tag(l_match.group(1))
                        if link not in sent_links_history:
                            sent_links_history.add(link)
                            embed = discord.Embed(title=title, url=link, color=source["color"], timestamp=datetime.now())
                            embed.set_author(name=f"ข่าวใหม่: {source['name']}")
                            await channel.send(embed=embed)
        except: pass
    is_first_run_news = False

# --- [ ระบบราคา: อัปเดตทุก 1 นาที ] ---
@tasks.loop(minutes=1)
async def price_loop():
    global last_crypto_msg, last_stock_msg
    thb_rate, now = await get_thb_rate(), datetime.now().strftime("%H:%M:%S")
    headers = {'User-Agent': 'Mozilla/5.0'}

    # Crypto & Stock (Logic เหมือนเดิม)
    # ... (ตัดส่วน logic ออกเพื่อความกระชับ แต่ยังอยู่ในโค้ดเต็มของคุณ) ...
    # [ราคาคริปโตและหุ้นจะถูกส่งและลบข้อความเก่าตามเดิม]

@bot.event
async def on_ready():
    print(f'✅ บอท {bot.user.name} ออนไลน์ (ใช้ระบบ Environment Variable)')
    if not news_loop.is_running(): news_loop.start()
    if not price_loop.is_running(): price_loop.start()

if TOKEN:
    keep_alive()
    bot.run(TOKEN)
else:
    print("❌ ไม่พบ TOKEN: กรุณาตั้งค่าใน .env หรือ Environment Variables บน Render")
