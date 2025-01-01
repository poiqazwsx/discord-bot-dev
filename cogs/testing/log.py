# cogs/testing/log.py
from discord.ext import commands
import logging

class Log(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.Cog.listener()
    async def on_message(self, message):
        print(f'Message from {message.author}: {message.content}')
        logging.info(f'Message from {message.author}: {message.content}')

async def setup(bot):
    logging.info("setting up the log cog...")
    await bot.add_cog(Log(bot))
