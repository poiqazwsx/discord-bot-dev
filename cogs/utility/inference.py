# cogs/utility/inference.py
import os
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from groq import AsyncGroq
import logging
model = "llama-3.3-70b-versatile"
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
        self.temperature = 1
        self.max_tokens = 1000
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
                        max_tokens=self.max_tokens,
                        temperature=self.temperature
                    )
                    reply = response.choices[0].message.content.strip()
                    logging.info(f"User:{message.author.id}\n Message{message}\n Response:{reply}")
                    self.memory[user_id].append({"role": "assistant", "content": reply})
                    for i in range(0, len(reply), 2000):
                        chunk = reply[i:i + 2000]
                        await message.channel.send(chunk)
                except Exception as e:
                    await message.channel.send("woopsies somethin happen")
                    logging.error(f"groq completion did a skill issue : {e}")
                    print(f"groq completion did a skill issue : {e}")


async def setup(bot):
    print("setting up the inference cog...")
    await bot.add_cog(Inference(bot))
