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

def setup(bot):
    print("setting up the message cog...")
    bot.add_cog(Message(bot))
