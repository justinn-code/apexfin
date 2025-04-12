from django.core.management.base import BaseCommand
from users.models import CustomUser, UserProfile

class Command(BaseCommand):
    help = 'Create missing UserProfiles for existing users'

    def handle(self, *args, **kwargs):
        users_without_profiles = CustomUser.objects.filter(userprofile__isnull=True)
        for user in users_without_profiles:
            UserProfile.objects.create(user=user)
            self.stdout.write(self.style.SUCCESS(f'✅ Created profile for: {user.username}'))
        self.stdout.write(self.style.SUCCESS('🎉 All missing user profiles created.'))
