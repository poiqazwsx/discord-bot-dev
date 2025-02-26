# cogs/utility/llm_current_settings.py
import discord
from discord import app_commands
from discord.ext import commands
import logging

from cogs.utility.inference_toggle import Toggle_llm
class LLMSettings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="llm_current_settings", description="Show the current LLM settings.")
    async def llm_current_settings(self, interaction: discord.Interaction):
        """
        Show the current LLM settings in an embed.
        """
        inference_cog = self.bot.get_cog("Inference")
        inference_toggle = self.bot.get_cog("Toggle_llm")
        auth_cog = self.bot.get_cog("Auth")
        if inference_toggle is None:
            await interaction.response.send_message("The `inference_toggle` cog is not loaded.", ephemeral=True)
            logging.error("The `inference_toggle` cog is not loaded.")
            return

        if auth_cog is None:
            await interaction.response.send_message("The `Auth` cog is not loaded.", ephemeral=True)
            logging.error("The `Auth` cog is not loaded.")
            return

        if not auth_cog.is_authorized(interaction):
             await interaction.response.send_message("You are not authorized to use this command.", ephemeral=True)
             logging.error(f"{interaction.user} tried to change llm_current_settings but was authorized")
             return

        if inference_cog is None:
            await interaction.response.send_message("The `Inference` cog is not loaded.", ephemeral=True)
            logging.error("The `Inference` cog is not loaded.")
            return

        embed = discord.Embed(title="Current LLM Settings", color=discord.Color.blue())
        embed.add_field(name="Model", value=inference_cog.model, inline=False)
        embed.add_field(name="Context Messages", value=inference_cog.memory_limit, inline=False)
        embed.add_field(name="Max Tokens", value=inference_cog.max_tokens, inline=False)
        embed.add_field(name="Temperature", value=inference_cog.temperature, inline=False)
        embed.add_field(name="Enabled", value=inference_toggle.is_inference_enabled(), inline=False)
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    logging.info("setting up the llm current settings cog...")
    await bot.add_cog(LLMSettings(bot))
