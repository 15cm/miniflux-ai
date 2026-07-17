"""Provider adapter with a single-request compatibility API."""

from common.config import Config
from common.logger import logger

config = Config()
llm_client = None


class LLMError(Exception):
    pass


class LLMRateLimitError(LLMError):
    pass


class LLMResponseError(LLMError):
    pass


def _client():
    global llm_client
    if llm_client is not None:
        return llm_client
    if config.llm_provider == "gemini":
        from google import genai
        from google.genai import types

        llm_client = genai.Client(
            http_options=types.HttpOptions(base_url=config.llm_base_url),
            api_key=config.llm_api_key,
        )
    else:
        from openai import OpenAI

        llm_client = OpenAI(base_url=config.llm_base_url, api_key=config.llm_api_key)
    return llm_client


def _raise_provider_error(exc: Exception):
    if "rate" in type(exc).__name__.lower() or "429" in str(exc):
        raise LLMRateLimitError("provider rate limit") from exc
    raise LLMError("LLM provider request failed") from exc


def get_ai_result(prompt: str, input_text: str):
    if config.llm_max_length and len(input_text) > config.llm_max_length:
        input_text = input_text[: config.llm_max_length]
    user_content = "The following is the input content:\n---\n" + input_text
    try:
        if config.llm_provider == "gemini":
            from google.genai import types

            response = _client().models.generate_content(
                model=config.llm_model,
                contents=user_content,
                config=types.GenerateContentConfig(system_instruction=[prompt]),
            )
            return response.text
        completion = _client().chat.completions.create(
            model=config.llm_model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_content},
            ],
            timeout=config.llm_timeout,
        )
        return completion.choices[0].message.content
    except Exception as exc:
        logger.error("LLM request failed: %s", type(exc).__name__)
        _raise_provider_error(exc)


def get_ai_json_result(
    prompt: str, request: str, *, max_output_tokens: int | None = None
) -> str:
    """Call provider with JSON contract. Request remains user content, never system text."""
    try:
        if config.llm_provider == "gemini":
            from google.genai import types

            kwargs = {"system_instruction": [prompt]}
            if config.llm_batching.response_format == "json_object":
                kwargs["response_mime_type"] = "application/json"
            response = _client().models.generate_content(
                model=config.llm_model,
                contents=request,
                config=types.GenerateContentConfig(**kwargs),
            )
            return response.text
        kwargs = {
            "model": config.llm_model,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": request},
            ],
            "timeout": config.llm_timeout,
        }
        if config.llm_batching.response_format == "json_object":
            kwargs["response_format"] = {"type": "json_object"}
        if max_output_tokens is not None:
            kwargs["max_completion_tokens"] = max_output_tokens
        completion = _client().chat.completions.create(**kwargs)
        return completion.choices[0].message.content
    except Exception as exc:
        logger.error("LLM JSON request failed: %s", type(exc).__name__)
        _raise_provider_error(exc)
