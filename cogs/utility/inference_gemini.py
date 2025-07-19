import os
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
import logging
from google import genai
from google.genai.types import Tool, GenerateContentConfig, GoogleSearch

# Import genai.types directly for multimodal content structure
from google.genai import types
import re # Import regex for URL finding

from io import BytesIO
import base64
import time
load_dotenv()

google_search_tool = Tool(
    google_search = GoogleSearch()
)
class GeminiInference(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        api_key = os.environ.get("GEMINI_API_KEY")
        if api_key is None:
            logging.error("GEMINI_API_KEY environment variable not found")
            raise Exception("GEMINI_API_KEY not found")

        # Initialize the Gemini client once for reuse
        self.client = genai.Client(api_key=api_key)
        self.memory = {}  # Stores chat objects per user
        self.memory_limit = 5  # Not currently used, but kept for potential future expansion
        # Default model - using 1.5-flash as it's known to support video input reliably
        self.model = "gemini-2.5-pro"
        self.temperature = 1
        self.max_tokens = 65536
        self.system_prompt = "You are a helpful assistant."
        # Regex to find YouTube URLs
        # This pattern is basic and might need refinement for edge cases
        self.youtube_url_pattern = re.compile(
            r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/"
            r"(watch\?v=[\w-]+(&\S+)?|embed/[\w-]+|v/[\w-]+|[\w-]+)" # watch?v=..., youtu.be/..., embed, v
        )
        # Models known to support video input
        self.video_capable_models = ["gemini-1.5-flash", "gemini-1.5-pro"]


    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return

        inference_toggle_cog = self.bot.get_cog("Toggle_llm")
        if inference_toggle_cog is None or not inference_toggle_cog.is_inference_enabled():
            return

        # Check which provider is selected
        provider_selector = self.bot.get_cog("ProviderSelector")
        if provider_selector is None:
            logging.error("ProviderSelector cog not found")
            return

        current_provider = provider_selector.get_current_provider()

        # If groq is selected, skip processing in this cog
        if current_provider != "gemini":
            return

        # Check if the bot was mentioned or if it's a reply to the bot (implies interaction)
        is_mentioned = self.bot.user in message.mentions
        is_reply_to_bot = message.reference and message.reference.resolved and message.reference.resolved.author == self.bot.user

        if is_mentioned or is_reply_to_bot:
            user_id = message.author.id

            # Extract content, message.clean_content automatically removes mentions
            content = message.clean_content

            # Find YouTube URLs in the original message content (before cleaning)
            # Use finditer to get match objects and extract the full matched string
            youtube_urls = [match.group(0) for match in self.youtube_url_pattern.finditer(message.content)]

            text_prompt = content
            # Remove URLs from the text prompt if they were found
            if youtube_urls:
                 # Iterate through found URLs and remove them from the text_prompt
                 for url in youtube_urls:
                     text_prompt = text_prompt.replace(url, "").strip() # Remove the matched URL string

            text_prompt = text_prompt.strip() # Clean up leading/trailing whitespace again

            if not text_prompt and not youtube_urls:
                # Only bot mention or reply without content
                return

            try:
                async with message.channel.typing():
                    # Initialize conversation history if it doesn't exist
                    if user_id not in self.memory:
                        self.memory[user_id] = []

                    # Check if we're handling video input and the model supports it
                    if youtube_urls and self.model in self.video_capable_models:
                        logging.info(f"Processing video input from {message.author.name} ({message.author.id}) with model {self.model}. URLs: {youtube_urls}, Text: '{text_prompt}'")

                        contents_parts = []
                        # Add FileData parts for each YouTube URL
                        # Note: Gemini API requires a MIME type. video/mp4 is commonly used,
                        # but the API handles the actual fetching/processing.
                        for url in youtube_urls:
                            contents_parts.append(types.Part(file_data=types.FileData(file_uri=url, mime_type='video/mp4')))

                        # Add the text prompt part
                        if text_prompt:
                            contents_parts.append(types.Part(text=text_prompt))
                        else:
                            # If no text prompt, add a default instruction
                            contents_parts.append(types.Part(text="Summarize the video."))

                        # Add the multimodal input to memory (as a text representation)
                        memory_input_text = f"Video(s): {', '.join(youtube_urls)}"
                        if text_prompt:
                             memory_input_text += f"\nText: {text_prompt}"
                        self.memory[user_id].append({"role": "user", "content": memory_input_text})

                        # Use streaming with thoughts for video content
                        thoughts = ""
                        answer = ""

                        for chunk in self.client.models.generate_content_stream(
                            model=self.model,
                            contents=types.Content(parts=contents_parts),
                            config=GenerateContentConfig(
                                temperature=self.temperature,
                                max_output_tokens=self.max_tokens,
                                thinking_config=types.ThinkingConfig(
                                    include_thoughts=True
                                )
                            )
                        ):
                            for part in chunk.candidates[0].content.parts:
                                if not part.text:
                                    continue
                                elif part.thought:
                                    thoughts += part.text
                                else:
                                    answer += part.text

                        reply = answer.strip() if answer else "The model processed the video but did not return a text response."

                        # Add the response to memory
                        self.memory[user_id].append({"role": "assistant", "content": reply})

                        # Trim memory if needed
                        if len(self.memory[user_id]) > self.memory_limit * 2:
                            self.memory[user_id] = self.memory[user_id][-self.memory_limit * 2:]

                        logging.info(f"Name:{message.author.name}\n User:{message.author.id}\n Multimodal Input:{memory_input_text}\n Response:{reply}")

                        # Send thoughts summary if available
                        if thoughts.strip():
                            thoughts_message = f"**Thoughts Summary:**\n{thoughts.strip()}"
                            # Send thoughts in chunks if too long
                            for i in range(0, len(thoughts_message), 2000):
                                chunk = thoughts_message[i:i + 2000]
                                await message.reply(chunk)

                        # Send the response in chunks if it's too long
                        for i in range(0, len(reply), 2000):
                            chunk = reply[i:i + 2000]
                            await message.reply(chunk)

                    elif self.model == "gemini-2.0-flash-exp-image-generation":
                        # Process with image generation capabilities (kept separate)
                        await self.process_with_image_gen(message, content) # Use original 'content' here for image prompt
                        return

                    elif youtube_urls and self.model not in self.video_capable_models:
                         # URLs found but model doesn't support video
                         video_models_str = ", ".join([f"`{m}`" for m in self.video_capable_models])
                         await message.reply(f"The current model (`{self.model}`) does not support video input. Please switch to a model like {video_models_str} using `/gemini_model` to process videos.")
                         logging.info(f"User {message.author.id} attempted video processing with non-video model {self.model}")

                    elif text_prompt: # Regular text processing if no URLs or model isn't video-capable and there's text
                        logging.info(f"Processing text input from {message.author.name} ({message.author.id}) with model {self.model}. Text: '{text_prompt}'")
                        # Add the text message to the memory BEFORE the API call
                        self.memory[user_id].append({"role": "user", "content": text_prompt})

                        # Use streaming with thoughts for text content
                        thoughts = ""
                        answer = ""

                        for chunk in self.client.models.generate_content_stream(
                            model=self.model,
                            contents=text_prompt,
                            config=GenerateContentConfig(
                                temperature=self.temperature,
                                max_output_tokens=self.max_tokens,
                                thinking_config=types.ThinkingConfig(
                                    include_thoughts=True
                                )
                            )
                        ):
                            for part in chunk.candidates[0].content.parts:
                                if not part.text:
                                    continue
                                elif part.thought:
                                    thoughts += part.text
                                else:
                                    answer += part.text

                        reply = answer.strip() if answer else "The model did not return a text response."

                        # Add the response to memory
                        self.memory[user_id].append({"role": "assistant", "content": reply})

                        # Trim memory if needed
                        if len(self.memory[user_id]) > self.memory_limit * 2:
                            self.memory[user_id] = self.memory[user_id][-self.memory_limit * 2:]

                        logging.info(f"Name:{message.author.name}\n User:{message.author.id}\n Message:{text_prompt}\n Response:{reply}")

                        # Send thoughts summary if available
                        if thoughts.strip():
                            thoughts_message = f"**<think>**\n{thoughts.strip()}\n**<\\think>**"
                            # Send thoughts in chunks if too long
                            for i in range(0, len(thoughts_message), 2000):
                                chunk = thoughts_message[i:i + 2000]
                                await message.reply(chunk)

                        # Send the response in chunks if it's too long
                        for i in range(0, len(reply), 2000):
                            chunk = reply[i:i + 2000]
                            await message.reply(chunk)
                            time.sleep(1)

            except Exception as e:
                # More specific error message
                await message.reply("An error occurred while processing your request.")
                logging.error(f"Gemini completion error for user {message.author.id}: {e}", exc_info=True) # Add exc_info to log traceback

    async def process_with_image_gen(self, message, prompt):
        """Process a message with the image generation model, which can return text, images, or both based on the prompt"""
        try:
            async with message.channel.typing():
                logging.info(f"Processing with image generation model. Prompt: {prompt}")

                # Add the user prompt to memory (simplified)
                user_id = message.author.id
                if user_id not in self.memory:
                    self.memory[user_id] = []
                self.memory[user_id].append({"role": "user", "content": prompt})

                # Call Gemini's API with multimodal response capability
                # Removed tools and response_modalities parameters based on diagnostic errors.
                # The model should be "gemini-2.0-flash-exp-image-generation" in this specific method call context.
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=GenerateContentConfig(
                        system_instruction="You are a helpful assistant."),
                )

                # Process the response which may contain text, image, or both
                # The genai library response structure might differ slightly based on model/version.
                # This part assumes the response has candidates and content/parts, and image data in inline_data.
                text_response = ""
                image_data = None

                if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                    for part in response.candidates[0].content.parts:
                        if part.text is not None:
                            text_response += part.text
                        elif part.inline_data is not None and part.inline_data.data is not None:
                             # Assuming inline_data contains the generated image bytes (base64 or raw)
                             # Try decoding as base64 first, then raw bytes if that fails
                             try:
                                 image_bytes = base64.b64decode(part.inline_data.data)
                                 image_data = BytesIO(image_bytes)
                                 logging.debug("Decoded image data as base64.")
                             except Exception:
                                 # If base64 decoding failed, try treating it as raw bytes
                                 try:
                                     image_data = BytesIO(part.inline_data.data)
                                     logging.debug("Treated image data as raw bytes.")
                                 except Exception as byte_error:
                                     logging.error(f"Could not process inline image data (not base64 or raw bytes): {byte_error}", exc_info=True)
                                     image_data = None # Failed to process image data


                # Add the response text to memory
                if text_response:
                    self.memory[user_id].append({"role": "assistant", "content": text_response})

                # Handle different response types
                if image_data:
                    # Send image with text if available
                    discord_file = discord.File(image_data, filename="generated_image.png")

                    if text_response:
                        # Send text in chunks if it's too long, with the image in the first message
                        if len(text_response) <= 2000:
                            await message.reply(text_response, file=discord_file)
                        else:
                            # Send first chunk with image
                            await message.reply(text_response[:2000], file=discord_file)
                            # Send remaining text in chunks
                            for i in range(2000, len(text_response), 2000):
                                chunk = text_response[i:i+2000]
                                await message.reply(chunk)
                    else:
                        await message.reply(file=discord_file)

                    logging.info(f"Generated image for {message.author.name} ({message.author.id})")
                elif text_response:
                    # Text-only response
                    for i in range(0, len(text_response), 2000):
                        chunk = text_response[i:i+2000]
                        await message.reply(chunk)
                else:
                    # No content generated
                    await message.reply("I couldn't generate a response (neither text nor image) for that prompt. Please try something else.")

        except Exception as e:
            await message.reply("I encountered an error processing your image request. Please try again with a different prompt.")
            logging.error(f"Image generation model error for user {message.author.id}: {e}", exc_info=True) # Add exc_info

    @app_commands.command(name="gemini_model", description="Change the Gemini model")
    async def change_gemini_model(self, interaction: discord.Interaction, model: str):
        """Change the Gemini model being used"""
        auth_cog = self.bot.get_cog("Auth")

        if auth_cog is None:
            logging.error("The Auth cog is not loaded.")
            return

        if not auth_cog.is_authorized(interaction):
            await interaction.response.send_message("You are not authorized to use this command.", ephemeral=True)
            logging.error(f"{interaction.user} tried to change Gemini model but was not authorized.")
            return

        # Define available models (update this list based on current Gemini offerings)
        available_models = [
            "gemini-2.0-flash",
            "gemini-2.0-pro",
            "gemini-1.5-flash", # Supports video input
            "gemini-1.5-pro",   # Supports video input
            "gemini-2.0-flash-exp-image-generation" # Supports image output? (based on original code)
        ]

        if model not in available_models:
            await interaction.response.send_message(f"Invalid model. Available models: {', '.join([f'`{m}`' for m in available_models])}", ephemeral=True)
            return

        self.model = model

        # Reset memory to use the new model for all users
        self.memory = {}

        response_message = f"Gemini model changed to: `{model}`"
        if model in self.video_capable_models:
             response_message += ". This model supports video input."
        elif model == "gemini-2.0-flash-exp-image-generation":
             response_message += ". This model can potentially generate images."

        await interaction.response.send_message(response_message, ephemeral=True)

        logging.info(f"Gemini model changed to {model} by {interaction.user.name} ({interaction.user.id})")


async def setup(bot):
    logging.info("Setting up the Gemini inference cog...")
    await bot.add_cog(GeminiInference(bot))
