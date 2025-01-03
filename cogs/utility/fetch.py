import discord
from discord.ext import commands
import logging
import os
import yaml
import pathlib
fetch_role = [1222332241070395432, 1225222029700104234, 1225222264644178000]

class Fetch(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        with open('config/config.yml', 'r') as file:
            config = yaml.safe_load(file)
        self.data_dir = os.path.abspath(config.get("fetch_data_dir", "fetch_data"))
        os.makedirs(self.data_dir, exist_ok=True)

    def is_authorized(self, user: discord.Member):
        return any(role.id in fetch_role for role in user.roles)

    def sanitize_path(self, file_name: str) -> str:
        safe_name = pathlib.Path(file_name).name
        return os.path.join(self.data_dir, f"{safe_name}.txt")

    @commands.command()
    async def fetch(self, ctx, name: str = None, *, content: str = None):
        if name is None:
            await ctx.send(
                "```Usage:\n"
                "!fetch <name> <content> - to save shit\n"
                "!fetch <name> - to get the saved shit```"
            )
            return

#        Usage:
#        !fetch <name> <content>  - to save shit
#        !fetch <name>            - to get the saved shit

        if not self.is_authorized(ctx.author):
            await ctx.send("You do not have permission to use this command.")
            return
        file_path = self.sanitize_path(name)

        if not file_path.startswith(self.data_dir):
            logging.warning(f"Unauthorized path access attempt: {file_path}")
            await ctx.send("Invalid file path.")
            return

        if content is None:
            if os.path.exists(file_path):
                try:
                    with open(file_path, "r") as f:
                        saved_content = f.read()
                        await ctx.send(f"```\n{saved_content}\n```")
                except Exception as e:
                    logging.error(f"Failed to read content from {file_path}: {e}")
                    await ctx.send(f"Error reading content for '{name}'.")
            else:
                logging.error(f"No content saved with the name '{name}'.")
                await ctx.send(f"No content saved with the name '{name}'.")
            return

        try:
            with open(file_path, "w") as f:
                f.write(content)
            await ctx.send(f"Data saved as `{name}.txt`")
            logging.info(f"Data saved as `{name}.txt` by {ctx.author}")
        except Exception as e:
            logging.error(f"Failed to save content to {file_path}: {e}")
            await ctx.send(f"Error saving data as `{name}.txt`")

async def setup(bot):
    logging.info("Setting up the fetch cog...")
    await bot.add_cog(Fetch(bot))
