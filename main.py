import discord
from discord.ext import commands
from discord import app_commands
import os, json, datetime, asyncio, random, re

# ================== ALAP ==================

TOKEN = os.getenv("DISCORD_TOKEN")

WARN_FILE = "warns.json"
WELCOME_FILE = "welcome.json"
LEAVE_FILE = "leave.json"
AUTO_ROLE_FILE = "autorole.json"
VIDEO_FILE = "videos.json"

FORBIDDEN_WORDS = [
    "fasz","geci","buzi","bazdmeg","kurva","anyád","szar",
    "szarka","any@d","apád","cigány","cigany","barom"
]
LINK_REGEX = r"http[s]?://"

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ================= SEGÉD / JOGOSULTSÁG =================

def load_json(file):
    if not os.path.exists(file):
        return {}
    try:
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def make_embed(title, desc, color):
    e = discord.Embed(
        title=title,
        description=desc,
        color=color,
        timestamp=datetime.datetime.utcnow()
    )
    e.set_footer(text="✨ SERVICE HUN ✨")
    return e

# Általános moderátor ellenőrző (üzenetkezeléshez stb.)
def mod_check(i: discord.Interaction):
    p = i.user.guild_permissions
    return p.administrator or p.manage_messages

# SPECIÁLIS ELLENŐRZŐ A TILTÁSHOZ (Csak a kért két rangnak)
def can_ban_check(i: discord.Interaction):
    allowed_roles = ["[⏰] TESTER  MODERÁTOR", "[🧨] MODERÁTOR"]
    user_role_names = [role.name for role in i.user.roles]
    
    # Ha admin, vagy benne van a két rang valamelyikében
    return i.user.guild_permissions.administrator or any(role in user_role_names for role in allowed_roles)

# ================= READY =================

@bot.event
async def on_ready():
    await bot.tree.sync()
    print("✅ Slash parancsok szinkronizálva")
    print(f"✅ Bot online: {bot.user}")

# ================= AUTOMOD =================

@bot.event
async def on_message(msg):
    if msg.author.bot or not msg.guild:
        return

    is_mod = msg.author.guild_permissions.administrator or msg.author.guild_permissions.manage_messages
    txt = msg.content.lower()
    uid = str(msg.author.id)

    if not is_mod and re.search(LINK_REGEX, txt):
        await msg.delete()
        data = load_json(WARN_FILE)
        data.setdefault(uid, [])
        data[uid].append("Tiltott link küldése")
        save_json(WARN_FILE, data)
        mute_time = len(data[uid]) * 2
        await msg.author.timeout(datetime.timedelta(minutes=mute_time))
        await msg.channel.send(embed=make_embed("🔗 Automatikus figyelmeztetés", f"👤 {msg.author.mention}\n📄 Indok: Tiltott link\n⚠️ Figy: {len(data[uid])}", discord.Color.red()))
        return

    if any(w in txt for w in FORBIDDEN_WORDS):
        await msg.delete()
        data = load_json(WARN_FILE)
        data.setdefault(uid, [])
        data[uid].append("Káromkodás")
        save_json(WARN_FILE, data)
        mute_time = len(data[uid]) * 2
        await msg.author.timeout(datetime.timedelta(minutes=mute_time))
        await msg.channel.send(embed=make_embed("🤬 Automatikus figyelmeztetés", f"👤 {msg.author.mention}\n📄 Indok: Káromkodás", discord.Color.orange()))
        return

    await bot.process_commands(msg)

# ================= BEÁLLÍTÁSOK =================

@bot.tree.command(name="üdvözlő_beállítás")
@app_commands.check(mod_check)
async def welcome_set(i: discord.Interaction, csatorna: discord.TextChannel):
    save_json(WELCOME_FILE, {"channel_id": csatorna.id})
    await i.response.send_message("✅ Üdvözlő beállítva", ephemeral=True)

@bot.tree.command(name="kilépő_beállítás")
@app_commands.check(mod_check)
async def leave_set(i: discord.Interaction, csatorna: discord.TextChannel):
    save_json(LEAVE_FILE, {"channel_id": csatorna.id})
    await i.response.send_message("✅ Kilépő beállítva", ephemeral=True)

@bot.tree.command(name="autorole_beállítás")
@app_commands.check(mod_check)
async def autorole_set(i: discord.Interaction, rang: discord.Role):
    save_json(AUTO_ROLE_FILE, {"role_id": rang.id})
    await i.response.send_message("✅ Autorole beállítva", ephemeral=True)

# ================= MODERÁCIÓ =================

@bot.tree.command(name="figyelmeztetés")
@app_commands.check(mod_check)
async def warn(i: discord.Interaction, tag: discord.Member, indok: str):
    data = load_json(WARN_FILE)
    data.setdefault(str(tag.id), []).append(indok)
    save_json(WARN_FILE, data)
    mute_time = len(data[str(tag.id)]) * 2
    await tag.timeout(datetime.timedelta(minutes=mute_time))
    await i.response.send_message(embed=make_embed("⚠️ Figyelmeztetés", f"👤 {tag.mention}\n📄 {indok}\n👮‍♂️ {i.user.mention}", discord.Color.orange()))

@bot.tree.command(name="némítás")
@app_commands.check(mod_check)
async def mute(i: discord.Interaction, tag: discord.Member, perc: int, indok: str):
    await tag.timeout(datetime.timedelta(minutes=perc))
    await i.response.send_message(embed=make_embed("🔇 Némítás", f"👤 {tag.mention}\n⏱ {perc} perc\n📄 {indok}", discord.Color.red()))

# ================= KITILTÁS / KIRÚGÁS (Csak a megadott rangoknak) =================

@bot.tree.command(name="kirúgás")
@app_commands.check(can_ban_check)
@app_commands.default_permissions(kick_members=True) # Elrejti azok elől, akiknek nincs alapból kick joguk
async def kick(i: discord.Interaction, tag: discord.Member, indok: str):
    await tag.kick(reason=indok)
    await i.response.send_message(embed=make_embed("👢 Kirúgás", f"{tag.mention}\n📄 {indok}\n👮‍♂️ {i.user.mention}", discord.Color.orange()))

@bot.tree.command(name="kitiltás")
@app_commands.check(can_ban_check)
@app_commands.default_permissions(ban_members=True) # Elrejti azok elől, akiknek nincs alapból ban joguk
async def ban(i: discord.Interaction, tag: discord.Member, indok: str):
    await tag.ban(reason=indok)
    await i.response.send_message(embed=make_embed("🚫 Kitiltás", f"{tag.mention}\n📄 {indok}\n👮‍♂️ {i.user.mention}", discord.Color.dark_red()))

# ================= VIDEÓ =================

@bot.tree.command(name="videó")
@app_commands.check(mod_check)
async def video(i: discord.Interaction, szoveg: str, video: discord.Attachment):
    await i.response.defer()
    if not video.content_type or not video.content_type.startswith("video"):
        return await i.followup.send("❌ Csak videó tölthető fel", ephemeral=True)
    data = load_json(VIDEO_FILE)
    data["count"] = data.get("count", 149) + 1
    save_json(VIDEO_FILE, data)
    await i.followup.send(content=f"**{data['count']}. Sikeres trade bizonyíték**\n{szoveg}", file=await video.to_file())

if TOKEN:
    bot.run(TOKEN)
                  
