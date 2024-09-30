from django.urls import path
from .views import GoogleCalendarInitView, GoogleCalendarRedirectView, GoogleCalendarEventsView, HomeView
from django.urls import path
from .views import UserProfileDetail, StoryList,  GenerateStoryView


urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    path('init/', GoogleCalendarInitView.as_view(), name='init'),
    path('redirect/', GoogleCalendarRedirectView.as_view(), name='redirect'),# New endpoint
    path('profile/<int:pk>/', UserProfileDetail.as_view(), name='user-profile-detail'),
    path('stories/', StoryList.as_view(), name='story-list'),
    path('events/', GoogleCalendarEventsView.as_view(), name='fetch-events'),
    path('generate-story/', GenerateStoryView.as_view(), name='generate-story'),
]
