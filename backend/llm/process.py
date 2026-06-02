from openai import OpenAI
from .utils import remove_emojis
import json
import os
from pathlib import Path

env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ.get("OPENAI_API_KEY"),
)

tools = [
    {
        "type": "function",
        "function": {
            "name": "change_destination",
            "description": "Change the navigation destination to a new location the user specifies.",
            "parameters": {
                "type": "object",
                "properties": {
                    "destination": {
                        "type": "string",
                        "description": "The new destination address or place name",
                    }
                },
                "required": ["destination"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_stop",
            "description": "Add a stop to the route based on the user's ask.",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "Keyword phrase to describe the stop",
                    },
                    "location_type": {
                        "type": "string",
                        "enum": [
                            "accounting",
                            "airport",
                            "amusement_park",
                            "aquarium",
                            "art_gallery",
                            "atm",
                            "bakery",
                            "bank",
                            "bar",
                            "beauty_salon",
                            "bicycle_store",
                            "book_store",
                            "bowling_alley",
                            "bus_station",
                            "cafe",
                            "campground",
                            "car_dealer",
                            "car_rental",
                            "car_repair",
                            "car_wash",
                            "casino",
                            "cemetery",
                            "church",
                            "city_hall",
                            "clothing_store",
                            "convenience_store",
                            "courthouse",
                            "dentist",
                            "department_store",
                            "doctor",
                            "drugstore",
                            "electrician",
                            "electronics_store",
                            "embassy",
                            "fire_station",
                            "florist",
                            "funeral_home",
                            "furniture_store",
                            "gas_station",
                            "gym",
                            "hair_care",
                            "hardware_store",
                            "hindu_temple",
                            "home_goods_store",
                            "hospital",
                            "insurance_agency",
                            "jewelry_store",
                            "laundry",
                            "lawyer",
                            "library",
                            "light_rail_station",
                            "liquor_store",
                            "local_government_office",
                            "locksmith",
                            "lodging",
                            "meal_delivery",
                            "meal_takeaway",
                            "mosque",
                            "movie_rental",
                            "movie_theater",
                            "moving_company",
                            "museum",
                            "night_club",
                            "painter",
                            "park",
                            "parking",
                            "pet_store",
                            "pharmacy",
                            "physiotherapist",
                            "plumber",
                            "police",
                            "post_office",
                            "primary_school",
                            "real_estate_agency",
                            "restaurant",
                            "roofing_contractor",
                            "rv_park",
                            "school",
                            "secondary_school",
                            "shoe_store",
                            "shopping_mall",
                            "spa",
                            "stadium",
                            "storage",
                            "store",
                            "subway_station",
                            "supermarket",
                            "synagogue",
                            "taxi_stand",
                            "tourist_attraction",
                            "train_station",
                            "transit_station",
                            "travel_agency",
                            "university",
                            "veterinary_care",
                            "zoo",
                        ],
                        "description": "Type of location",
                    },
                },
                "required": ["keyword", "location_type"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    }
]


def change_destination(destination=None, status=None):
    import requests
    resp = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": destination, "format": "json", "limit": 1},
        headers={"User-Agent": "PassengerPrincess/1.0"},
    )
    results = resp.json()
    if not results:
        return json.dumps({"message": f"Could not find {destination}"})
    place = results[0]
    from api.maps import Location
    status.dest = Location(
        lat=float(place["lat"]),
        lng=float(place["lon"]),
        name=destination,
        address=place["display_name"],
    )
    status.update_status()
    return json.dumps({
        "message": f"Destination changed to {destination}",
        "new_dest": {"lat": float(place["lat"]), "lng": float(place["lon"])},
    })


def add_stop(keyword=None, location_type=None, status=None):
    name, stop_coords = status.add_stop(keyword, location_type)
    return json.dumps({"message": "added stop: " + name, "stop": stop_coords})


tool_dict = {"add_stop": add_stop, "change_destination": change_destination}


def process_user_speech(text: str, status, messages=list):
    messages.append(
        {
            "role": "user",
            "content": [{"type": "text", "text": f"Trip Status: {status.dict()}\n User: {text}"}],
        }
    )
    content = None
    extras = {}  # carries new_dest or stop coords back to caller
    while not content:
        completion = client.chat.completions.create(
            model="openai/gpt-4o-mini", messages=messages, tools=tools
        )
        response_message = completion.choices[0].message
        content = response_message.content
        tool_call = response_message.tool_calls
        print(content, tool_call)
        if tool_call:
            messages.append({"role": "assistant", "tool_calls": tool_call})
            for tc in tool_call:
                resp = tool_dict[tc.function.name](
                    **json.loads(tc.function.arguments), status=status
                )
                try:
                    extras.update(json.loads(resp))
                except Exception:
                    pass
                messages.append({"role": "tool", "content": resp, "tool_call_id": tc.id})
            content = None
    content = remove_emojis(response_message.content)
    messages.append({"role": "assistant", "content": [{"type": "text", "text": content}]})
    return content, messages, status, extras
