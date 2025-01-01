# cogs/untility/auth.py
import discord
from discord.ext import commands
authorized_users = [9366731394129664414, 2987654321098765432]
authorized_roles = [1198707036070871102, 222222222222222222]

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
class Auth(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def is_authorized(interaction: discord.Interaction):
        user = interaction.user
        if user.id in authorized_users:
            return True
        if any(role.id in authorized_roles for role in user.roles):
            return True
#    if user.id == interaction.guild.owner_id:
#        return TrueF
        return False
    @commands.command()
    async def check_auth(self, ctx):
        if ctx.author.id in authorized_users:
            await ctx.send("userid auth")
        elif any(role.id in authorized_roles for role in ctx.author.roles):
            await ctx.send("role auth")
        else:
            await ctx.send("no perms")



async def setup(bot):
    print("setting up the auth cog...")
    await bot.add_cog(Auth(bot))
