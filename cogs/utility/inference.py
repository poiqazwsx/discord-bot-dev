import os
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from groq import AsyncGroq
model = "llama-3.3-70b-versatile"
ALLOWED_ROLE_ID = 1198707036070871102
load_dotenv()
class Inference(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        api_key = os.environ.get("GROQ_API_KEY")
        if api_key is None:
            print("Error: GROQ_API_KEY environment variable aint real")
            raise Exception("GROQ_API_KEY aint real")
        self.client = AsyncGroq(api_key=api_key)
        self.memory = {}
        self.memory_limit = 5
        self.model = model
        def is_allowed_role():
            async def predicate(interaction: discord.Interaction):
                role = interaction.guild.get_role(ALLOWED_ROLE_ID)
                if role is None:
                    await interaction.response.send_message("The specified role does not exist.", ephemeral=True)
                    return False
                if role in interaction.user.roles:
                    return True
                else:
                    await interaction.response.send_message("You do not have the required role to use this command.", ephemeral=True)
                    return False
            return app_commands.check(predicate)
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return
        if self.bot.user in message.mentions:
            user_id = message.author.id
            content = message.clean_content.replace(f"@{self.bot.user.name}", "").strip()
            if content:
                if user_id not in self.memory:
                   self.memory[user_id] = []
                self.memory[user_id].append({"role": "user", "content": content})
                if len(self.memory[user_id]) > self.memory_limit * 2:
                    self.memory[user_id] = self.memory[user_id][-self.memory_limit * 2:]
                try:
                    messages = self.memory[user_id]
                    response = await self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        max_tokens=1000,
                        temperature=1
                    )
                    reply = response.choices[0].message.content.strip()
                    self.memory[user_id].append({"role": "assistant", "content": reply})
                    for i in range(0, len(reply), 2000):
                        chunk = reply[i:i + 2000]
                        await message.channel.send(chunk)
                except Exception as e:
                    await message.channel.send("woopsies somethin happen")
                    print(f"groq completion did a skill issue : {e}")


async def setup(bot):
    print("setting up the inference cog...")
    await bot.add_cog(Inference(bot))
