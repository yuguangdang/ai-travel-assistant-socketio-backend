import os
import requests
from dotenv import load_dotenv

load_dotenv()

cancellation_url = os.getenv("CANCELLATION_URL")


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
        res = requests.post(cancellation_url, json=data)
        itinerary = res.text
        print(f"itinerary: {itinerary}")
        return itinerary
    except requests.RequestException as e:
        print(f"Error fetching itinerary: {e}")
        return None
