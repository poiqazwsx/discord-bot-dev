import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
import logging

class ProfileEditor(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="edit_profile", description="Edit bot profile (Admin only).")
    @app_commands.describe(
        username="New bot username",
        app_name="New application name",
        description="New bot description",
        avatar="New bot avatar image",
        banner="New bot banner image"
    )
    async def edit_profile(self, interaction: discord.Interaction,
                      username: Optional[str] = None,
                      app_name: Optional[str] = None,
                      description: Optional[str] = None,
                      avatar: Optional[discord.Attachment] = None,
                      banner: Optional[discord.Attachment] = None):
        """
        Edit various bot settings (Admin only).

        Usage: /edit_profile [username] [app_name] [description] [avatar] [banner]

        Example:
        /edit_profile username="New Bot Name"
        """

        auth_cog = self.bot.get_cog("Auth")
        if auth_cog is None:
           await interaction.response.send_message("The `Auth` cog is not loaded.", ephemeral=True)
           logging.error("The `Auth` cog is not loaded.")
           return

        if not auth_cog.is_authorized(interaction):
             await interaction.response.send_message("You are not authorized to use this command.", ephemeral=True)
             logging.error(f"{interaction.user} tried to change bot settings but was not authorized")
             return

        await interaction.response.defer(ephemeral=True)

        try:
            updated_fields = []
            if username:
                await self.bot.user.edit(username=username)
                updated_fields.append(f"Username changed to '{username}'")
            if app_name:
                app_info = await self.bot.application_info()
                await app_info.edit(name=app_name)
                updated_fields.append(f"Application name changed to '{app_name}'")
            if description:
                app_info = await self.bot.application_info()
                await app_info.edit(description=description)
                updated_fields.append(f"Description changed to '{description}'")
            if avatar:
                avatar_data = await avatar.read()
                await self.bot.user.edit(avatar=avatar_data)
                updated_fields.append("Avatar updated")
            if banner:
                banner_data = await banner.read()
                await self.bot.user.edit(banner=banner_data)
                updated_fields.append("Banner updated")

            if updated_fields:
                await interaction.followup.send("\n".join(updated_fields))
            else:
                await interaction.followup.send("No settings were changed.")

        except discord.HTTPException as e:
            await interaction.followup.send(f"An error occurred: {e}")
            logging.error(f"Error editing bot settings: {e}")

        except Exception as e:
             await interaction.followup.send(f"An error occurred: {e}")
             logging.error(f"Error editing bot settings: {e}")


async def setup(bot):
    logging.info("setting up the profile editor cog...")
    await bot.add_cog(ProfileEditor(bot))
