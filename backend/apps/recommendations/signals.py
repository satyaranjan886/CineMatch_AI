"""Cache invalidation hooks for personalized recommendations."""

from __future__ import annotations

from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from apps.accounts.models import UserPreference
from apps.interactions.models import Like, MovieInteraction, Rating, WatchHistory, Watchlist
from apps.recommendations.cache import (
    invalidate_collaborative_for_user,
    invalidate_home_recommendations_for_user,
)


def _invalidate_for_user(user) -> None:
    if user is None:
        return
    invalidate_home_recommendations_for_user(user)
    invalidate_collaborative_for_user(user.id)


@receiver(post_save, sender=Like)
@receiver(post_delete, sender=Like)
@receiver(post_save, sender=Rating)
@receiver(post_delete, sender=Rating)
@receiver(post_save, sender=WatchHistory)
@receiver(post_delete, sender=WatchHistory)
@receiver(post_save, sender=MovieInteraction)
@receiver(post_delete, sender=MovieInteraction)
@receiver(post_save, sender=Watchlist)
@receiver(post_delete, sender=Watchlist)
def invalidate_home_on_interaction(sender, instance, **kwargs) -> None:
    _invalidate_for_user(instance.user)


@receiver(m2m_changed, sender=UserPreference.favorite_genres.through)
def invalidate_home_on_genre_preference_change(sender, instance, action, **kwargs) -> None:
    if action in {"post_add", "post_remove", "post_clear"}:
        _invalidate_for_user(instance.user)
