"""Fake account scoring from sign up signals. Weights are hand set until enough labelled data exists to train."""
import math
import re


def spam_score(username: str, email: str, bio: str, follows_per_hour: float = 0.0) -> float:
    digits = sum(c.isdigit() for c in username) / max(len(username), 1)
    features = {
        "digit_heavy_username": 1.0 if digits > 0.5 else 0.0,
        "random_looking": 1.0 if re.search(r"[bcdfghjklmnpqrstvwxz]{6,}", username.lower()) else 0.0,
        "link_in_bio": 1.0 if "http" in bio.lower() else 0.0,
        "disposable_email": 1.0 if email.split("@")[-1].lower() in {"mailinator.com", "guerrillamail.com"} else 0.0,
        "follow_burst": min(follows_per_hour / 100.0, 1.0),
    }
    weights = {
        "digit_heavy_username": 1.2, "random_looking": 1.0, "link_in_bio": 0.5, "disposable_email": 2.0, "follow_burst": 2.5,
    }
    z = -3.0 + sum(weights[k] * v for k, v in features.items())
    return round(1 / (1 + math.exp(-z)), 4)
