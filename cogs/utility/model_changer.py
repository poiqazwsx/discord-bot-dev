# cogs/utility/model_changer.py
import discord
from discord import app_commands
from discord.ext import commands


class ModelChanger(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.allowed_models = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "llama-guard-3-8b"]

    @app_commands.command(name="set_model", description="Set the model for inference")
    async def set_model(self, interaction: discord.Interaction, model: str):
        """Sets the model used by the bot."""

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

        if model not in self.allowed_models:
            await interaction.response.send_message("Invalid Model.", ephemeral=True)
            return
        inference_cog.model = model
        await interaction.response.send_message(f"Model set to `{model}`.", ephemeral=True)
    @set_model.autocomplete("model")
    async def model_autocomplete(self, interaction: discord.Interaction, current: str):
            return [
                app_commands.Choice(name=model, value=model)
                for model in self.allowed_models if current.lower() in model.lower()
            ]


async def setup(bot):
    print("setting up the model changer cog...")
    await bot.add_cog(ModelChanger(bot))
