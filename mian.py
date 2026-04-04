import discord
from discord.ext import commands
from discord import app_commands, ui
import os, json, datetime, asyncio, random, re, sqlite3
from collections import defaultdict

# ================== KONFIGURÁCIÓ & RANGOK ==================

TOKEN = os.getenv("DISCORD_TOKEN")

# A TE SAJÁT ID-D (100% FIX)
OWNER_ID = 1394681197681971332 

# Moderátor rangok ID-jai
TESTER_MOD_ID = 1485380635442020352
MOD_ID = 1462561594473975969

# A 3 SPECIFIKUS RANG ID-JA A VIDEÓHOZ
MIDDLEMAN_ID = 1454586433292468235 # {🥉} | Middle Man (100M)
SENIOR_MM_ID = 1454586731528454308  # {🥈} | Senior Middleman (250M)
ELITE_MM_ID = 1454587037205135474   # {🥇} | Elite middleman (315M+-)

# --- RAILWAY VOLUME ÉS FIX TÁROLÁS BEÁLLÍTÁSA ---
PERSISTENT_DATA_PATH = "./data/"
if not os.path.exists(PERSISTENT_DATA_PATH):
    os.makedirs(PERSISTENT_DATA_PATH, exist_ok=True)

WARN_FILE = os.path.join(PERSISTENT_DATA_PATH, "warns.json")
WELCOME_FILE = os.path.join(PERSISTENT_DATA_PATH, "welcome.json")
LEAVE_FILE = os.path.join(PERSISTENT_DATA_PATH, "leave.json")
AUTO_ROLE_FILE = os.path.join(PERSISTENT_DATA_PATH, "autorole.json")
VIDEO_FILE = os.path.join(PERSISTENT_DATA_PATH, "videos.json")
LOG_FILE = os.path.join(PERSISTENT_DATA_PATH, "logs.json")
DB_FILE = os.path.join(PERSISTENT_DATA_PATH, "giveaway.db")

FORBIDDEN_WORDS = ["fasz","geci","buzi","bazdmeg","kurva","anyád","szar","szarka","any@d","apád","cigány","cigany","barom","bazmeg","pornó","porno","nyomorék","szopj","szopjle","kutya","apad","apád","hülye","fsz","gyász"]
LINK_REGEX = r"http[s]?://"
GIF_REGEX = r"https?://.*(?:tenor\.com|giphy\.com|.+\.gif)"

user_messages = defaultdict(list)

