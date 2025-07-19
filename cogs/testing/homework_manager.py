import discord
from discord import app_commands
from discord.ext import commands
import logging
from datetime import timedelta

class HomeworkManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.authorized_users = [936673139419664414, 917711764571951144, 911742715019001897]  # poopmaster, lusbert & nick088

    @app_commands.command(name="homework", description="Mute to go do homework (FOR LUSBERT & POOPMASTER ONLY).")
    @app_commands.describe(
        who="Who to mute (Lusbert or Poopmaster)",
        duration="Duration of the mute (minutes).",
        reason="Reason for muting (defaults to 'Homework')"
    )
    async def homework(self, interaction: discord.Interaction, who: discord.Member, duration: int, reason: str = "Homework"):
        if interaction.user.id not in self.authorized_users:
            await interaction.response.send_message("You cannot mute them.", ephemeral=True)
            logging.info(f"Unauthorized homework mute attempt by {interaction.user.id} for {who.id}")
            return

        timeout_duration = timedelta(minutes=duration)
        try:
            await who.timeout(timeout_duration)
            await interaction.response.send_message(
                f"{who.mention} has been muted for {duration} minutes. Reason: {reason}"
            )
            logging.info(f"User {who.id} muted for {duration} minutes by {interaction.user.id}")
        except discord.Forbidden:
            await interaction.response.send_message("I don't have permission to mute this member.", ephemeral=True)
            logging.error(f"Failed to mute {who.id}: Insufficient permissions")
        except discord.HTTPException as e:
            await interaction.response.send_message(f"Failed to mute the member: {e}", ephemeral=True)
            logging.error(f"Failed to mute {who.id}: {e}")

    @app_commands.command(name="unmute", description="Unmute a user (FOR LUSBERT & POOPMASTER ONLY).")
    @app_commands.describe(
        who="Who to unmute (Lusbert or Poopmaster)",
    )
    async def unmute(self, interaction: discord.Interaction, who: discord.Member):
        if interaction.user.id not in self.authorized_users:
            await interaction.response.send_message("You cannot unmute them.", ephemeral=True)
            logging.info(f"Unauthorized unmute attempt by {interaction.user.id} for {who.id}")
            return

        try:
            await who.timeout(None)
            await interaction.response.send_message(f"{who.mention} has been unmuted.")
            logging.info(f"User {who.id} unmuted by {interaction.user.id}")
        except discord.Forbidden:
            await interaction.response.send_message("I don't have permission to unmute this member.", ephemeral=True)
            logging.error(f"Failed to unmute {who.id}: Insufficient permissions")
        except discord.HTTPException as e:
            await interaction.response.send_message(f"Failed to unmute the member: {e}", ephemeral=True)
            logging.error(f"Failed to unmute {who.id}: {e}")

async def setup(bot):
    logging.info("Setting up the homework manager cog...")
    await bot.add_cog(HomeworkManager(bot))
