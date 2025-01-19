# cogs/utility/memory_changer.py
import discord
from discord import app_commands
from discord.ext import commands
import logging

class Contextchange(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="set_memory", description="Change the memory for the LLM.")
    async def set_system_prompt(self, interaction: discord.Interaction, memory: int):
        """Command to set the memory."""
        inference_cog = self.bot.get_cog("Inference")
        if inference_cog is None:
            await interaction.response.send_message("Inference cog not loaded.", ephemeral=True)
            logging.error("Attempt to set context, but the Inference cog is not loaded.")
            return

        auth_cog = self.bot.get_cog("Auth")
        if auth_cog and not auth_cog.is_authorized(interaction):
            await interaction.response.send_message("You are not authorized to use this command.", ephemeral=True)
            logging.error(f"{interaction.user} tried to set the memory but was not authorized.")
            return

        inference_cog.memory_limit = memory
        await interaction.response.send_message(f"memory updated to: {memory}", ephemeral=True)
        logging.info(f"memory updated by {interaction.user}: {memory}")

async def setup(bot):
    logging.info("setting up the memory changer cog...")
    await bot.add_cog(Contextchange(bot))
