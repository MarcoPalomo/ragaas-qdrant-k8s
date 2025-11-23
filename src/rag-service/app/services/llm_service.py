"""LLM service for generating responses using OpenAI."""

import asyncio
from typing import Optional

from openai import AsyncOpenAI

from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class LLMService:
    """Service for interacting with OpenAI LLM."""

    def __init__(
        self,
        client: Optional[AsyncOpenAI] = None,
        model: Optional[str] = None,
    ):
        """
        Initialize LLM service.

        Args:
            client: Optional AsyncOpenAI client (for testing)
            model: Model name to use
        """
        self.client = client or AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = model or settings.openai_model

    async def generate_response(
        self,
        query: str,
        context: list[str],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> tuple[str, float]:
        """
        Generate a response using retrieved context.

        Args:
            query: User's question
            context: List of relevant document chunks
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens in response

        Returns:
            Tuple of (response text, confidence score)
        """
        temperature = temperature or settings.openai_temperature
        max_tokens = max_tokens or settings.openai_max_tokens

        # Build context string
        context_text = "\n\n---\n\n".join(context) if context else "No relevant context found."

        system_prompt = """You are a helpful assistant that answers questions based on the provided context.
Always base your answers on the context provided. If the context doesn't contain enough information
to answer the question, say so clearly. Be concise and accurate."""

        user_prompt = f"""Context:
{context_text}

Question: {query}

Please provide a clear and accurate answer based on the context above."""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )

            answer = response.choices[0].message.content or ""

            # Calculate confidence based on context availability and response
            confidence = self._calculate_confidence(context, answer)

            logger.info(
                "Generated response",
                extra={
                    "query_length": len(query),
                    "context_chunks": len(context),
                    "response_length": len(answer),
                    "confidence": confidence,
                },
            )

            return answer, confidence

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            raise

    async def generate_streaming_response(
        self,
        query: str,
        context: list[str],
        temperature: Optional[float] = None,
    ):
        """
        Generate a streaming response.

        Args:
            query: User's question
            context: List of relevant document chunks
            temperature: Sampling temperature

        Yields:
            Response chunks as they are generated
        """
        temperature = temperature or settings.openai_temperature
        context_text = "\n\n---\n\n".join(context) if context else "No relevant context found."

        system_prompt = """You are a helpful assistant that answers questions based on the provided context.
Always base your answers on the context provided."""

        user_prompt = f"""Context:
{context_text}

Question: {query}"""

        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                stream=True,
            )

            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error(f"Error in streaming response: {e}")
            raise

    def _calculate_confidence(self, context: list[str], answer: str) -> float:
        """
        Calculate confidence score for the response.

        Args:
            context: Retrieved context chunks
            answer: Generated answer

        Returns:
            Confidence score between 0 and 1
        """
        if not context:
            return 0.3

        # Base confidence on context availability
        base_confidence = min(0.5 + (len(context) * 0.1), 0.9)

        # Reduce confidence for uncertainty phrases
        uncertainty_phrases = [
            "i don't know",
            "not sure",
            "unclear",
            "no information",
            "cannot determine",
            "not enough context",
        ]

        answer_lower = answer.lower()
        for phrase in uncertainty_phrases:
            if phrase in answer_lower:
                base_confidence *= 0.7
                break

        return round(base_confidence, 2)

    async def summarize(self, text: str, max_length: int = 500) -> str:
        """
        Summarize a piece of text.

        Args:
            text: Text to summarize
            max_length: Maximum summary length

        Returns:
            Summarized text
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that creates concise summaries.",
                    },
                    {
                        "role": "user",
                        "content": f"Summarize the following text in {max_length} characters or less:\n\n{text}",
                    },
                ],
                temperature=0.3,
                max_tokens=max_length // 2,
            )

            return response.choices[0].message.content or ""

        except Exception as e:
            logger.error(f"Error summarizing text: {e}")
            raise
