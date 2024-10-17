import os
import json
from dotenv import load_dotenv
from django.http import HttpResponseRedirect
from rest_framework import exceptions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import redirect

from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from datetime import datetime, timedelta, timezone, time
from django.views.generic import TemplateView
from django.http import JsonResponse
from google.oauth2.credentials import Credentials

from django.contrib.auth.models import User, AnonymousUser
from django.contrib.auth import login
from .models import UserProfile

from rest_framework import generics
from .models import UserProfile, Story
from .serializers import UserProfileSerializer, StorySerializer

from django.core.mail import send_mail

import openai

from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response

from rest_framework.permissions import IsAuthenticated
from django.core.cache import cache

from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator

from django.db import transaction




load_dotenv()

"""As we are using http for testing purposes only,
 and google_auth_oauthlib needs a https connection,
 so we are setting the environment variable to 1
 """
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

CLIENT_CONFIG = {
    "web": {
        "project_id": os.getenv('PROJECT_ID'),
        "client_id": os.getenv('CLIENT_ID'),
        "client_secret": os.getenv('CLIENT_SECRET'),
        "redirect_uris": [os.getenv('REDIRECT_URI')],
        "javascript_origins": [os.getenv('JS_ORIGIN')],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    }
}

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly',
        'https://www.googleapis.com/auth/userinfo.email',
        'https://www.googleapis.com/auth/userinfo.profile',
        'openid']

class GoogleCalendarInitView(APIView):
    def get(self, request):
        try:
            flow = Flow.from_client_config(CLIENT_CONFIG, SCOPES, redirect_uri=os.getenv('REDIRECT_URI'))
            authorization_url, state = flow.authorization_url(access_type='offline', include_granted_scopes='true')
            request.session['state'] = state
            return HttpResponseRedirect(authorization_url)
        except Exception as e:
            raise exceptions.ValidationError(str(e))
        

def update_in_time_window_for_events(user):
    """Update the in_time_window field for all events of the given user."""
    current_time_utc = datetime.now(timezone.utc)


    # Fetch all existing events for the user
    existing_events = Event.objects.filter(user=user)

    for event in existing_events:
        event_start = event.start
        event_in_story_window = False

        # Set the story window logic based on the current time
        if current_time_utc.time() < time(8, 0):  # Before 8 AM
            event_in_story_window = event_start.date() == (current_time_utc.date() - timedelta(days=1))  # Yesterday's events
        else:  # After 8 AM
            event_in_story_window = event_start.date() == current_time_utc.date()  # Today's events

        # Update the event
        event.in_time_window = event_in_story_window
        event.save()

from .models import Event, UserProfile

class GoogleCalendarEventsView(APIView):
    def get(self, request):
        # Check for user authentication and credentials
        credentials_data = request.session.get('credentials')
        if not credentials_data:
            return JsonResponse({'error': 'User not authenticated with Google.'}, status=401)
        
        if isinstance(request.user, AnonymousUser):
            return JsonResponse({'error': 'User not authenticated with Django.'}, status=401)


        # Implement rate-limiting
        user_id = request.user.id
        cache_key = f"google_calendar_last_call_{user_id}"
        last_call_timestamp = cache.get(cache_key)
        current_time = datetime.now(timezone.utc).timestamp()

        # Check if the last call was within the last 2 seconds
        if last_call_timestamp and (current_time - last_call_timestamp) < 5:
            return JsonResponse({'error': 'Rate limit exceeded. Please wait 2 seconds between requests.'}, status=429)

        # Update the cache with the current timestamp
        cache.set(cache_key, current_time, timeout=2)
        
        # Set up Google OAuth credentials
        credentials = Credentials(
            token=credentials_data['token'],
            refresh_token=credentials_data['refresh_token'],
            token_uri=credentials_data['token_uri'],
            client_id=credentials_data['client_id'],
            client_secret=credentials_data['client_secret'],
            scopes=credentials_data['scopes']
        )

        # Refresh token if necessary
        if credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(request())
                request.session['credentials'] = {
                    'token': credentials.token,
                    'refresh_token': credentials.refresh_token,
                    'token_uri': credentials.token_uri,
                    'client_id': credentials.client_id,
                    'client_secret': credentials.client_secret,
                    'scopes': credentials.scopes,
                }
                request.session.modified = True
            except Exception as e:
                return JsonResponse({'error': f'Failed to refresh token: {str(e)}'}, status=500)

        # Initialize Google Calendar API service
        service = build('calendar', 'v3', credentials=credentials)

        # Get current UTC time
