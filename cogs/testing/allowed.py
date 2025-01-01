# cogs/testing/allowed.py
import discord
from discord import app_commands
from discord.ext import commands

ALLOWED_ROLE_ID = 1198707036070871102


class Allowed(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def is_allowed_role(self):
        async def predicate(interaction: discord.Interaction):
            role = interaction.guild.get_role(ALLOWED_ROLE_ID)
            if role is None:
                await interaction.response.send_message("role dont exist.", ephemeral=True)
                return False
            if role in interaction.user.roles:
                return True
            else:
                await interaction.response.send_message(
                    "no perms.", ephemeral=True
                )
                return False

        return app_commands.check(predicate)


async def setup(bot):
    print("setting up the allowed cog...")
    await bot.add_cog(Allowed(bot))
