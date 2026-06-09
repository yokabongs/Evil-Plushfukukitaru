import discord
from discord import app_commands
from discord.ext import commands
import os
import re
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
 
# ── Config ────────────────────────────────────────────────────────────────────
BOT_TOKEN      = os.environ["DISCORD_BOT_TOKEN"]
TARGET_USER_ID = int(os.environ["TARGET_USER_ID"])
OWNER_USER_ID  = int(os.environ["OWNER_USER_ID"])
PORT           = int(os.environ.get("PORT", 8080))
 
SLUR_PATTERN = re.compile(
    r"n[i1!|]+[g9q@]+[g9q@]*[aeiou\xE6@3uh]*[rz]*",
    re.IGNORECASE,
)
 
def contains_slur(text: str) -> bool:
    return bool(SLUR_PATTERN.search(text.replace(" ", "")))
 
live_count: dict[int, int] = {}
 
# ── Dummy HTTP server ─────────────────────────────────────────────────────────
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, *args):
        pass
 
threading.Thread(target=lambda: HTTPServer(("0.0.0.0", PORT), HealthHandler).serve_forever(), daemon=True).start()
 
# ── Bot setup ─────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
 
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree
 
# ── Events ────────────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    await tree.sync()
    print(f"Logged in as {bot.user} — tracking user ID {TARGET_USER_ID}")
 
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    if message.author.id != TARGET_USER_ID:
        return
    if not contains_slur(message.content):
        return
 
    guild_id = message.guild.id if message.guild else 0
    live_count[guild_id] = live_count.get(guild_id, 0) + 1
    n = live_count[guild_id]
 
    print(f"[{datetime.utcnow():%Y-%m-%d %H:%M:%S UTC}] #{message.channel} — count now {n}")
 
    await message.channel.send(
        f"lmaooo {message.author.mention} said it again, (#{n} all time)"
    )
 
    await bot.process_commands(message)
 
# ── /count ────────────────────────────────────────────────────────────────────
@tree.command(name="count", description="How many times has Alex said the n-word?")
async def slash_count(interaction: discord.Interaction):
    guild_id = interaction.guild_id or 0
    total = live_count.get(guild_id, 0)
 
    try:
        user = await bot.fetch_user(TARGET_USER_ID)
        name = user.display_name
    except Exception:
        name = f"User {TARGET_USER_ID}"
 
    embed = discord.Embed(
        title="💀 N-Word Counter",
        description=f"**{name}** has said it **{total}** time(s).",
        color=discord.Color.yellow(),
    )
    await interaction.response.send_message(embed=embed)
 
# ── /setcount ─────────────────────────────────────────────────────────────────
@tree.command(name="setcount", description="Manually set the n-word count (owner only).")
@app_commands.describe(value="The count to set")
async def slash_setcount(interaction: discord.Interaction, value: int):
    if interaction.user.id != OWNER_USER_ID:
        await interaction.response.send_message("❌ Only the bot owner can use this.", ephemeral=True)
        return
 
    guild_id = interaction.guild_id or 0
    live_count[guild_id] = value
 
    try:
        user = await bot.fetch_user(TARGET_USER_ID)
        name = user.display_name
    except Exception:
        name = f"User {TARGET_USER_ID}"
 
    await interaction.response.send_message(
        f"✅ Count for **{name}** set to **{value}**.", ephemeral=True
    )
 
# ── /lb ───────────────────────────────────────────────────────────────────────
@tree.command(name="lb", description="N-word count across all servers.")
async def slash_lb(interaction: discord.Interaction):
    if not live_count:
        await interaction.response.send_message("No data yet — use `/setcount` to set an initial value!")
        return
 
    try:
        user = await bot.fetch_user(TARGET_USER_ID)
        name = user.display_name
    except Exception:
        name = f"User {TARGET_USER_ID}"
 
    lines = []
    for guild_id, count in sorted(live_count.items(), key=lambda x: x[1], reverse=True):
        g = bot.get_guild(guild_id)
        lines.append(f"**{g.name if g else guild_id}** — {count}x")
 
    embed = discord.Embed(
        title=f"{name}'s N-Word Stats",
        description="\n".join(lines),
        color=discord.Color.red(),
    )
    await interaction.response.send_message(embed=embed)
 
# ── Run ───────────────────────────────────────────────────────────────────────
bot.run(BOT_TOKEN)
 
