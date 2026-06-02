import googlemaps
import math
from pydantic import BaseModel
from typing import Optional
import os
import re
from pathlib import Path

_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        if "=" in _line and not _line.startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

gmap = googlemaps.Client(key=os.environ.get("GMAPS_API_KEY"))


class Location(BaseModel):
    lat: float
    lng: float
    name: Optional[str] = None
    address: Optional[str] = None

    def __eq__(self, other):
        if not isinstance(other, Location):
            return NotImplemented
        return round(self.lat, 5) == round(other.lat, 5) and round(self.lng, 5) == round(other.lng, 5)

    def __hash__(self):
        return hash((round(self.lat, 5), round(self.lng, 5)))


class Step(BaseModel):
    start_location: Location
    end_location: Location
    distance: str
    instructions: str
    action: Optional[str] = None


def get_directions(start: Location, end: Location, waypoints: list = []):
    result = gmap.directions(
        origin=(start.lat, start.lng),
        destination=(end.lat, end.lng),
        mode="driving",
        alternatives=False,
        waypoints=[(w.lat, w.lng) for w in waypoints] if waypoints else [],
        traffic_model="best_guess",
        departure_time="now",
    )
    return result[0]


def get_leg_steps(leg):
    steps = []
    for step in leg["steps"]:
        s = Step(
            start_location=Location(lat=step["start_location"]["lat"], lng=step["start_location"]["lng"]),
            end_location=Location(lat=step["end_location"]["lat"], lng=step["end_location"]["lng"]),
            distance=step["distance"]["text"],
            instructions=re.sub(r"<[^>]+>", "", step["html_instructions"]),
        )
        if "maneuver" in step:
            s.action = step["maneuver"]
        steps.append(s)
    return steps


def get_all_route_steps(route):
    steps = []
    for leg in route["legs"]:
        steps.extend(get_leg_steps(leg))
    return steps


def get_route_summary(route):
    leg = route["legs"][0]
    duration = leg.get("duration_in_traffic", leg["duration"])
    return {"duration": duration["text"], "distance": leg["distance"]["text"]}


def create_route_with_stop(start, end, keyword, location_type):
    results = gmap.places_nearby(
        location=(start.lat, start.lng),
        keyword=keyword,
        rank_by="distance",
        type=location_type,
    )
    if not results.get("results"):
        return get_directions(start, end), "your destination", None
    place = results["results"][0]
    loc = place["geometry"]["location"]
    stop = Location(lat=loc["lat"], lng=loc["lng"], name=place["name"])
    route = get_directions(start, end, waypoints=[stop])
    return route, place["name"], stop


def calculate_bearing(start_location, end_location):
    d_lon = end_location.lng - start_location.lng
    y = math.sin(d_lon) * math.cos(start_location.lat)
    x = math.cos(start_location.lat) * math.sin(end_location.lat) - math.sin(
        start_location.lat) * math.cos(end_location.lat) * math.cos(d_lon)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def calculate_relative_bearing(old_bearing, new_bearing):
    return (old_bearing - new_bearing + 360) % 360


def distance(loc1, loc2):
    lat1, lon1 = math.radians(loc1.lat), math.radians(loc1.lng)
    lat2, lon2 = math.radians(loc2.lat), math.radians(loc2.lng)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    return 6371000 * 2 * math.asin(math.sqrt(a))


def get_turn_direction(instruction):
    return "Right" if re.search(r'right', instruction, re.IGNORECASE) else "Left"


def extract_turn_landmarks(route_steps):
    return route_steps
