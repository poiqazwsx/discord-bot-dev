import discord
from discord import app_commands
from discord.ext import commands
import logging
status = "enabled"

class Toggle_llm(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.inference_enabled = True

    @app_commands.command(name="toggle_llm", description="enable or disable.")
    async def toggle_inference(self, interaction: discord.Interaction):
         """Toggles the LLM functionality on or off."""
         auth_cog = self.bot.get_cog("Auth")

         if auth_cog is None:
             logging.error("The `Auth` cog is not loaded.")
             return
         if not auth_cog.is_authorized(interaction):
             await interaction.response.send_message("You are not authorized to use this command.", ephemeral=True)
             logging.error(f"{interaction.user} tried to toggle LLM but was not authorized.")
             return
         self.inference_enabled = not self.inference_enabled
         status = "enabled" if self.inference_enabled else "disabled"
         await interaction.response.send_message(f"LLM is now {status}.", ephemeral=True)
         logging.info(f"LLM toggled to {status} by {interaction.user}.")

    def is_inference_enabled(self):
        return self.inference_enabled


async def setup(bot):
    logging.info("setting up the inference toggle cog...")
    await bot.add_cog(Toggle_llm(bot))
