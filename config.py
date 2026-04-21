HOTEL = {
    "name": "BuPlace Hotel",
    "location": "Bangkok, Thailand",
    "website": "buplace.com",
    "days_ahead": 180,
    "currency": "THB",
    "rooms": {
        "Studio": {"floor": 800,  "base": 1000, "ceiling": 3000},
        "Family": {"floor": 1500, "base": 1900, "ceiling": 5700},
    },
}

# Customer segment weights (must sum to 1.0)
# Used to explain demand drivers in comments/tooltips
SEGMENTS = {
    "thai_domestic": 0.30,  # Thai travelers from upcountry
    "thai_couple":   0.20,  # Thai couples (incl. with farang partner)
    "chinese":       0.20,  # Chinese tourists
    "asian":         0.15,  # Other Asian tourists (JP, KR, SG, MY, etc.)
    "european":      0.15,  # European + Western tourists
}
