# bot/cogs/testing/deepsite.py
import discord
from discord.ext import commands
import logging
import re
import os
import io
import subprocess
import platform
import tempfile
from groq import AsyncGroq

# Define authorized role IDs like in fetch.py
deepsite_roles = [1222332241070395432, 1225222029700104234]

class DeepSiteGenerator(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        api_key = os.environ.get("GROQ_API_KEY")
        if api_key is None:
            logging.error("GROQ_API_KEY environment variable not found for DeepSiteGenerator")
            # Depending on your application's needs, you might want to handle this differently.
            # For now, we'll let it potentially raise an error later if used without a key.
            self.client = None
        else:
            self.client = AsyncGroq(api_key=api_key)

        # --- Configuration ---
        # You might want to make these configurable later, perhaps using other cogs
        self.model = "deepseek-r1-distill-llama-70b" # Llama 3.1 70B is often good for code/structured output
        self.temperature = 0.7 # A bit of creativity, but not too wild
        self.max_tokens = 4096 # Allow for larger HTML files
        self.system_prompt = """You are an expert web developer specializing in creating single-file HTML websites.
Your goal is to generate complete, functional HTML code based on the user's prompt.
Include HTML structure, CSS (using Tailwind CSS via its CDN link: <script src="https://cdn.tailwindcss.com"></script> in the <head>), and JavaScript all within the single HTML file provided.
Ensure the generated code is ready to be saved as an `.html` file and opened directly in a browser.

If the user provides existing HTML code to iterate on, modify that code according to the new instructions.

Respond ONLY with the complete, raw HTML code, starting precisely with `<!DOCTYPE html>` and ending precisely with `</html>`.
Do NOT include any explanations, comments outside the code, or markdown code fences (like ```html ... ```) around your final output."""
        # --- End Configuration ---

        if self.client is None:
            logging.warning("DeepSiteGenerator initialized without a valid Groq client due to missing API key.")

    def is_authorized(self, user: discord.Member):
        """Check if user has the required roles for deepsite commands"""
        return any(role.id in deepsite_roles for role in user.roles)

    def extract_html_code(self, text: str) -> str:
        """Extracts HTML code, handling potential markdown fences."""
        # Regex to find code blocks (optional language specifier)
        code_block_regex = r"```(?:html)?\n([\s\S]+?)\n```"
        match = re.search(code_block_regex, text, re.IGNORECASE | re.DOTALL)

        if match:
            # If a code block is found, return its content
            code = match.group(1).strip()
        else:
            # If no code block, assume the entire text might be the code
            # Try to find the start and end tags just in case
            start_match = re.search(r"<!DOCTYPE html>", text, re.IGNORECASE)
            end_match = re.search(r"</html>", text, re.IGNORECASE)
            if start_match and end_match:
                code = text[start_match.start() : end_match.end() + len("</html>")].strip()
            else:
                # Fallback: return the whole text if tags aren't found either
                code = text.strip()

        # Ensure it starts correctly (strip potential leading markdown/text)
        doctype_match = re.search(r"<!DOCTYPE html>", code, re.IGNORECASE)
        if doctype_match:
            code = code[doctype_match.start():]

        return code

    async def get_previous_html(self, ctx: commands.Context) -> str | None:
        """Checks if the command is a reply and tries to get HTML from the replied message."""
        if not ctx.message.reference or not ctx.message.reference.resolved:
            return None

        replied_message = ctx.message.reference.resolved
        content = replied_message.content
        html_code = None

        # 1. Check for attachments
        if replied_message.attachments:
            for attachment in replied_message.attachments:
                if attachment.filename.lower().endswith((".html", ".htm")):
                    try:
                        html_bytes = await attachment.read()
                        html_code = html_bytes.decode('utf-8')
                        logging.info(f"Using HTML from attachment: {attachment.filename}")
                        return html_code # Return first valid HTML attachment
                    except Exception as e:
                        logging.warning(f"Could not read or decode attachment {attachment.filename}: {e}")

        # 2. Check message content for code blocks or raw HTML
        if content:
            html_code = self.extract_html_code(content)
            # Basic check to see if it looks like HTML
            if html_code.startswith("<!DOCTYPE html>") and html_code.endswith("</html>"):
                 logging.info("Using HTML from replied message content.")
                 return html_code
            else:
                 logging.info("Replied message content doesn't look like valid HTML after extraction.")
                 html_code = None # Reset if extraction didn't yield valid HTML

        if html_code:
            logging.info("Using HTML from replied message content.")
            return html_code
        else:
            logging.info("No valid HTML found in replied message or its attachments.")
            return None

    def open_in_browser(self, file_path):
        """Open the HTML file in the default browser based on platform"""
        try:
            if platform.system() == 'Windows':
                os.startfile(file_path)
            elif platform.system() == 'Darwin':  # macOS
                subprocess.run(['open', file_path], check=True)
            else:  # Linux
                subprocess.run(['xdg-open', file_path], check=True)
            return True
        except Exception as e:
            logging.error(f"Failed to open file in browser: {e}")
            return False

    @commands.command(aliases=['ds', 'website'])
    async def deepsite(self, ctx: commands.Context, *, prompt: str):
        """
        Generates a single-file HTML website based on your prompt using an AI model.
        Optionally, reply to a message containing HTML code (or an .html file) to iterate on it.

        Usage:
        !deepsite <your website description>
        (Replying to existing HTML/file) !deepsite <changes you want to make>
        """
        # Check if user is authorized
        if not self.is_authorized(ctx.author):
            await ctx.send("You do not have permission to use this command.")
            return

        if not self.client:
            await ctx.send("DeepSiteGenerator is not configured correctly (missing API key). Please contact the bot owner.")
            logging.error("DeepSite command failed: Groq client not initialized.")
            return

        if not prompt:
            await ctx.send("Please provide a prompt describing the website you want to generate.")
            return

        previous_html = await self.get_previous_html(ctx)

        messages = [{"role": "system", "content": self.system_prompt}]
        if previous_html:
            messages.append({"role": "assistant", "content": previous_html})
            messages.append({"role": "user", "content": f"Iterate on the previous HTML code with the following instructions: {prompt}"})
            await ctx.send(f"🔄 Iterating on previous design with prompt: `{prompt[:100]}...`")
        else:
            messages.append({"role": "user", "content": prompt})
            await ctx.send(f"✨ Generating new site with prompt: `{prompt[:100]}...`")


        async with ctx.typing():
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature
                )

                generated_content = response.choices[0].message.content.strip()
                extracted_html = self.extract_html_code(generated_content)

                if not extracted_html.lower().startswith("<!doctype html"):
                   logging.warning(f"Generated content doesn't start with <!DOCTYPE html>:\n{extracted_html[:200]}")
                   # Optionally prepend if missing and it looks like HTML otherwise
                   if "<html" in extracted_html.lower() and "<body" in extracted_html.lower():
                       extracted_html = "<!DOCTYPE html>\n" + extracted_html


                # Send the generated HTML as a file
                html_bytes = extracted_html.encode('utf-8')
                file_buffer = io.BytesIO(html_bytes)
                discord_file = discord.File(fp=file_buffer, filename="generated_site.html")

                # Also save the file locally and open in browser
                with tempfile.NamedTemporaryFile(delete=False, suffix='.html') as tmp_file:
                    tmp_file.write(html_bytes)
                    local_path = tmp_file.name

                # Try to open the file in browser
                opened = self.open_in_browser(local_path)

                if opened:
                    await ctx.send(f"✅ Website code generated for '{prompt[:50]}...'. Here is the file (also opened in your browser):", file=discord_file)
                else:
                    await ctx.send(f"✅ Website code generated for '{prompt[:50]}...'. Here is the file (couldn't open in browser):", file=discord_file)

                logging.info(f"DeepSite generated HTML file for user {ctx.author} (prompt: {prompt[:50]}...), saved locally at {local_path}")

            except Exception as e:
                logging.error(f"Error during DeepSite generation for prompt '{prompt[:50]}...': {e}", exc_info=True)
                await ctx.send(f"❌ An error occurred while generating the website: {str(e)}")

async def setup(bot):
    logging.info("Setting up the DeepSite Generator cog...")
    await bot.add_cog(DeepSiteGenerator(bot))
