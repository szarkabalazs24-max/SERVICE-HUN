import discord
from discord.ext import commands
from discord import app_commands, ui
import os, json, datetime, asyncio, random, re, sqlite3
from collections import defaultdict

# ================== KONFIGURÁCIÓ ==================

TOKEN = os.getenv("DISCORD_TOKEN")

# TILTOTT RANGOK A BAN/KICK HASZNÁLATÁBÓL
TESTER_MOD_ID = 1485380635442020352
MOD_ID = 1462561594473975969

WARN_FILE = "warns.json"
WELCOME_FILE = "welcome.json"
LEAVE_FILE = "leave.json"
AUTO_ROLE_FILE = "autorole.json"
VIDEO_FILE = "videos.json"

FORBIDDEN_WORDS = ["fasz","geci","buzi","bazdmeg","kurva","anyád","szar","szarka","any@d","apád","cigány","cigany","barom"]
LINK_REGEX = r"http[s]?://"

user_messages = defaultdict(list)

# --- ADATBÁZIS ---
def init_db():
    conn = sqlite3.connect('giveaway.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS participants 
                      (msg_id TEXT, user_id TEXT, UNIQUE(msg_id, user_id))''')
    conn.commit()
    conn.close()

init_db()

intents = discord.Intents.all()

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
    if TESTER_MOD_ID in user_role_ids or MOD_ID in user_role_ids:
        return False
    return i.user.guild_permissions.administrator

def parse_duration(duration_str):
    raw_time = duration_str.lower()
    seconds = 0
    try:
        if 'm' in raw_time: seconds = int(raw_time.replace('m', '')) * 60
        elif 'h' in raw_time: seconds = int(raw_time.replace('h', '')) * 3600
        elif 'd' in raw_time: seconds = int(raw_time.replace('d', '')) * 86400
        else: seconds = int(raw_time) * 60
        return seconds
    except:
        return None

# ================= NYEREMÉNYJÁTÉK MODUL =================

class GiveawayButtons(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Jelentkezem!", style=discord.ButtonStyle.primary, custom_id="toggle_join_btn")
    async def toggle_join(self, interaction: discord.Interaction, button: ui.Button):
        msg_id, user_id = str(interaction.message.id), str(interaction.user.id)
        conn = sqlite3.connect('giveaway.db'); c = conn.cursor()
        c.execute("SELECT * FROM participants WHERE msg_id = ? AND user_id = ?", (msg_id, user_id))
        if c.fetchone():
            c.execute("DELETE FROM participants WHERE msg_id = ? AND user_id = ?", (msg_id, user_id))
            status = "❌ Sikeresen törölted a jelentkezésedet!."
        else:
            c.execute("INSERT INTO participants VALUES (?, ?)", (msg_id, user_id))
            status = "✅ Sikeresen jelentkeztél a játékra!"
        conn.commit()
        c.execute("SELECT COUNT(*) FROM participants WHERE msg_id = ?", (msg_id,))
        count = c.fetchone(); conn.close()
        
        embed = interaction.message.embeds[0]
        for idx, field in enumerate(embed.fields):
            if "Jelentkezők" in field.name:
                embed.set_field_at(idx, name="👤 Jelentkezők", value=f"**{count}** fő", inline=False)
                break
        await interaction.message.edit(embed=embed)
        await interaction.response.send_message(status, ephemeral=True)

class GiveawayModal(ui.Modal, title='Nyereményjáték Beállítása'):
    duration = ui.TextInput(label='Mennyi ideig tartson? (pl. 10m, 2h, 1d)', placeholder='Pl. 30m', required=True)
    winner_count = ui.TextInput(label='Hány nyertes legyen?', default='1', required=True)
    prize = ui.TextInput(label='Mi a nyeremény?', placeholder='Írd ide a nyereményt!', required=True)
    description = ui.TextInput(label='Leírás', style=discord.TextStyle.paragraph, required=False, max_length=1000)

    async def on_submit(self, interaction: discord.Interaction):
        seconds = parse_duration(self.duration.value)
        if seconds is None: return await interaction.response.send_message("❌ Hibás időformátum!", ephemeral=True)

        end_timestamp = int((discord.utils.utcnow() + datetime.timedelta(seconds=seconds)).timestamp())
        embed = discord.Embed(title="🎁 NYEREMÉNYJÁTÉK ELINDULT", description=f"Nyeremény: **{self.prize.value}**", color=0x5865F2)
        if self.description.value: embed.add_field(name="📝 Leírás", value=self.description.value, inline=False)
        embed.add_field(name="🏆 Nyertesek", value=f"{self.winner_count.value} fő", inline=True)
        embed.add_field(name="⏳ Hátralévő idő", value=f"<t:{end_timestamp}:R> múlva ér véget", inline=True)
        embed.add_field(name="👤 Jelentkezők", value="**0** fő", inline=False)
        embed.set_footer(text="Kattints a gombra a jelentkezéshez vagy leiratkozáshoz! 🎉")

        view = GiveawayButtons()
        await interaction.response.send_message(embed=embed, view=view)
        msg = await interaction.original_response()

        try:
            dm_embed = discord.Embed(title="🎫 Nyereményjáték Létrehozva", color=discord.Color.green())
            dm_embed.add_field(name="🆔 Nyereményjáték ID", value=f"`{msg.id}`", inline=False)
            dm_embed.set_footer(text="Ezt az ID-t használd a /reroll parancshoz!")
            await interaction.user.send(embed=dm_embed)
        except: pass

        await asyncio.sleep(seconds)
        conn = sqlite3.connect('giveaway.db'); c = conn.cursor()
        c.execute("SELECT user_id FROM participants WHERE msg_id = ?", (str(msg.id),))
        users = [row[0] for row in c.fetchall()]; conn.close()
        
        if users:
            winners = random.sample(users, min(len(users), int(self.winner_count.value)))
            mentions = ", ".join([f"<@{w}>" for w in winners])
            await interaction.channel.send(f"🎊 **GRATULÁLUNK!** {mentions} megnyerte a következőt: **{self.prize.value}**! 🏆")
        else: await interaction.channel.send(f"😢 A(z) **{self.prize.value}** sorsolása sikertelen (nincs jelentkező).")

# ================= BOT SETUP =================

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
    async def setup_hook(self):
        self.add_view(GiveawayButtons())
        await self.tree.sync()

bot = MyBot()

# ================= AUTOMOD & ESEMÉNYEK =================

@bot.event
async def on_message(msg):
    if msg.author.bot or not msg.guild: return
    is_mod = msg.author.guild_permissions.administrator or msg.author.guild_permissions.manage_messages
    uid, txt = str(msg.author.id), msg.content.lower()
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
        await msg.delete(); data = load_json(WARN_FILE); now = datetime.datetime.utcnow().isoformat()
        data.setdefault(uid, []).append({"indok": indok, "mod": "Rendszer (Automod)", "ido": now})
        save_json(WARN_FILE, data); mute_time = len(data[uid]) * 2
        await msg.author.timeout(datetime.timedelta(minutes=mute_time))
        await msg.channel.send(embed=make_embed("🛑 Automatikus figyelmeztetés", f"👤 **Tag:** {msg.author.mention}\n📄 **Indok:** {indok}\n⚠️ **Figyelmeztetések:** {len(data[uid])}\n🔇 **Némítás:** {mute_time} perc\n👮‍♂️ **Intézkedett:** Rendszer (Automod)", discord.Color.red()))
        return
    await bot.process_commands(msg)

@bot.event
async def on_member_join(member):
    ar = load_json(AUTO_ROLE_FILE); role = member.guild.get_role(ar.get("role_id", 0))
    if role: await member.add_roles(role)
    data = load_json(WELCOME_FILE); ch = member.guild.get_channel(data.get("channel_id", 0))
    if ch: await ch.send(f"👋 Üdvözlünk a szerveren {member.mention}! Érezd jól magad! Te vagy a(z) {member.guild.member_count}. tag ❤️‍🔥")

@bot.event
async def on_member_remove(member):
    data = load_json(LEAVE_FILE); ch = member.guild.get_channel(data.get("channel_id", 0))
    if ch: await ch.send(f"🚪 {member.name} ({member.mention} kilépett a szerverről.\nKöszönjük, hogy itt voltál!")

# ================= PARANCSOK =================

@bot.tree.command(name="figyelmeztetés")
@app_commands.check(mod_check)
async def warn(i, tag: discord.Member, indok: str):
    data = load_json(WARN_FILE); uid = str(tag.id); now = datetime.datetime.utcnow().isoformat()
    data.setdefault(uid, []).append({"indok": indok, "mod": str(i.user), "ido": now})
    save_json(WARN_FILE, data); mute_time = len(data[uid]) * 2
    await tag.timeout(datetime.timedelta(minutes=mute_time))
    await i.response.send_message(embed=make_embed("⚠️ Figyelmeztetés", f"👤 {tag.mention}\n📄 {indok}\n⚠️ Összes: {len(data[uid])}\n🔇 Némítás: {mute_time} perc\n👮‍♂️ Intézkedett: {i.user.mention}", discord.Color.orange()))

@bot.tree.command(name="némítás")
@app_commands.check(mod_check)
@app_commands.describe(időtartam="Pl. 10m, 2h, 1d")
async def mute(i: discord.Interaction, tag: discord.Member, időtartam: str, indok: str):
    seconds = parse_duration(időtartam)
    if seconds is None: return await i.response.send_message("❌ Hibás időformátum! Használj m, h, vagy d betűt (pl: 30m, 2h, 1d).", ephemeral=True)
    
    await tag.timeout(datetime.timedelta(seconds=seconds))
    await i.response.send_message(embed=make_embed("🔇 Némítás", f"👤 {tag.mention}\n⏱ {időtartam}\n📄 {indok}\n👮‍♂️ intézkedett: {i.user.mention}", discord.Color.red()))

@bot.tree.command(name="kirúgás")
@app_commands.check(high_mod_check)
async def kick(i, tag: discord.Member, indok: str):
    await tag.kick(reason=indok); await i.response.send_message(embed=make_embed("👢 Kirúgás", f"👤 {tag.mention}\n📄 {indok}\n👮‍♂️intézkedett:{i.user.mention}", discord.Color.orange()))

@bot.tree.command(name="kitiltás")
@app_commands.check(high_mod_check)
async def ban(i, tag: discord.Member, indok: str):
    await tag.ban(reason=indok); await i.response.send_message(embed=make_embed("🚫 Kitiltás", f"👤 {tag.mention}\n📄 {indok}\n👮‍♂️intézkedett:{i.user.mention}", discord.Color.dark_red()))

@bot.tree.command(name="nyeremenyjatek")
@app_commands.check(mod_check)
async def start_giveaway(interaction: discord.Interaction):
    await interaction.response.send_modal(GiveawayModal())

@bot.tree.command(name="reroll")
@app_commands.check(mod_check)
async def reroll(interaction: discord.Interaction, uzenet_id: str):
    conn = sqlite3.connect('giveaway.db'); c = conn.cursor()
    c.execute("SELECT user_id FROM participants WHERE msg_id = ?", (uzenet_id,))
    users = [row[0] for row in c.fetchall()]; conn.close()
    if users: await interaction.response.send_message(f"🎲 **Újrasorsolás!** Az új nyertes: <@{random.choice(users)}>! 🎉")
    else: await interaction.response.send_message("❌ Nincs jelentkező.", ephemeral=True)

@bot.tree.command(name="figyelmeztetés_info")
@app_commands.check(mod_check)
async def warn_info(i, tag: discord.Member):
    data = load_json(WARN_FILE); warns = data.get(str(tag.id), [])
    if not warns: return await i.response.send_message(f"✅ {tag.mention}-nak nincs figyelmeztetése.", ephemeral=True)
    desc = ""
    for idx, w in enumerate(warns, 1):
        try:
            diff = datetime.datetime.utcnow() - datetime.datetime.fromisoformat(w['ido'])
            napja = f"{diff.days} napja" if diff.days > 0 else "ma"
        except: napja = "régen"
        desc += f"**{idx}.** `{w['indok']}`\n└ 👮‍♂️: {w['mod']} | 📅: {napja}\n\n"
    await i.response.send_message(embed=make_embed(f"⚠️ {tag.name} figyelmeztetései", desc, discord.Color.blue()))

@bot.tree.command(name="némítás_feloldás")
@app_commands.check(mod_check)
async def unmute(i, tag: discord.Member):
    await tag.timeout(None); await i.response.send_message(embed=make_embed("🔊 Némítás feloldva", f"👤 {tag.mention}\n👮‍♂️ {i.user.mention}", discord.Color.green()))

@bot.tree.command(name="figyelmeztetés_törlés")
@app_commands.check(mod_check)
async def warn_del(i, tag: discord.Member, szám: int):
    data = load_json(WARN_FILE); warns = data.get(str(tag.id), [])
    if 0 < szám <= len(warns):
        warns.pop(szám - 1); save_json(WARN_FILE, data)
        await i.response.send_message(embed=make_embed("🧹 Figyelmeztetés törölve", f"👤 {tag.mention}\n📉 Maradt: {len(warns)}\n👮‍♂️ Intézkedett: {i.user.mention}", discord.Color.green()))
    else: await i.response.send_message("❌ Érvénytelen sorszám!", ephemeral=True)

@bot.tree.command(name="üdvözlő_beállítás")
@app_commands.check(mod_check)
async def welcome_set(i, csatorna: discord.TextChannel):
    save_json(WELCOME_FILE, {"channel_id": csatorna.id}); await i.response.send_message("✅ Üdvözlő beállítva", ephemeral=True)

@bot.tree.command(name="kilépő_beállítás")
@app_commands.check(mod_check)
async def leave_set(i, csatorna: discord.TextChannel):
    save_json(LEAVE_FILE, {"channel_id": csatorna.id}); await i.response.send_message("✅ Kilépő beállítva", ephemeral=True)

@bot.tree.command(name="autorole_beállítás")
@app_commands.check(mod_check)
async def autorole_set(i, rang: discord.Role):
    save_json(AUTO_ROLE_FILE, {"role_id": rang.id}); await i.response.send_message("✅ Autorole beállítva", ephemeral=True)

@bot.tree.command(name="videó")
@app_commands.check(mod_check)
async def video(i, szoveg: str, video: discord.Attachment):
    await i.response.defer(); data = load_json(VIDEO_FILE)
    data["count"] = data.get("count", 147) + 1; save_json(VIDEO_FILE, data)
    await i.followup.send(content=f"**{data['count']}. Sikeres trade bizonyíték**\n{szoveg}", file=await video.to_file())

@bot.tree.error
async def on_app_command_error(i: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CheckFailure):
        if not i.response.is_done(): await i.response.send_message("❌ **Ezt a parancsot nem áll jogodban használni!**", ephemeral=True)

@bot.event
async def on_ready():
    await bot.tree.sync(); print(f"✅ Bot online: {bot.user}")

if TOKEN: bot.run(TOKEN)
  
