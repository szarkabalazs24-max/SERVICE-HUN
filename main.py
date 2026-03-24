import discord
from discord.ext import commands
from discord import app_commands, ui
import os, json, datetime, asyncio, random, re, sqlite3
from collections import defaultdict

# ================== KONFIGURÁCIÓ ==================

TOKEN = os.getenv("DISCORD_TOKEN")

# RANG ID-K (A megadott értékeid)
TESTER_MOD_ID = 1485380635442020352  # [⏰] TESTER MODERÁTOR
MOD_ID = 1462561594473975969         # [🧨] MODERÁTOR

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
    return i.user.guild_permissions.administrator or TESTER_MOD_ID in user_role_ids or MOD_ID in user_role_ids

# ================= NYEREMÉNYJÁTÉK RENDSZER =================

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
            status = "❌ Eltávolítottalak a jelentkezők közül."
        else:
            c.execute("INSERT INTO participants VALUES (?, ?)", (msg_id, user_id))
            status = "✅ Sikeresen jelentkeztél!"
        conn.commit()
        c.execute("SELECT COUNT(*) FROM participants WHERE msg_id = ?", (msg_id,))
        count = c.fetchone()[0]; conn.close()
        embed = interaction.message.embeds[0]
        for i, field in enumerate(embed.fields):
            if "Jelentkezők" in field.name:
                embed.set_field_at(i, name="👤 Jelentkezők", value=f"**{count}** fő", inline=False)
        await interaction.message.edit(embed=embed)
        await interaction.response.send_message(status, ephemeral=True)

class GiveawayModal(ui.Modal, title='Nyereményjáték Beállítása'):
    duration = ui.TextInput(label='Időtartam (pl. 10m, 2h, 1d)', placeholder='30m', required=True)
    winner_count = ui.TextInput(label='Hány nyertes?', default='1', required=True)
    prize = ui.TextInput(label='Nyeremény', placeholder='Írd ide...', required=True)
    description = ui.TextInput(label='Leírás', style=discord.TextStyle.paragraph, required=False)

    async def on_submit(self, interaction: discord.Interaction):
        raw_time = self.duration.value.lower()
        seconds = 0
        try:
            if 'm' in raw_time: seconds = int(raw_time.replace('m', '')) * 60
            elif 'h' in raw_time: seconds = int(raw_time.replace('h', '')) * 3600
            elif 'd' in raw_time: seconds = int(raw_time.replace('d', '')) * 86400
            else: seconds = int(raw_time) * 60
        except: return await interaction.response.send_message("❌ Hibás időformátum!", ephemeral=True)

        end_ts = int((discord.utils.utcnow() + datetime.timedelta(seconds=seconds)).timestamp())
        embed = discord.Embed(title="🎁 NYEREMÉNYJÁTÉK", description=f"Nyeremény: **{self.prize.value}**", color=0x5865F2)
        embed.add_field(name="🏆 Nyertesek", value=f"{self.winner_count.value} fő", inline=True)
        embed.add_field(name="⏳ Vége", value=f"<t:{end_ts}:R>", inline=True)
        embed.add_field(name="👤 Jelentkezők", value="**0** fő", inline=False)
        if self.description.value: embed.add_field(name="📝 Leírás", value=self.description.value, inline=False)
        
        view = GiveawayButtons()
        await interaction.response.send_message(embed=embed, view=view)
        msg = await interaction.original_response()
        await asyncio.sleep(seconds)
        
        conn = sqlite3.connect('giveaway.db'); c = conn.cursor()
        c.execute("SELECT user_id FROM participants WHERE msg_id = ?", (str(msg.id),))
        users = [row[0] for row in c.fetchall()]; conn.close()
        if users:
            winners = random.sample(users, min(len(users), int(self.winner_count.value)))
            mentions = ", ".join([f"<@{w}>" for w in winners])
            await interaction.channel.send(f"🎊 **GRATULÁLUNK!** {mentions} megnyerte: **{self.prize.value}**!")
        else: await interaction.channel.send(f"😢 Senki nem jelentkezett a(z) **{self.prize.value}** játékra.")

