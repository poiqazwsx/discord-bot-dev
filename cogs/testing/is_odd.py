# bot/cogs/testing/isodd.py
import discord
from discord.ext import commands
import logging
import os
from groq import AsyncGroq

# Define authorized role IDs
isodd_roles = [1222332241070395432, 1225222029700104234]

class IsOddChecker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        api_key = os.environ.get("GROQ_API_KEY")
        if api_key is None:
            logging.error("GROQ_API_KEY environment variable not found for IsOddChecker")
            raise Exception("GROQ_API_KEY ain't real")
        self.client = AsyncGroq(api_key=api_key)

        # --- Configuration ---
        self.model = "deepseek-r1-distill-llama-70b" # Using a smaller model for this simple task
        self.temperature = 1
        self.max_tokens = 1000
        self.system_prompt = "You are a helpful assistant that determines if numbers are odd or even."

    def is_authorized(self, user: discord.Member):
        """Check if user has the required roles for isodd command"""
        return any(role.id in isodd_roles for role in user.roles)

    @commands.command(aliases=['odd'])
    async def is_odd(self, ctx: commands.Context, number: str = None):
        """
        Checks if a number is odd or even using an AI model.

        Usage:
        !isodd <number>
        """
        # Check if user is authorized
        if not self.is_authorized(ctx.author):
            await ctx.send("You do not have permission to use this command.")
            return

        if not number:
            await ctx.send("Please provide a number to check if it's odd or even.")
            return

        async with ctx.typing():
            try:
                messages = [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": f"Is {number} odd or even?"}
                ]

                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature
                )

                reply = response.choices[0].message.content.strip()
                logging.info(f"Name:{ctx.author.name}\n User:{ctx.author.id}\n Message:Is {number} odd or even?\n Response:{reply}")

                # Send the response directly, similar to inference.py
                for i in range(0, len(reply), 2000):
                    chunk = reply[i:i + 2000]
                    await ctx.send(chunk)

            except Exception as e:
                await ctx.send("woopsies somethin happen")
                logging.error(f"groq completion did a skill issue : {e}")

async def setup(bot):
    logging.info("Setting up the IsOdd Checker cog...")
    await bot.add_cog(IsOddChecker(bot))
