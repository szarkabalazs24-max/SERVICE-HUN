import discord
from discord.ext import commands
from discord import app_commands
import os, json, datetime, asyncio, random, re
from collections import defaultdict

# ================== KONFIGURÁCIÓ ==================

TOKEN = os.getenv("DISCORD_TOKEN")

# IDE MÁSOLD BE A RANGOK ID-JÁT!
TESTER_MOD_ID = 1485380635442020352  # [⏰] TESTER MODERÁTOR ID
MOD_ID = 1462561594473975969         # [🧨] MODERÁTOR ID

WARN_FILE = "warns.json"
WELCOME_FILE = "welcome.json"
LEAVE_FILE = "leave.json"
AUTO_ROLE_FILE = "autorole.json"
VIDEO_FILE = "videos.json"

FORBIDDEN_WORDS = ["fasz","geci","buzi","bazdmeg","kurva","anyád","szar","szarka","any@d","apád","cigány","cigany","barom"]
LINK_REGEX = r"http[s]?://"

# SPAM SZŰRŐ MEMÓRIA
user_messages = defaultdict(list)

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ================= SEGÉDFÜGGVÉNYEK =================

def load_json(file):
    if not os.path.exists(file): return {}
    try:
        with open(file, "r", encoding="utf-8") as f: return json.load(f)
    except: return {}

def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f: json.dump(data, f, indent=4, ensure_ascii=False)

def make_embed(title, desc, color):
    e = discord.Embed(title=title, description=desc, color=color, timestamp=datetime.datetime.utcnow())
    e.set_footer(text="✨ SERVICE HUN ✨")
    return e

def mod_check(i: discord.Interaction):
    p = i.user.guild_permissions
    return p.administrator or p.manage_messages

def high_mod_check(i: discord.Interaction):
    user_role_ids = [role.id for role in i.user.roles]
    return i.user.guild_permissions.administrator or TESTER_MOD_ID in user_role_ids or MOD_ID in user_role_ids

# ================= AUTOMOD (SPAM + LINK + KÁROMKODÁS) =================

@bot.event
async def on_message(msg):
    if msg.author.bot or not msg.guild: return
    is_mod = msg.author.guild_permissions.administrator or msg.author.guild_permissions.manage_messages
    uid = str(msg.author.id)
    txt = msg.content.lower()

    indok = None
    if not is_mod:
        if re.search(LINK_REGEX, txt): indok = "Tiltott link küldése"
        elif any(w in txt for w in FORBIDDEN_WORDS): indok = "Káromkodás"
        else:
            now = datetime.datetime.now()
            user_messages[uid] = [t for t in user_messages[uid] if (now - t).seconds < 5]
            user_messages[uid].append(now)
            if len(user_messages[uid]) >= 5: indok = "Spamming (Túl sok üzenet)"

    if indok:
        await msg.delete()
        data = load_json(WARN_FILE)
        now_iso = datetime.datetime.utcnow().isoformat()
        data.setdefault(uid, []).append({"indok": indok, "mod": "Rendszer (Automod)", "ido": now_iso})
        save_json(WARN_FILE, data)
        mute_time = len(data[uid]) * 2
        await msg.author.timeout(datetime.timedelta(minutes=mute_time))
        await msg.channel.send(embed=make_embed("🛑 Automatikus figyelmeztetés", f"👤 **Tag:** {msg.author.mention}\n📄 **Indok:** {indok}\n⚠️ **Figyelmeztetések:** {len(data[uid])}\n🔇 **Némítás:** {mute_time} perc\n👮‍♂️ **Intézkedett:** Rendszer (Automod)", discord.Color.red()))
        return
    await bot.process_commands(msg)

# ================= BELÉPÉS / KILÉPÉS =================

@bot.event
async def on_member_join(member):
    ar = load_json(AUTO_ROLE_FILE)
    role = member.guild.get_role(ar.get("role_id", 0))
    if role: await member.add_roles(role)
    data = load_json(WELCOME_FILE)
    ch = member.guild.get_channel(data.get("channel_id", 0))
    if ch: await ch.send(f"👋 Üdv a szerveren {member.mention}! Te vagy a(z) {member.guild.member_count}. tag 💙")

@bot.event
async def on_member_remove(member):
    data = load_json(LEAVE_FILE)
    ch = member.guild.get_channel(data.get("channel_id", 0))
    if ch: await ch.send(f"🚪 {member.name} kilépett a szerverről.")

# ================= BEÁLLÍTÁSOK =================

@bot.tree.command(name="üdvözlő_beállítás")
@app_commands.check(mod_check)
async def welcome_set(i: discord.Interaction, csatorna: discord.TextChannel):
    save_json(WELCOME_FILE, {"channel_id": csatorna.id})
    await i.response.send_message("✅ Üdvözlő csatorna beállítva!", ephemeral=True)

@bot.tree.command(name="kilépő_beállítás")
@app_commands.check(mod_check)
async def leave_set(i: discord.Interaction, csatorna: discord.TextChannel):
    save_json(LEAVE_FILE, {"channel_id": csatorna.id})
    await i.response.send_message("✅ Kilépő csatorna beállítva!", ephemeral=True)

@bot.tree.command(name="autorole_beállítás")
@app_commands.check(mod_check)
async def autorole_set(i: discord.Interaction, rang: discord.Role):
    save_json(AUTO_ROLE_FILE, {"role_id": rang.id})
    await i.response.send_message("✅ Autorole rang beállítva!", ephemeral=True)

