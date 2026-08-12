import time

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.throttles import SearchThrottle
from apps.common.observability.metrics import observe_cache, observe_search
from apps.movies.serializers import MovieListSerializer
from apps.search.cache import (
    get_cached_semantic_search,
    semantic_search_cache_key,
    set_cached_semantic_search,
)
from apps.search.serializers import SemanticSearchResponseSerializer
from apps.search.services.similarity import SemanticSimilarityService


class SemanticSearchView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [SearchThrottle]

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="q", description="Natural language search query", required=True, type=str
            ),
            OpenApiParameter(name="limit", description="Maximum results", required=False, type=int),
            OpenApiParameter(
                name="model_version",
                description="Embedding model version",
                required=False,
                type=str,
            ),
        ],
        responses={200: SemanticSearchResponseSerializer},
    )
    def get(self, request):
        started = time.perf_counter()
        query = request.query_params.get("q", "").strip()
        if not query:
            raise ValidationError({"q": "Query parameter is required."})
        if len(query) > 500:
            raise ValidationError({"q": "Query must be 500 characters or fewer."})

        limit = min(int(request.query_params.get("limit", 20)), 100)
        model_version = request.query_params.get("model_version")
        service = SemanticSimilarityService(model_version=model_version)

        cache_key = semantic_search_cache_key(
            query=query,
            limit=limit,
            model_name=service.model_name,
            model_version=service.model_version,
        )
        cached = get_cached_semantic_search(cache_key)
        if cached is not None:
            observe_cache(cache_name="search_semantic", hit=True)
            observe_search(
                cached=True,
                latency_seconds=time.perf_counter() - started,
                result_count=int(cached.get("count", 0)),
            )
            return Response(cached)

        observe_cache(cache_name="search_semantic", hit=False)
        matches = service.search_by_query(query, limit=limit)
        payload = {
            "query": query,
            "model_name": service.model_name,
            "model_version": service.model_version,
            "count": len(matches),
            "results": [
                {
                    **MovieListSerializer(match.movie).data,
                    "score": round(match.score, 6),
                }
                for match in matches
            ],
        }
        set_cached_semantic_search(cache_key, payload)
        observe_search(
            cached=False,
            latency_seconds=time.perf_counter() - started,
            result_count=len(matches),
        )
        return Response(payload)
