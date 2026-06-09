import discord
from discord import app_commands
from discord.ext import commands
import os
import re
import threading
import asyncio
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
 
# ── Config ────────────────────────────────────────────────────────────────────
BOT_TOKEN      = os.environ["DISCORD_BOT_TOKEN"]
TARGET_USER_ID = int(os.environ["TARGET_USER_ID"])
PORT           = int(os.environ.get("PORT", 8080))
SCAN_LIMIT     = 15000   # messages per channel (raise if needed)
 
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
        title="Alex N-Word Counter",
        description=f"**{name}** has said it **{total}** time(s).",
        color=discord.Color.yellow(),
    )
    await interaction.response.send_message(embed=embed)
 
# ── /scan ─────────────────────────────────────────────────────────────────────
@tree.command(name="scan", description=f"Scan up to {15000} messages per channel for the true total.")
async def slash_scan(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
 
    try:
        target = await bot.fetch_user(TARGET_USER_ID)
        name = target.display_name
    except Exception:
        name = f"User {TARGET_USER_ID}"
 
    guild = interaction.guild
    total = 0
    channels_scanned = 0
    skipped = 0
 
    for channel in guild.text_channels:
        if not channel.permissions_for(guild.me).read_message_history:
            skipped += 1
            continue
 
        channels_scanned += 1
        channel_count = 0
 
        try:
            async for msg in channel.history(limit=SCAN_LIMIT, oldest_first=False):
                if msg.author.id == TARGET_USER_ID and contains_slur(msg.content):
                    channel_count += 1
                await asyncio.sleep(0)  # yield to event loop, prevents hanging
        except discord.Forbidden:
            skipped += 1
            channels_scanned -= 1
            continue
        except Exception as e:
            print(f"Error scanning #{channel.name}: {e}")
            continue
 
        if channel_count:
            print(f"  #{channel.name}: {channel_count}")
        total += channel_count
 
    live_count[guild.id] = total
 
    embed = discord.Embed(title="🔍 Scan Done", color=discord.Color.red())
    embed.add_field(name="User",             value=name,              inline=True)
    embed.add_field(name="Total Found",      value=str(total),        inline=True)
    embed.add_field(name="Channels Scanned", value=str(channels_scanned), inline=True)
    if skipped:
        embed.set_footer(text=f"{skipped} channel(s) skipped (no access)")
    embed.description = f"*(scanned last {SCAN_LIMIT:,} messages per channel)*"
 
    await interaction.followup.send(embed=embed)
 
# ── /lb ───────────────────────────────────────────────────────────────────────
@tree.command(name="lb", description="N-word count across all servers.")
async def slash_lb(interaction: discord.Interaction):
    if not live_count:
        await interaction.response.send_message("No data yet — run `/scan` first!")
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
