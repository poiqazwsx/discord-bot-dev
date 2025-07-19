# cogs/utility/provider_selector.py
import discord
from discord import app_commands
from discord.ext import commands
import logging

class ProviderSelector(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.current_provider = "groq"  # Default provider
        self.available_providers = ["groq", "gemini"]

    @app_commands.command(name="select_provider", description="Select which LLM provider to use (groq or gemini)")
    async def select_provider(self, interaction: discord.Interaction, provider: str):
        """Select which LLM provider to use"""
        auth_cog = self.bot.get_cog("Auth")

        if auth_cog is None:
            logging.error("The `Auth` cog is not loaded.")
            return

        if not auth_cog.is_authorized(interaction):
            await interaction.response.send_message("You are not authorized to use this command.", ephemeral=True)
            logging.error(f"{interaction.user} tried to change provider but was not authorized.")
            return

        provider = provider.lower()
        if provider not in self.available_providers:
            await interaction.response.send_message(
                f"Invalid provider. Available providers: {', '.join(self.available_providers)}",
                ephemeral=True
            )
            return

        self.current_provider = provider
        await interaction.response.send_message(f"LLM provider changed to: {provider}", ephemeral=True)
        logging.info(f"LLM provider changed to {provider} by {interaction.user.name} ({interaction.user.id})")

    def get_current_provider(self):
        return self.current_provider

async def setup(bot):
    logging.info("Setting up the provider selector cog...")
    await bot.add_cog(ProviderSelector(bot))