# Get current UTC time
        now = datetime.now(timezone.utc)

        # Calculate start and end dates
        start_date = now - timedelta(days=30)
        end_date = now + timedelta(days=60)

        # Ensure start_date and end_date are formatted correctly
        # Use timespec='seconds' to round to seconds and append 'Z' for UTC
        start_date_rfc3339 = start_date.isoformat(timespec='seconds').replace('+00:00', 'Z')
        end_date_rfc3339 = end_date.isoformat(timespec='seconds').replace('+00:00', 'Z')

        print("start_date_rfc3339:", start_date_rfc3339)
        print("end_date_rfc3339:", end_date_rfc3339)


        # Fetch user's syncToken (if available) for incremental sync
        user_profile = UserProfile.objects.get(user=request.user)
        sync_token = user_profile.google_sync_token

        try:
            if sync_token:
                # Use syncToken to fetch only changed events but still apply date range filter
                print("Using syncToken for incremental sync")
                events_result = service.events().list(
                    calendarId='primary',
                    syncToken=sync_token,
                    timeMin=start_date_rfc3339,  # Add timeMin for the start date
                    timeMax=end_date_rfc3339    # Add timeMax for the end date
                ).execute()
            else:
                # No syncToken, first sync, fetch all events within the time range
                events_result = service.events().list(
                    calendarId='primary',
                    maxResults=250,
                    singleEvents=True,
                    orderBy='startTime',
                    timeMin=start_date_rfc3339,
                    timeMax=end_date_rfc3339
                ).execute()

        except Exception as e:
            if 'Sync token is invalid' in str(e):
                request.session['syncToken'] = None  # Reset sync token for a full sync on the next attempt
            
            print("Error while fetching events:", str(e))
            return JsonResponse({'error': f'Failed to fetch events: {str(e)}'}, status=500)

        events = events_result.get('items', [])

        # Save or update events in the database
        for event in events:
            event_start_str = event['start'].get('dateTime', event['start'].get('date'))
            event_end_str = event['end'].get('dateTime', event['end'].get('date'))

            # Convert to datetime while preserving the timezone info
            event_start = datetime.fromisoformat(event_start_str)
            event_end = datetime.fromisoformat(event_end_str)

            # If the event is an all-day event (date only), make it UTC-aware with start of the day
            if 'date' in event['start']:
                event_start = event_start.replace(tzinfo=timezone.utc)
            if 'date' in event['end']:
                event_end = event_end.replace(tzinfo=timezone.utc)   

            event_in_story_window = False

            current_time = now.time()

            # Define the story window logic
            if current_time < time(8, 0):  # Before 8 AM
                event_in_story_window = event_start.date() == (now.date() - timedelta(days=1))  # Yesterday's events
            else:  # After 8 AM
                event_in_story_window = event_start.date() == now.date()  # Today's events

            Event.objects.update_or_create(
                user=request.user,
                event_id=event['id'],
                defaults={
                    'summary': event.get('summary', 'No title'),
                    'description': event.get('description', ''),
                    'start': event_start,
                    'end': event_end,
                    'created': event['created'],
                    'updated': event['updated'],
                    'html_link': event['htmlLink'],
                    'location': event.get('location', ''),
                    'status': event['status'],
                    'organizer_email': event.get('organizer', {}).get('email', ''),
                    'in_time_window': event_in_story_window,
                }
            )

        # Store the new syncToken after the fetch
        if 'nextSyncToken' in events_result:
            print("Storing nextSyncToken:", events_result['nextSyncToken'])
            user_profile.google_sync_token = events_result['nextSyncToken']
            user_profile.save()

        update_in_time_window_for_events(request.user)

        return JsonResponse({"events": events}, status=200)




class GoogleCalendarRedirectView(APIView):
    def set_session(self, request, credentials):
        request.session['credentials'] = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes,
        }
        request.session.modified = True 

    def get(self, request):
        try:
            state = request.session.get('state')
            if not state:
                return Response({'error': 'Invalid state parameter'}, status=400)

            # Fetch token and store credentials in session
            flow = Flow.from_client_config(CLIENT_CONFIG, SCOPES, state=state, redirect_uri=os.getenv('REDIRECT_URI'))
            flow.fetch_token(authorization_response=request.build_absolute_uri())
            credentials = flow.credentials
            self.set_session(request, credentials)
            
            # Extract user info from Google credentials
            user_info_service = build('oauth2', 'v2', credentials=credentials)
            user_info = user_info_service.userinfo().get().execute()

            # Create or get user
            user, created = User.objects.get_or_create(username=user_info['email'], email=user_info['email'])

            if created:
                user.first_name = user_info.get('given_name', '')
                user.last_name = user_info.get('family_name', '')
                user.save()

            # Log the user in with Django's authentication system
            user.backend = 'django.contrib.auth.backends.ModelBackend'
            login(request, user)  # Log the user into Django

            # Ensure user profile exists (signal should handle this automatically)
            UserProfile.objects.get_or_create(user=user)

            # Redirect the user to the dashboard
            return HttpResponseRedirect(f'http://localhost:3000/dashboard?auth=true&email={user.email}')

        except Exception as e:
            return Response({'error': str(e)}, status=500)



