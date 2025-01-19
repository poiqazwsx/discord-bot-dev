import discord
from discord.ext import commands
import logging
import os
import yaml
import pathlib
import time
import fnmatch

fetch_role = [1222332241070395432, 1225222029700104234]

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

    @commands.command(aliases=['f'])
    async def fetch(self, ctx, name: str = None, *, content: str = None):
        if not self.is_authorized(ctx.author):
            await ctx.send("You do not have permission to use this command.")
            return

        if name is None:
            await ctx.send(
                "```Usage:\n"
                "!f or !fetch\n"
                "!fetch <name> <content> - to save shit\n"
                "!fetch <name> - to get the saved shit\n"
                "!fetch <pattern>* - to search for saved shit\n"
                "!fd <name> - to delete saved shit\n"
                "!fl - to list all saved shit\n"
                "!fs <text> - to search all files for text\n"
                "Functions:\n"
                "{mention} - mentions the user you reply to\n"
                "{time} - shows current time\n"
                "{membercount} - shows server member count\n"
                "{author} - shows the author of the command\n"
                "{channel} - shows the current channel\n"
                "{replycontent} - shows the content of the replied message```"
            )
            return

        if '*' in name:
            try:
                files = [f[:-4] for f in os.listdir(self.data_dir) if fnmatch.fnmatch(f, f"{name}.txt")]
                if not files:
                    await ctx.send("No fetch files found matching the pattern.")
                    return

                if len(files) == 1:
                    file_path = self.sanitize_path(files[0])
                    with open(file_path, "r") as f:
                        saved_content = f.read()
                        if ctx.message.reference and ctx.message.reference.resolved:
                            mentioned_user = ctx.message.reference.resolved.author
                            saved_content = saved_content.replace("{mention}", mentioned_user.mention)
                            reply_content = ctx.message.reference.resolved.content
                            saved_content = saved_content.replace("{replycontent}", reply_content)
                        saved_content = saved_content.replace("{time}", f"<t:{int(time.time())}:f>")
                        member_count = ctx.guild.member_count
                        saved_content = saved_content.replace("{membercount}", str(member_count))
                        saved_content = saved_content.replace("{author}", ctx.author.mention)
                        saved_content = saved_content.replace("{channel}", ctx.channel.mention)
                        await ctx.send(f"> *~/fetch_data/{files[0]}.txt*\n{saved_content}\n")
                else:
                    files_list = "\n".join(files)
                    await ctx.send(f"```Matching fetch files:\n{files_list}```")
            except Exception as e:
                logging.error(f"Failed to search files: {e}")
                await ctx.send("Error searching fetch files.")
            return

        file_path = self.sanitize_path(name)
        if not file_path.startswith(self.data_dir):
            logging.warning(f"Unauthorized path access attempt: {file_path} by {ctx.author}")
            await ctx.send("Invalid file path.")
            return

        if content is None:
            if os.path.exists(file_path):
                try:
                    with open(file_path, "r") as f:
                        saved_content = f.read()
                        if ctx.message.reference and ctx.message.reference.resolved:
                            mentioned_user = ctx.message.reference.resolved.author
                            saved_content = saved_content.replace("{mention}", mentioned_user.mention)
                            reply_content = ctx.message.reference.resolved.content
                            saved_content = saved_content.replace("{replycontent}", reply_content)
                        saved_content = saved_content.replace("{time}", f"<t:{int(time.time())}:f>")
                        member_count = ctx.guild.member_count
                        saved_content = saved_content.replace("{membercount}", str(member_count))
                        saved_content = saved_content.replace("{author}", ctx.author.mention)
                        saved_content = saved_content.replace("{channel}", ctx.channel.mention)
                        await ctx.send(f"> *~/fetch_data/{name}.txt*\n{saved_content}\n")
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

    @commands.command(aliases=['fd'])
    async def fetch_delete(self, ctx, name: str = None):
        if not self.is_authorized(ctx.author):
            await ctx.send("You do not have permission to use this command.")
            return

        if name is None:
            await ctx.send("Please provide a name to delete.")
            return

        file_path = self.sanitize_path(name)
        if not file_path.startswith(self.data_dir):
            logging.warning(f"Unauthorized path access attempt: {file_path} by {ctx.author}")
            await ctx.send("Invalid file path.")
            return

        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                await ctx.send(f"Deleted `{name}.txt`")
                logging.info(f"`{name}.txt` deleted by {ctx.author}")
            except Exception as e:
                logging.error(f"Failed to delete {file_path}: {e}")
                await ctx.send(f"Error deleting `{name}.txt`")
        else:
            await ctx.send(f"No file found with name `{name}.txt`")

    @commands.command(aliases=['fl'])
    async def fetch_list(self, ctx):
        if not self.is_authorized(ctx.author):
            await ctx.send("You do not have permission to use this command.")
            return

        try:
            files = [f[:-4] for f in os.listdir(self.data_dir) if f.endswith('.txt')]
            if not files:
                await ctx.send("No fetch files found.")
                return
            files_list = "\n".join(files)
            await ctx.send(f"```Saved fetch files:\n{files_list}```")
        except Exception as e:
            logging.error(f"Failed to list files: {e}")
            await ctx.send("Error listing fetch files.")

    @commands.command(aliases=['fs'])
    async def fetch_search(self, ctx, *, search_text: str):
        if not self.is_authorized(ctx.author):
            await ctx.send("You do not have permission to use this command.")
            return

        if not search_text:
            await ctx.send("Please provide text to search for.")
            return

        try:
            matches = []
            for filename in os.listdir(self.data_dir):
                if filename.endswith('.txt'):
                    file_path = os.path.join(self.data_dir, filename)
                    with open(file_path, 'r') as f:
                        content = f.read()
                        if search_text.lower() in content.lower():
                            matches.append(f"{filename[:-4]}: {content[:100]}...")

            if matches:
                result = "\n\n".join(matches)
                await ctx.send(f"```Search results for '{search_text}':\n\n{result}```")
            else:
                await ctx.send(f"No matches found for '{search_text}'")
        except Exception as e:
            logging.error(f"Failed to search files: {e}")
            await ctx.send("Error searching fetch files.")

async def setup(bot):
    logging.info("Setting up the fetch cog...")
    await bot.add_cog(Fetch(bot))
