"""Invalidate movie detail cache when catalog rows change."""

from __future__ import annotations

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.movies.cache import invalidate_movie_detail
from apps.movies.models import Movie, MovieActor, MovieDirector, MovieGenre


@receiver(post_save, sender=Movie)
@receiver(post_delete, sender=Movie)
def invalidate_on_movie_change(sender, instance, **kwargs) -> None:
    invalidate_movie_detail(instance.id)


@receiver(post_save, sender=MovieGenre)
@receiver(post_delete, sender=MovieGenre)
@receiver(post_save, sender=MovieActor)
@receiver(post_delete, sender=MovieActor)
@receiver(post_save, sender=MovieDirector)
@receiver(post_delete, sender=MovieDirector)
def invalidate_on_catalog_link_change(sender, instance, **kwargs) -> None:
    invalidate_movie_detail(instance.movie_id)