# New view to fetch only events for the next story
class NextStoryEventsView(APIView):
    def get(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'User not authenticated'}, status=401)

        # Fetch events that are marked to be included in the next story
        next_story_events = Event.objects.filter(user=request.user, in_time_window=True)

        # Serialize and return the events
        event_list = [
            {
                'summary': event.summary,
                'start': event.start,
                'end': event.end,
                'in_time_window': event.in_time_window,
                'wanted_by_the_user' : event.wanted_by_the_user
            }
            for event in next_story_events
        ]

        return JsonResponse({'events': event_list}, status=200)




class ChangeWantedStatusView(APIView):
    def post(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'User not authenticated'}, status=401)

        event_id = request.data.get('event_id')
        wanted_by_the_user = request.data.get('wanted_by_the_user')

        # Validate input
        if event_id is None or wanted_by_the_user is None:
            return JsonResponse({'error': 'Invalid data provided'}, status=400)

        if not isinstance(wanted_by_the_user, bool):
            return JsonResponse({'error': 'Invalid value for wanted_by_the_user. Must be a boolean.'}, status=400)

        try:
            # Use atomic transaction to ensure data consistency
            with transaction.atomic():
                event = Event.objects.get(user=request.user, id=event_id)
                event.wanted_by_the_user = wanted_by_the_user
                event.save()

            return JsonResponse({'message': 'Event updated successfully'}, status=200)

        except Event.DoesNotExist:
            return JsonResponse({'error': 'Event not found'}, status=404)

        except Exception as e:
            # Log the error for debugging purposes
            print(f"Unexpected error occurred: {e}")
            return JsonResponse({'error': 'An unexpected error occurred'}, status=500)


# class HomeView(APIView):
#     def get(self, request):
#         return Response({'Google Calendar Integration, click on the link to authorize your google account: http://localhost:8000/rest/v1/calendar/init/'})

class HomeView(TemplateView):
    template_name = 'index.html'


# calenders/views.py


class UserProfileDetail(generics.RetrieveUpdateAPIView):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer

class StoryList(generics.ListAPIView):
    serializer_class = StorySerializer

    def get_queryset(self):
        user_profile = UserProfile.objects.get(user=self.request.user)
        return Story.objects.filter(user_profile=user_profile)




def send_story_email(user_email, subject, message):
    send_mail(
        subject,
        message,
        'Joan <akibodejoan@gmail.com>',
        [user_email],
        fail_silently=False,
    )





class DjangoAuthStatusView(APIView):
    @method_decorator(login_required)
    def get(self, request):
        return JsonResponse({'is_authenticated': True}, status=200)

    def handle_no_permission(self):
        return JsonResponse({'is_authenticated': False}, status=200)



class GoogleAuthStatusView(APIView):
    def get(self, request):
        # Check for user authentication and Google credentials
        credentials_data = request.session.get('credentials')
        if credentials_data:
            credentials = Credentials(
                token=credentials_data['token'],
                refresh_token=credentials_data['refresh_token'],
                token_uri=credentials_data['token_uri'],
                client_id=credentials_data['client_id'],
                client_secret=credentials_data['client_secret'],
                scopes=credentials_data['scopes'],
            )

            if credentials.valid:
                return JsonResponse({'is_authenticated': True}, status=200)

        return JsonResponse({'is_authenticated': False}, status=200)





class GenerateStoryView(APIView):
    def post(self, request):
        try:
            # Retrieve events from the POST request body
            events = Event.objects.filter(user=request.user, in_time_window=True, wanted_by_the_user=True).order_by('start')

            if not events:
                return JsonResponse({'error': 'No events provided'}, status=400)

            # Prepare the prompt for ChatGPT
            event_descriptions = "\n".join(
                [f"- Event '{event['summary']}' starting at {event['start']}" for event in events]
            )

            prompt = (
                f"Here are the events for the last week:\n{event_descriptions}\n"
                "Write a detailed and engaging story based on these events. Highlight the significant moments and create an engaging narrative. maximum 100 mots"
            )

            # Ensure your OpenAI API key is set
            openai.api_key = settings.OPENAI_API_KEY

            print("OpenAI API Key:", openai.api_key)  # This should now print your actual API key

            # Call the OpenAI API using the latest SDK syntax
            response = openai.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a creative storyteller."},
                    {"role": "user", "content": prompt}
                ]
            )

                        # Log the entire response from OpenAI for debugging
            print("OpenAI API Response:", response)            # Log the entire response from OpenAI for debugging

            # Extract the generated story
            story = response.choices[0].message.content

            print(story)

            return JsonResponse({"story": story}, status=200)
        
        except Exception as e:
            # Print the error to the console for debugging
            print("Error occurred:", e)
            return JsonResponse({"error": str(e)}, status=500)