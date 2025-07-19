#bot.py
#importpgog
import discord
import asyncio
from discord.ext import commands
from dotenv import load_dotenv
import logging
import yaml
import os
load_dotenv()
DISCORD_BOT_KEY = os.environ.get("DISCORD_BOT_KEY")
#print(DISCORD_BOT_KEY) how to leak ur key 101
# stalking
def load_config():
    with open('config/config.yml', 'r') as file:
        return yaml.safe_load(file)
config = load_config()
# setup logging
log_file_path = config.get("log_file_path", "bot.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename=log_file_path,
    encoding='utf-8'
)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logging.getLogger().addHandler(console_handler)
# intents shittt
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
# fortnite events
@bot.event
async def on_ready():
    try:
        logging.info(f'Logged in as {bot.user}')
        if bot.guilds:
            for guild in bot.guilds:
                logging.info(f'Server: {guild.name} (ID: {guild.id})')
        else:
            logging.info("Not currently in any servers")
        try:
            synced = await bot.tree.sync()
            logging.info(f"Synced {len(synced)} commands")
        except Exception as e:
            logging.error(f"Failed to sync commands: {e}")
    except Exception as e:
        logging.error(f"skill issue: {e}")


# load cogs
async def load_cogs():
    try:
          await bot.load_extension("cogs.testing.message")
          await bot.load_extension("cogs.testing.homework_manager")
          await bot.load_extension("cogs.testing.log")
          await bot.load_extension("cogs.testing.allowed")
          await bot.load_extension("cogs.utility.auth")
          await bot.load_extension("cogs.utility.inference")
          await bot.load_extension("cogs.utility.model_changer")
          await bot.load_extension("cogs.utility.llm_current_settings")
          await bot.load_extension("cogs.utility.inference_toggle")
          await bot.load_extension("cogs.utility.profile_editor")
          await bot.load_extension("cogs.utility.server_info")
          await bot.load_extension("cogs.utility.fetch")
          await bot.load_extension("cogs.utility.reminder")
          await bot.load_extension("cogs.utility.prompt_changer")
          await bot.load_extension("cogs.utility.temp_changer")
          await bot.load_extension("cogs.utility.memory_changer")
          await bot.load_extension("cogs.utility.ping")
          await bot.load_extension("cogs.utility.compiler")
          await bot.load_extension("cogs.utility.provider_selector")
          await bot.load_extension("cogs.utility.inference_gemini")
          await bot.load_extension("cogs.testing.messages_sender")
          await bot.load_extension("cogs.utility.code_generator")
          await bot.load_extension("cogs.testing.deepsite")
          await bot.load_extension("cogs.utility.deep_research")
          await bot.load_extension("cogs.testing.is_odd")
    except Exception as e:
        logging.error(f"failed to load cog: {e}")

# do stuff yes
async def main():
    try:
        await load_cogs()
        await bot.start(DISCORD_BOT_KEY)
    except discord.LoginFailure as e:
        logging.error(f"Login failed: {e}")
    except Exception as e:
        logging.error(f"somethin happen: {e}")


# sdfjlksdjkljlkdfs
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("you killed me :(")
        logging.info("KeyboardInterrupt")
    except Exception as e:
        logging.error(f"unexpected error: {e}")
