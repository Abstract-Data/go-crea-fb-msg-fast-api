"""GitHub Copilot SDK wrapper service."""

import logging
from typing import Any

import httpx

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
            return False
        
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                # Simple health check - adjust endpoint based on Copilot SDK API
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except Exception:
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
        if not self.enabled or not await self.is_available():
            # Fallback to OpenAI or other LLM
            logger.warning("Copilot SDK not available, falling back to OpenAI")
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
                return response.json()["content"]
        except Exception as e:
            logger.error(f"Copilot SDK error: {e}, falling back to OpenAI")
            return await self._fallback_to_openai(system_prompt, messages)
    
    async def _fallback_to_openai(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
    ) -> str:
        """Fallback to OpenAI when Copilot is unavailable."""
        # TODO: Implement OpenAI API call
        # This requires openai package and API key from settings
        raise NotImplementedError("OpenAI fallback not yet implemented")
