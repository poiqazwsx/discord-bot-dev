import discord
from discord import app_commands
from discord.ext import commands
import logging

class ServerInfo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="serverinfo", description="Get information about the server.")
    async def serverinfo(self, interaction: discord.Interaction):
        """
        info
        """

        embed = discord.Embed(
            title="Sanctuary: Open Source AI",
            description="Sanctuary is a Discord server dedicated to open-source AI projects and research. It's a place for users, developers, and researchers to connect, share their work, help each other and collaborate.  The server aims to highlight amazing open-source projects and inspire developers to push the boundaries of AI.",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="How to Help",
            value="1. Boost the server to unlock more features.\n2. Spread the word to your friends.\n3. Help improve the server by posting suggestions in the designated channel.",
            inline=False
        )
        embed.add_field(name="Permanent Invite Link", value="[Join Sanctuary](https://discord.gg/kSaydjBXwf)", inline=False)
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    logging.info("setting up the server info cog...")
    await bot.add_cog(ServerInfo(bot))
