import discord
from discord import app_commands
from discord.ext import commands
import os
from datetime import datetime

BOT_TOKEN      = os.environ["DISCORD_BOT_TOKEN"]
TARGET_USER_ID = int(os.environ["TARGET_USER_ID"])

import re

# Breakdown:
#   n         — letter n
#   [i1!|]+   — i / 1 / ! / | (leet i)
#   [g9q@]+   — one or more g / 9 / q / @ (leet g); catches "niqqer", "n1g9a"
#   [g9q@]*   — optional second cluster (double-g variants)
#   [aeiouæ@3uh]*  — optional vowel tail: a/e/i/o/u/æ/@/3/u/h
#   [rz]*     — optional trailing r or z ("niggerz", "niggaz")
SLUR_PATTERN = re.compile(
    r"n[i1!|]+[g9q@]+[g9q@]*[aeiou\xE6@3uh]*[rz]*",
    re.IGNORECASE,
)

def contains_slur(text: str) -> bool:
    # Strip spaces so "n i g g a" still matches
    return bool(SLUR_PATTERN.search(text.replace(" ", "")))

live_count: dict[int, int] = {}

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ Logged in as {bot.user} — tracking user ID {TARGET_USER_ID}")

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

@tree.command(name="count", description="How many times has the Alex said it?")
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

@tree.command(name="scan", description="Scan full message history to get the true total.")
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

    for channel in guild.text_channels:
        if not channel.permissions_for(guild.me).read_message_history:
            continue
        channels_scanned += 1
        try:
            async for msg in channel.history(limit=None):
                if msg.author.id == TARGET_USER_ID and contains_slur(msg.content):
                    total += 1
        except discord.Forbidden:
            pass

    live_count[guild.id] = total

    embed = discord.Embed(
        title="🔍 Full History Scan Done",
        color=discord.Color.red(),
    )
    embed.add_field(name="User",     value=name,              inline=True)
    embed.add_field(name="Total",    value=str(total),        inline=True)
    embed.add_field(name="Channels", value=str(channels_scanned), inline=True)
    await interaction.followup.send(embed=embed)

@tree.command(name="lb", description="N-word leaderboard across servers.")
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

bot.run(BOT_TOKEN)
