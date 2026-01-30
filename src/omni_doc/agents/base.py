"""Base class for specialized documentation agents."""

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel

from omni_doc.config import get_settings
from omni_doc.models.state import OmniDocState
from omni_doc.utils.logging import get_logger, LLMError

logger = get_logger(__name__)

# Type variable for agent output
T = TypeVar("T", bound=BaseModel)


class BaseDocAgent(ABC, Generic[T]):
    """Abstract base class for specialized documentation agents.

    Agents are responsible for specific documentation tasks like:
    - Generating corrections for outdated docs
    - Writing new documentation
    - Creating architectural diagrams

    Subclasses must implement:
    - name: Agent identifier
    - system_prompt: System prompt for the LLM
    - output_model: Pydantic model for structured output
    - process(): Main processing logic
    """

    def __init__(self, temperature: float = 0.2) -> None:
        """Initialize the agent.

        Args:
            temperature: LLM temperature (0.0-1.0). Higher = more creative.
        """
        self._temperature = temperature
        self._llm: ChatGoogleGenerativeAI | None = None

    @property
    @abstractmethod
    def name(self) -> str:
        """Agent name identifier."""
        ...

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """System prompt for the agent."""
        ...

    @property
    @abstractmethod
    def output_model(self) -> type[T]:
        """Pydantic model class for structured output."""
        ...

    def _get_llm(self) -> ChatGoogleGenerativeAI:
        """Get or create the LLM instance."""
        if self._llm is None:
            settings = get_settings()
            self._llm = ChatGoogleGenerativeAI(
                model=settings.gemini_model,
                google_api_key=settings.google_api_key.get_secret_value(),
                temperature=self._temperature,
            )
        return self._llm

    async def _invoke(self, user_prompt: str) -> T:
        """Invoke the LLM with structured output.

        Args:
            user_prompt: User/context prompt

        Returns:
            Structured output matching output_model

        Raises:
            LLMError: If LLM invocation fails
        """
        try:
            llm = self._get_llm()
            structured_llm = llm.with_structured_output(self.output_model)

            response: T = await structured_llm.ainvoke([
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt},
            ])

            return response

        except Exception as e:
            logger.exception(f"Agent {self.name} LLM invocation failed")
            raise LLMError(
                f"Agent {self.name} failed: {e}",
                model=get_settings().gemini_model,
            ) from e

    @abstractmethod
    async def process(self, state: OmniDocState) -> dict[str, Any]:
        """Process the state and return updates.

        Args:
            state: Current workflow state

        Returns:
            State updates (typically agent_outputs, findings)
        """
        ...

    def _build_context(self, state: OmniDocState) -> str:
        """Build context string from state.

        Override in subclasses for custom context building.

        Args:
            state: Current workflow state

        Returns:
            Context string for the LLM
        """
        parts = []

        # PR info
        pr_metadata = state.get("pr_metadata", {})
        parts.append(f"## PR: {pr_metadata.get('title', 'Unknown')}")
        parts.append(f"Author: {pr_metadata.get('author', 'unknown')}")
        parts.append("")

        # File changes
        file_changes = state.get("file_changes", [])
        if file_changes:
            parts.append("## File Changes")
            for fc in file_changes[:15]:
                parts.append(f"- {fc['filename']} ({fc['status']})")
            parts.append("")

        # Current findings
        findings = state.get("findings", [])
        if findings:
            parts.append("## Current Findings")
            for f in findings[:10]:
                parts.append(f"- [{f['severity']}] {f['title']}")
            parts.append("")

        return "\n".join(parts)
