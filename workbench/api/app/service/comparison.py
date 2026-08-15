"""Comparison service for multi-provider classification/sentiment testing."""

from __future__ import annotations

import uuid

from app.service.classification import classification_service
from app.service.sentiment import sentiment_service
from app.types.classification import (
    ComparisonRequest,
    ComparisonResponse,
    ComparisonResult,
    ComparisonSummary,
)


class ComparisonService:
    """Service for running comparisons across multiple providers."""

    def __init__(self):
        self._results_cache: dict[str, ComparisonResponse] = {}

    async def compare(self, request: ComparisonRequest) -> ComparisonResponse:
        """Run comparison across multiple providers."""
        run_id = str(uuid.uuid4())[:8]
        all_results: list[ComparisonResult] = []

        for provider_config in request.providers:
            provider = provider_config.provider
            model_id = provider_config.model_id

            # Run classification for all texts
            for i, text in enumerate(request.texts):
                text_preview = text[:100] + ("..." if len(text) > 100 else "")

                # Classification
                from app.types.classification import ClassificationRequest

                class_result = await classification_service.classify(
                    ClassificationRequest(
                        text=text,
                        categories=request.categories,
                        provider=provider,
                        model_id=model_id,
                        temperature=provider_config.temperature,
                        max_tokens=provider_config.max_tokens,
                        system_prompt=request.system_prompt,
                    )
                )

                # Sentiment (if requested)
                sent_result = None
                if request.include_sentiment:
                    from app.types.classification import SentimentRequest

                    sent_result = await sentiment_service.analyze(
                        SentimentRequest(
                            text=text,
                            provider=provider,
                            model_id=model_id,
                            temperature=provider_config.temperature,
                            max_tokens=provider_config.max_tokens,
                            include_emotions=True,
                        )
                    )

                result = ComparisonResult(
                    text_index=i,
                    text_preview=text_preview,
                    provider=provider,
                    model_id=class_result.model_id,
                    classification=class_result,
                    sentiment=sent_result,
                    latency_ms=class_result.latency_ms + (sent_result.latency_ms if sent_result else 0),
                )
                all_results.append(result)

        # Calculate summary statistics
        summary = self._calculate_summary(all_results, request)

        response = ComparisonResponse(
            results=all_results,
            summary=summary,
        )

        # Cache for potential export
        self._results_cache[run_id] = response

        return response

    def _calculate_summary(self, results: list[ComparisonResult], request: ComparisonRequest) -> ComparisonSummary:
        """Calculate summary statistics."""
        total_texts = len(request.texts)
        total_providers = len(request.providers)

        if not results:
            return ComparisonSummary(
                total_texts=total_texts,
                total_providers=total_providers,
                avg_latency_ms=0.0,
                category_agreement_rate=0.0,
                sentiment_agreement_rate=0.0,
            )

        # Average latency
        avg_latency = sum(r.latency_ms for r in results) / len(results)

        # Category agreement rate
        category_agreements = 0
        for i in range(total_texts):
            text_results = [r for r in results if r.text_index == i and r.classification]
            if len(text_results) == total_providers:
                categories = [r.classification.category for r in text_results]
                if all(c == categories[0] for c in categories):
                    category_agreements += 1

        category_agreement_rate = (category_agreements / total_texts * 100) if total_texts > 0 else 0.0

        # Sentiment agreement rate
        sentiment_agreements = 0
        if request.include_sentiment:
            for i in range(total_texts):
                text_results = [r for r in results if r.text_index == i and r.sentiment]
                if len(text_results) == total_providers:
                    sentiments = [r.sentiment.sentiment.value for r in text_results]
                    if all(s == sentiments[0] for s in sentiments):
                        sentiment_agreements += 1

        sentiment_agreement_rate = (sentiment_agreements / total_texts * 100) if total_texts > 0 else 0.0

        return ComparisonSummary(
            total_texts=total_texts,
            total_providers=total_providers,
            avg_latency_ms=avg_latency,
            category_agreement_rate=category_agreement_rate,
            sentiment_agreement_rate=sentiment_agreement_rate,
        )

    def get_cached(self, run_id: str) -> ComparisonResponse | None:
        """Get cached comparison result."""
        return self._results_cache.get(run_id)

    def list_cached(self) -> list[str]:
        """List cached comparison run IDs."""
        return list(self._results_cache.keys())


comparison_service = ComparisonService()
