# cogs/utility/code_generator.py
import discord
from discord.ext import commands
import logging
import re
import os
from groq import AsyncGroq

class CodeGenerator(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        api_key = os.environ.get("GROQ_API_KEY")
        if api_key is None:
            logging.error("GROQ_API_KEY environment variable not found")
            raise Exception("GROQ_API_KEY not found")
        self.client = AsyncGroq(api_key=api_key)
        self.model = "llama-3.3-70b-versatile"
        self.temperature = 1
        self.max_tokens = 2000
        self.supported_languages = {
            "python": "py",
            "java": "java",
            "javascript": "js",
            "c": "c",
            "cpp": "cpp",
            "c++": "cpp",
            "rust": "rust",
            "go": "go",
            "csharp": "cs",
            "c#": "cs"
        }

    @commands.command()
    async def code(self, ctx, *, prompt=None):
        if not prompt:
            await ctx.send("Please provide a prompt describing the code you want to generate.")
            return

        # First, determine what language to use
        language_prompt = (
            "What programming language would be most appropriate for the following task? If the user gives one they want use that instead unless it isnt in the list."
            "Respond with just the name of one language from this list: Python, Java, JavaScript, C, C++, Rust, Go, C#."
            f"Task: {prompt}"
        )

        async with ctx.typing():
            try:
                # Determine the language
                language_response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": language_prompt}],
                    temperature=0.2,
                    max_tokens=50
                )
                language_text = language_response.choices[0].message.content.strip().lower()

                # Find the language in the response
                detected_language = None
                for lang in self.supported_languages:
                    if lang in language_text:
                        detected_language = lang
                        break

                if not detected_language:
                    detected_language = "python"  # Default to Python if no clear language is detected

                lang_code = self.supported_languages.get(detected_language, "py")

                # Now generate the actual code
                code_prompt = (
                    f"Write complete, working {detected_language} code for the following task. "
                    f"Only provide the code itself without explanations, wrapped in a code block. "
                    f"Task: {prompt}"
                )

                code_response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": code_prompt}],
                    temperature=self.temperature,
                    max_tokens=self.max_tokens
                )

                code_text = code_response.choices[0].message.content.strip()

                # Extract the code block using regex
                code_block_regex = r"```(?:\w+)?\n([\s\S]+?)\n```"
                match = re.search(code_block_regex, code_text)

                if match:
                    code = match.group(1)
                else:
                    # If no code block is found, use the entire response
                    code = code_text

                # Send generated code
                await ctx.send(f"Generated {detected_language} code:\n```{lang_code}\n{code}\n```")

                # Now compile and run the code using the Compiler cog
                compiler_cog = self.bot.get_cog("Compiler")
                if compiler_cog:
                    await ctx.send("Executing code...")
                    result, error = await compiler_cog.compile_code(
                        compiler_cog.language_compilers[lang_code]["id"],
                        code
                    )

                    if error:
                        await ctx.send(f"Error running code: {error}")
                    else:
                        output = compiler_cog.format_output(result, lang_code)

                        # Send the output, handling Discord's message length limit
                        if len(output) > 2000:
                            chunks = [output[i:i+1994] for i in range(0, len(output), 1994)]
                            for chunk in chunks:
                                await ctx.send(chunk)
                        else:
                            await ctx.send(output)
                else:
                    await ctx.send("Compiler module not available. Code execution skipped.")

            except Exception as e:
                logging.error(f"Error in code generation: {e}")
                await ctx.send(f"An error occurred while generating or running the code: {str(e)}")

async def setup(bot):
    logging.info("Setting up the code generator cog...")
    await bot.add_cog(CodeGenerator(bot))
