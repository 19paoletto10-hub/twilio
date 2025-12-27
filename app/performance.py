"""
Performance monitoring and profiling utilities.

This module provides decorators and utilities for:
- Function execution timing
- Memory usage tracking
- Request performance metrics
- Slow query detection

These tools help identify performance bottlenecks and
optimize critical code paths.
"""

from __future__ import annotations

import functools
import logging
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Generator, Generic, List, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


# =============================================================================
# Performance Metrics
# =============================================================================


@dataclass
class ExecutionMetrics:
    """Metrics for a single function execution."""
    
    function_name: str
    start_time: float
    end_time: float
    duration_ms: float
    success: bool
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_execution(
        cls,
        function_name: str,
        start: float,
        end: float,
        success: bool = True,
        error: Optional[str] = None,
        **metadata: Any,
    ) -> "ExecutionMetrics":
        return cls(
            function_name=function_name,
            start_time=start,
            end_time=end,
            duration_ms=(end - start) * 1000,
            success=success,
            error=error,
            metadata=metadata,
        )


class MetricsCollector:
    """
    Thread-safe collector for execution metrics.
    
    Stores metrics in a bounded buffer and provides aggregation methods.
    """
    
    __slots__ = ("_metrics", "_lock", "_max_size")
    
    def __init__(self, max_size: int = 10000):
        self._metrics: List[ExecutionMetrics] = []
        self._lock = threading.RLock()
        self._max_size = max_size
    
    def record(self, metrics: ExecutionMetrics) -> None:
        """Record new metrics."""
        with self._lock:
            if len(self._metrics) >= self._max_size:
                # Remove oldest 10%
                self._metrics = self._metrics[self._max_size // 10:]
            self._metrics.append(metrics)
    
    def get_stats(self, function_name: Optional[str] = None) -> Dict[str, Any]:
        """Get aggregated statistics."""
        with self._lock:
            if function_name:
                filtered = [m for m in self._metrics if m.function_name == function_name]
            else:
                filtered = list(self._metrics)
        
        if not filtered:
            return {"count": 0}
        
        durations = [m.duration_ms for m in filtered]
        successes = sum(1 for m in filtered if m.success)
        
        return {
            "count": len(filtered),
            "success_count": successes,
            "failure_count": len(filtered) - successes,
            "success_rate": successes / len(filtered) * 100,
            "avg_duration_ms": sum(durations) / len(durations),
            "min_duration_ms": min(durations),
            "max_duration_ms": max(durations),
            "p50_duration_ms": sorted(durations)[len(durations) // 2],
            "p95_duration_ms": sorted(durations)[int(len(durations) * 0.95)] if len(durations) >= 20 else None,
        }
    
    def get_slow_operations(
        self,
        threshold_ms: float = 1000.0,
        limit: int = 100,
    ) -> List[ExecutionMetrics]:
        """Get operations exceeding threshold."""
        with self._lock:
            slow = [m for m in self._metrics if m.duration_ms > threshold_ms]
            return sorted(slow, key=lambda m: -m.duration_ms)[:limit]
    
    def clear(self) -> None:
        """Clear all metrics."""
        with self._lock:
            self._metrics.clear()


# Global metrics collector
_metrics = MetricsCollector()


def get_metrics() -> MetricsCollector:
    """Get global metrics collector."""
    return _metrics


# =============================================================================
# Timing Decorators
# =============================================================================


def timed(
    log_level: int = logging.DEBUG,
    threshold_ms: Optional[float] = None,
    include_args: bool = False,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator to measure and log function execution time.
    
    Args:
        log_level: Logging level for timing messages
        threshold_ms: Only log if execution exceeds this threshold
        include_args: Include function arguments in log message
        
    Usage:
        @timed(threshold_ms=100)
        def slow_function(x: int) -> int:
            ...
    """
    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            start = time.perf_counter()
            success = True
            error: Optional[str] = None
            
            try:
                result = fn(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                error = str(e)
                raise
            finally:
                end = time.perf_counter()
                duration_ms = (end - start) * 1000
                
                # Record metrics
                metrics = ExecutionMetrics.from_execution(
                    function_name=fn.__name__,
                    start=start,
                    end=end,
                    success=success,
                    error=error,
                )
                _metrics.record(metrics)
                
                # Log if above threshold
                if threshold_ms is None or duration_ms >= threshold_ms:
                    args_str = ""
                    if include_args:
                        args_str = f" args={args}, kwargs={kwargs}"
                    
                    logger.log(
                        log_level,
                        "%s executed in %.2fms%s%s",
                        fn.__name__,
                        duration_ms,
                        args_str,
                        " [FAILED]" if not success else "",
                    )
        
        return wrapper
    return decorator


@contextmanager
def timed_block(
    name: str,
    log_level: int = logging.DEBUG,
    threshold_ms: Optional[float] = None,
) -> Generator[None, None, None]:
    """
    Context manager for timing code blocks.
    
    Usage:
        with timed_block("database_query"):
            result = db.execute(query)
    """
    start = time.perf_counter()
    success = True
    error: Optional[str] = None
    
    try:
        yield
    except Exception as e:
        success = False
        error = str(e)
        raise
    finally:
        end = time.perf_counter()
        duration_ms = (end - start) * 1000
        
        metrics = ExecutionMetrics.from_execution(
            function_name=name,
            start=start,
            end=end,
            success=success,
            error=error,
        )
        _metrics.record(metrics)
        
        if threshold_ms is None or duration_ms >= threshold_ms:
            logger.log(
                log_level,
                "Block '%s' executed in %.2fms%s",
                name,
                duration_ms,
                " [FAILED]" if not success else "",
            )


# =============================================================================
# Rate Limiting
# =============================================================================


class RateLimiter:
    """
    Token bucket rate limiter for API call throttling.
    
    Implements a token bucket algorithm where:
    - Tokens are added at a constant rate
    - Each call consumes one token
    - Calls are blocked when bucket is empty
    """
    
    __slots__ = ("_rate", "_capacity", "_tokens", "_last_update", "_lock")
    
    def __init__(self, rate: float, capacity: int):
        """
        Initialize rate limiter.
        
        Args:
            rate: Tokens per second to add
            capacity: Maximum tokens in bucket
        """
        self._rate = rate
        self._capacity = capacity
        self._tokens = float(capacity)
        self._last_update = time.monotonic()
        self._lock = threading.RLock()
    
    def acquire(self, timeout: Optional[float] = None) -> bool:
        """
        Acquire a token, blocking if necessary.
        
        Args:
            timeout: Maximum seconds to wait (None = block forever)
            
        Returns:
            True if token acquired, False if timeout
        """
        deadline = None if timeout is None else time.monotonic() + timeout
        
        while True:
            with self._lock:
                self._refill()
                
                if self._tokens >= 1:
                    self._tokens -= 1
                    return True
                
                # Calculate wait time for next token
                wait_time = (1 - self._tokens) / self._rate
            
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                wait_time = min(wait_time, remaining)
            
            time.sleep(wait_time)
    
    def try_acquire(self) -> bool:
        """Try to acquire token without blocking."""
        with self._lock:
            self._refill()
            
            if self._tokens >= 1:
                self._tokens -= 1
                return True
            return False
    
    def _refill(self) -> None:
        """Add tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self._last_update
        self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
        self._last_update = now


def rate_limited(
    calls_per_second: float = 10.0,
    burst: int = 10,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator to rate limit function calls.
    
    Usage:
        @rate_limited(calls_per_second=5)
        def api_call():
            ...
    """
    limiter = RateLimiter(rate=calls_per_second, capacity=burst)
    
    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            limiter.acquire()
            return fn(*args, **kwargs)
        
        wrapper._rate_limiter = limiter  # type: ignore
        return wrapper
    
    return decorator


# =============================================================================
# Lazy Initialization
# =============================================================================


class Lazy(Generic[T]):
    """
    Lazy initialization wrapper for expensive objects.
    
    Object is only created on first access, and cached for subsequent uses.
    Thread-safe initialization.
    
    Usage:
        expensive_client = Lazy(lambda: ExpensiveClient(config))
        # Later...
        result = expensive_client.get().do_something()
    """
    
    __slots__ = ("_factory", "_value", "_lock", "_initialized")
    
    def __init__(self, factory: Callable[[], T]):
        self._factory = factory
        self._value: Optional[T] = None
        self._lock = threading.RLock()
        self._initialized = False
    
    def get(self) -> T:
        """Get the lazily initialized value."""
        if not self._initialized:
            with self._lock:
                if not self._initialized:
                    self._value = self._factory()
                    self._initialized = True
        return self._value  # type: ignore
    
    def reset(self) -> None:
        """Reset to uninitialized state."""
        with self._lock:
            self._value = None
            self._initialized = False
    
    @property
    def is_initialized(self) -> bool:
        """Check if value has been initialized."""
        return self._initialized
