from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.accounts.models import Profile, User, UserPreference


@receiver(post_save, sender=User)
def create_user_profile_and_preferences(sender, instance: User, created: bool, **kwargs) -> None:
    if not created:
        return
    display_name = instance.first_name or instance.email.split("@")[0]
    Profile.objects.create(user=instance, display_name=display_name, is_primary=True)
    UserPreference.objects.create(user=instance)
