# cogs/utility/compiler.py
from discord.ext import commands
import logging
import aiohttp
import json
import re
import argparse
import shlex

class ArgumentParserError(Exception):
    pass

class CustomArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise ArgumentParserError(message)

class Compiler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.godbolt_url = "https://godbolt.org/api/compiler"
        self.language_compilers = {
            "py": {"id": "python311", "name": "Python 3.11"},
            "python": {"id": "python311", "name": "Python 3.11"},
            "java": {"id": "java2102", "name": "jdk 21.0.2"},
            "js": {"id": "v8trunk", "name": "v8 (trunk)"},
            "javascript": {"id": "v8trunk", "name": "v8 (trunk)"},
            "c": {"id": "g142", "name": "x86-64 gcc 14.2"},
            "cpp": {"id": "g142", "name": "x86-64 gcc 14.2"},
            "c++": {"id": "g142", "name": "x86-64 gcc 14.2"},
            "rust": {"id": "r190", "name": "rustc 1.9.0"},
            "asm": {"id": "nasm21601", "name": "NASM 2.16.01"},
            "cs": {"id": "dotnet90csharpcoreclr", "name": ".NET 9.0 CoreCLR"},
            "c#": {"id": "dotnet90csharpcoreclr", "name": ".NET 9.0 CoreCLR"},
            "go": {"id": "gl1232", "name": "x86-64 gc 1.23.2"},
        }

    async def compile_code(self, compiler_id, source_code, user_args="", show_asm=False):
        async with aiohttp.ClientSession() as session:
            compile_endpoint = f"{self.godbolt_url}/{compiler_id}/compile"

            payload = {
                "source": source_code,
                "options": {
                    "userArguments": user_args,
                    "executeParameters": {
                        "args": [],
                        "stdin": ""
                    },
                    "compilerOptions": {
                        "executorRequest": True
                    },
                    "filters": {
                        "binary": False,
                        "execute": True,
                        "labels": True,
                        "directives": True,
                        "commentOnly": True,
                        "demangle": True,
                        "intel": True
                    }
                }
            }

            try:
                headers = {"Content-Type": "application/json", "Accept": "text/plain"}
                async with session.post(compile_endpoint, json=payload, headers=headers) as response:
                    if response.status != 200:
                        return None, f"API returned status code {response.status}"

                    response_text = await response.text()
                    # Try to parse as JSON first
                    result = {}
                    compilation_messages = None
                    try:
                        response_json = json.loads(response_text)
                        if 'compilationMessages' in response_json:
                            compilation_messages = response_json['compilationMessages']
                            result['compilationMessages'] = compilation_messages
                        return response_json, None
                    except json.JSONDecodeError:
                        # If not JSON, parse as plain text
                        pass

                    # Parse plain text for stdout
                    stdout_start_marker = "Standard out:\n"
                    stdout_start_index = response_text.find(stdout_start_marker)
                    if stdout_start_index != -1:
                        stdout_end_index = response_text.find("\nStandard error:", stdout_start_index)
                        if stdout_end_index == -1:
                            stdout_end_index = len(response_text)
                        stdout_output = response_text[stdout_start_index + len(stdout_start_marker):stdout_end_index].strip()
                        result['execResult'] = result.get('execResult', {})
                        result['execResult']['stdout'] = stdout_output

                    # Parse plain text for stderr
                    stderr_start_marker = "Standard error:\n"
                    stderr_start_index = response_text.find(stderr_start_marker)
                    if stderr_start_index != -1:
                        stderr_output = response_text[stderr_start_index + len(stderr_start_marker):].strip()
                        result['execResult'] = result.get('execResult', {})
                        result['execResult']['stderr'] = stderr_output

                    # If we found any output, consider it a success
                    # Check for result code pattern in response text
                    result_code_match = re.search(r"# Compiler exited with result code (\d+)", response_text)
                    if result_code_match:
                        exit_code = int(result_code_match.group(1))
                        result['execResult'] = result.get('execResult', {})
                        result['execResult']['code'] = exit_code
                        return result, None
                    elif 'execResult' in result:
                        result['execResult']['code'] = 0
                        return result, None
                    else:
                        logging.error(f"Failed to parse response: {response_text[:500]}")
                        return None, "Failed to parse API response"
            except Exception as e:
                logging.error(f"Error compiling code: {e}")
                return None, f"Error: {str(e)}"

    def format_output(self, result, language, show_asm=False):
        if not result:
            return "Failed to compile or run code."

        output = []
        output.append("**Compilation provided by Compiler Explorer at https://godbolt.org/**")

        # Process compilation messages
        self._process_compilation_messages(result, output)

        # Process compilation errors
        if self._process_compilation_errors(result, output):
            return "\n".join(output)

        # Process assembly output if requested
        self._process_assembly_output(result, show_asm, output)

        # Process execution results
        self._process_execution_results(result, output)

        # If no output was generated but compilation was successful
        if len(output) <= 1:
            output.append("**Compilation successful but no output was generated.**")

        return "\n".join(output)

    def _process_compilation_messages(self, result, output):
        if "compilationMessages" in result and result["compilationMessages"]:
            compilation_msgs = "\n".join([f"- {msg.get('message', '')}" for msg in result["compilationMessages"]])
            if compilation_msgs:
                output.append(f"**Compilation Messages:**\n```\n{compilation_msgs[:1900]}```")

    def _process_compilation_errors(self, result, output):
        if "buildResult" in result and result["buildResult"].get("code") != 0:
            if "buildResult" in result and "stderr" in result["buildResult"]:
                stderr = result["buildResult"]["stderr"]
                output.append(f"**Compilation Error:**\n```\n{stderr[:1900]}```")
                return True
        return False

    def _process_assembly_output(self, result, show_asm, output):
        if show_asm and "asm" in result:
            asm_output = []
            for asm_section in result["asm"]:
                if "text" in asm_section:
                    asm_output.append(asm_section["text"])

            if asm_output:
                asm_combined = "\n".join(asm_output)
                if len(asm_combined) > 1900:
                    asm_combined = asm_combined[:1900] + "\n... (truncated)"
                output.append(f"**Assembly:**\n```asm\n{asm_combined}```")

    def _process_execution_results(self, result, output):
        if "execResult" in result:
            exec_result = result["execResult"]

            # Add stdout if available
            if "stdout" in exec_result and exec_result["stdout"]:
                stdout = exec_result["stdout"].strip()
                if stdout:
                    output.append(f"**Output:**\n```\n{stdout[:1900]}```")

            # Add stderr if available
            if "stderr" in exec_result and exec_result["stderr"]:
                stderr = exec_result["stderr"].strip()
                if stderr:
                    output.append(f"**Error:**\n```\n{stderr[:1900]}```")

            # Add execution time
            if "execTime" in exec_result:
                output.append(f"**Execution Time:** {exec_result['execTime']} ms")

            # Check for exit code
            if "code" in exec_result:
                status = "Success" if exec_result["code"] == 0 else "Failed"
                output.append(f"**Status:** {status} (Exit code: {exec_result['code']})")

    def extract_code_block(self, content):
        # Pattern for code blocks: ```language\ncode\n```
        pattern = r"```([a-zA-Z0-9+]+)?\n([\s\S]+?)\n```"
        match = re.search(pattern, content)
        if match:
            language = match.group(1) or "text"
            code = match.group(2)
            return language.lower(), code
        return None, None

    def parse_compile_arguments(self, content):
        try:
            # Extract arguments before the code block
            code_block_start = content.find("```")
            if code_block_start == -1:
                return {}, "Could not find code block"

            args_part = content[:code_block_start].strip()

            # Parse the arguments using a custom parser
            parser = CustomArgumentParser(description="Compiler options", add_help=False)
            parser.add_argument("-a", type=str, help="Compiler arguments", default="")
            parser.add_argument("-s", action="store_true", help="Show assembly output")

            if not args_part:
                return {"args": "", "show_asm": False}, None

            try:
                parsed_args = parser.parse_args(shlex.split(args_part))
                return vars(parsed_args), None
            except ArgumentParserError as e:
                return {}, str(e)
            except Exception as e:
                return {}, f"Error parsing arguments: {str(e)}"

        except Exception as e:
            return {}, f"Error processing arguments: {str(e)}"

    @commands.command()
    async def compile(self, ctx):
        content = ctx.message.content.replace('!compile', '', 1).strip()

        # Parse arguments
        arg_dict, arg_error = self.parse_compile_arguments(content)
        if arg_error:
            help_msg = (
                "Usage: !compile [options] ```language\ncode\n```\n"
                "Options:\n"
                "  -a=\"arg1 arg2\"   Compiler/interpreter arguments\n"
                "  -s,         Show assembly output (for compiled languages)\n"
                "Example: !compile -a=\"-O3 -Wall\" -s ```c\nint main() { return 0; }\n```"
            )
            await ctx.send(f"Error parsing command arguments: {arg_error}\n\n{help_msg}")
            return

        user_args = arg_dict.get("-a", "")
        show_asm = arg_dict.get("-s", False)

        language, source_code = self.extract_code_block(content)

        if not source_code:
            await ctx.send("Please provide code in a code block format. Example: ```language\ncode here\n```")
            return

        if language not in self.language_compilers:
            supported_langs = ", ".join(f"`{lang}`" for lang in self.language_compilers.keys())
            await ctx.send(f"Unsupported language. Supported languages are: {supported_langs}")
            return

        compiler_info = self.language_compilers[language]
        await ctx.send(f"Compiling {compiler_info['name']} code{' with arguments: ' + user_args if user_args else ''}...")

        async with ctx.typing():
            result, error = await self.compile_code(compiler_info['id'], source_code, user_args, show_asm)

            if error:
                await ctx.send(f"Error: {error}")
                return

            output = self.format_output(result, language, show_asm)

            # Send the output, handling Discord's message length limit
            if len(output) > 2000:
                chunks = [output[i:i+1994] for i in range(0, len(output), 1994)]
                for i, chunk in enumerate(chunks):
                    await ctx.send(f"{chunk}")
            else:
                await ctx.send(output)

async def setup(bot):
    logging.info("Setting up the compiler cog...")
    await bot.add_cog(Compiler(bot))