# ================= MODERÁCIÓ =================

@bot.tree.command(name="figyelmeztetés_info")
@app_commands.check(mod_check)
async def warn_info(i: discord.Interaction, tag: discord.Member):
    data = load_json(WARN_FILE)
    warns = data.get(str(tag.id), [])
    if not warns: return await i.response.send_message(f"✅ {tag.mention}-nak nincs figyelmeztetése.", ephemeral=True)
    desc = ""
    for idx, w in enumerate(warns, 1):
        try:
            diff = datetime.datetime.utcnow() - datetime.datetime.fromisoformat(w['ido'])
            napja = f"{diff.days} napja" if diff.days > 0 else "ma"
        except: napja = "régen"
        desc += f"**{idx}.** `{w['indok']}`\n└ 👮‍♂️: {w['mod']} | 📅: {napja}\n\n"
    await i.response.send_message(embed=make_embed(f"⚠️ {tag.name} figyelmeztetései", desc, discord.Color.blue()))

@bot.tree.command(name="figyelmeztetés")
@app_commands.check(mod_check)
async def warn(i: discord.Interaction, tag: discord.Member, indok: str):
    data = load_json(WARN_FILE)
    uid = str(tag.id)
    now = datetime.datetime.utcnow().isoformat()
    data.setdefault(uid, []).append({"indok": indok, "mod": str(i.user), "ido": now})
    save_json(WARN_FILE, data)
    mute_time = len(data[uid]) * 2
    await tag.timeout(datetime.timedelta(minutes=mute_time))
    await i.response.send_message(embed=make_embed("⚠️ Figyelmeztetés", f"👤 **Tag:** {tag.mention}\n📄 **Indok:** {indok}\n⚠️ **Összesen:** {len(data[uid])}\n🔇 **Némítás:** {mute_time} perc\n👮‍♂️ **Intézkedett:** {i.user.mention}", discord.Color.orange()))

@bot.tree.command(name="figyelmeztetés_törlés")
@app_commands.check(mod_check)
async def warn_del(i: discord.Interaction, tag: discord.Member, szám: int):
    data = load_json(WARN_FILE)
    warns = data.get(str(tag.id), [])
    if 0 < szám <= len(warns):
        warns.pop(szám - 1)
        save_json(WARN_FILE, data)
        await i.response.send_message(embed=make_embed("🧹 Törlés", f"👤 **Tag:** {tag.mention}\n📉 **Maradt:** {len(warns)}\n👮‍♂️ **Intézkedett:** {i.user.mention}", discord.Color.green()))
    else: await i.response.send_message("❌ Érvénytelen sorszám!", ephemeral=True)

@bot.tree.command(name="némítás")
@app_commands.check(mod_check)
async def mute(i: discord.Interaction, tag: discord.Member, perc: int, indok: str):
    await tag.timeout(datetime.timedelta(minutes=perc))
    await i.response.send_message(embed=make_embed("🔇 Némítás", f"👤 **Tag:** {tag.mention}\n⏱ **Időtartam:** {perc} perc\n📄 **Indok:** {indok}\n👮‍♂️ **Intézkedett:** {i.user.mention}", discord.Color.red()))

@bot.tree.command(name="némítás_feloldás")
@app_commands.check(mod_check)
async def unmute(i: discord.Interaction, tag: discord.Member):
    await tag.timeout(None)
    await i.response.send_message(embed=make_embed("🔊 Némítás feloldva", f"👤 **Tag:** {tag.mention}\n👮‍♂️ **Intézkedett:** {i.user.mention}", discord.Color.green()))

# ================= SZIGORÚ JOGOK =================

@bot.tree.command(name="kirúgás")
@app_commands.check(high_mod_check)
@app_commands.default_permissions(kick_members=True)
async def kick(i: discord.Interaction, tag: discord.Member, indok: str):
    await tag.kick(reason=indok)
    await i.response.send_message(embed=make_embed("👢 Kirúgás", f"👤 {tag.mention}\n📄 Indok: {indok}\n👮‍♂️ Intézkedett: {i.user.mention}", discord.Color.orange()))

@bot.tree.command(name="kitiltás")
@app_commands.check(high_mod_check)
@app_commands.default_permissions(ban_members=True)
async def ban(i: discord.Interaction, tag: discord.Member, indok: str):
    await tag.ban(reason=indok)
    await i.response.send_message(embed=make_embed("🚫 Kitiltás", f"👤 {tag.mention}\n📄 Indok: {indok}\n👮‍♂️ Intézkedett: {i.user.mention}", discord.Color.dark_red()))

# ================= EGYÉB =================

@bot.tree.command(name="videó")
@app_commands.check(mod_check)
async def video(i: discord.Interaction, szoveg: str, video: discord.Attachment):
    await i.response.defer()
    data = load_json(VIDEO_FILE)
    data["count"] = data.get("count", 149) + 1
    save_json(VIDEO_FILE, data)
    await i.followup.send(content=f"**{data['count']}. Sikeres trade bizonyíték**\n{szoveg}", file=await video.to_file())

@bot.tree.error
async def on_app_command_error(i: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CheckFailure):
        if not i.response.is_done(): await i.response.send_message("❌ **Ezt a parancsot nem áll jogodban használni!**", ephemeral=True)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Bot online: {bot.user}")

if TOKEN: bot.run(TOKEN)
