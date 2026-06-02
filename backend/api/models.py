from pydantic import BaseModel
from typing import List, Optional
from .maps import (
    get_directions, get_all_route_steps, get_route_summary,
    create_route_with_stop, Location, Step, extract_turn_landmarks,
)


class TripStatus(BaseModel):
    start: Location
    dest: Location
    curr: Location
    duration: str
    distance: str
    route: Optional[List[Step]] = []
    landmarks: Optional[List[Location]] = []

    def model_post_init(self, _):
        directions = get_directions(self.start, self.dest)
        summary = get_route_summary(directions)
        self.duration = summary["duration"]
        self.distance = summary["distance"]
        self.route = get_all_route_steps(directions)
        self.route.reverse()

    def check_route_instruction(self):
        if not self.route:
            return None
        if self.curr == self.route[0].start_location:
            step = self.route.pop(0)
            return step.instructions
        return None

    def update_status(self):
        directions = get_directions(self.curr, self.dest)
        summary = get_route_summary(directions)
        self.duration = summary["duration"]
        self.distance = summary["distance"]
        self.route = get_all_route_steps(directions)

    def add_stop(self, keyword, location_type):
        directions, stop_name, stop_location = create_route_with_stop(
            self.curr, self.dest, keyword, location_type
        )
        summary = get_route_summary(directions)
        self.duration = summary["duration"]
        self.distance = summary["distance"]
        self.route = get_all_route_steps(directions)
        stop_coords = {"lat": stop_location.lat, "lng": stop_location.lng} if stop_location else None
        return stop_name, stop_coords
