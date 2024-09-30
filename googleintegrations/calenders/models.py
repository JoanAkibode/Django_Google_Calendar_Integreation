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