# ================= BOT INDÍTÁSA =================

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
    uid = str(msg.author.id); txt = msg.content.lower()
    indok = None
    if not is_mod:
        if re.search(LINK_REGEX, txt): indok = "Tiltott link"
        elif any(w in txt for w in FORBIDDEN_WORDS): indok = "Káromkodás"
        else:
            now = datetime.datetime.now()
            user_messages[uid] = [t for t in user_messages[uid] if (now - t).seconds < 5]
            user_messages[uid].append(now)
            if len(user_messages[uid]) >= 5: indok = "Spamming"
    if indok:
        await msg.delete(); data = load_json(WARN_FILE)
        data.setdefault(uid, []).append({"indok": indok, "mod": "Automod", "ido": datetime.datetime.utcnow().isoformat()})
        save_json(WARN_FILE, data); await msg.author.timeout(datetime.timedelta(minutes=len(data[uid])*2))
        await msg.channel.send(embed=make_embed("🛑 Automod", f"{msg.author.mention} büntetve: {indok}\nFigyelmeztetések: {len(data[uid])}", 0xFF0000))
        return
    await bot.process_commands(msg)

@bot.event
async def on_member_join(member):
    ar = load_json(AUTO_ROLE_FILE); role = member.guild.get_role(ar.get("role_id", 0))
    if role: await member.add_roles(role)
    data = load_json(WELCOME_FILE); ch = member.guild.get_channel(data.get("channel_id", 0))
    if ch: await ch.send(f"👋 Üdv {member.mention}! Te vagy a {member.guild.member_count}. tag! 💙")

@bot.event
async def on_member_remove(member):
    data = load_json(LEAVE_FILE); ch = member.guild.get_channel(data.get("channel_id", 0))
    if ch: await ch.send(f"🚪 {member.name} elhagyta a szervert.")

# ================= BEÁLLÍTÁSOK =================

@bot.tree.command(name="üdvözlő_beállítás")
@app_commands.check(mod_check)
async def welcome_set(i, csatorna: discord.TextChannel):
    save_json(WELCOME_FILE, {"channel_id": csatorna.id}); await i.response.send_message("✅ Kész!", ephemeral=True)

@bot.tree.command(name="kilépő_beállítás")
@app_commands.check(mod_check)
async def leave_set(i, csatorna: discord.TextChannel):
    save_json(LEAVE_FILE, {"channel_id": csatorna.id}); await i.response.send_message("✅ Kész!", ephemeral=True)

@bot.tree.command(name="autorole_beállítás")
@app_commands.check(mod_check)
async def autorole_set(i, rang: discord.Role):
    save_json(AUTO_ROLE_FILE, {"role_id": rang.id}); await i.response.send_message("✅ Kész!", ephemeral=True)

# ================= MODERÁCIÓ =================

@bot.tree.command(name="figyelmeztetés_info")
@app_commands.check(mod_check)
async def warn_info(i, tag: discord.Member):
    data = load_json(WARN_FILE); warns = data.get(str(tag.id), [])
    if not warns: return await i.response.send_message("✅ Nincs figyelmeztetése.", ephemeral=True)
    desc = ""
    for idx, w in enumerate(warns, 1):
        try:
            diff = datetime.datetime.utcnow() - datetime.datetime.fromisoformat(w['ido'])
            napja = f"{diff.days} napja" if diff.days > 0 else "ma"
        except: napja = "régen"
        desc += f"**{idx}.** `{w['indok']}` (Mod: {w['mod']}, Mikor: {napja})\n"
    await i.response.send_message(embed=make_embed(f"⚠️ {tag.name} figyelmeztetései", desc, 0x0000FF))

