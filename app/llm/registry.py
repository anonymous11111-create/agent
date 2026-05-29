from langchain_openai import ChatOpenAI

from app.config import settings

_cache: dict[str, object] = {}


def get_chat_model(model_name: str):
    """Get a LangChain chat model instance by model name."""
    if model_name in _cache:
        return _cache[model_name]

    if model_name == "deepseek-chat":
        model = ChatOpenAI(
            model="deepseek-chat",
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
            timeout=60.0,
            max_retries=2,
        )
    elif model_name.startswith("glm"):
        model = ChatOpenAI(
            model=model_name,
            api_key=settings.ZHIPUAI_API_KEY,
            base_url=settings.ZHIPUAI_BASE_URL,
            timeout=60.0,
            max_retries=2,
        )
    else:
        raise ValueError(f"Unknown model: {model_name}")

    _cache[model_name] = model
    return model
