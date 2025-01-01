# cogs/utility/ping.py
import discord
from discord import app_commands
from discord.ext import commands
import logging

class ping(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ping", description="latency")
    async def ping(self, interaction: discord.Interaction):
        latency = self.bot.latency * 1000
        await interaction.response.send_message(f"Pong! Latency is {latency:.2f} ms")

async def setup(bot):
    logging.info("setting up the ping cog...")
    await bot.add_cog(ping(bot))
