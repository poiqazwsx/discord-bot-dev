# bot/cogs/utility/deep_research.py
import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import os
import logging
from dotenv import load_dotenv
from groq import AsyncGroq, RateLimitError, APIError
import random
import concurrent.futures
import httpx
import time
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import unquote

# We'll reuse/adapt the search/scrape logic inspired by deep_researcher.py
# Make sure these dependencies are installed: beautifulsoup4, httpx, markdownify
from bs4 import BeautifulSoup
from markdownify import markdownify
# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# --- Groq Configuration ---
PRIMARY_GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
FALLBACK_GROQ_MODELS = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "gemma2-9b-it"]
GROQ_RATE_LIMIT_COOLDOWN_SECONDS = 65

# --- Search/Scrape Configuration ---
MAX_SEARCH_RESULTS_OVERALL_CAP = 15
MAX_PAGES_TO_SCRAPE_INITIAL = 4
MAX_SCRAPE_CONTENT_LENGTH = 5000

# --- Iterative Research Configuration ---
MAX_RESEARCH_LOOPS = 4
MAX_INITIAL_GENERATED_QUERIES = 3
MAX_RESULTS_PER_INITIAL_QUERY = 3
MAX_FOLLOWUP_GENERATED_QUERIES = 2
MAX_RESULTS_PER_FOLLOWUP_QUERY = 2
MAX_PAGES_TO_SCRAPE_PER_FOLLOWUP_ROUND = 2

# --- Utility Functions ---

def get_useragent():
    agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
    ]
    return random.choice(agents)

async def _think_and_log(message: str, delay: float = 0.2):
    logger.info(f"[THOUGHT] {message}")
    if delay > 0:
        await asyncio.sleep(delay)

