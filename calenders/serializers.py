# calenders/serializers.py
from rest_framework import serializers
from .models import UserProfile, Story, Event

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = '__all__'

class StorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Story
        fields = '__all__'


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = ['event_id', 'summary', 'description', 'location', 'start', 'end', 'created', 'updated', 'status', 'html_link', 'organizer_email']
