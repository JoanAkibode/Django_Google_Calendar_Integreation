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
from datetime import datetime, timedelta
from django.views.generic import TemplateView
from django.http import JsonResponse
from google.oauth2.credentials import Credentials

from django.contrib.auth.models import User
from .models import UserProfile

from rest_framework import generics
from .models import UserProfile, Story
from .serializers import UserProfileSerializer, StorySerializer

from django.core.mail import send_mail

import openai

from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response


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
        

class GoogleCalendarEventsView(APIView):
    def get(self, request):
        # Check for user authentication and credentials
        credentials_data = request.session.get('credentials')
        if not credentials_data:
            return JsonResponse({'error': 'User not authenticated.'}, status=401)

        # Set up Google OAuth credentials
        credentials = Credentials(
            token=credentials_data['token'],
            refresh_token=credentials_data['refresh_token'],
            token_uri=credentials_data['token_uri'],
            client_id=credentials_data['client_id'],
            client_secret=credentials_data['client_secret'],
            scopes=credentials_data['scopes']
        )

        # Initialize Google Calendar API service
        service = build('calendar', 'v3', credentials=credentials)
        
        # Fetch events from the past week
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        seven_days_ago_rfc3339 = seven_days_ago.isoformat() + 'Z'
        try:
            events_result = service.events().list(
                calendarId='primary',
                maxResults=request.GET.get('maxResults', 50),  # Allows specifying maxResults via query parameters
                singleEvents=True,
                orderBy='startTime',
                timeMin=seven_days_ago_rfc3339
            ).execute()
        except Exception as e:
            return JsonResponse({'error': f'Failed to fetch events: {str(e)}'}, status=500)

        events = events_result.get('items', [])
        
        # Create a list of events data
        events_data = [
            {'summary': event.get('summary', 'No title'), 'start': event['start'].get('dateTime', event['start'].get('date'))}
            for event in events
        ]

        # Return the events in a standardized response
        return JsonResponse({"events": events_data}, status=200)

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

            # Ensure user profile exists (signal should handle this automatically)
            UserProfile.objects.get_or_create(user=user)

            # Redirect the user
            return HttpResponseRedirect('/')
        except Exception as e:
            return Response({'error': str(e)}, status=500)


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




class GenerateStoryView(APIView):
    def post(self, request):
        try:
            # Retrieve events from the POST request body
            events = request.data.get('events', [])
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