async def tavily_search(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    tavily_api_key = os.environ.get("TAVILY_API_KEY")
    if not tavily_api_key:
        logger.warning("TAVILY_API_KEY not found. Tavily search unavailable.")
        return []
    await _think_and_log(f"Searching Tavily for: '{query}' (max {max_results} results).")
    try:
        from tavily import TavilyClient
        client = TavilyClient(tavily_api_key)
        loop = asyncio.get_running_loop()
        search_response = await loop.run_in_executor(
            None, lambda: client.search(query=query, search_depth="basic", max_results=max_results)
        )
        tavily_results = []
        for result in search_response.get('results', []):
            title = result.get('title', 'No Title')
            url = result.get('url', None)
            if url:
                tavily_results.append({'title': title, 'href': url})
            else: logger.warning(f"Tavily result missing URL: {title}")
        logger.info(f"Tavily found {len(tavily_results)} results for '{query}'.")
        return tavily_results
    except ImportError:
        logger.error("TavilyClient library not found. Please install it: pip install tavily-python")
        return []
    except Exception as e:
        logger.error(f"Error during Tavily search for '{query}': {e}", exc_info=True)
        return []

async def _perform_search_for_single_query(query: str, max_results: int) -> List[Dict[str, str]]:
    """Search using Tavily for a single query."""
    results = await tavily_search(query, max_results)
    return results

async def _perform_searches_for_query_list(
    queries: List[str],
    max_results_per_query: int,
    research_log: List[str]
) -> List[Dict[str, str]]:
    all_search_results_map = {}

    search_tasks = []
    for q in queries:
        search_tasks.append(_perform_search_for_single_query(q, max_results_per_query))

    results_from_all_queries = await asyncio.gather(*search_tasks)

    for i, query_results in enumerate(results_from_all_queries):
        query = queries[i]
        research_log.append(f"  - Search for '{query}' yielded {len(query_results)} results.")
        for res in query_results:
            if res['href'] not in all_search_results_map:
                all_search_results_map[res['href']] = res

    unique_results = list(all_search_results_map.values())
    random.shuffle(unique_results)
    logger.info(f"Combined {len(unique_results)} unique results from {len(queries)} queries.")
    return unique_results


async def scrape_page_content(url: str, title: str, max_length: int = MAX_SCRAPE_CONTENT_LENGTH) -> Optional[str]:
    await _think_and_log(f"Scraping: {title} ({url})", delay=0.1)
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
            headers = {'User-Agent': get_useragent()}
            response = await client.get(url, headers=headers)
            response.raise_for_status()

            if 'text/html' not in response.headers.get('Content-Type', '').lower():
                logger.warning(f"Skipping non-HTML content ({response.headers.get('Content-Type')}) for {url}")
                return f"\n\n--- SOURCE: {title} ---\nURL: {url}\n\nCONTENT:\n[Non-HTML content type]\n\n" + "-" * 60 + "\n"

            html_content = response.text
            soup = BeautifulSoup(html_content, 'html.parser')
            for element in soup(["script", "style", "nav", "footer", "header", "aside", "form", "button", "iframe", "noscript", "img", "svg"]):
                element.decompose()
            main_content_tags = ['main', 'article', 'div[role="main"]', 'div.content', 'div#content']
            main_content = None
            for tag_selector in main_content_tags:
                found_content = soup.select_one(tag_selector) if any(c in tag_selector for c in '[.#') else soup.find(tag_selector)
                if found_content: main_content = found_content; break
            if not main_content: main_content = soup.body if soup.body else soup

            markdown_content = markdownify(str(main_content), heading_style="ATX", bullets='*').strip()
            lines = (line.strip() for line in markdown_content.splitlines())
            chunks_inner = (phrase.strip() for line in lines for phrase in line.split("  "))
            cleaned_content = '\n'.join(chunk for chunk in chunks_inner if chunk)

            if not cleaned_content:
                logger.warning(f"Extracted empty content for {url}")
                return f"\n\n--- SOURCE: {title} ---\nURL: {url}\n\nCONTENT:\n[Failed to extract meaningful content]\n\n" + "-" * 60 + "\n"

            truncated_msg = "... [Truncated]"
            if len(cleaned_content) > max_length:
                cleaned_content = cleaned_content[:max_length - len(truncated_msg)] + truncated_msg

            logger.info(f"Scraped {url} (Length: {len(cleaned_content)})")
            return f"\n\n--- SOURCE: {title} ---\nURL: {url}\n\nCONTENT:\n{cleaned_content}\n\n" + "-" * 60 + "\n"
    except httpx.TimeoutException:
        return f"\n\n--- SOURCE: {title} ---\nURL: {url}\n\nCONTENT:\n[Failed: Request Timeout]\n\n" + "-" * 60 + "\n"
    except httpx.HTTPStatusError as e:
        return f"\n\n--- SOURCE: {title} ---\nURL: {url}\n\nCONTENT:\n[Failed: HTTP {e.response.status_code}]\n\n" + "-" * 60 + "\n"
    except Exception as e:
        logger.error(f"Error processing {url}: {e}", exc_info=True)
        return f"\n\n--- SOURCE: {title} ---\nURL: {url}\n\nCONTENT:\n[Failed: {str(e)[:50]}]\n\n" + "-" * 60 + "\n"

async def scrape_multiple_pages(
    search_results: List[Dict[str, str]],
    num_to_scrape: int,
    research_log: List[str]
) -> Tuple[str, int, List[str]]:
    if not search_results: return "No search results to scrape.", 0, []

    to_scrape = search_results[:num_to_scrape]
    await _think_and_log(f"Selected top {len(to_scrape)} of {len(search_results)} results for scraping.")
    research_log.append(f"Attempting to scrape {len(to_scrape)} pages.")

    tasks = [scrape_page_content(result['href'], result['title']) for result in to_scrape]
    scraped_contents_list = await asyncio.gather(*tasks)

    compiled_content = ""
    successful_scrapes_count = 0
    successfully_scraped_page_urls = []

    for i, content_result in enumerate(scraped_contents_list):
        page_title = to_scrape[i]['title']
        page_url = to_scrape[i]['href']
        is_failure = (
            not content_result or
            "[Failed to" in content_result or
            "[Non-HTML" in content_result or
            "[Failed:" in content_result or
            "[empty content]" in content_result or
            "[meaningful content]" in content_result or
            len(content_result.split("CONTENT:\n", 1)[-1].strip()) < 50
        )

        if not is_failure:
            compiled_content += content_result
            successful_scrapes_count += 1
            successfully_scraped_page_urls.append(page_url)
            research_log.append(f"    - Successfully scraped: {page_title[:50]}... ({page_url})")
        else:
            research_log.append(f"    - Failed or empty scrape: {page_title[:50]}... ({page_url})")

    msg = f"Successfully scraped content from {successful_scrapes_count}/{len(to_scrape)} pages."
    await _think_and_log(msg)
    research_log.append(msg)

    final_content = compiled_content if successful_scrapes_count > 0 else "Could not retrieve useful content from selected pages."
    return final_content, successful_scrapes_count, successfully_scraped_page_urls

async def _call_groq_llm_with_fallback(
    groq_client: AsyncGroq,
    messages: List[Dict[str, str]],
    current_model_idx: int,
    max_tokens: int = 1024,
    temperature: float = 0.7
) -> Tuple[Optional[str], int]:
    models_to_try = [PRIMARY_GROQ_MODEL] + [m for m in FALLBACK_GROQ_MODELS if m != PRIMARY_GROQ_MODEL]

    for i in range(len(models_to_try)):
        model_idx_to_use = (current_model_idx + i) % len(models_to_try)
        model_to_use = models_to_try[model_idx_to_use]
        await _think_and_log(f"Attempting LLM call with Groq model: {model_to_use}", delay=0.1)
        try:
            start_llm_time = time.time()
            chat_completion = await groq_client.chat.completions.create(
                messages=messages,
                model=model_to_use,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            response_text = chat_completion.choices[0].message.content
            llm_time = time.time() - start_llm_time
            logger.info(f"Groq call completed in {llm_time:.2f}s using {model_to_use}.")
            return response_text, model_idx_to_use
        except RateLimitError:
            logger.warning(f"Rate limit hit for Groq model {model_to_use}.")
            if i < len(models_to_try) - 1:
                await _think_and_log(f"Cooldown {GROQ_RATE_LIMIT_COOLDOWN_SECONDS}s then trying next model.")
                await asyncio.sleep(GROQ_RATE_LIMIT_COOLDOWN_SECONDS)
            else:
                return "Error: Groq API rate limit hit on all models.", model_idx_to_use
        except APIError as e:
            logger.error(f"Groq API error with model {model_to_use}: {e}")
            if i >= len(models_to_try) - 1:
                return f"Error: Groq API error: {e}", model_idx_to_use
        except Exception as e:
            logger.error(f"Unexpected error during Groq call with {model_to_use}: {e}", exc_info=True)
            return f"Error: Unexpected issue during LLM call: {e}", model_idx_to_use
    return "Error: Could not complete LLM call with any model.", current_model_idx


async def _generate_llm_search_queries(
    groq_client: AsyncGroq,
    current_model_idx: int,
    original_query: str,
    research_log: List[str],
    context: Optional[str] = None,
    max_queries_to_generate: int = 3
) -> Tuple[List[str], int]:
    purpose = "analyze context and suggest follow-up search queries" if context else "analyze the original query and suggest initial search queries"
    await _think_and_log(f"Using LLM to {purpose} for '{original_query}'.")

    system_prompt = f"""You are a research assistant. Your task is to {purpose}.
User's original query: "{original_query}"
"""
    if context:
        system_prompt += f"\n\nCurrent research context (first 1000 chars):\n\"\"\"\n{context[:1000]}...\n\"\"\""

    system_prompt += f"""
Instructions:
- Provide a list of up to {max_queries_to_generate} distinct, specific, and effective search queries.
- Each query should be on a new line, and nothing else.
- Do NOT number the queries or use bullet points. Just list the raw query strings.
- If analyzing context, focus on queries that would fill gaps or clarify ambiguities.
- If generating initial queries, aim for diverse angles covering key aspects of the original query.
Example output:
search query 1
another search query
a third specific search query
"""
    messages = [{"role": "system", "content": system_prompt}]

    llm_response, model_idx_used = await _call_groq_llm_with_fallback(
        groq_client, messages, current_model_idx, max_tokens=200, temperature=0.6
    )

    if not llm_response or llm_response.startswith("Error:"):
        research_log.append(f"LLM query generation failed: {llm_response}")
        return [], model_idx_used

    queries = [q.strip() for q in llm_response.split('\n') if q.strip()]
    queries = queries[:max_queries_to_generate]

    log_msg = f"LLM generated {len(queries)} queries: {queries}" if queries else "LLM did not generate usable queries."
    research_log.append(log_msg)
    logger.info(log_msg)
    return queries, model_idx_used


async def synthesize_with_groq(
    context: str,
    original_query: str,
    groq_client: AsyncGroq,
    current_model_idx: int,
    research_log: List[str]
) -> Tuple[Optional[str], int]:
    await _think_and_log(f"Synthesizing report for '{original_query}' with Groq.")
    system_prompt = f"""You are an expert research assistant. Synthesize the provided context into a comprehensive, well-structured, objective report on: "{original_query}".

Context: Provided by web searches. Each source is marked with '--- SOURCE: ... URL: ... CONTENT: ... ---'.

Instructions:
- Analyze the context. Identify key findings, facts, figures, and arguments for "{original_query}".
- Structure your report logically: title (e.g., "# Research Report: [Topic]"), introduction, main body (use markdown ## or ### headings), conclusion.
- Synthesize information into a narrative. Do not simply list points.
- Maintain accuracy and neutrality. Stick STRICTLY to the provided context. No external knowledge or opinions.
- If context is contradictory/insufficient, implicitly show this by focusing on supported info, or explicitly state limitations if crucial.
- Format with Markdown (headings, lists, bold).
- **Output ONLY the report itself.** No preamble like "Here is the report:". Start with the title.
"""
    user_message_content = f"Generate the research report based *only* on this context:\n\n```context\n{context}\n```"
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message_content},
    ]

    report, model_idx_used = await _call_groq_llm_with_fallback(
        groq_client, messages, current_model_idx, max_tokens=4000, temperature=0.4
    )
    if report and not report.startswith("Error:"):
        research_log.append(f"Synthesis successful using model {PRIMARY_GROQ_MODEL if model_idx_used == 0 else FALLBACK_GROQ_MODELS[model_idx_used-1]}.")
    else:
        research_log.append(f"Synthesis failed: {report}")
    return report, model_idx_used

