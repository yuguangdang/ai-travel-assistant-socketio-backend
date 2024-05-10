import os
import requests
from dotenv import load_dotenv

load_dotenv()

CANCELLATION_URL = os.getenv("CANCELLATION_URL")


def get_itinerary(pnr):
    """
    Retrieve the itinerary based on the PNR.

    Parameters:
    pnr (str): The Passenger Name Record identifier.

    Returns:
    dict: A dictionary containing the itinerary details, or None if an error occurs.
    """
    data = {
        "PNR": pnr,
        "LASTNAME": "test_lastname",
        "USER_ROLE": "traveller",
        "EMAIL": "test_email@example.com",
        "DEBTORID": "CTMZZZZZZZ",
        "OFFICE": "test_office",
        "INTENT": "check_if_cancel_possible",
    }

    try:
        res = requests.post(CANCELLATION_URL, json=data)
        itinerary = res.text
        print(f"itinerary: {itinerary}")
        return itinerary
    except requests.RequestException as e:
        print(f"Error fetching itinerary: {e}")
        return None

def flight_schedule(departure_airport, arrival_airport, year, month, day):
    # API endpoint
    url = f"https://api.flightstats.com/flex/schedules/rest/v1/json/from/{departure_airport}/to/{arrival_airport}/departing/{year}/{month}/{day}"
    
    # API credentials (replace with your actual appId and appKey)
    params = {
        'appId': '38d3993c',
        'appKey': 'b26e24febea74f8426496d989190874c'
    }
    
    # Make the API request
    response = requests.get(url, params=params)
    
    # Check if the request was successful
    if response.status_code == 200:
        # Return the JSON data
        return response.json()
    else:
        # Return the error status and message if something went wrong
        return {'error': response.status_code, 'message': 'Failed to retrieve data'}
