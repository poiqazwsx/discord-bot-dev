# cogs/utility/temp_changer.py
import discord
from discord import app_commands
from discord.ext import commands
import logging

class Tempchange(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="set_temp", description="Change the temp for the LLM.")
    async def set_system_prompt(self, interaction: discord.Interaction, temperature: str):
        """Command to set the temp."""
        inference_cog = self.bot.get_cog("Inference")
        if inference_cog is None:
            await interaction.response.send_message("Inference cog not loaded.", ephemeral=True)
            logging.error("Attempt to set temp, but the Inference cog is not loaded.")
            return

        auth_cog = self.bot.get_cog("Auth")
        if auth_cog and not auth_cog.is_authorized(interaction):
            await interaction.response.send_message("You are not authorized to use this command.", ephemeral=True)
            logging.error(f"{interaction.user} tried to set the temp but was not authorized.")
            return

        inference_cog.temperature = float(temperature)
        await interaction.response.send_message(f"temp updated to: {temperature}", ephemeral=True)
        logging.info(f"temp updated by {interaction.user}: {temperature}")

async def setup(bot):
    logging.info("setting up the temp changer cog...")
    await bot.add_cog(Tempchange(bot))
