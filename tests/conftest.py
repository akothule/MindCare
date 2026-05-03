import pytest

from mindcare.config import get_settings
from mindcare.rate_limiter import get_chat_rate_limiter
from mindcare.session_store import get_session_store


@pytest.fixture(autouse=True)
def reset_in_memory_runtime_state() -> None:
    store = get_session_store()
    store._sessions.clear()  # noqa: SLF001
    store._high_risk_counts.clear()  # noqa: SLF001

    settings = get_settings()
    limiter = get_chat_rate_limiter(
        max_requests=settings.rate_limit_max_requests,
        window_seconds=settings.rate_limit_window_seconds,
    )
    limiter.reset()
