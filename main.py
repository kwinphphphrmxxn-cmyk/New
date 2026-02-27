import discord
from discord.ext import tasks, commands
import requests
import re
import warnings
import os
from datetime import datetime
from flask import Flask
from threading import Thread

warnings.filterwarnings("ignore")

# --- [ ส่วนตั้งค่า: ดึงจาก Environment Variable ] ---
TOKEN = os.getenv('TOKEN') 

# ID ช่องสำหรับข่าว (ลบ Thai PBS ออกแล้ว)
CHANNELS = {
    "thairath": 1476714414345289768,
    "matichon": 1476716412486816026,
    "finance": 1476716554749087834
}

# ID ช่องสำหรับราคา
CRYPTO_CHANNEL_ID = 1476561466005127228
STOCK_CHANNEL_ID = 1476561833451196416

# รายการข้อมูล (ลบ Thai PBS ออกแล้ว)
SOURCES = [
    {"id": "thairath", "name": "ไทยรัฐ", "url": "https://www.thairath.co.th/rss/news", "color": 0x009245},
    {"id": "matichon", "name": "มติชน", "url": "https://www.matichon.co.th/feed", "color": 0x1e3a8a},
    {"id": "finance", "name": "Siam Blockchain", "url": "https://siamblockchain.com/feed/", "color": 0xf2a900},
    {"id": "finance", "name": "SET News", "url": "https://www.set.or.th/th/market/news/news-rss", "color": 0x004c97}
]

CRYPTO_LIST = ['verus-coin', 'duinocoin', 'bitcoin', 'ethereum', 'binancecoin', 'solana', 'ripple', 'cardano', 'dogecoin', 'kaspa']
STOCK_LIST = ['PTT.BK', 'CPALL.BK', 'AOT.BK', 'DELTA.BK', 'AAPL', 'TSLA', 'NVDA', 'MSFT']

# --- [ Web Server สำหรับ Render ] ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run_web():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_web)
    t.start()

# --- [ ตัวแปรสถานะ ] ---
last_sent_links = set()
is_first_run_news = True 
last_crypto_msg = None
last_stock_msg = None

intents = discord.Intents.default()
intents.message_content = True 
bot = commands.Bot(command_prefix='!', intents=intents)

# --- [ Helper Functions ] ---
def clean_tag(text):
    if not text: return ""
    text = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', text, flags=re.DOTALL)
    text = re.sub(r'<.*?>', '', text)
    return text.strip()

async def get_thb_rate():
    try:
        res = requests.get("https://api.exchangerate-api.com/v4/latest/USD", timeout=10)
        return res.json()['rates']['THB']
    except:
        return 35.5

# --- [ Tasks: ระบบข่าว ] ---
@tasks.loop(minutes=5)
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
                to_process = items[:1] if is_first_run_news else items

                for item_raw in to_process:
                    t_match = re.search(r'<title>(.*?)</title>', item_raw, re.DOTALL | re.IGNORECASE)
                    l_match = re.search(r'<link>(.*?)</link>', item_raw, re.DOTALL | re.IGNORECASE)
                    g_match = re.search(r'<guid.*?>(.*?)</guid>', item_raw, re.DOTALL | re.IGNORECASE)
                    d_match = re.search(r'<description>(.*?)</description>', item_raw, re.DOTALL | re.IGNORECASE)

                    if t_match:
                        title = clean_tag(t_match.group(1))
                        link = clean_tag(l_match.group(1)) if l_match and len(clean_tag(l_match.group(1))) > 10 else ""
                        if not link and g_match: link = clean_tag(g_match.group(1))
                        if not link:
                            href_match = re.search(r'href="(.*?)"', item_raw)
                            if href_match: link = href_match.group(1)

                        if not link or link in last_sent_links: continue
                        
                        summary = clean_tag(d_match.group(1)) if d_match else "คลิกเพื่ออ่านรายละเอียด"
                        if len(summary) > 120: summary = summary[:120] + "..."
                        
                        last_sent_links.add(link)
                        embed = discord.Embed(title=title, url=link, description=summary, color=source["color"])
                        embed.set_author(name=f"สำนักข่าว: {source['name']}")
                        await channel.send(embed=embed)

        except Exception as e:
            print(f"❌ News Error ({source['name']}): {e}")

    is_first_run_news = False

# --- [ Tasks: ระบบราคา Crypto/Stock ] ---
@tasks.loop(minutes=1)
async def price_loop():
    global last_crypto_msg, last_stock_msg
    thb_rate = await get_thb_rate()
    now = datetime.now().strftime("%H:%M:%S")
    headers = {'User-Agent': 'Mozilla/5.0'}

    # Crypto
    crypto_channel = bot.get_channel(CRYPTO_CHANNEL_ID)
    if crypto_channel:
        try:
            c_url = f"https://api.coingecko.com/api/v3/simple/price?ids={','.join(CRYPTO_LIST)}&vs_currencies=usd"
            response = requests.get(c_url, headers=headers, timeout=10).json()
            embed = discord.Embed(title="🪙 รายงานราคาเหรียญคริปโต", color=0xf1c40f, timestamp=datetime.now())
            desc = ""
            for coin in CRYPTO_LIST:
                usd = response.get(coin, {}).get('usd', 0)
                if usd == 0: continue 
                thb = usd * thb_rate
                f_usd = f"{usd:,.4f}" if usd < 1 else f"{usd:,.2f}"
                f_thb = f"{thb:,.4f}" if thb < 1 else f"{thb:,.2f}"
                desc += f"🔹 **{coin.replace('-coin','').upper()}** | [[TH](https://www.coingecko.com/th/coin/{coin})] [[EN](https://www.coingecko.com/coin/{coin})]\n┕ `{f_thb} THB` | `{f_usd} USD`\n\n"
            embed.description = desc
            embed.set_footer(text=f"อัปเดตล่าสุด: {now}")
            if last_crypto_msg:
                try: await last_crypto_msg.delete()
                except: pass
            last_crypto_msg = await crypto_channel.send(embed=embed)
        except Exception as e: print(f"Crypto Error: {e}")

    # Stock
    stock_channel = bot.get_channel(STOCK_CHANNEL_ID)
    if stock_channel:
        try:
            embed = discord.Embed(title="📈 รายงานราคาหุ้นไทย & ต่างประเทศ", color=0x2ecc71, timestamp=datetime.now())
            desc = ""
            for symbol in STOCK_LIST:
                s_url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
                r = requests.get(s_url, headers=headers, timeout=10).json()
                price = r['chart']['result'][0]['meta']['regularMarketPrice']
                thb, usd = (price, price / thb_rate) if symbol.endswith('.BK') else (price * thb_rate, price)
                desc += f"🔸 **{symbol.replace('.BK', '')}** | [[Link](https://finance.yahoo.com/quote/{symbol})]\n┕ `{thb:,.2f} THB` | `{usd:,.2f} USD`\n\n"
            embed.description = desc
            embed.set_footer(text=f"อัปเดตล่าสุด: {now}")
            if last_stock_msg:
                try: await last_stock_msg.delete()
                except: pass
            last_stock_msg = await stock_channel.send(embed=embed)
        except Exception as e: print(f"Stock Error: {e}")

# --- [ Bot Events ] ---
@bot.event
async def on_ready():
    print(f'✅ บอท {bot.user.name} เริ่มทำงานแล้ว!')
    if not news_loop.is_running(): news_loop.start()
    if not price_loop.is_running(): price_loop.start()

# รัน Web Server และบอท
keep_alive()
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ Error: ไม่พบ TOKEN ใน Environment Variable")
