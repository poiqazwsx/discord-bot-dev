# cogs/utility/llm_current_settings.py
import discord
from discord import app_commands
from discord.ext import commands

class LLMSettings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="llm_current_settings", description="Show the current LLM settings.")
    async def llm_current_settings(self, interaction: discord.Interaction):
        """
        Show the current LLM settings in an embed.
        """
        inference_cog = self.bot.get_cog("Inference")
        auth_cog = self.bot.get_cog("Auth")
        if auth_cog is None:
            await interaction.response.send_message("The `Auth` cog is not loaded.", ephemeral=True)
            return

        if not auth_cog.is_authorized(interaction):
             await interaction.response.send_message("You are not authorized to use this command.", ephemeral=True)
             return

        if inference_cog is None:
            await interaction.response.send_message("The `Inference` cog is not loaded.", ephemeral=True)
            return

        embed = discord.Embed(title="Current LLM Settings", color=discord.Color.blue())
        embed.add_field(name="Model", value=inference_cog.model, inline=False)
        embed.add_field(name="Context Messages", value=inference_cog.memory_limit, inline=False)
        embed.add_field(name="Max Tokens", value=inference_cog.max_tokens, inline=False)
        embed.add_field(name="Temperature", value=inference_cog.temperature, inline=False)
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    print("setting up the llm_current_settings cog...")
    await bot.add_cog(LLMSettings(bot))
