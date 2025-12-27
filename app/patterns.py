"""
Design patterns and advanced techniques for the Twilio SMS AI Platform.

This module implements enterprise-grade patterns for:
- Result types (Railway-Oriented Programming)
- Retry with exponential backoff
- Circuit breaker pattern
- Caching decorators
- Async message processing protocols

These patterns promote:
- Explicit error handling without exceptions
- Resilient external service calls
- Type safety and mypy compliance
- Testability and separation of concerns
"""

from __future__ import annotations

import functools
import hashlib
import logging
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Protocol,
    Tuple,
    TypeVar,
    Union,
    overload,
)

logger = logging.getLogger(__name__)

# =============================================================================
# Type Variables
# =============================================================================
T = TypeVar("T")
E = TypeVar("E")
R = TypeVar("R")

# =============================================================================
# Result Type (Railway-Oriented Programming)
# =============================================================================


@dataclass(frozen=True, slots=True)
class Success(Generic[T]):
    """Represents a successful operation result."""
    
    value: T
    
    def is_success(self) -> bool:
        return True
    
    def is_failure(self) -> bool:
        return False
    
    def unwrap(self) -> T:
        """Get the success value. Safe to call after checking is_success()."""
        return self.value
    
    def unwrap_or(self, default: T) -> T:
        """Get the success value or return default."""
        return self.value
    
    def map(self, fn: Callable[[T], R]) -> "Result[R, Any]":
        """Apply function to success value."""
        try:
            return Success(fn(self.value))
        except Exception as e:
            return Failure(e)
    
    def flat_map(self, fn: Callable[[T], "Result[R, E]"]) -> "Result[R, E]":
        """Chain another Result-returning function."""
        return fn(self.value)


@dataclass(frozen=True, slots=True)
class Failure(Generic[E]):
    """Represents a failed operation result."""
    
    error: E
    context: Dict[str, Any] = field(default_factory=dict)
    
    def is_success(self) -> bool:
        return False
    
    def is_failure(self) -> bool:
        return True
    
    def unwrap(self) -> Any:
        """Raises the error. Use unwrap_or() for safe access."""
        if isinstance(self.error, Exception):
            raise self.error
        raise ValueError(f"Operation failed: {self.error}")
    
    def unwrap_or(self, default: T) -> T:
        """Return default value for failed operations."""
        return default
    
    def map(self, fn: Callable[[Any], R]) -> "Failure[E]":
        """No-op for failures - preserves error."""
        return self
    
    def flat_map(self, fn: Callable[[Any], "Result[R, E]"]) -> "Failure[E]":
        """No-op for failures - preserves error."""
        return self


# Union type for Result
Result = Union[Success[T], Failure[E]]


def result_from_exception(fn: Callable[..., T]) -> Callable[..., Result[T, Exception]]:
    """Decorator to convert exception-throwing functions to Result-returning."""
    
    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Result[T, Exception]:
        try:
            return Success(fn(*args, **kwargs))
        except Exception as e:
            return Failure(e, context={"args": args, "kwargs": kwargs})
    
    return wrapper


# =============================================================================
# Retry Pattern with Exponential Backoff
# =============================================================================


