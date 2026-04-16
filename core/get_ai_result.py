from openai import OpenAI
from google import genai
from google.genai import types
from common.config import Config
from common.logger import logger

config = Config()

if not config.llm_provider or config.llm_provider == "openai":
    llm_client = OpenAI(base_url=config.llm_base_url, api_key=config.llm_api_key)
elif config.llm_provider == "gemini":
    llm_client = genai.Client(
        http_options=types.HttpOptions(base_url=config.llm_base_url),
        api_key=config.llm_api_key,
    )


def get_ai_result(prompt: str, input_text: str):
    """Call LLM with prompt as system instruction and input_text as user content.

    Args:
        prompt: System instruction / role description.
        input_text: Already-rendered user input (Jinja-rendered, markdownified if needed).
    """
    if config.llm_max_length and len(input_text) > config.llm_max_length:
        input_text = input_text[: config.llm_max_length]

    user_content = "The following is the input content:\n---\n" + input_text

    if config.llm_provider == "gemini":
        try:
            response = llm_client.models.generate_content(
                model=config.llm_model,
                contents=user_content,
                config=types.GenerateContentConfig(
                    system_instruction=[prompt],
                ),
            )
            return response.text
        except Exception as e:
            logger.error(f"Error in get_ai_result (Gemini): {e}")
            raise
    else:
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_content},
        ]
        try:
            completion = llm_client.chat.completions.create(
                model=config.llm_model, messages=messages, timeout=config.llm_timeout
            )
            return completion.choices[0].message.content
        except Exception as e:
            logger.error(f"Error in get_ai_result (OpenAI): {e}")
            raise
