# Search configuration

# --------------------------------------------------
# Nearby Search Settings
# --------------------------------------------------

# Initial radius used when searching for nearby places
INITIAL_RADIUS_KM = 10

# Radius increase when not enough places are found
RADIUS_INCREMENT_KM = 10

# Maximum radius allowed for nearby searches
MAX_RADIUS_KM = 100

# Minimum number of places to find before stopping
MIN_RESULTS = 10


# --------------------------------------------------
# Recommendation Score Weights
# --------------------------------------------------

# All weights should add up to 1.0
DISTANCE_WEIGHT = 0.25
RATING_WEIGHT = 0.20
POPULARITY_WEIGHT = 0.15
INTEREST_WEIGHT = 0.20
SEASON_WEIGHT = 0.10
RATING_CONFIDENCE_WEIGHT = 0.10


# --------------------------------------------------
# Recommendation Sorting
# --------------------------------------------------

DEFAULT_SORT = "recommended"

SUPPORTED_SORT_OPTIONS = [
    "recommended",
    "distance",
    "rating",
    "popularity",
]


# --------------------------------------------------
# Recommendation Limits
# --------------------------------------------------

# Maximum number of recommendations displayed
MAX_RECOMMENDATIONS = 10