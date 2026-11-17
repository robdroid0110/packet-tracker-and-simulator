"""Saved metric grid profiles for the map-style Physical Workspace (§22).

Spacing is calibrated through the same container dimensions as cable distances.
Grid presentation never changes placement, carrier state, or radio behaviour.
"""
from __future__ import annotations
import math
import re
from .model import LabError
from .physical_distance import frame_scale

DEFAULT_SPACING = {"intercity":2500.0, "city":100.0, "building":5.0, "generic":1.0}
COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


def defaults():
    return {kind:{"enabled":True,"spacing_m":spacing,"color":"#d4dbe2"}
            for kind,spacing in DEFAULT_SPACING.items()}


def validate_profile(kind, enabled, spacing_m, color):
    if not isinstance(kind,str) or kind not in DEFAULT_SPACING:
        raise LabError("grid type must be intercity, city, building or generic")
    if not isinstance(enabled,bool):raise LabError("grid enabled must be boolean")
    if (isinstance(spacing_m,bool) or not isinstance(spacing_m,(int,float))
            or not math.isfinite(spacing_m) or not 0.01<=spacing_m<=1000000):
        raise LabError("grid spacing must be 0.01..1000000 meters")
    if not isinstance(color,str) or not COLOR.fullmatch(color):
        raise LabError("grid color must be #RRGGBB")
    return {"enabled":enabled,"spacing_m":float(spacing_m),"color":color.lower()}


def set_profile(lab,kind,enabled,spacing_m,color):
    profile=validate_profile(kind,enabled,spacing_m,color)
    lab.physical_grids[kind]=profile


def load_profiles(raw):
    if not isinstance(raw,dict):raise LabError("physical_grids must be an object")
    profiles=defaults()
    for kind,profile in raw.items():
        if not isinstance(profile,dict):raise LabError("invalid saved grid profile")
        profiles[kind]=validate_profile(kind,profile.get("enabled"),
                                       profile.get("spacing_m"),profile.get("color"))
    return profiles


def view(lab,location):
    kind="intercity" if location=="intercity" else lab._physical_location(location)["type"]
    if kind not in DEFAULT_SPACING:
        return {"supported":False,"container_type":kind}
    profile=lab.physical_grids[kind]
    scale=frame_scale(lab,location)
    return {"supported":True,"container_type":kind,**profile,
            "spacing_x_px":profile["spacing_m"]/scale["meters_per_x"],
            "spacing_y_px":profile["spacing_m"]/scale["meters_per_y"],
            "coordinate_system":"container canvas units; origin 0,0",
            "geometry":scale}
