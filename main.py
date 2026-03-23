import discord
from discord.ext import commands
from discord import app_commands
import os, json, datetime, asyncio, random, re

# ================== KONFIGURÁCIÓ (ÍRD ÁT AZ ID-KAT!) ==================

TOKEN = os.getenv("DISCORD_TOKEN")

# IDE MÁSOLD BE A RANGOK ID-JÁT!
TESTER_MOD_ID = 123456789012345678  # [⏰] TESTER MODERÁTOR ID
MOD_ID = 876543210987654321         # [🧨] MODERÁTOR ID

WARN_FILE = "warns.json"
WELCOME_FILE = "welcome.json"
LEAVE_FILE = "leave.json"
AUTO_ROLE_FILE = "autorole.json"
VIDEO_FILE = "videos.json"

FORBIDDEN_WORDS = ["fasz","geci","buzi","bazdmeg","kurva","anyád","szar","szarka","any@d","apád","cigány","cigany","barom","anyad"]
LINK_REGEX = r"http[s]?://"

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ================= SEGÉD / JOGOSULTSÁGOK =================

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

# ================= ESEMÉNYEK =================

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Bot online: {bot.user}")

@bot.event
async def on_message(msg):
    if msg.author.bot or not msg.guild: return
    is_mod = msg.author.guild_permissions.administrator or msg.author.guild_permissions.manage_messages
    txt = msg.content.lower()
    uid = str(msg.author.id)

    if not is_mod and (re.search(LINK_REGEX, txt) or any(w in txt for w in FORBIDDEN_WORDS)):
        await msg.delete()
        data = load_json(WARN_FILE)
        data.setdefault(uid, []).append("Automata szűrés")
        save_json(WARN_FILE, data)
        mute_time = len(data[uid]) * 2
        await msg.author.timeout(datetime.timedelta(minutes=mute_time))
        return
    await bot.process_commands(msg)

@bot.event
async def on_member_join(member):
    ar = load_json(AUTO_ROLE_FILE)
    role = member.guild.get_role(ar.get("role_id", 0))
    if role: await member.add_roles(role)

# ================= BEÁLLÍTÁSOK =================

@bot.tree.command(name="üdvözlő_beállítás")
@app_commands.check(mod_check)
async def welcome_set(i: discord.Interaction, csatorna: discord.TextChannel):
    save_json(WELCOME_FILE, {"channel_id": csatorna.id})
    await i.response.send_message("✅ Beállítva", ephemeral=True)

@bot.tree.command(name="kilépő_beállítás")
@app_commands.check(mod_check)
async def leave_set(i: discord.Interaction, csatorna: discord.TextChannel):
    save_json(LEAVE_FILE, {"channel_id": csatorna.id})
    await i.response.send_message("✅ Beállítva", ephemeral=True)

@bot.tree.command(name="autorole_beállítás")
@app_commands.check(mod_check)
async def autorole_set(i: discord.Interaction, rang: discord.Role):
    save_json(AUTO_ROLE_FILE, {"role_id": rang.id})
    await i.response.send_message("✅ Beállítva", ephemeral=True)

# ================= MODERÁCIÓ =================

@bot.tree.command(name="figyelmeztetés")
@app_commands.check(mod_check)
async def warn(i: discord.Interaction, tag: discord.Member, indok: str):
    data = load_json(WARN_FILE)
    data.setdefault(str(tag.id), []).append(indok)
    save_json(WARN_FILE, data)
    mute_time = len(data[str(tag.id)]) * 2
    await tag.timeout(datetime.timedelta(minutes=mute_time))
    await i.response.send_message(embed=make_embed("⚠️ Figyelmeztetés", f"👤 {tag.mention}\n📄 {indok}", discord.Color.orange()))

@bot.tree.command(name="figyelmeztetés_törlés")
@app_commands.check(mod_check)
async def warn_del(i: discord.Interaction, tag: discord.Member, szám: int):
    data = load_json(WARN_FILE)
    warns = data.get(str(tag.id), [])
    if 0 < szám <= len(warns):
        warns.pop(szám - 1)
        save_json(WARN_FILE, data)
        await i.response.send_message("🧹 Törölve", ephemeral=True)

@bot.tree.command(name="némítás")
@app_commands.check(mod_check)
async def mute(i: discord.Interaction, tag: discord.Member, perc: int, indok: str):
    await tag.timeout(datetime.timedelta(minutes=perc))
    await i.response.send_message(embed=make_embed("🔇 Némítás", f"👤 {tag.mention}\n⏱ {perc} perc", discord.Color.red()))

@bot.tree.command(name="némítás_feloldás")
@app_commands.check(mod_check)
async def unmute(i: discord.Interaction, tag: discord.Member):
    await tag.timeout(None)
    await i.response.send_message(f"🔊 {tag.mention} feloldva.")

# ================= SPECIÁLIS TILTÁS / KIRÚGÁS =================

@bot.tree.command(name="kirúgás")
@app_commands.check(high_mod_check)
@app_commands.default_permissions(kick_members=True)
async def kick(i: discord.Interaction, tag: discord.Member, indok: str):
    await tag.kick(reason=indok)
    await i.response.send_message(embed=make_embed("👢 Kirúgás", f"{tag.mention}\n📄 {indok}", discord.Color.orange()))

@bot.tree.command(name="kitiltás")
@app_commands.check(high_mod_check)
@app_commands.default_permissions(ban_members=True)
async def ban(i: discord.Interaction, tag: discord.Member, indok: str):
    await tag.ban(reason=indok)
    await i.response.send_message(embed=make_embed("🚫 Kitiltás", f"{tag.mention}\n📄 {indok}", discord.Color.dark_red()))

# ================= VIDEÓ TRADE =================

@bot.tree.command(name="videó")
@app_commands.check(mod_check)
async def video(i: discord.Interaction, szoveg: str, video: discord.Attachment):
    await i.response.defer()
    data = load_json(VIDEO_FILE)
    data["count"] = data.get("count", 147) + 1
    save_json(VIDEO_FILE, data)
    await i.followup.send(content=f"**{data['count']}. sikeres trade bizonyíték**\n{szoveg}", file=await video.to_file())

# ================= HIBAKEZELŐ (A KÉRT ÜZENETTEL) =================

@bot.tree.error
async def on_app_command_error(i: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CheckFailure):
        # Ez az üzenet jelenik meg a sima modoknak/tagoknak:
        await i.response.send_message("❌ **Ezt a parancsot nem áll jogodban használni!**", ephemeral=True)

if TOKEN:
    bot.run(TOKEN)
