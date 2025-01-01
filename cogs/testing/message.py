# cogs/testing/message.py
from discord.ext import commands


class Message(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return

        if "test" in message.content.lower():
            await message.channel.send("test")



async def setup(bot):
    print("setting up the message cog...")
    await bot.add_cog(Message(bot))
