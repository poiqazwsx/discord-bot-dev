# cogs/utility/inference.py
import os
import json
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from groq import AsyncGroq
import logging
from together import Together
import requests
import io
import datetime
import pytz
from tavily import TavilyClient

model = "qwen/qwen3-32b"
load_dotenv()



class Inference(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        api_key = os.environ.get("GROQ_API_KEY")
        if api_key is None:
            logging.error("GROQ_API_KEY environment variable aint real")
            raise Exception("GROQ_API_KEY aint real")

        together_api_key = os.environ.get("TOGETHER_API_KEY")
        if together_api_key is None:
            logging.warning("TOGETHER_API_KEY environment variable not found, image generation disabled")
            self.together_client = None
        else:
            self.together_client = Together(api_key=together_api_key)

            tavily_api_key = os.environ.get("TAVILY_API_KEY")
            if tavily_api_key is None:
                logging.warning("TAVILY_API_KEY environment variable not found, web search disabled")
                self.tavily_client = None
                self.search_enabled = False
            else:
                self.tavily_client = TavilyClient(tavily_api_key)
                self.search_enabled = True

        self.client = AsyncGroq(api_key=api_key)
        self.memory = {}
        self.memory_limit = 5
        self.model = model
        self.temperature = 1
        self.max_tokens = 40960
        self.system_prompt = "You are a helpful assistant."

        # Image generation settings
        self.image_gen_enabled = True
        self.image_model = "black-forest-labs/FLUX.1-schnell-Free"
        self.image_steps = 4

        # Tools for LLM
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "generate_image",
                    "description": "Generate an image based on a text prompt if asked to",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "prompt": {
                                "type": "string",
                                "description": "The text prompt describing the image to generate"
                            }
                        },
                        "required": ["prompt"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_current_time",
                    "description": "Get the current time in a specific timezone",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "timezone": {
                                "type": "string",
                                "description": "The timezone to get the current time for (e.g., 'UTC', 'US/Eastern', 'Europe/London', 'Asia/Tokyo')"
                            }
                        },
                        "required": ["timezone"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_web",
                    "description": "Search the web for current information",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The search query"
                            }
                        },
                        "required": ["query"]
                    }
                }
            }
        ]

        # Add the search_web method to the Inference class
    async def search_web(self, query):
            if not self.search_enabled or self.tavily_client is None:
                return {"error": "Web search is not available. TAVILY_API_KEY not set."}

            try:
                # Use a more explicit response format to guide the LLM
                response = self.tavily_client.search(query=query)

                # Format the results in a way that's easy for the LLM to use
                formatted_results = []
                for i, result in enumerate(response.get("results", [])[:3]):  # Limit to top 3 results
                    formatted_results.append(
                        f"Result {i+1}:\n"
                        f"Title: {result.get('title', 'No title')}\n"
                        f"URL: {result.get('url', 'No URL')}\n"
                        f"Content: {result.get('content', 'No content')}\n"
                    )

                search_response = {
                    "query": query,
                    "results": formatted_results,
                    "timestamp": datetime.datetime.now(pytz.UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
                }

                return search_response
            except Exception as e:
                logging.error(f"Error searching the web: {e}")
                return {"error": str(e)}

    # Add the get_current_time method to the Inference class

    async def get_current_time(self, timezone):
        try:
            tz = pytz.timezone(timezone)
            current_time = datetime.datetime.now(tz)
            formatted_time = current_time.strftime("%Y-%m-%d %H:%M:%S %Z")
            return {"time": formatted_time, "timezone": timezone}
        except Exception as e:
            logging.error(f"Error getting time for timezone {timezone}: {e}")
            return {"error": f"Could not get time for timezone '{timezone}': {str(e)}"}


    async def generate_image(self, prompt):
        if self.together_client is None:
            return {"error": "Image generation is not available. TOGETHER_API_KEY not set."}

        if not self.image_gen_enabled:
            return {"error": "Image generation is currently disabled."}

        try:
            response = self.together_client.images.generate(
                prompt=prompt,
                model=self.image_model,
                steps=self.image_steps
            )

            # Check if response and data are valid
            if response and hasattr(response, 'data') and response.data and len(response.data) > 0:
                image_url = response.data[0].url

                # Handle URLs that are too long for Discord's embed limit
                if len(image_url) > 2000:
                    # Download the image and upload it directly
                    image_response = requests.get(image_url)
                    if image_response.status_code == 200:
                        return {"file": image_response.content}
                    else:
                        return {"error": f"Failed to download image: HTTP {image_response.status_code}"}
                else:
                    return {"url": image_url}
            else:
                return {"error": "No image data received from API"}
        except Exception as e:
            logging.error(f"Error generating image: {e}")
            return {"error": str(e)}

    @app_commands.command(name="toggle-image-gen", description="Toggle image generation capability")
    async def toggle_image_gen(self, interaction: discord.Interaction):
        self.image_gen_enabled = not self.image_gen_enabled
        status = "enabled" if self.image_gen_enabled else "disabled"
        await interaction.response.send_message(f"Image generation is now {status}")
        logging.info(f"Image generation {status} by {interaction.user.name}")

    @app_commands.command(name="set-image-model", description="Set the image generation model")
    @app_commands.choices(model=[
        app_commands.Choice(name="FLUX.1 Schnell (Fast)", value="black-forest-labs/FLUX.1-schnell"),
    ])
    async def set_image_model(self, interaction: discord.Interaction, model: str):
        self.image_model = model
#        await interaction.response.send_message(f"Image generation model set to: {model}")
        logging.info(f"Image model changed to {model} by {interaction.user.name}")

    @app_commands.command(name="set-image-steps", description="Set the number of diffusion steps")
    async def set_image_steps(self, interaction: discord.Interaction, steps: int):
        if steps < 1 or steps > 50:
            await interaction.response.send_message("Steps must be between 1 and 50")
            return

        self.image_steps = steps
        await interaction.response.send_message(f"Image generation steps set to: {steps}")
        logging.info(f"Image steps changed to {steps} by {interaction.user.name}")

    @app_commands.command(name="generate-image", description="Generate an image from a prompt")
    async def generate_image_command(self, interaction: discord.Interaction, prompt: str):
        await interaction.response.defer()

        if not self.image_gen_enabled:
            await interaction.followup.send("Image generation is currently disabled.")
            return

        try:
            logging.info(f"Generating image with prompt: {prompt}")
            image_result = await self.generate_image(prompt)

            if "url" in image_result:
                embed = discord.Embed(
                    title="Generated Image",
                    description=f"Prompt: {prompt}",
                    color=discord.Color.blue()
                )
                embed.set_image(url=image_result["url"])
#                embed.set_footer(text=f"Model: {self.image_model} | Steps: {self.image_steps}")
                await interaction.followup.send(embed=embed)
                logging.info(f"Image generated successfully for user: {interaction.user.name}")
            elif "file" in image_result:
                # Send the image as a file attachment
                file = discord.File(io.BytesIO(image_result["file"]), filename="generated_image.png")
                await interaction.followup.send(
                    f"**Generated Image**\nPrompt: {prompt}\nModel: FLUX.1-schnell | Steps: {self.image_steps}",
                    file=file
                )
                logging.info(f"Image generated and uploaded as file for user: {interaction.user.name}")
            else:
                await interaction.followup.send(f"Error: {image_result.get('error', 'Unknown error')}")

        except Exception as e:
            logging.error(f"Error generating image: {e}")
            await interaction.followup.send(f"Error generating image: {str(e)}")

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

        # If gemini is selected, skip processing in this cog
        if current_provider != "groq":
            return

        if self.bot.user in message.mentions:
            user_id = message.author.id
            content = message.clean_content.replace(f"@{self.bot.user.name}", "").strip()
            if content:
                if user_id not in self.memory:
                   self.memory[user_id] = [{"role": "system", "content": self.system_prompt}]
                self.memory[user_id].append({"role": "user", "content": content})
                if len(self.memory[user_id]) > self.memory_limit * 2:
                    self.memory[user_id] = self.memory[user_id][-self.memory_limit * 2:]
                try:
                    messages = self.memory[user_id]

                    # Only use tools with compatible models and if image gen is enabled
                    use_tools = self.image_gen_enabled and self.together_client is not None
                    use_tools = use_tools and ("llama-3.3" in self.model or "llama-4" in self.model)
                    enable_search = self.search_enabled and self.tavily_client is not None
                    if use_tools:
                        # Update system prompt to include info about image generation
                        if messages[0]["role"] == "system":
                                messages[0]["content"] = "You are a helpful assistant. If a user asks you to generate or create an image, use the generate_image tool. If a user asks about the current time in a specific timezone, use the get_current_time tool. If asked you can search for current information on the web using the search_web tool"
                        # Convert our tool format to the format expected by Groq API
                        from groq.types.chat import ChatCompletionToolParam
                        api_tools = []
                        for tool in self.tools:
                            api_tools.append(ChatCompletionToolParam(
                                type=tool["type"],
                                function={
                                    "name": tool["function"]["name"],
                                    "description": tool["function"]["description"],
                                    "parameters": tool["function"]["parameters"]
                                }
                            ))

                        response = await self.client.chat.completions.create(
                            model=self.model,
                            messages=messages,
                            max_tokens=self.max_tokens,
                            temperature=self.temperature,
                            tools=api_tools,
                            tool_choice="auto"
                        )
                    else:
                        # Restore regular system prompt if needed
                        if messages[0]["role"] == "system" and "generate_image tool" in messages[0]["content"]:
                            messages[0]["content"] = self.system_prompt

                        response = await self.client.chat.completions.create(
                            model=self.model,
                            messages=messages,
                            max_tokens=self.max_tokens,
                            temperature=self.temperature
                        )

                    response_message = response.choices[0].message

                    # Check if tool call is present
                    if hasattr(response_message, 'tool_calls') and response_message.tool_calls:
                        # Handle tool calls
                        for tool_call in response_message.tool_calls:
                            if tool_call.function.name == "generate_image":
                                try:
                                    args = json.loads(tool_call.function.arguments)
                                    prompt = args.get("prompt")

                                    # Tell user that we're generating an image
                                    await message.reply(f"Generating image with prompt: {prompt}")

                                    # Actually generate the image
                                    image_result = await self.generate_image(prompt)

                                    if "url" in image_result:
                                        try:
                                            # Create an embed with the image
                                            embed = discord.Embed(
                                                title="Generated Image",
                                                description=f"Prompt: {prompt}",
                                                color=discord.Color.blue()
                                            )
                                            embed.set_image(url=image_result["url"])
                                            embed.set_footer(text=f"Model: flux| Steps: {self.image_steps}")
                                            await message.reply(embed=embed)
                                        except discord.HTTPException as embed_error:
                                            logging.error(f"Discord embed error: {embed_error}")
                                            # Fallback to downloading and uploading the image
                                            try:
                                                img_response = requests.get(image_result["url"])
                                                if img_response.status_code == 200:
                                                    file = discord.File(io.BytesIO(img_response.content), filename="generated_image.png")
                                                    await message.reply(

                                                        file=file
                                                    )
                                                else:
                                                    await message.reply(f"Failed to download image: HTTP {img_response.status_code}")
                                            except Exception as download_error:
                                                logging.error(f"Image download fallback error: {download_error}")
                                                await message.reply(f"Failed to process the image: {str(download_error)}")
                                    elif "file" in image_result:
                                        # Send the image as a file attachment
                                        file = discord.File(io.BytesIO(image_result["file"]), filename="generated_image.png")
                                        await message.reply(
                                            file=file
                                        )
                                    else:
                                        await message.reply(f"Error generating image: {image_result.get('error', 'Unknown error')}")

                                    # Add the tool result to the messages
                                    tool_result = {"url": "image_generated"} if "url" in image_result or "file" in image_result else image_result
                                    self.memory[user_id].append({
                                        "role": "assistant",
                                        "content": None,
                                        "tool_calls": [{
                                            "id": tool_call.id,
                                            "type": "function",
                                            "function": {
                                                "name": "generate_image",
                                                "arguments": tool_call.function.arguments
                                            }
                                        }]
                                    })
                                    self.memory[user_id].append({
                                        "role": "tool",
                                        "tool_call_id": tool_call.id,
                                        "content": json.dumps(tool_result)
                                    })
                                except Exception as e:
                                    logging.error(f"Error in image generation tool call: {e}")
                                    await message.reply(f"Error processing image generation: {str(e)}")

                            elif tool_call.function.name == "get_current_time":
                                        try:
                                            args = json.loads(tool_call.function.arguments)
                                            timezone = args.get("timezone", "UTC")

                                            # Get the current time
                                            time_result = await self.get_current_time(timezone)

                                            if "error" in time_result:
                                                await message.reply(f"Error getting time: {time_result['error']}")
                                            else:
                                                await message.reply(f"Current time in {time_result['timezone']}: {time_result['time']}")

                                            # Add the tool result to the memory
                                            self.memory[user_id].append({
                                                "role": "assistant",
                                                "content": None,
                                                "tool_calls": [{
                                                    "id": tool_call.id,
                                                    "type": "function",
                                                    "function": {
                                                        "name": "get_current_time",
                                                        "arguments": tool_call.function.arguments
                                                    }
                                                }]
                                            })
                                            self.memory[user_id].append({
                                                "role": "tool",
                                                "tool_call_id": tool_call.id,
                                                "content": json.dumps(time_result)
                                            })
                                        except Exception as e:
                                            logging.error(f"Error in time tool call: {e}")
                                            await message.reply(f"Error processing time request: {str(e)}")

                            elif tool_call.function.name == "search_web":
                                        try:
                                            args = json.loads(tool_call.function.arguments)
                                            query = args.get("query")

                                            # Tell user that we're searching
                                            await message.reply(f"Searching the web for: {query}")

                                            # Perform the search
                                            search_result = await self.search_web(query)

                                            if "error" in search_result:
                                                await message.reply(f"Error searching: {search_result['error']}")
                                            else:
                                                # Don't send any user-facing message about the search results yet

                                            # Add the tool call to the memory
                                                self.memory[user_id].append({
                                                "role": "assistant",
                                                "content": None,
                                                "tool_calls": [{
                                                    "id": tool_call.id,
                                                    "type": "function",
                                                    "function": {
                                                        "name": "search_web",
                                                        "arguments": tool_call.function.arguments
                                                    }
                                                }]
                                            })

                                            # Add the tool response to the memory
                                            self.memory[user_id].append({
                                                "role": "tool",
                                                "tool_call_id": tool_call.id,
                                                "content": json.dumps(search_result)
                                            })

                                            # Make a follow-up call to get the LLM's response with the search results
                                            follow_up_response = await self.client.chat.completions.create(
                                                model=self.model,
                                                messages=self.memory[user_id],
                                                max_tokens=self.max_tokens,
                                                temperature=self.temperature
                                            )

                                            follow_up_reply = follow_up_response.choices[0].message.content.strip()
                                            if follow_up_reply:
                                                # Add the follow-up response to memory
                                                self.memory[user_id].append({"role": "assistant", "content": follow_up_reply})
                                                # Send the response to the user
                                                for i in range(0, len(follow_up_reply), 2000):
                                                    chunk = follow_up_reply[i:i + 2000]
                                                    await message.reply(chunk)
                                            else:
                                                await message.reply("I couldn't generate a response based on the search results.")

                                        except Exception as e:
                                            logging.error(f"Error in search web tool call: {e}")
                                            await message.reply(f"Error processing web search: {str(e)}")


                        # If there was a message content besides the tool calls, send it
                        if response_message.content and response_message.content.strip():
                            reply = response_message.content.strip()
                            self.memory[user_id].append({"role": "assistant", "content": reply})
                            for i in range(0, len(reply), 2000):
                                chunk = reply[i:i + 2000]
                                await message.reply(chunk)
                    else:
                        # No tool calls, just regular content
                        if response_message.content:
                            reply = response_message.content.strip()
                            logging.info(f"Name:{message.author.name}\n User:{message.author.id}\n Message{message.content}\n Response:{reply}")
                            self.memory[user_id].append({"role": "assistant", "content": reply})
                            for i in range(0, len(reply), 2000):
                                chunk = reply[i:i + 2000]
                                await message.reply(chunk)
                        else:
                            await message.reply("I couldn't generate a response.")

                except Exception as e:
                    await message.reply("woopsies somethin happen")
                    logging.error(f"groq completion did a skill issue : {e}")

async def setup(bot):
    logging.info("setting up the inference cog...")
    await bot.add_cog(Inference(bot))
