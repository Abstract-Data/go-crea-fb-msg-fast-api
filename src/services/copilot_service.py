"""GitHub Copilot SDK wrapper service."""

import logging
import time
from typing import Any

import httpx
import logfire

logger = logging.getLogger(__name__)


class CopilotService:
    """Wrapper for GitHub Copilot SDK runtime."""
    
    def __init__(self, base_url: str, enabled: bool = True):
        """
        Initialize Copilot service.
        
        Args:
            base_url: Base URL for Copilot CLI (e.g., http://localhost:5909)
            enabled: Whether Copilot SDK is enabled
        """
        self.base_url = base_url.rstrip('/')
        self.enabled = enabled
    
    async def is_available(self) -> bool:
        """Check if Copilot SDK is available."""
        if not self.enabled:
            logfire.info("Copilot SDK disabled", enabled=False)
            return False
        
        start_time = time.time()
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                # Simple health check - adjust endpoint based on Copilot SDK API
                response = await client.get(f"{self.base_url}/health")
                elapsed = time.time() - start_time
                is_available = response.status_code == 200
                
                logfire.info(
                    "Copilot SDK health check",
                    available=is_available,
                    status_code=response.status_code,
                    response_time_ms=elapsed * 1000,
                    base_url=self.base_url,
                )
                return is_available
        except Exception as e:
            elapsed = time.time() - start_time
            logfire.warn(
                "Copilot SDK health check failed",
                error=str(e),
                error_type=type(e).__name__,
                response_time_ms=elapsed * 1000,
                base_url=self.base_url,
            )
            return False
    
    async def synthesize_reference(
        self,
        website_url: str,
        text_chunks: list[str],
    ) -> str:
        """
        Use Copilot to synthesize a reference doc markdown string.
        
        Args:
            website_url: Source website URL
            text_chunks: List of text chunks from scraping
            
        Returns:
            Synthesized markdown reference document
        """
        system_prompt = (
            "You are a content synthesis assistant. Produce a concise but thorough "
            "reference document for an AI agent that will answer questions about this website. "
            "Focus on policies, services, FAQs, contact, and important positions."
        )
        
        user_prompt = f"""
        Website URL: {website_url}
        
        Please synthesize the following content into a structured markdown reference document 
        with headings: Overview, Key Topics, Common Questions, Important Details.
        
        Content chunks:
        {chr(10).join(f"--- Chunk {i+1} ---{chr(10)}{chunk}" for i, chunk in enumerate(text_chunks))}
        """
        
        return await self.chat(system_prompt, [
            {"role": "user", "content": user_prompt}
        ])
    
    async def chat(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
    ) -> str:
        """
        General chat wrapper used by agent_service.
        
        Args:
            system_prompt: System prompt for the conversation
            messages: List of message dicts with 'role' and 'content'
            
        Returns:
            Response text from Copilot
        """
        start_time = time.time()
        message_count = len(messages)
        
        if not self.enabled or not await self.is_available():
            # Fallback to OpenAI or other LLM
            logfire.warn(
                "Copilot SDK not available, falling back to OpenAI",
                enabled=self.enabled,
                base_url=self.base_url,
            )
            return await self._fallback_to_openai(system_prompt, messages)
        
        try:
            # TODO: Implement actual Copilot SDK API call
            # This is a placeholder - adjust based on actual Copilot SDK API
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/chat",
                    json={
                        "system_prompt": system_prompt,
                        "messages": messages
                    }
                )
                response.raise_for_status()
                result = response.json()["content"]
                elapsed = time.time() - start_time
                
                logfire.info(
                    "Copilot SDK chat completed",
                    success=True,
                    response_time_ms=elapsed * 1000,
                    message_count=message_count,
                    response_length=len(result),
                    base_url=self.base_url,
                )
                return result
        except Exception as e:
            elapsed = time.time() - start_time
            logfire.error(
                "Copilot SDK chat error, falling back to OpenAI",
                error=str(e),
                error_type=type(e).__name__,
                response_time_ms=elapsed * 1000,
                message_count=message_count,
                base_url=self.base_url,
            )
            return await self._fallback_to_openai(system_prompt, messages)
    
    async def _fallback_to_openai(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
    ) -> str:
        """Fallback to OpenAI when Copilot is unavailable."""
        start_time = time.time()
        logfire.info(
            "Using OpenAI fallback",
            message_count=len(messages),
            base_url=self.base_url,
        )
        
        # TODO: Implement OpenAI API call
        # This requires openai package and API key from settings
        elapsed = time.time() - start_time
        logfire.error(
            "OpenAI fallback not implemented",
            response_time_ms=elapsed * 1000,
        )
        raise NotImplementedError("OpenAI fallback not yet implemented")