# --- ADATBÁZIS INICIALIZÁLÁSA ---
def init_db():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS participants 
                          (msg_id TEXT, user_id TEXT, UNIQUE(msg_id, user_id))''')
        conn.commit()
        conn.close()
    except:
        pass

init_db()

intents = discord.Intents.all()

# ================= SEGÉDFÜGGVÉNYEK =================

def parse_duration(duration_str):
    time_dict = {"d": 86400, "h": 3600, "m": 60}
    seconds = 0
    matches = re.findall(r"(\d+)([dhm])", duration_str.lower())
    
    display_parts = []
    for amount, unit in matches:
        amount = int(amount)
        seconds += amount * time_dict[unit]
        if unit == "d": display_parts.append(f"{amount} nap")
        elif unit == "h": display_parts.append(f"{amount} óra")
        elif unit == "m": display_parts.append(f"{amount} perc")
        
    if seconds == 0:
        try:
            val = int(duration_str)
            return val * 60, f"{val} perc"
        except: return 0, ""
        
    return seconds, ", ".join(display_parts)

def load_json(file):
    if not os.path.exists(file): return {}
    try:
        with open(file, "r", encoding="utf-8") as f:
            content = f.read()
            if not content: return {}
            return json.loads(content)
    except: return {}

def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f: json.dump(data, f, indent=4, ensure_ascii=False)

def make_embed(title, desc, color):
    e = discord.Embed(title=title, description=desc, color=color, timestamp=datetime.datetime.utcnow())
    e.set_footer(text="✨ SERVICE HUN ✨")
    return e

async def send_log(guild, embed):
    data = load_json(LOG_FILE)
    ch_id = data.get("log_channel")
    if ch_id:
        try:
            channel = guild.get_channel(int(ch_id))
            if channel: await channel.send(embed=embed)
        except: pass

# --- JOGOSULTSÁG ELLENŐRZŐK ---

def is_target_mod(member: discord.Member):
    user_role_ids = [role.id for role in member.roles]
    return member.guild_permissions.administrator or TESTER_MOD_ID in user_role_ids or MOD_ID in user_role_ids

def tester_and_up(i: discord.Interaction):
    user_role_ids = [role.id for role in i.user.roles]
    return i.user.guild_permissions.administrator or TESTER_MOD_ID in user_role_ids or MOD_ID in user_role_ids

def mod_and_up(i: discord.Interaction):
    user_role_ids = [role.id for role in i.user.roles]
    return i.user.guild_permissions.administrator or MOD_ID in user_role_ids

def admin_only_check(i: discord.Interaction):
    return i.user.guild_permissions.administrator

def video_check(i: discord.Interaction):
    user_role_ids = [role.id for role in i.user.roles]
    allowed_ids = [MIDDLEMAN_ID, SENIOR_MM_ID, ELITE_MM_ID]
    return i.user.guild_permissions.administrator or any(rid in user_role_ids for rid in allowed_ids)

# ================= NYEREMÉNYJÁTÉK RENDSZER =================

class GiveawayButtons(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Jelentkezem!", style=discord.ButtonStyle.primary, custom_id="toggle_join_btn")
    async def toggle_join(self, interaction: discord.Interaction, button: ui.Button):
        msg_id = str(interaction.message.id); user_id = str(interaction.user.id)
        conn = sqlite3.connect(DB_FILE); c = conn.cursor()
        c.execute("SELECT * FROM participants WHERE msg_id = ? AND user_id = ?", (msg_id, user_id))
        if c.fetchone():
            c.execute("DELETE FROM participants WHERE msg_id = ? AND user_id = ?", (msg_id, user_id))
            status_text = "❌ Sikeresen kiléptél a nyereményjátékból!"
        else:
            c.execute("INSERT INTO participants VALUES (?, ?)", (msg_id, user_id))
            status_text = "✅ Sikeresen jelentkeztél a nyereményjátékra!"
        conn.commit(); c.execute("SELECT COUNT(*) FROM participants WHERE msg_id = ?", (msg_id,))
        count_res = c.fetchone()
        count = count_res[0] if count_res else 0
        conn.close()
        embed = interaction.message.embeds[0]
        for idx, field in enumerate(embed.fields):
            if "Jelentkezők" in field.name:
                embed.set_field_at(idx, name="👤 Jelentkezők", value=f"**{count}** fő", inline=False)
                break
        await interaction.message.edit(embed=embed)
        await interaction.response.send_message(status_text, ephemeral=True)

class GiveawayModal(ui.Modal, title='Nyereményjáték Beállítása'):
    duration = ui.TextInput(label='Mennyi ideig tartson? (pl. 10m, 2h, 1d)', placeholder='Pl. 1d 2h 30m', required=True)
    winner_count = ui.TextInput(label='Hány nyertes legyen?', default='1', required=True)
    prize = ui.TextInput(label='Mi a nyeremény?', placeholder='Írd ide a nyereményt!', required=True)
    description = ui.TextInput(label='Leírás', style=discord.TextStyle.paragraph, required=False, max_length=1000)

    async def on_submit(self, interaction: discord.Interaction):
        seconds, human_readable = parse_duration(self.duration.value)
        if seconds <= 0:
            return await interaction.response.send_message("❌ Hibás időformátum!", ephemeral=True)

        end_timestamp = int((discord.utils.utcnow() + datetime.timedelta(seconds=seconds)).timestamp())
        
        embed = discord.Embed(title="🎁 NYEREMÉNYJÁTÉK ELINDULT", description=f"Nyeremény: **{self.prize.value}**", color=0x5865F2)
        if self.description.value: 
            embed.add_field(name="📝 Leírás", value=self.description.value, inline=False)
        embed.add_field(name="🏆 Nyertesek", value=f"{self.winner_count.value} fő", inline=True)
        embed.add_field(name="⏳ Időtartam", value=f"{human_readable} (<t:{end_timestamp}:R>)", inline=True)
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
        except:
            await interaction.followup.send(f"⚠️ ID: `{msg.id}` (DM-et nem tudtam küldeni)", ephemeral=True)

        await asyncio.sleep(seconds)
        await self.process_winners(interaction, self.prize.value, self.winner_count.value, msg.id, view)

    async def process_winners(self, interaction, prize, count, msg_id, view):
        conn = sqlite3.connect(DB_FILE); c = conn.cursor()
        c.execute("SELECT user_id FROM participants WHERE msg_id = ?", (str(msg_id),))
        users = [row[0] for row in c.fetchall()]; conn.close()
        for item in view.children: item.disabled = True
        try:
            msg = await interaction.channel.fetch_message(msg_id)
            old_embed = msg.embeds[0]
            old_embed.title = "🔒 NYEREMÉNYJÁTÉK LEZÁRULT"
            old_embed.color = discord.Color.dark_grey()
            for idx, field in enumerate(old_embed.fields):
                if "Időtartam" in field.name:
                    old_embed.set_field_at(idx, name="⏳ Állapot", value="Véget ért", inline=True)
            await msg.edit(embed=old_embed, view=view)
        except: pass
        if users:
            winners = random.sample(users, min(len(users), int(count)))
            mentions = ", ".join([f"<@{w}>" for w in winners])
            await interaction.channel.send(f"🎊 **GRATULÁLUNK!** {mentions} megnyerte a következőt: **{prize}**! 🏆")
        else: await interaction.channel.send(f"😢 A(z) **{prize}** sorsolása sikertelen (nem maradt jelentkező).")

# ================= BOT SETUP =================

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
    async def setup_hook(self):
        self.add_view(GiveawayButtons()); await self.tree.sync()

bot = MyBot()

# ================= ESEMÉNYEK & AUTOMOD =================

@bot.event
async def on_ready():
    print(f"✅ Bot online: {bot.user}")

@bot.event
async def on_message(msg):
    if msg.author.bot or not msg.guild: return
    is_mod = msg.author.guild_permissions.administrator or MOD_ID in [r.id for r in msg.author.roles]
    uid, txt = str(msg.author.id), msg.content.lower()

    if any(user.id == OWNER_ID for user in msg.mentions) and not is_mod:
        indok = "tulaj ping tilos"
        try: await msg.delete()
        except: pass
        data = load_json(WARN_FILE); now = datetime.datetime.utcnow().isoformat()
        data.setdefault(uid, []).append({"indok": indok, "mod": "Rendszer (Automod)", "ido": now})
        save_json(WARN_FILE, data); mute_time = len(data[uid]) * 2
        try: await msg.author.timeout(datetime.timedelta(minutes=mute_time), reason=indok)
        except: pass
        await msg.channel.send(embed=make_embed("🛑 Automatikus figyelmeztetés", f"👤 **Tag:** {msg.author.mention}\n📄 **Indok:** {indok}\n⚠️ **Figyelmeztetések:** {len(data[uid])}\n🔇 **Némítás:** {mute_time} perc\n👮‍♂️ **Intézkedett:** Rendszer (Automod)", discord.Color.red()))
        return

    if is_mod: return await bot.process_commands(msg)
    indok = None
    if re.search(LINK_REGEX, txt) or re.search(GIF_REGEX, txt): indok = "tiltott link vagy GIF küldése"
    elif any(w in txt for w in FORBIDDEN_WORDS): indok = "Káromkodás"
    else:
        now = datetime.datetime.now()
        user_messages[uid] = [t for t in user_messages[uid] if (now - t).seconds < 5]
        user_messages[uid].append(now)
        if len(user_messages[uid]) >= 5: indok = "Spamming (Túl sok üzenet)"
    if indok:
        try: await msg.delete()
        except: pass
        data = load_json(WARN_FILE); now = datetime.datetime.utcnow().isoformat()
        data.setdefault(uid, []).append({"indok": indok, "mod": "Rendszer (Automod)", "ido": now})
        save_json(WARN_FILE, data); mute_time = len(data[uid]) * 2
        try: await msg.author.timeout(datetime.timedelta(minutes=mute_time), reason=indok)
        except: pass
        await msg.channel.send(embed=make_embed("🛑 Automatikus figyelmeztetés", f"👤 **Tag:** {msg.author.mention}\n📄 **Indok:** {indok}\n⚠️ **Figyelmeztetések:** {len(data[uid])}\n🔇 **Némítás:** {mute_time} perc\n👮‍♂️ **Intézkedett:** Rendszer (Automod)", discord.Color.red()))
        return
    await bot.process_commands(msg)

@bot.event
async def on_member_join(member):
    ar = load_json(AUTO_ROLE_FILE); 
    role_id = ar.get("role_id")
    if role_id:
        try:
            role = member.guild.get_role(int(role_id))
            if role: await member.add_roles(role)
        except: pass
    data = load_json(WELCOME_FILE); 
    ch_id = data.get("channel_id")
    if ch_id:
        try:
            ch = member.guild.get_channel(int(ch_id))
            if ch: await ch.send(f"👋 Üdv a szerveren {member.mention}! Te vagy a(z) {member.guild.member_count}. tag 💙")
        except: pass

@bot.event
async def on_member_remove(member):
    data = load_json(LEAVE_FILE); 
    ch_id = data.get("channel_id")
    if ch_id:
        try:
            ch = member.guild.get_channel(int(ch_id))
            if ch: await ch.send(f"🚪 {member.mention} ({member.name}) kilépett a szerverről.\nKöszönjük, hogy itt voltál!")
        except: pass

@bot.event
async def on_message_delete(message):
    if message.author.bot: return
    await send_log(message.guild, make_embed("🗑️ Log: Üzenet Törölve", f"**Szerző:** {message.author.mention}\n**Csatorna:** {message.channel.mention}\n**Tartalom:**\n{message.content or '*Csak média*'}", discord.Color.orange()))

@bot.event
async def on_message_edit(before, after):
    if before.author.bot or before.content == after.content: return
    desc = f"**Szerző:** {before.author.mention}\n**Csatorna:** {before.channel.mention}\n**Régi:**\n{before.content}\n**Új:**\n{after.content}"
    await send_log(before.guild, make_embed("📝 Log: Üzenet Szerkesztve", desc, discord.Color.blue()))

# ================= MODERÁCIÓS PARANCSOK =================

@bot.tree.command(name="figyelmeztetés")
@app_commands.check(tester_and_up)
async def warn(i, tag: discord.Member, indok: str):
    if is_target_mod(tag): return await i.response.send_message("🛑 Moderátort nem figyelmeztethetsz!", ephemeral=False)
    data = load_json(WARN_FILE); uid = str(tag.id)
    data.setdefault(uid, []).append({"indok": indok, "mod": str(i.user), "ido": datetime.datetime.utcnow().isoformat()})
    save_json(WARN_FILE, data); mute_time = len(data[uid]) * 2
    await tag.timeout(datetime.timedelta(minutes=mute_time), reason=indok)
    await i.response.send_message(embed=make_embed("⚠️ Figyelmeztetés", f"👤 **tag:** {tag.mention}\n📄 **indok:** {indok}\n⚠️ **Összes figyelmeztetése**: {len(data[uid])}\n🔇 **Némítás:** {mute_time} perc\n👮‍♂️ **Intézkedett:** {i.user.mention}", discord.Color.orange()))

@bot.tree.command(name="némítás")
@app_commands.check(mod_and_up)
async def mute(i: discord.Interaction, tag: discord.Member, időtartam: str, indok: str):
    if is_target_mod(tag): return await i.response.send_message("🛑 Moderátort nem némíthatsz le!", ephemeral=False)
    sec, human_readable = parse_duration(időtartam)
    if sec == 0: return await i.response.send_message("❌ Érvénytelen időformátum! (Pl: 1d 2h 30m)", ephemeral=True)
    if sec > 2419200: return await i.response.send_message("❌ Maximum 28 napra némíthatsz!", ephemeral=True)
    await tag.timeout(datetime.timedelta(seconds=sec), reason=indok)
    await i.response.send_message(embed=make_embed("🔇 Némítás", f"👤 **tag:** {tag.mention}\n⏳ **Időtartam:** {human_readable}\n📄 **indok:** {indok}\n👮‍♂️ **intézkedett:** {i.user.mention}", discord.Color.red()))

@bot.tree.command(name="némítás_feloldás")
@app_commands.check(mod_and_up)
async def unmute(i, tag: discord.Member):
    await tag.timeout(None); await i.response.send_message(embed=make_embed("🔊 Némítás feloldva", f"👤 **tag:** {tag.mention}\n👮‍♂️ **intézkedett:** {i.user.mention}", discord.Color.green()))

@bot.tree.command(name="figyelmeztetés_info")
@app_commands.check(mod_and_up)
async def warn_info(i, tag: discord.Member):
    data = load_json(WARN_FILE); warns = data.get(str(tag.id), [])
    desc = "".join([f"**{idx+1}.** `{w['indok']}`\n└ 👮‍♂️: {w['mod']}\n" for idx, w in enumerate(warns)]) if warns else "Nincs figyelmeztetése."
    await i.response.send_message(embed=make_embed(f"⚠️ {tag.name} figyelmeztetései", desc, discord.Color.blue()))

@bot.tree.command(name="figyelmeztetés_törlés")
@app_commands.check(mod_and_up)
async def warn_del(i, tag: discord.Member, mennyiség: int):
    if mennyiség <= 0: return await i.response.send_message("❌ Kérlek, pozitív számot adj meg!", ephemeral=True)
    data = load_json(WARN_FILE); uid = str(tag.id); warns = data.get(uid, [])
    if not warns: return await i.response.send_message(f"❌ {tag.mention}-nak nincs figyelmeztetése.", ephemeral=True)
    torelendo = min(len(warns), mennyiség)
    for _ in range(torelendo): warns.pop()
    save_json(WARN_FILE, data)
    await i.response.send_message(embed=make_embed("🧹 Figyelmeztetések törölve", f"👤 **tag:** {tag.mention}\n📉 **Törölve:** {torelendo} db\n⚠️ **Maradt:** {len(warns)}\n👮‍♂️ **Intézkedett:** {i.user.mention}", discord.Color.green()))

@bot.tree.command(name="kirúgás")
@app_commands.check(admin_only_check)
async def kick(i, tag: discord.Member, indok: str):
    if is_target_mod(tag): return await i.response.send_message("🛑 Moderátort nem rúghatsz ki!", ephemeral=False)
    await tag.kick(reason=indok); await i.response.send_message(embed=make_embed("👢 Kirúgás", f"👤 **tag:** {tag.mention}\n📄 **indok:** {indok}\n👮‍♂️**intézkedett:** {i.user.mention}", discord.Color.orange()))

@bot.tree.command(name="kitiltás")
@app_commands.check(admin_only_check)
async def ban(i, tag: discord.Member, indok: str):
    if is_target_mod(tag): return await i.response.send_message("🛑 Moderátort nem tilthatsz ki!", ephemeral=False)
    await tag.ban(reason=indok); await i.response.send_message(embed=make_embed("🚫 Kitiltás", f"👤 **tag:** {tag.mention}\n📄 **indok:** {indok}\n👮‍♂️ **intézkedett:** {i.user.mention}", discord.Color.dark_red()))

# ================= BEÁLLÍTÁSOK (CSAK ADMIN) =================

@bot.tree.command(name="üdvözlő_beállítás")
@app_commands.check(admin_only_check)
async def welcome_set(i, csatorna: discord.TextChannel):
    save_json(WELCOME_FILE, {"channel_id": csatorna.id}); await i.response.send_message("✅ Üdvözlő csatorna beállítva.", ephemeral=True)

@bot.tree.command(name="kilépő_beállítás")
@app_commands.check(admin_only_check)
async def leave_set(i, csatorna: discord.TextChannel):
    save_json(LEAVE_FILE, {"channel_id": csatorna.id}); await i.response.send_message("✅ Kilépő csatorna beállítva.", ephemeral=True)

@bot.tree.command(name="autorole_beállítás")
@app_commands.check(admin_only_check)
async def autorole_set(i, rang: discord.Role):
    save_json(AUTO_ROLE_FILE, {"role_id": rang.id}); await i.response.send_message("✅ Autorole rang beállítva.", ephemeral=True)

@bot.tree.command(name="log_beállítás")
@app_commands.check(admin_only_check)
async def log_set(i, csatorna: discord.TextChannel):
    save_json(LOG_FILE, {"log_channel": csatorna.id}); await i.response.send_message("✅ Log csatorna beállítva.", ephemeral=True)

# ================= VIDEÓ & NYEREMÉNYJÁTÉK =================

@bot.tree.command(name="videó")
@app_commands.check(video_check)
async def video(i, szoveg: str, video: discord.Attachment):
    await i.response.defer(); data = load_json(VIDEO_FILE)
    data["count"] = data.get("count", 0) + 1; save_json(VIDEO_FILE, data)
    await i.followup.send(content=f"**{data['count']}. Sikeres trade bizonyíték**\n{szoveg}", file=await video.to_file())


@bot.tree.command(name="nyeremenyjatek")
@app_commands.check(admin_only_check)
async def start_giveaway(i: discord.Interaction):
    await i.response.send_modal(GiveawayModal())

@bot.tree.command(name="reroll")
@app_commands.check(admin_only_check)
async def reroll(i: discord.Interaction, msg_id: str):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("SELECT user_id FROM participants WHERE msg_id = ?", (msg_id,))
    users = [row[0] for row in c.fetchall()]; conn.close()
    if users:
        winner = random.choice(users)
        await i.response.send_message(f"🎉 **Új sorsolás!** Az új nyertes: <@{winner}>! 🏆")
    else: await i.response.send_message("❌ Nincs jelentkező ebben a játékban!", ephemeral=True)

# ================= INDÍTÁS =================
if __name__ == "__main__":
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("HIBA: DISCORD_TOKEN nem található!")