# --- DeepResearch Cog ---

class DeepResearch(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.groq_api_key = os.environ.get("GROQ_API_KEY")
        if not self.groq_api_key:
            logger.error("GROQ_API_KEY not found. DeepResearch cog will be non-functional.")
            self.groq_client = None
        else:
            self.groq_client = AsyncGroq(api_key=self.groq_api_key)
        self.current_groq_model_idx = 0

    @app_commands.command(name="deepresearch", description="Performs iterative deep research on a topic.")
    @app_commands.describe(
        topic="The topic to research",
        max_initial_results_to_consider="Max initial search results to process (optional, affects initial scrape pool)"
    )
    @app_commands.choices(max_initial_results_to_consider=[
        app_commands.Choice(name="3 Results", value=3),
        app_commands.Choice(name="5 Results (Default)", value=5),
        app_commands.Choice(name="7 Results", value=7),
        app_commands.Choice(name="10 Results", value=10),
    ])
    async def deep_research(self, interaction: discord.Interaction, topic: str, max_initial_results_to_consider: Optional[app_commands.Choice[int]] = None):
        # Determine ephemeral state from the initial defer. This command is designed to be non-ephemeral.
        # However, if a user somehow invoked it ephemerally (e.g. via a wrapper command), we'd respect that.
        # For this specific command, we will make it always non-ephemeral.
        is_ephemeral_response = False # For deepresearch, we want public reports.
        await interaction.response.defer(thinking=True, ephemeral=is_ephemeral_response)

        research_log = [f"Deep Research initiated by {interaction.user} for topic: '{topic}'."]
        start_time = time.time()

        if not self.groq_client:
            await interaction.followup.send("❌ Configuration Error: Groq API key is missing. Cannot perform research.", ephemeral=True) # Config errors can be ephemeral
            return

        num_initial_results_cap = max_initial_results_to_consider.value if max_initial_results_to_consider else 5
        research_log.append(f"User specified max {num_initial_results_cap} initial results to consider for scraping.")

        compiled_scraped_context = ""
        total_pages_scraped = 0
        successfully_scraped_urls = set()

        try:
            final_loop_num = 0
            for loop_num in range(MAX_RESEARCH_LOOPS):
                final_loop_num = loop_num
                current_loop_log_header = f"\n--- Research Loop {loop_num + 1}/{MAX_RESEARCH_LOOPS} ---"
                research_log.append(current_loop_log_header)
                await interaction.edit_original_response(content=f"🧠 Researching '{topic}'... (Loop {loop_num + 1}/{MAX_RESEARCH_LOOPS})")

                if loop_num == 0:
                    await interaction.edit_original_response(content=f"💡 Generating initial search angles for '{topic}'...")
                    search_queries, self.current_groq_model_idx = await _generate_llm_search_queries(
                        self.groq_client, self.current_groq_model_idx, topic, research_log,
                        max_queries_to_generate=MAX_INITIAL_GENERATED_QUERIES
                    )
                    if not search_queries: search_queries = [topic]
                    max_results_this_round = MAX_RESULTS_PER_INITIAL_QUERY
                    max_pages_to_scrape_this_round = min(num_initial_results_cap, MAX_PAGES_TO_SCRAPE_INITIAL)
                else:
                    if not compiled_scraped_context:
                        research_log.append("No context from previous loops, cannot generate follow-up queries. Ending refinement.")
                        break
                    await interaction.edit_original_response(content=f"🤔 Analyzing context to find gaps for '{topic}'...")
                    search_queries, self.current_groq_model_idx = await _generate_llm_search_queries(
                        self.groq_client, self.current_groq_model_idx, topic, research_log,
                        context=compiled_scraped_context, max_queries_to_generate=MAX_FOLLOWUP_GENERATED_QUERIES
                    )
                    if not search_queries:
                        research_log.append("LLM found no new research angles. Ending refinement.")
                        break
                    max_results_this_round = MAX_RESULTS_PER_FOLLOWUP_QUERY
                    max_pages_to_scrape_this_round = MAX_PAGES_TO_SCRAPE_PER_FOLLOWUP_ROUND

                await interaction.edit_original_response(content=f"🔍 Searching with {len(search_queries)} queries (Loop {loop_num+1})...")
                combined_search_results = await _perform_searches_for_query_list(
                    search_queries, max_results_this_round, research_log
                )

                if not combined_search_results:
                    research_log.append("No search results found in this loop. Cannot continue this loop.")
                    if loop_num == 0 and not compiled_scraped_context:
                         await interaction.edit_original_response(content=f"⚠️ Could not find any search results for '{topic}'. Aborting.")
                         return
                    continue

                results_to_consider_for_scraping = combined_search_results[:max_pages_to_scrape_this_round]

                research_log.append(f"Considering {len(results_to_consider_for_scraping)} unique results for scraping (capped at {max_pages_to_scrape_this_round}).")

                if not results_to_consider_for_scraping:
                    research_log.append("No suitable search results to scrape in this loop.")
                    continue

                await interaction.edit_original_response(content=f"📄 Scraping up to {max_pages_to_scrape_this_round} pages (Loop {loop_num+1})...")
                newly_scraped_content, num_successfully_scraped, new_successful_urls = await scrape_multiple_pages(
                    results_to_consider_for_scraping, max_pages_to_scrape_this_round, research_log
                )
                total_pages_scraped += num_successfully_scraped
                successfully_scraped_urls.update(new_successful_urls)

                if newly_scraped_content and not newly_scraped_content.startswith("Could not retrieve"):
                    compiled_scraped_context += newly_scraped_content
                    research_log.append(f"Added {len(newly_scraped_content)} chars from {num_successfully_scraped} pages this loop.")
                else:
                    research_log.append("No new content successfully scraped in this loop.")

            if not compiled_scraped_context:
                await interaction.edit_original_response(content=f"⚠️ Failed to gather any information for '{topic}' after all research attempts.")
                logger.warning(f"Research for '{topic}' yielded no usable context.")
                research_log.append("Overall process yielded no usable context.")
                return

            await interaction.edit_original_response(content=f"✍️ Synthesizing final report for '{topic}'...")
            report, self.current_groq_model_idx = await synthesize_with_groq(
                compiled_scraped_context, topic, self.groq_client, self.current_groq_model_idx, research_log
            )

            if not report or report.startswith("Error:"):
                err_msg = report if report else 'Failed to generate report.'
                await interaction.edit_original_response(content=f"❌ {err_msg}")
                logger.error(f"Failed to synthesize report for '{topic}': {err_msg}")
                research_log.append(f"Final synthesis failed: {err_msg}")
                return

            total_time = time.time() - start_time
            logger.info(f"Report for '{topic}'. Length: {len(report)} chars. Total time: {total_time:.2f}s")

            used_model_name = PRIMARY_GROQ_MODEL
            if self.current_groq_model_idx > 0 and self.current_groq_model_idx <= len(FALLBACK_GROQ_MODELS):
                 used_model_name = FALLBACK_GROQ_MODELS[self.current_groq_model_idx-1]

            research_summary_for_footer = [
                f"Topic: '{topic}'",
                f"Total research loops executed: {final_loop_num + 1}.",
                f"Total pages successfully scraped: {total_pages_scraped} from {len(successfully_scraped_urls)} unique sites.",
                f"Synthesis model: {used_model_name}.",
                f"Total time: {total_time:.2f}s."
            ]

            footer_content = (
                "\n\n---\n"
                "**Research Process Summary:**\n"
                + "\n".join([f"- {s.strip('- ')}" for s in research_summary_for_footer])
            )

            if successfully_scraped_urls:
                footer_content += "\n\n**Successfully Scraped Sources:**"
                max_urls_to_display = 5
                urls_to_list = list(successfully_scraped_urls)
                for i, url in enumerate(urls_to_list):
                    if i < max_urls_to_display:
                        footer_content += f"\n  - <{url}>"
                    elif i == max_urls_to_display:
                        footer_content += f"\n  - ...and {len(urls_to_list) - max_urls_to_display} more."
                        break
            else:
                footer_content += "\n\n**Successfully Scraped Sources:** None"

            full_report_with_footer = report + footer_content

            max_chunk_size = 2000
            if len(full_report_with_footer) <= max_chunk_size:
                await interaction.edit_original_response(content=full_report_with_footer)
            else:
                chunks = []
                remaining_text = full_report_with_footer
                while remaining_text:
                    if len(remaining_text) <= max_chunk_size:
                        chunks.append(remaining_text)
                        break
                    split_at = remaining_text.rfind('\n', 0, max_chunk_size)
                    if split_at == -1 or split_at < max_chunk_size // 2:
                        split_at = max_chunk_size
                    chunks.append(remaining_text[:split_at])
                    remaining_text = remaining_text[split_at:].lstrip()

                await interaction.edit_original_response(content=chunks[0])
                for chunk_content in chunks[1:]: # Corrected variable name
                    await asyncio.sleep(0.5)
                    # Pass the determined ephemeral state for followups
                    await interaction.followup.send(chunk_content, ephemeral=is_ephemeral_response)

            logger.info(f"Successfully completed deep research for '{topic}' by {interaction.user}")

        except Exception as e:
            logger.exception(f"Unexpected error during deep research for '{topic}': {e}")
            research_log.append(f"FATAL ERROR: {type(e).__name__} - {str(e)}")
            try:
                err_report = f"❌ An critical error occurred: {str(e)}\n\n**Research Log Snippet:**\n"
                err_report += "\n".join([f"  - {s.strip()}" for s in research_log[-5:]])
                if len(err_report) > 1950: err_report = err_report[:1950] + "..."

                # Check if original response was already sent
                if interaction.is_expired() or not await interaction.original_response(): # More robust check
                     await interaction.followup.send(err_report, ephemeral=True) # Send as new message if original is gone/failed
                else:
                    await interaction.edit_original_response(content=err_report)

            except discord.NotFound:
                logger.warning("Interaction or original response not found when trying to send fatal error.")
                pass
            except Exception as followup_e:
                logger.error(f"Failed to send fatal error to Discord: {followup_e}")


async def setup(bot):
    if not os.environ.get("GROQ_API_KEY"):
        logger.error("GROQ_API_KEY not set. DeepResearch cog will not be loaded.")
        return
    if not os.environ.get("TAVILY_API_KEY"):
        logger.warning("TAVILY_API_KEY not set. Tavily search will be unavailable for DeepResearch.")

    logger.info("Setting up the DeepResearch cog...")
    await bot.add_cog(DeepResearch(bot))
