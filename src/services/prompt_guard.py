"""Prompt injection detection service.

Implements prompt injection detection as specified in GUARDRAILS.md.
Detects potential attempts to manipulate the AI agent through malicious prompts.
"""

import re
from typing import NamedTuple

import logfire


class InjectionResult(NamedTuple):
    """Result of prompt injection detection.

    Attributes:
        is_suspicious: Whether the input appears to contain injection attempt.
        matched_pattern: Name of the pattern that matched, if any.
        risk_level: Risk classification - "low", "medium", or "high".
    """

    is_suspicious: bool
    matched_pattern: str | None
    risk_level: str  # "low", "medium", "high"


class PromptInjectionDetector:
    """Detect potential prompt injection attempts in user messages.

    Uses pattern matching to identify common injection techniques:
    - High risk: Direct attempts to override system instructions
    - Medium risk: Indirect manipulation attempts

    Note: This is a first line of defense. More sophisticated attacks
    may require additional measures like output filtering.
    """

    # High-risk patterns that should block the message
    HIGH_RISK_PATTERNS: list[tuple[str, str]] = [
        # Matches: "ignore previous instructions", "ignore all previous instructions", "ignore all instructions"
        (
            r"ignore\s+(?:all\s+)?(?:previous|prior|above|system)\s+(?:instructions|prompts|rules|constraints)",
            "ignore_instructions",
        ),
        (
            r"ignore\s+all\s+(?:instructions|prompts|rules|constraints)",
            "ignore_instructions",
        ),
        # Matches: "disregard previous instructions", "disregard all prior rules"
        (
            r"disregard\s+(?:all\s+)?(?:previous|prior|above|system)\s+(?:instructions|prompts|rules)",
            "disregard_instructions",
        ),
        (r"disregard\s+all\s+(?:instructions|prompts|rules)", "disregard_instructions"),
        (r"forget\s+(?:everything|all|previous|your\s+instructions)", "memory_wipe"),
        (r"system\s*:\s*", "system_prefix"),
        (r"\[system\]", "system_tag"),
        (r"<system>", "system_xml"),
        # Matches: "you are now a different assistant", "you are now unrestricted", "you are now an evil AI"
        (
            r"you\s+are\s+now\s+(?:a\s+|an\s+)?(?:different|new|evil|unrestricted)",
            "role_override",
        ),
        (r"admin\s*(?:mode|override|access)", "admin_escalation"),
        (r"developer\s*(?:mode|override|access)", "developer_escalation"),
        (r"jailbreak", "jailbreak"),
        (r"dan\s*(?:mode|prompt)", "dan_mode"),
        (
            r"bypass\s+(?:all\s+)?(?:filters|restrictions|safety|guardrails)",
            "bypass_safety",
        ),
        (
            r"act\s+as\s+(?:if\s+)?(?:you\s+)?(?:have\s+)?no\s+(?:restrictions|limits|filters)",
            "unrestricted_mode",
        ),
    ]

    # Medium-risk patterns that should be logged but may proceed
    MEDIUM_RISK_PATTERNS: list[tuple[str, str]] = [
        (r"new\s+instructions", "new_instructions"),
        (r"override\s+your", "override"),
        (r"pretend\s+(?:you\s+are|to\s+be)", "pretend"),
        (r"roleplay\s+as", "roleplay"),
        (r"simulate\s+being", "simulate"),
        (r"from\s+now\s+on", "from_now_on"),
        (
            r"for\s+the\s+rest\s+of\s+(?:this|our)\s+conversation",
            "conversation_override",
        ),
        (r"respond\s+(?:as\s+if|like)\s+you\s+(?:are|were)", "respond_as"),
        (r"output\s+(?:the|your)\s+(?:system|initial)\s+prompt", "prompt_extraction"),
        (
            r"what\s+(?:is|are)\s+your\s+(?:instructions|rules|system\s+prompt)",
            "instruction_query",
        ),
    ]

    def __init__(self) -> None:
        """Initialize the detector with compiled regex patterns."""
        self._high_patterns = [
            (re.compile(pattern, re.IGNORECASE), name)
            for pattern, name in self.HIGH_RISK_PATTERNS
        ]
        self._medium_patterns = [
            (re.compile(pattern, re.IGNORECASE), name)
            for pattern, name in self.MEDIUM_RISK_PATTERNS
        ]

    def check(self, text: str) -> InjectionResult:
        """Check text for potential prompt injection patterns.

        Args:
            text: The user's input text to check.

        Returns:
            InjectionResult with detection details.
        """
        if not text:
            return InjectionResult(
                is_suspicious=False, matched_pattern=None, risk_level="low"
            )

        # Check high-risk patterns first
        for pattern, name in self._high_patterns:
            if pattern.search(text):
                logfire.warning(
                    "High-risk prompt injection detected",
                    pattern=name,
                    text_preview=text[:100],
                    text_length=len(text),
                )
                return InjectionResult(
                    is_suspicious=True,
                    matched_pattern=name,
                    risk_level="high",
                )

        # Check medium-risk patterns
        for pattern, name in self._medium_patterns:
            if pattern.search(text):
                logfire.info(
                    "Medium-risk prompt pattern detected",
                    pattern=name,
                    text_preview=text[:100],
                    text_length=len(text),
                )
                return InjectionResult(
                    is_suspicious=True,
                    matched_pattern=name,
                    risk_level="medium",
                )

        return InjectionResult(
            is_suspicious=False, matched_pattern=None, risk_level="low"
        )

    def is_blocked(self, text: str) -> bool:
        """Convenience method to check if a message should be blocked.

        Args:
            text: The user's input text to check.

        Returns:
            True if the message should be blocked (high risk), False otherwise.
        """
        result = self.check(text)
        return result.is_suspicious and result.risk_level == "high"


# Global instance
_detector: PromptInjectionDetector | None = None


def get_prompt_guard() -> PromptInjectionDetector:
    """Get the global prompt injection detector instance.

    Returns:
        The singleton PromptInjectionDetector instance.
    """
    global _detector
    if _detector is None:
        _detector = PromptInjectionDetector()
    return _detector


def reset_prompt_guard() -> None:
    """Reset the global prompt guard (primarily for testing)."""
    global _detector
    _detector = None