class RetryStrategy(Enum):
    """Retry strategy types."""
    
    EXPONENTIAL = auto()
    LINEAR = auto()
    CONSTANT = auto()


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    jitter: bool = True
    retryable_exceptions: Tuple[type, ...] = (Exception,)
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for a given attempt number."""
        if self.strategy == RetryStrategy.EXPONENTIAL:
            delay = self.base_delay * (2 ** (attempt - 1))
        elif self.strategy == RetryStrategy.LINEAR:
            delay = self.base_delay * attempt
        else:
            delay = self.base_delay
        
        delay = min(delay, self.max_delay)
        
        if self.jitter:
            import random
            delay *= (0.5 + random.random())
        
        return delay


def retry(config: Optional[RetryConfig] = None) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for retrying functions with exponential backoff.
    
    Usage:
        @retry(RetryConfig(max_attempts=3))
        def call_external_api():
            ...
    """
    cfg = config or RetryConfig()
    
    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Optional[Exception] = None
            
            for attempt in range(1, cfg.max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except cfg.retryable_exceptions as e:
                    last_exception = e
                    if attempt < cfg.max_attempts:
                        delay = cfg.calculate_delay(attempt)
                        logger.warning(
                            "Retry %d/%d for %s after %.2fs: %s",
                            attempt, cfg.max_attempts, fn.__name__, delay, e
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            "All %d retries failed for %s: %s",
                            cfg.max_attempts, fn.__name__, e
                        )
            
            if last_exception:
                raise last_exception
            raise RuntimeError("Unexpected retry loop exit")
        
        return wrapper
    return decorator


# =============================================================================
# Circuit Breaker Pattern
# =============================================================================


class CircuitState(Enum):
    """Circuit breaker states."""
    
    CLOSED = auto()      # Normal operation
    OPEN = auto()        # Failing, reject calls
    HALF_OPEN = auto()   # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    
    failure_threshold: int = 5
    success_threshold: int = 2
    timeout: float = 30.0
    excluded_exceptions: Tuple[type, ...] = ()


class CircuitBreaker:
    """
    Circuit breaker implementation for resilient external service calls.
    
    States:
    - CLOSED: Normal operation, counting failures
    - OPEN: Service is failing, reject all calls immediately
    - HALF_OPEN: Testing if service recovered
    
    Thread-safe implementation.
    """
    
    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._lock = threading.RLock()
    
    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._state = CircuitState.HALF_OPEN
                    self._success_count = 0
            return self._state
    
    def _should_attempt_reset(self) -> bool:
        if self._last_failure_time is None:
            return True
        return (time.time() - self._last_failure_time) >= self.config.timeout
    
    def record_success(self) -> None:
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    logger.info("Circuit %s closed after recovery", self.name)
            elif self._state == CircuitState.CLOSED:
                self._failure_count = 0
    
    def record_failure(self, exception: Exception) -> None:
        if isinstance(exception, self.config.excluded_exceptions):
            return
        
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                logger.warning("Circuit %s re-opened after failure in half-open", self.name)
            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self.config.failure_threshold:
                    self._state = CircuitState.OPEN
                    logger.warning("Circuit %s opened after %d failures", self.name, self._failure_count)
    
    def call(self, fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Execute function with circuit breaker protection."""
        state = self.state
        
        if state == CircuitState.OPEN:
            raise CircuitOpenError(f"Circuit {self.name} is open")
        
        try:
            result = fn(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            self.record_failure(e)
            raise


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass


def circuit_breaker(
    name: str,
    config: Optional[CircuitBreakerConfig] = None
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator to wrap function with circuit breaker.
    
    Usage:
        @circuit_breaker("twilio_api")
        def send_sms(to: str, body: str):
            ...
    """
    breaker = CircuitBreaker(name, config)
    
    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            return breaker.call(fn, *args, **kwargs)
        
        # Expose breaker for testing/monitoring
        wrapper._circuit_breaker = breaker  # type: ignore
        return wrapper
    
    return decorator


# =============================================================================
# Caching Decorators
# =============================================================================


@dataclass
class CacheEntry(Generic[T]):
    """Cache entry with value and expiration."""
    
    value: T
    expires_at: float
    
    def is_expired(self) -> bool:
        return time.time() > self.expires_at


class TTLCache(Generic[T]):
    """Thread-safe TTL cache."""
    
    def __init__(self, ttl: float = 300.0, max_size: int = 1000):
        self.ttl = ttl
        self.max_size = max_size
        self._cache: Dict[str, CacheEntry[T]] = {}
        self._lock = threading.RLock()
    
    def _make_key(self, *args: Any, **kwargs: Any) -> str:
        """Create cache key from arguments."""
        key_data = (args, tuple(sorted(kwargs.items())))
        return hashlib.sha256(str(key_data).encode()).hexdigest()[:16]
    
    def get(self, key: str) -> Optional[T]:
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            if entry.is_expired():
                del self._cache[key]
                return None
            return entry.value
    
    def set(self, key: str, value: T) -> None:
        with self._lock:
            if len(self._cache) >= self.max_size:
                self._evict_expired()
            self._cache[key] = CacheEntry(value, time.time() + self.ttl)
    
    def _evict_expired(self) -> None:
        now = time.time()
        expired_keys = [k for k, v in self._cache.items() if v.expires_at < now]
        for k in expired_keys:
            del self._cache[k]
    
    def clear(self) -> None:
        with self._lock:
            self._cache.clear()


def cached(ttl: float = 300.0, max_size: int = 1000) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for caching function results with TTL.
    
    Usage:
        @cached(ttl=60.0)
        def expensive_computation(x: int) -> int:
            ...
    """
    cache: TTLCache[Any] = TTLCache(ttl=ttl, max_size=max_size)
    
    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            key = cache._make_key(*args, **kwargs)
            cached_value = cache.get(key)
            if cached_value is not None:
                return cached_value
            
            result = fn(*args, **kwargs)
            cache.set(key, result)
            return result
        
        # Expose cache for testing/clearing
        wrapper._cache = cache  # type: ignore
        return wrapper
    
    return decorator


# =============================================================================
# Message Processing Protocol
# =============================================================================


class MessageProcessor(Protocol):
    """Protocol for message processors."""
    
    def can_handle(self, message: Dict[str, Any]) -> bool:
        """Check if this processor can handle the message."""
        ...
    
    def process(self, message: Dict[str, Any]) -> Result[Dict[str, Any], Exception]:
        """Process the message and return result."""
        ...


@dataclass
class ProcessorChain:
    """
    Chain of Responsibility pattern for message processing.
    
    Processors are tried in order until one handles the message.
    """
    
    processors: List[MessageProcessor] = field(default_factory=list)
    
    def add(self, processor: MessageProcessor) -> "ProcessorChain":
        """Add processor to chain (fluent API)."""
        self.processors.append(processor)
        return self
    
    def process(self, message: Dict[str, Any]) -> Result[Dict[str, Any], Exception]:
        """Process message through chain."""
        for processor in self.processors:
            if processor.can_handle(message):
                return processor.process(message)
        
        return Failure(
            ValueError("No processor found for message"),
            context={"message_keys": list(message.keys())}
        )


# =============================================================================
# Utility Functions
# =============================================================================


def utc_now() -> datetime:
    """Get current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    """Get current UTC datetime as ISO string."""
    return utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")


def safe_int(value: Any, default: int = 0) -> int:
    """Safely convert value to int."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert value to float."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def truncate(s: str, max_len: int = 100, suffix: str = "...") -> str:
    """Truncate string with suffix."""
    if len(s) <= max_len:
        return s
    return s[:max_len - len(suffix)] + suffix
