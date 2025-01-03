import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import re
from datetime import timedelta
import logging

class Reminder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="reminder", description="Set a reminder.")
    async def reminder(self, interaction: discord.Interaction, time: str, *, message: str):
        await interaction.response.defer()
        time_regex = re.compile(r"(\d+)\s*(s|sec|seconds|m|min|minutes|h|hour|hours|d|day|days)")
        time_parts = time.split()
        delta = timedelta()
        valid_units = ["s", "sec", "seconds", "m", "min", "minutes", "h", "hour", "hours", "d", "day", "days"]
        i = 0
        while i < len(time_parts):
            match = time_regex.match(time_parts[i])
            if not match:
                if i + 1 < len(time_parts) and time_parts[i + 1].lower() in valid_units:
                    combined_part = time_parts[i] + time_parts[i + 1]
                    match = time_regex.match(combined_part)
                    if match:
                        i += 1
                    else:
                        await interaction.followup.send(f"Invalid time format in '{time_parts[i]}'. Please use a valid format like '1h', '30m', '2d 6h', '1 second'.", ephemeral=True)
                        logging.error(f"User: {interaction.user} - Error: Invalid time format in '{time_parts[i]}'.")
                        return
                else:
                    await interaction.followup.send(f"Invalid time format in '{time_parts[i]}'. Please use a valid format like '1h', '30m', '2d 6h', '1 second'.", ephemeral=True)
                    logging.error(f"User: {interaction.user} - Error: Invalid time format in '{time_parts[i]}'.")
                    return

            time_amount = int(match.group(1))
            time_unit = match.group(2).lower()

            if time_unit not in valid_units:
                await interaction.followup.send(f"Invalid time unit '{time_unit}'. Please use s/m/h/d or their full names.", ephemeral=True)
                logging.error(f"User: {interaction.user} - Error: Invalid time unit '{time_unit}'.")
                return

            if time_unit in ("s", "sec", "seconds"):
                delta += timedelta(seconds=time_amount)
            elif time_unit in ("m", "min", "minutes"):
                delta += timedelta(minutes=time_amount)
            elif time_unit in ("h", "hour", "hours"):
                delta += timedelta(hours=time_amount)
            elif time_unit in ("d", "day", "days"):
                delta += timedelta(days=time_amount)

            i += 1

        await interaction.followup.send(f"Reminder set for {time} from now.")
        logging.info(f"User:{interaction.user} - set a timer for {time}")

        await asyncio.sleep(delta.total_seconds())

        await interaction.channel.send(f"<@{interaction.user.id}> ⏰ Reminder: {message}")
        logging.info(f"User:{interaction.user} - Reminder: {message}")

async def setup(bot):
    logging.info("setting up the reminder cog...")
    await bot.add_cog(Reminder(bot))
