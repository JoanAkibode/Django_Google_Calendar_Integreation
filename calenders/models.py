from django.db import models
from django.contrib.auth.models import User

class GoogleCalendar(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    google_id = models.CharField(max_length=200)
    access_token = models.CharField(max_length=500)
    refresh_token = models.CharField(max_length=500)



class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    email = models.EmailField()
    google_sync_token = models.CharField(max_length=255, blank=True, null=True)  # Store sync token
    preferred_style = models.CharField(max_length=100, default="Narrative")
    story_frequency = models.CharField(max_length=20, choices=[('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly')], default='weekly')
    goals = models.TextField(blank=True)  # Users can specify their life goals

class Story(models.Model):
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='stories')
    date_created = models.DateTimeField(auto_now_add=True)
    story_text = models.TextField()
    date_of_story = models.DateField()  # The date the story is about

    def __str__(self):
        return f"Story for {self.user_profile.user.email} on {self.date_of_story}"


class Event(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='events')  # Link to the user
    event_id = models.CharField(max_length=255, unique=True)  # Store Google event id
    summary = models.CharField(max_length=255)  # Event title
    description = models.TextField(blank=True, null=True)  # Event description (optional)
    location = models.CharField(max_length=255, blank=True, null=True)  # Event location (optional)
    start = models.DateTimeField()  # Start time
    end = models.DateTimeField()  # End time
    created = models.DateTimeField()  # When the event was created
    updated = models.DateTimeField()  # Last time the event was updated
    status = models.CharField(max_length=50)  # Status of the event (e.g., confirmed)
    html_link = models.URLField(blank=True, null=True)  # Optional link to the event on Google Calendar
    organizer_email = models.EmailField(blank=True, null=True)  # Organizer's email address (optional)
    include_in_next_daily_story = models.BooleanField(default=False)  # Include this event in the next daily story

    def __str__(self):
        return f'{self.summary} ({self.event_id})'



