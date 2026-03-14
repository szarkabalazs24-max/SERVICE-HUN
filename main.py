import discord
from discord.ext import commands
from discord import app_commands
import os, json, datetime, asyncio, random, re

TOKEN = os.getenv("DISCORD_TOKEN")

WARN_FILE = "warns.json"
WELCOME_FILE = "welcome.json"
LEAVE_FILE = "leave.json"
AUTO_ROLE_FILE = "autorole.json"

FORBIDDEN_WORDS = ["fasz","geci","buzi","bazdmeg","kurva","anyád","szar","szarka","Szarka","any@d","apád","cigány"]
LINK_REGEX = r"http[s]?://"

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ================= SEGÉD =================

def load_json(file):
    if not os.path.exists(file):
        return {}
    with open(file, "r", encoding="utf-8") as f:
        return json.load(f)

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
    e.set_footer(text="✨ SERVICE | HUN  ✨")
    return e

def mod_check(i: discord.Interaction):
    p = i.user.guild_permissions
    return p.administrator or p.manage_messages

# ================= READY =================

@bot.event
async def on_ready():
    await bot.tree.sync()
    print("✅ Bot online")

# ================= AUTOMOD =================

@bot.event
async def on_message(msg):
    if msg.author.bot:
        return

    txt = msg.content.lower()

    if re.search(LINK_REGEX, txt):
        await msg.delete()
        await msg.author.timeout(datetime.timedelta(minutes=10))
        return

    if any(w in txt for w in FORBIDDEN_WORDS):
        await msg.delete()

    await bot.process_commands(msg)

# ================= BELÉPÉS / KILÉPÉS =================

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
            f"👋 {member.mention}\n"
            f"Te vagy a **{member.guild.member_count}. tag**!"
        )

@bot.event
async def on_member_remove(member):
    data = load_json(LEAVE_FILE)
    ch = member.guild.get_channel(data.get("channel_id", 0))
    if ch:
        await ch.send(f"🚪 Kilépett: **{member.name}**")

# ================= BEÁLLÍTÁS =================

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

# ================= FIGYELMEZTETÉS =================

@bot.tree.command(name="figyelmeztetés")
@app_commands.check(mod_check)
async def warn(i: discord.Interaction, tag: discord.Member, indok: str):
    data = load_json(WARN_FILE)
    data.setdefault(str(tag.id), []).append(indok)
    save_json(WARN_FILE, data)

    await i.response.send_message(
        embed=make_embed(
            "⚠️ Figyelmeztetés",
            f"👤 {tag.mention}\n"
            f"📄 {indok}\n"
            f"📊 Összes: {len(data[str(tag.id)])}\n"
            f"👮‍♂️ Intézkedett: {i.user.mention}",
            discord.Color.orange()
        )
    )

@bot.tree.command(name="figyelmeztetés_törlés")
@app_commands.check(mod_check)
async def warn_del(i: discord.Interaction, tag: discord.Member, szám: int):
    data = load_json(WARN_FILE)
    warns = data.get(str(tag.id), [])

    if szám < 1 or szám > len(warns):
        return await i.response.send_message("❌ Hibás sorszám", ephemeral=True)

    warns.pop(szám - 1)
    save_json(WARN_FILE, data)

    await i.response.send_message(
        embed=make_embed(
            "🧹 Figyelmeztetés törölve",
            f"👤 {tag.mention}\n"
            f"📉 Maradt: {len(warns)}\n"
            f"👮‍♂️ Intézkedett: {i.user.mention}",
            discord.Color.green()
        )
    )

# ================= NÉMÍTÁS =================

@bot.tree.command(name="némítás")
@app_commands.check(mod_check)
async def mute(i: discord.Interaction, tag: discord.Member, perc: int, indok: str):
    await tag.timeout(datetime.timedelta(minutes=perc), reason=indok)

    await i.response.send_message(
        embed=make_embed(
            "🔇 Némítás",
            f"👤 {tag.mention}\n"
            f"⏱ {perc} perc\n"
            f"📄 {indok}\n"
            f"👮‍♂️ Intézkedett: {i.user.mention}",
            discord.Color.red()
        )
    )

@bot.tree.command(name="némítás_feloldás")
@app_commands.check(mod_check)
async def unmute(i: discord.Interaction, tag: discord.Member):
    await tag.timeout(None)

    await i.response.send_message(
        embed=make_embed(
            "🔊 Némítás feloldva",
            f"👤 {tag.mention}\n"
            f"👮‍♂️ Intézkedett: {i.user.mention}",
            discord.Color.green()
        )
    )

# ================= KITILTÁS =================

@bot.tree.command(name="kirúgás")
@app_commands.check(mod_check)
async def kick(i: discord.Interaction, tag: discord.Member, indok: str):
    await tag.kick(reason=indok)
    await i.response.send_message(
        embed=make_embed(
            "👢 Kirúgás",
            f"{tag.mention}\n📄 {indok}\n👮‍♂️ {i.user.mention}",
            discord.Color.orange()
        )
    )

@bot.tree.command(name="kitiltás")
@app_commands.check(mod_check)
async def ban(i: discord.Interaction, tag: discord.Member, indok: str):
    await tag.ban(reason=indok)
    await i.response.send_message(
        embed=make_embed(
            "🚫 Kitiltás",
            f"{tag.mention}\n📄 {indok}\n👮‍♂️ {i.user.mention}",
            discord.Color.dark_red()
        )
    )

@bot.tree.command(name="id_kitiltás")
@app_commands.check(mod_check)
async def idban(i: discord.Interaction, uid: str, indok: str):
    user = await bot.fetch_user(int(uid))
    await i.guild.ban(user, reason=indok)
    await i.response.send_message(
        embed=make_embed(
            "🚫 ID kitiltás",
            f"🆔 {uid}\n📄 {indok}\n👮‍♂️ {i.user.mention}",
            discord.Color.dark_red()
        )
    )

# ================= START =================

bot.run(TOKEN)
