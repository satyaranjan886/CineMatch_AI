import time

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.analytics.services.logging import log_recommendation_serve
from apps.common.observability.metrics import observe_recommendation
from apps.movies.serializers import MovieListSerializer
from apps.recommendations.serializers import (
    HomeRecommendationResponseSerializer,
    RecommendationResponseSerializer,
)
from apps.recommendations.services.collaborative import CollaborativeRecommendationService
from apps.recommendations.services.hybrid import HybridHomeRecommendationService
from apps.recommendations.services.popularity import PopularityRecommendationService
from apps.recommendations.services.trending import TrendingRecommendationService


class PopularRecommendationsView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses={200: RecommendationResponseSerializer})
    def get(self, request):
        started = time.perf_counter()
        limit = min(int(request.query_params.get("limit", 20)), 100)
        service = PopularityRecommendationService()
        result = service.get_recommendations(limit=limit)
        payload = _build_payload(result, limit)
        movie_ids = [item.movie.id for item in result.items[:limit]]
        event = log_recommendation_serve(
            algorithm=result.strategy,
            movie_ids=movie_ids,
            cached=result.cached,
            user=getattr(request, "user", None),
            surface="popular",
        )
        observe_recommendation(
            algorithm=result.strategy,
            model_version=str(result.context.get("model_version", "")),
            latency_seconds=time.perf_counter() - started,
            candidate_count=result.context.get("candidate_count", len(result.items)),
            recommendation_count=len(movie_ids),
            cached=result.cached,
        )
        payload["serve_id"] = str(event.id) if event is not None else None
        return Response(payload)


class TrendingRecommendationsView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="window", description="Trending window in hours", required=False, type=int
            ),
            OpenApiParameter(
                name="limit", description="Maximum items to return", required=False, type=int
            ),
        ],
        responses={200: RecommendationResponseSerializer},
    )
    def get(self, request):
        from django.conf import settings

        started = time.perf_counter()
        limit = min(int(request.query_params.get("limit", 20)), 100)
        window = int(
            request.query_params.get(
                "window",
                settings.RECOMMENDATION_TRENDING_DEFAULT_WINDOW_HOURS,
            )
        )
        service = TrendingRecommendationService()
        result = service.get_recommendations(limit=limit, context={"window_hours": window})
        payload = _build_payload(result, limit)
        movie_ids = [item.movie.id for item in result.items[:limit]]
        event = log_recommendation_serve(
            algorithm=result.strategy,
            movie_ids=movie_ids,
            cached=result.cached,
            user=getattr(request, "user", None),
            surface="trending",
            metadata={"window_hours": window},
        )
        observe_recommendation(
            algorithm=result.strategy,
            latency_seconds=time.perf_counter() - started,
            candidate_count=result.context.get("candidate_count", len(result.items)),
            recommendation_count=len(movie_ids),
            cached=result.cached,
        )
        payload["serve_id"] = str(event.id) if event is not None else None
        return Response(payload)


class CollaborativeRecommendationsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: RecommendationResponseSerializer})
    def get(self, request):
        started = time.perf_counter()
        limit = min(int(request.query_params.get("limit", 20)), 100)
        service = CollaborativeRecommendationService()
        result = service.get_recommendations(user=request.user, limit=limit)
        payload = _build_payload(result, limit)
        payload["fallback"] = bool(result.context.get("fallback"))
        if result.context.get("reason"):
            payload["reason"] = result.context["reason"]
        movie_ids = [item.movie.id for item in result.items[:limit]]
        event = log_recommendation_serve(
            algorithm=result.strategy,
            movie_ids=movie_ids,
            cached=result.cached,
            user=request.user,
            surface="collaborative",
        )
        observe_recommendation(
            algorithm=result.strategy,
            model_version=str(result.context.get("model_version", "")),
            latency_seconds=time.perf_counter() - started,
            candidate_count=result.context.get("candidate_count", len(result.items)),
            recommendation_count=len(movie_ids),
            cached=result.cached,
            user_id=str(request.user.id),
        )
        payload["serve_id"] = str(event.id) if event is not None else None
        return Response(payload)


class HomeRecommendationsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: HomeRecommendationResponseSerializer})
    def get(self, request):
        started = time.perf_counter()
        context = {}
        if request.query_params.get("context"):
            context["surface"] = request.query_params.get("context")

        service = HybridHomeRecommendationService()
        result = service.get_home_recommendations(user=request.user, context=context)
        payload = _build_home_payload(result)
        movie_ids = []
        for section in result.sections:
            for item in section.movies:
                movie_ids.append(item.movie.id)
        event = log_recommendation_serve(
            algorithm="hybrid_home",
            movie_ids=movie_ids,
            cached=result.cached,
            user=request.user,
            model_version=result.version,
            surface=context.get("surface", "home"),
            metadata={
                "sections": [section.name for section in result.sections],
                "experiment_id": result.context.get("experiment_id"),
                "variant": result.context.get("variant"),
                "model_key": result.context.get("model_key"),
                "candidate_count": result.context.get("candidate_count"),
                "recommendation_count": len(movie_ids),
            },
        )
        observe_recommendation(
            algorithm="hybrid_home",
            model_version=result.version,
            latency_seconds=time.perf_counter() - started,
            candidate_count=result.context.get("candidate_count"),
            recommendation_count=len(movie_ids),
            cached=result.cached,
            user_id=str(request.user.id),
        )
        payload["serve_id"] = str(event.id) if event is not None else None
        response = Response(payload)
        from django.conf import settings as django_settings

        if getattr(django_settings, "LOADTEST_TIMING", False):
            response["X-Cinematch-Cache"] = "HIT" if result.cached else "MISS"
            timings = result.context.get("timings_ms")
            if timings:
                parts = [f"{key}={value}" for key, value in timings.items()]
                response["X-Cinematch-Timing"] = ";".join(parts)
        return response


def _build_home_payload(result) -> dict:
    return {
        "version": result.version,
        "cached": result.cached,
        "sections": [
            {
                "name": section.name,
                "algorithm": section.algorithm,
                "model_version": section.model_version,
                "count": len(section.movies),
                "movies": [
                    {
                        **_serialize_home_movie(item.movie),
                        "score": round(item.score, 4),
                        "reason": item.reason,
                        "primary_source": item.primary_source,
                    }
                    for item in section.movies
                ],
            }
            for section in result.sections
        ],
    }


def _serialize_home_movie(movie) -> dict:
    return MovieListSerializer(movie).data


def _build_payload(result, limit: int) -> dict:
    items = result.items[:limit]
    return {
        "strategy": result.strategy,
        "cached": result.cached,
        "count": len(items),
        "results": [
            {
                **MovieListSerializer(item.movie).data,
                "score": round(item.score, 4),
                "reason": item.reason,
            }
            for item in items
        ],
    }
