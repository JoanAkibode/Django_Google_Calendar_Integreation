from django.urls import path
from .views import GoogleCalendarInitView, GoogleCalendarRedirectView, GoogleCalendarEventsView, HomeView
from django.urls import path
from .views import UserProfileDetail, StoryList,  GenerateStoryView,NextStoryEventsView, ChangeWantedStatusView,DjangoAuthStatusView, GoogleAuthStatusView


urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    path('init/', GoogleCalendarInitView.as_view(), name='init'),
    path('redirect/', GoogleCalendarRedirectView.as_view(), name='redirect'),# New endpoint
    path('profile/<int:pk>/', UserProfileDetail.as_view(), name='user-profile-detail'),
    path('stories/', StoryList.as_view(), name='story-list'),
    path('events/', GoogleCalendarEventsView.as_view(), name='fetch-events'),
    path('generate-story/', GenerateStoryView.as_view(), name='generate-story'),
    path('next-story-events/', NextStoryEventsView.as_view(), name='next_story_events'),
    path('change-wanted-status/', ChangeWantedStatusView.as_view(), name='change_wanted_status'),
    path('auth/status/', DjangoAuthStatusView.as_view(), name='django-auth-status'),

    # Google authentication status
    path('google-status/', GoogleAuthStatusView.as_view(), name='google-auth-status'),

]
