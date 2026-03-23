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

FORBIDDEN_WORDS = [
    "fasz","geci","buzi","bazdmeg","kurva","anyád","szar",
    "szarka","any@d","apád","cigány","fos","kutya","rák","barom","bazmeg","cigany"
]
LINK_REGEX = r"http[s]?://"

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ================== SEGÉD ==================

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
    e.set_footer(text="✨ SERVICE | HUN ✨")
    return e

def mod_check(i: discord.Interaction):
    if not i.guild:
        return False
    perms = i.user.guild_permissions
    return perms.administrator or perms.manage_messages

# ================== READY ==================

@bot.event
async def on_ready():
    await bot.tree.sync()
    print("✅ Slash parancsok szinkronizálva (Railway)")
    print(f"✅ Bot online: {bot.user}")

# ================== AUTOMOD ==================

@bot.event
async def on_message(msg):
    if msg.author.bot or not msg.guild:
        return

    is_mod = (
        msg.author.guild_permissions.administrator
        or msg.author.guild_permissions.manage_messages
    )

    txt = msg.content.lower()
    uid = str(msg.author.id)

    # LINK SZŰRŐ
    if not is_mod and re.search(LINK_REGEX, txt):
        await msg.delete()
        data = load_json(WARN_FILE)
        data.setdefault(uid, []).append("Tiltott link küldése")
        save_json(WARN_FILE, data)

        mute_time = len(data[uid]) * 2
        await msg.author.timeout(datetime.timedelta(minutes=mute_time))

        await msg.channel.send(
            embed=make_embed(
                "🔗 Automatikus figyelmeztetés",
                f"👤 {msg.author.mention}\n"
                f"📄 Indok: Tiltott link\n"
                f"⚠️ Figyelmeztetések: {len(data[uid])}\n"
                f"🔇 Némítás: {mute_time} perc",
                discord.Color.red()
            )
        )
        return

    # KÁROMKODÁS
    if any(w in txt for w in FORBIDDEN_WORDS):
        await msg.delete()
        data = load_json(WARN_FILE)
        data.setdefault(uid, []).append("Káromkodás")
        save_json(WARN_FILE, data)

        mute_time = len(data[uid]) * 2
        await msg.author.timeout(datetime.timedelta(minutes=mute_time))

        await msg.channel.send(
            embed=make_embed(
                "🤬 Automatikus figyelmeztetés",
                f"👤 {msg.author.mention}\n"
                f"📄 Indok: Káromkodás\n"
                f"⚠️ Figyelmeztetések: {len(data[uid])}\n"
                f"🔇 Némítás: {mute_time} perc",
                discord.Color.orange()
            )
        )
        return

    
    # ⬇⬇⬇ EZ FONTOS ⬇⬇⬇
    await bot.process_commands(msg)
  
# ================== BELÉPÉS / KILÉPÉS ==================

@bot.event
async def on_member_join(member):
    ar = load_json(AUTO_ROLE_FILE)
    role = member.guild.get_role(ar.get("role_id", 0))
    if role:
        await member.add_roles(role)

    data = load_json(WELCOME_FILE)
    ch = member.guild.get_channel(data.get("channel_id", 0))
    if ch:
        await ch.send(
            f"👋 Üdv a szerveren {member.mention}!\n"
            f"Te vagy a {member.guild.member_count}. tag 💙"
        )

@bot.event
async def on_member_remove(member):
    data = load_json(LEAVE_FILE)
    ch = member.guild.get_channel(data.get("channel_id", 0))
    if ch:
        await ch.send(
            f"🚪 {member.name} kilépett a szerverről.\n"
            f"Köszönjük, hogy itt voltál!"
        )

# ================== BEÁLLÍTÁS ==================

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

# ================== FIGYELMEZTETÉS ==================

@bot.tree.command(name="figyelmeztetés")
@app_commands.check(mod_check)
async def warn(i: discord.Interaction, tag: discord.Member, indok: str):
    data = load_json(WARN_FILE)
    data.setdefault(str(tag.id), []).append(indok)
    save_json(WARN_FILE, data)
    await i.response.send_message(
        f"⚠️ {tag.mention} figyelmeztetve.\nIndok: {indok}",
        ephemeral=True
    )

# ================== INDÍTÁS ==================

bot.run(TOKEN)
