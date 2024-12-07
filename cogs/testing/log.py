# cogs/testing/log.py
from discord.ext import commands


class Log(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.Cog.listener()
    async def on_message(self, message):
        print(f'Message from {message.author}: {message.content}')



def setup(bot):
    print("setting up the log cog...")
    bot.add_cog(Log(bot))

