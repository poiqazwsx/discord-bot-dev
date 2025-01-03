# cogs/utility/system_prompt_editor.py
import discord
from discord import app_commands
from discord.ext import commands
import logging

class Systempromptchange(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="set_system_prompt", description="Change the system prompt for the LLM.")
    async def set_system_prompt(self, interaction: discord.Interaction, prompt: str):
        """Command to set the system prompt."""
        inference_cog = self.bot.get_cog("Inference")
        if inference_cog is None:
            await interaction.response.send_message("Inference cog not loaded.", ephemeral=True)
            logging.error("Attempt to set system prompt, but the Inference cog is not loaded.")
            return

        auth_cog = self.bot.get_cog("Auth")
        if auth_cog and not auth_cog.is_authorized(interaction):
            await interaction.response.send_message("You are not authorized to use this command.", ephemeral=True)
            logging.error(f"{interaction.user} tried to set the system prompt but was not authorized.")
            return

        inference_cog.system_prompt = prompt
        await interaction.response.send_message(f"System prompt updated to: {prompt}", ephemeral=True)
        logging.info(f"System prompt updated by {interaction.user}: {prompt}")

async def setup(bot):
    logging.info("setting up the system prompt editor cog...")
    await bot.add_cog(Systempromptchange(bot))
