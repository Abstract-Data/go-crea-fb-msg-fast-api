"""Correlation ID middleware for request tracing across services."""

import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

import logfire


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add correlation IDs to requests for distributed tracing.
    
    Adds a unique correlation ID to each request that can be used to
    trace requests across services and correlate logs.
    """
    
    def __init__(self, app: ASGIApp, header_name: str = "X-Correlation-ID"):
        """
        Initialize correlation ID middleware.
        
        Args:
            app: ASGI application
            header_name: HTTP header name for correlation ID
        """
        super().__init__(app)
        self.header_name = header_name
    
    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        """
        Process request and add correlation ID.
        
        Args:
            request: Incoming request
            call_next: Next middleware/handler
            
        Returns:
            Response with correlation ID header
        """
        # Get correlation ID from header or generate new one
        correlation_id = request.headers.get(
            self.header_name.lower(),
            str(uuid.uuid4())
        )
        
        # Add to request state for use in handlers
        request.state.correlation_id = correlation_id
        
        # Add to Logfire span for automatic correlation (if available)
        # Use span with correlation_id in attributes for tracing
        span_method = getattr(logfire, "span", None)
        if span_method:
            with span_method("request", correlation_id=correlation_id):
                response = await call_next(request)
                response.headers[self.header_name] = correlation_id
                return response
        else:
            # Fallback if logfire.span is not available (e.g., in tests)
            response = await call_next(request)
            response.headers[self.header_name] = correlation_id
            return response
