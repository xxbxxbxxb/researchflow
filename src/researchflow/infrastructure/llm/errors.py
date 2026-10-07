class LLMProviderError(RuntimeError):
    """Base error for failures at the LLM provider boundary."""
    
class LLMProviderRequestError(LLMProviderError):
    """The request is invalid or cannot be authorized."""

class LLMProviderRateLimitError(LLMProviderError):
    """The provider rejected the request because of rate limiting."""
    def __init__(
        self,
        message: str,
        retry_after_seconds: float | None = None,
    ) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds
    
class LLMProviderUnavailableError(LLMProviderError):
    """A transient provider or transport failure occurred."""

class LLMProviderProtocolError(LLMProviderError):
    """The provider response does not satisfy the expected schema."""
    
