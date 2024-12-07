import discord 
import asyncio
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    try:
        print(f'Logged in as {bot.user}')
        if bot.guilds:
            for guild in bot.guilds:
                print(f'Server: {guild.name} (ID: {guild.id})') 
        else:
            print("Not currently in any servers")
    except Exception as e:
        print("skill issue")
# load cogs
async def load_cogs():
    try:
         bot.load_extension("cogs.testing.message")
    except Exception as e:
        print(f"Failed to load cog: {e}")

# do stuff yes
async def main(): 
    try:
        await load_cogs()  
        await bot.start("") 
    except discord.LoginFailure as e:
        print(f"Login failed: {e}")
    except Exception as e:
        print(f"An error occured: {e}")

if __name__ == "__main__":
    asyncio.run(main())




