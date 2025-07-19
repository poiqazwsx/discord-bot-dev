# bot/cogs/testing/messages_sender.py
import discord
from discord import app_commands
from discord.ext import commands
import logging

class MessageSender(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="send_message", description="Send a message as the bot (Admin only)")
    @app_commands.describe(
        message="The message to send"
    )
    async def send_message(self, interaction: discord.Interaction,
                           message: str):
        """
        Send a message as the bot in the current channel (Admin only).

        Usage: /send_message [message]

        Example:
        /send_message message="Hello everyone!"
        """

        # Check if Auth cog is loaded
        auth_cog = self.bot.get_cog("Auth")
        if auth_cog is None:
            await interaction.response.send_message("The `Auth` cog is not loaded.", ephemeral=True)
            logging.error("The `Auth` cog is not loaded.")
            return

        # Check if user is authorized
        if not auth_cog.is_authorized(interaction):
            await interaction.response.send_message("You are not authorized to use this command.", ephemeral=True)
            logging.error(f"{interaction.user} tried to send a message as the bot but was not authorized")
            return

        # Get the current channel from the interaction
        channel = interaction.channel

        # Check if the bot has permission to send messages in the current channel
        if not channel.permissions_for(interaction.guild.me).send_messages:
            await interaction.response.send_message(
                "I don't have permission to send messages in this channel",
                ephemeral=True
            )
            return

        try:
            # Send the message to the current channel
            await channel.send(message)

            # Confirm to the command user
            await interaction.response.send_message(
                "Message sent successfully.",
                ephemeral=True
            )

            logging.info(f"{interaction.user} sent a message as the bot to {channel.name}")

        except discord.HTTPException as e:
            await interaction.response.send_message(
                f"Failed to send message: {e}",
                ephemeral=True
            )
            logging.error(f"Error sending message: {e}")

        except Exception as e:
            await interaction.response.send_message(
                f"An unexpected error occurred: {e}",
                ephemeral=True
            )
            logging.error(f"Unexpected error when sending message: {e}")

    @app_commands.command(name="reply_to", description="Reply to a message as the bot (Admin only)")
    @app_commands.describe(
        message_link="The link to the message to reply to",
        reply="The reply content"
    )
    async def reply_to(self, interaction: discord.Interaction,
                      message_link: str,
                      reply: str):
        """
        Reply to a specific message as the bot (Admin only).

        Usage: /reply_to [message_link] [reply]

        Example:
        /reply_to message_link="https://discord.com/channels/123456789/987654321/123987456" reply="This is my response!"
        """

        # Check authorization
        auth_cog = self.bot.get_cog("Auth")
        if auth_cog is None:
            await interaction.response.send_message("The `Auth` cog is not loaded.", ephemeral=True)
            logging.error("The `Auth` cog is not loaded.")
            return

        if not auth_cog.is_authorized(interaction):
            await interaction.response.send_message("You are not authorized to use this command.", ephemeral=True)
            logging.error(f"{interaction.user} tried to reply to a message as the bot but was not authorized")
            return

        # Validate and parse the message link
        try:
            # Message links are in the format: https://discord.com/channels/guild_id/channel_id/message_id
            parts = message_link.split('/')
            if 'discord.com/channels' not in message_link or len(parts) < 7:
                await interaction.response.send_message("Invalid message link format.", ephemeral=True)
                return

            guild_id = int(parts[-3])
            channel_id = int(parts[-2])
            message_id = int(parts[-1])

            # Check if the guild ID matches the current guild
            if guild_id != interaction.guild.id:
                await interaction.response.send_message("The message link must be from this server.", ephemeral=True)
                return

            # Get the channel and message
            channel = interaction.guild.get_channel(channel_id)
            if not channel:
                await interaction.response.send_message("Channel not found.", ephemeral=True)
                return

            message = await channel.fetch_message(message_id)
            if not message:
                await interaction.response.send_message("Message not found.", ephemeral=True)
                return

            # Reply to the message
            await message.reply(reply)

            await interaction.response.send_message("Reply sent successfully.", ephemeral=True)
            logging.info(f"{interaction.user} replied to a message as the bot in {channel.name}")

        except ValueError:
            await interaction.response.send_message("Invalid message link. Please make sure it's correctly formatted.", ephemeral=True)
        except discord.NotFound:
            await interaction.response.send_message("Message or channel not found.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("I don't have permission to reply to that message.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
            logging.error(f"Error replying to message: {e}")

    @app_commands.command(name="send_dm", description="Send a direct message to a user (Admin only)")
    @app_commands.describe(
        user="The user to send a DM to",
        message="The message to send"
    )
    async def send_dm(self, interaction: discord.Interaction, user: discord.Member, message: str):
        """
        Send a direct message to a user as the bot (Admin only).

        Usage: /send_dm [user] [message]

        Example:
        /send_dm user=@username message="Hello, this is an important notification!"
        """
        # Check authorization
        auth_cog = self.bot.get_cog("Auth")
        if auth_cog is None:
            await interaction.response.send_message("The `Auth` cog is not loaded.", ephemeral=True)
            logging.error("The `Auth` cog is not loaded.")
            return

        if not auth_cog.is_authorized(interaction):
            await interaction.response.send_message("You are not authorized to use this command.", ephemeral=True)
            logging.error(f"{interaction.user} tried to send a DM as the bot but was not authorized")
            return

        try:
            # Attempt to send the DM
            await user.send(message)

            # Confirm to the command user
            await interaction.response.send_message(
                f"DM sent successfully to {user.display_name}.",
                ephemeral=True
            )

            logging.info(f"{interaction.user} sent a DM as the bot to {user.display_name} ({user.id})")

        except discord.Forbidden:
            # This occurs if the user has DMs closed or has blocked the bot
            await interaction.response.send_message(
                f"I couldn't send a DM to {user.display_name}. They may have DMs closed or have blocked me.",
                ephemeral=True
            )
            logging.error(f"Failed to send DM to {user.display_name} ({user.id}): User has DMs closed or has blocked the bot")

        except Exception as e:
            await interaction.response.send_message(
                f"An unexpected error occurred: {e}",
                ephemeral=True
            )
            logging.error(f"Unexpected error when sending DM to {user.display_name} ({user.id}): {e}")

async def setup(bot):
    logging.info("Setting up the message sender cog...")
    await bot.add_cog(MessageSender(bot))
