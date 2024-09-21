from django.urls import path
from .views import GoogleCalendarInitView, GoogleCalendarRedirectView, GoogleCalendarEventsView, HomeView

urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    path('init/', GoogleCalendarInitView.as_view(), name='init'),
    path('redirect/', GoogleCalendarRedirectView.as_view(), name='redirect'),
    path('events/', GoogleCalendarEventsView.as_view(), name='google_events'),  # New endpoint
]
