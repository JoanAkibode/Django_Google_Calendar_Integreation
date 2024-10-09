from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from calenders.views import GoogleCalendarEventsView
from django.http import HttpRequest

class Command(BaseCommand):
    help = 'Fetch and store Google Calendar events for all users'

    def handle(self, *args, **kwargs):
        for user in User.objects.all():
            # Create a request object
            request = HttpRequest()
            request.user = user
            # Call the GoogleCalendarEventsView to fetch and save the events
            response = GoogleCalendarEventsView.as_view()(request)
            print(f"Updated events for {user.email}")
        self.stdout.write(self.style.SUCCESS('Successfully updated calendar events for all users'))