@bot.tree.command(name="figyelmeztetés")
@app_commands.check(mod_check)
async def warn(i, tag: discord.Member, indok: str):
    data = load_json(WARN_FILE); uid = str(tag.id)
    data.setdefault(uid, []).append({"indok": indok, "mod": str(i.user), "ido": datetime.datetime.utcnow().isoformat()})
    save_json(WARN_FILE, data); await tag.timeout(datetime.timedelta(minutes=len(data[uid])*2))
    await i.response.send_message(embed=make_embed("⚠️ Figyelmeztetés", f"{tag.mention} figyelmeztetve: {indok}\nÖsszesen: {len(data[uid])}", 0xFFA500))

@bot.tree.command(name="figyelmeztetés_törlés")
@app_commands.check(mod_check)
async def warn_del(i, tag: discord.Member, szám: int):
    data = load_json(WARN_FILE); warns = data.get(str(tag.id), [])
    if 0 < szám <= len(warns):
        warns.pop(szám - 1); save_json(WARN_FILE, data)
        await i.response.send_message("🧹 Törölve!", ephemeral=True)
    else: await i.response.send_message("❌ Hibás sorszám!", ephemeral=True)

@bot.tree.command(name="némítás")
@app_commands.check(mod_check)
async def mute(i, tag: discord.Member, perc: int, indok: str):
    await tag.timeout(datetime.timedelta(minutes=perc))
    await i.response.send_message(embed=make_embed("🔇 Némítás", f"{tag.mention} némítva {perc} percre. Indok: {indok}", 0xFF0000))

@bot.tree.command(name="némítás_feloldás")
@app_commands.check(mod_check)
async def unmute(i, tag: discord.Member):
    await tag.timeout(None); await i.response.send_message("🔊 Némítás feloldva!", ephemeral=True)

# ================= SZIGORÚ JOGOK =================

@bot.tree.command(name="kirúgás")
@app_commands.check(high_mod_check)
async def kick(i, tag: discord.Member, indok: str):
    await tag.kick(reason=indok); await i.response.send_message(f"👢 {tag.name} kirúgva.")

@bot.tree.command(name="kitiltás")
@app_commands.check(high_mod_check)
async def ban(i, tag: discord.Member, indok: str):
    await tag.ban(reason=indok); await i.response.send_message(f"🚫 {tag.name} kitiltva.")

# ================= NYEREMÉNYJÁTÉK PARANCSOK =================

@bot.tree.command(name="nyeremenyjatek")
@app_commands.check(mod_check)
async def giveaway_start(interaction: discord.Interaction):
    await interaction.response.send_modal(GiveawayModal())

@bot.tree.command(name="reroll")
@app_commands.check(mod_check)
async def reroll(interaction: discord.Interaction, uzenet_id: str):
    conn = sqlite3.connect('giveaway.db'); c = conn.cursor()
    c.execute("SELECT user_id FROM participants WHERE msg_id = ?", (uzenet_id,))
    users = [row[0] for row in c.fetchall()]; conn.close()
    if users: await interaction.response.send_message(f"🎲 Új nyertes: <@{random.choice(users)}>! 🎉")
    else: await interaction.response.send_message("❌ Nincs jelentkező.", ephemeral=True)

# ================= VIDEÓ TRADE =================

@bot.tree.command(name="videó")
@app_commands.check(mod_check)
async def video(i, szoveg: str, video: discord.Attachment):
    await i.response.defer(); data = load_json(VIDEO_FILE)
    data["count"] = data.get("count", 149) + 1; save_json(VIDEO_FILE, data)
    await i.followup.send(content=f"**{data['count']}. Sikeres trade**\n{szoveg}", file=await video.to_file())

@bot.tree.error
async def on_error(i, error):
    if isinstance(error, app_commands.CheckFailure):
        await i.response.send_message("❌ Nincs jogod ehhez!", ephemeral=True)

if TOKEN: bot.run(TOKEN)
  
