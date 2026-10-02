from services.data_quality import canonicalize_district, is_tamil_nadu_district, is_educational_place
from config.districts import TN_DISTRICTS

from database.connection import (
    fetch_all,
    fetch_one,
    execute_query,
)


# ============================================================
# COMMON HELPERS
# ============================================================

def _safe_limit(limit, default=10):
    """
    Convert limit into a safe positive integer.
    """
    try:
        limit = int(limit)
        if limit <= 0:
            return default
        return limit
    except (TypeError, ValueError):
        return default


# ============================================================
# LIVE UPDATE / CURRENT STATUS QUERIES
# ============================================================

def get_or_create_source(source_name, source_url=None, source_type="web"):
    """Return a traceable source record, creating it when necessary."""
    row = fetch_one(
        "SELECT source_id FROM sources WHERE source_name = ? AND COALESCE(source_url, '') = COALESCE(?, '') LIMIT 1",
        (source_name, source_url),
    )
    if row:
        return row["source_id"]
    return execute_query(
        """INSERT INTO sources (source_name, source_url, source_type, collection_method, last_checked)
           VALUES (?, ?, ?, 'automated update', CURRENT_TIMESTAMP)""",
        (source_name, source_url, source_type),
    )


def upsert_tourism_place(place, source_id=None):
    """Insert or refresh a place discovered by an approved source.

    Uses the same matching (Wikidata/OSM id, then district + normalised
    name) and provenance tracking as the bulk refresh pipeline.
    """
    from database.ingest import Ingestor

    name = str(place.get("place_name", "")).strip()
    district = canonicalize_district(place.get("district"))
    if not name or not district or not is_tamil_nadu_district(district):
        return None
    if is_educational_place(place):
        return None
    record = {**place, "place_name": name, "district": district, "source_id": source_id,
              "sources": [(source_id, place.get("source_url") or "")] if source_id else []}
    with Ingestor() as ingestor:
        place_id, _ = ingestor.upsert_place(record)
    return place_id


def get_latest_place_status(place_id):
    return fetch_one(
        "SELECT * FROM place_status WHERE place_id = ? ORDER BY checked_at DESC, status_id DESC LIMIT 1",
        (place_id,),
    )


def upsert_place_status(place_id, status, suitability_score=1.0, details="", source_id=None,
                        source_url=None, expires_at=None):
    return execute_query(
        """INSERT INTO place_status
           (place_id, status, suitability_score, details, source_id, source_url, expires_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (place_id, status, suitability_score, details, source_id, source_url, expires_at),
    )


def record_search_history(query_location, latitude=None, longitude=None, initial_radius=None,
                          final_radius=None, places_found=0):
    return execute_query(
        """INSERT INTO search_history
           (query_location, latitude, longitude, initial_radius, final_radius, places_found)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (query_location, latitude, longitude, initial_radius, final_radius, places_found),
    )


# ============================================================
# CATEGORY QUERIES
# ============================================================

def get_categories():
    """
    Return all tourism categories.
    """

    query = """
        SELECT
            category_id,
            category_name,
            description
        FROM categories
        ORDER BY category_name
    """

    return fetch_all(query)


def get_all_categories():
    """
    Alias for get_categories().
    """

    return get_categories()


def get_category_by_id(category_id):
    """
    Return one category by ID.
    """

    query = """
        SELECT
            category_id,
            category_name,
            description
        FROM categories
        WHERE category_id = ?
    """

    return fetch_one(
        query,
        (category_id,),
    )


def get_category_by_name(category_name):
    """
    Return one category by name.
    """

    if not category_name:
        return None

    query = """
        SELECT
            category_id,
            category_name,
            description
        FROM categories
        WHERE LOWER(category_name) = LOWER(?)
        LIMIT 1
    """

    return fetch_one(
        query,
        (str(category_name).strip(),),
    )


# ============================================================
# COMMON PLACE SELECT
# ============================================================

PLACE_SELECT = """
    SELECT
        p.place_id,
        p.place_name,
        p.district,
        p.city_town,
        p.city_town AS city,
        p.state,
        p.category_id,

        c.category_name,

        p.subcategory,
        p.description,

        p.latitude,
        p.longitude,
        p.location_precision,

        p.address,

        p.opening_time,
        p.closing_time,
        p.opening_days,

        p.avg_visit_duration,
        p.entry_fee,

        p.best_season,

        p.popularity_score,
        p.tourism_relevance,

        p.verified,
        p.source_id,

        p.created_at,
        p.updated_at,

        COALESCE(r.rating, 0) AS rating,
        COALESCE(r.rating_count, 0) AS rating_count,

        COALESCE(
            r.rating *
            (
                CAST(r.rating_count AS REAL)
                /
                NULLIF(r.rating_count + 10, 0)
            ),
            0
        ) AS weighted_rating,

        (
            SELECT i.image_url
            FROM images i
            WHERE i.place_id = p.place_id
            ORDER BY
                i.is_primary DESC,
                i.image_id ASC
            LIMIT 1
        ) AS image_url

    FROM places p

    LEFT JOIN categories c
        ON p.category_id = c.category_id

    LEFT JOIN (
        SELECT
            place_id,
            AVG(rating) AS rating,
            SUM(
                COALESCE(rating_count, 0)
            ) AS rating_count
        FROM ratings
        GROUP BY place_id
    ) r
        ON p.place_id = r.place_id
"""


# ============================================================
# PLACE QUERIES
# ============================================================

def get_all_places(limit=None):
    """
    Return tourist places.

    If limit is None:
        return all places.

    If limit is provided:
        return only that many places.
    """

    if limit is None:

        query = (
            PLACE_SELECT
            + """
            ORDER BY
                p.popularity_score DESC,
                weighted_rating DESC,
                p.place_name
            """
        )

        return fetch_all(query)

    limit = _safe_limit(limit)

    query = (
        PLACE_SELECT
        + """
        ORDER BY
            p.popularity_score DESC,
            weighted_rating DESC,
            p.place_name
        LIMIT ?
        """
    )

    return fetch_all(
        query,
        (limit,),
    )


def get_place_by_id(place_id):
    """
    Return one tourist place by ID.
    """

    query = (
        PLACE_SELECT
        + """
        WHERE p.place_id = ?
        LIMIT 1
        """
    )

    return fetch_one(
        query,
        (place_id,),
    )


def get_place_by_name(place_name):
    """
    Return one tourist place by exact name.
    """

    if not place_name:
        return None

    query = (
        PLACE_SELECT
        + """
        WHERE LOWER(p.place_name) = LOWER(?)
        LIMIT 1
        """
    )

    return fetch_one(
        query,
        (str(place_name).strip(),),
    )


# ============================================================
# SEARCH PLACES
# ============================================================

def search_places(
    search_query=None,
    search_text=None,
    category_id=None,
    limit=50,
):
    """
    Search tourist places.

    Compatible with both:

        search_places("Marina")

    and:

        search_places(
            search_text="Marina",
            limit=10
        )

    Searches:
        - place name
        - district
        - city/town
        - state
        - subcategory
        - description
        - address
        - category
    """

    # --------------------------------------------------------
    # COMPATIBILITY
    # --------------------------------------------------------

    if search_text is not None:
        search_query = search_text

    search_query = str(
        search_query or ""
    ).strip()

    limit = _safe_limit(limit, 50)

    # --------------------------------------------------------
    # BUILD CONDITIONS
    # --------------------------------------------------------

    conditions = []
    parameters = []

    if search_query:

        pattern = f"%{search_query}%"

        conditions.append(
            """
            (
                LOWER(p.place_name) LIKE LOWER(?)
                OR LOWER(COALESCE(p.city_town, '')) LIKE LOWER(?)
                OR LOWER(COALESCE(p.district, '')) LIKE LOWER(?)
                OR LOWER(COALESCE(p.state, '')) LIKE LOWER(?)
                OR LOWER(COALESCE(p.subcategory, '')) LIKE LOWER(?)
                OR LOWER(COALESCE(p.description, '')) LIKE LOWER(?)
                OR LOWER(COALESCE(p.address, '')) LIKE LOWER(?)
                OR LOWER(COALESCE(c.category_name, '')) LIKE LOWER(?)
            )
            """
        )

        parameters.extend(
            [
                pattern,
                pattern,
                pattern,
                pattern,
                pattern,
                pattern,
                pattern,
                pattern,
            ]
        )

    # --------------------------------------------------------
    # CATEGORY FILTER
    # --------------------------------------------------------

    if category_id is not None:

        conditions.append(
            "p.category_id = ?"
        )

        parameters.append(
            category_id
        )

    # --------------------------------------------------------
    # QUERY
    # --------------------------------------------------------

    query = PLACE_SELECT

    if conditions:

        query += """
            WHERE
        """

        query += " AND ".join(
            conditions
        )

    # --------------------------------------------------------
    # RANKING
    # --------------------------------------------------------

    if search_query:

        query += """
            ORDER BY
                CASE
                    WHEN LOWER(p.place_name)
                         = LOWER(?)
                    THEN 1

                    WHEN LOWER(p.place_name)
                         LIKE LOWER(?)
                    THEN 2

                    WHEN LOWER(p.city_town)
                         LIKE LOWER(?)
                    THEN 3

                    ELSE 4
                END,

                p.popularity_score DESC,
                weighted_rating DESC,
                p.place_name

            LIMIT ?
        """

        parameters.extend(
            [
                search_query,
                f"{search_query}%",
                f"%{search_query}%",
                limit,
            ]
        )

    else:

        query += """
            ORDER BY
                p.popularity_score DESC,
                weighted_rating DESC,
                p.place_name

            LIMIT ?
        """

        parameters.append(
            limit
        )

    return fetch_all(
        query,
        tuple(parameters),
    )


# ============================================================
# CATEGORY / LOCATION FILTERS
# ============================================================

def get_places_by_category(
    category_name
):
    """
    Return places belonging to a category.
    """

    if not category_name:
        return []

    query = (
        PLACE_SELECT
        + """
        WHERE
            LOWER(c.category_name)
            = LOWER(?)

        ORDER BY
            p.popularity_score DESC,
            weighted_rating DESC,
            p.place_name
        """
    )

    return fetch_all(
        query,
        (category_name,),
    )


def get_places_by_district(
    district
):
    """
    Return places in a district.
    """

    if not district:
        return []

    query = (
        PLACE_SELECT
        + """
        WHERE
            LOWER(p.district)
            = LOWER(?)

        ORDER BY
            p.popularity_score DESC,
            weighted_rating DESC,
            p.place_name
        """
    )

    return fetch_all(
        query,
        (district,),
    )


def get_places_by_city(
    city
):
    """
    Return places in a city/town.

    IMPORTANT:
    Database column = city_town
    """

    if not city:
        return []

    query = (
        PLACE_SELECT
        + """
        WHERE
            LOWER(p.city_town)
            = LOWER(?)

        ORDER BY
            p.popularity_score DESC,
            weighted_rating DESC,
            p.place_name
        """
    )

    return fetch_all(
        query,
        (city,),
    )


def get_places_by_state(
    state="Tamil Nadu"
):
    """
    Return places belonging to a state.
    """

    query = (
        PLACE_SELECT
        + """
        WHERE
            LOWER(p.state)
            = LOWER(?)

        ORDER BY
            p.popularity_score DESC,
            weighted_rating DESC,
            p.place_name
        """
    )

    return fetch_all(
        query,
        (state,),
    )


# ============================================================
# POPULAR PLACES
# ============================================================

def get_popular_places(
    limit=10
):
    """
    Return popular tourist destinations.
    """

    limit = _safe_limit(limit)

    query = (
        PLACE_SELECT
        + """
        ORDER BY
            p.popularity_score DESC,
            weighted_rating DESC,
            p.place_name

        LIMIT ?
        """
    )

    return fetch_all(
        query,
        (limit,),
    )


# ============================================================
# TOP RATED PLACES
# ============================================================

def get_top_rated_places(
    limit=10
):
    """
    Return highest-rated tourist destinations.
    """

    limit = _safe_limit(limit)

    query = (
        PLACE_SELECT
        + """
        WHERE
            COALESCE(rating_count, 0) > 0

        ORDER BY
            weighted_rating DESC,
            rating DESC,
            rating_count DESC,
            p.popularity_score DESC

        LIMIT ?
        """
    )

    return fetch_all(
        query,
        (limit,),
    )


# ============================================================
# RECOMMENDATIONS
# ============================================================

def get_recommendations(
    category_name=None,
    interests=None,
    limit=10,
):
    """
    Return tourism recommendations.

    Ranking uses:
        1. Interest/category match
        2. Tourism relevance
        3. Popularity
        4. Weighted rating
    """

    limit = _safe_limit(limit)

    conditions = []
    parameters = []

    interest_values = []

    if interests:

        if isinstance(
            interests,
            str
        ):
            interest_values = [
                x.strip()
                for x in interests.split(",")
                if x.strip()
            ]

        elif isinstance(
            interests,
            (list, tuple, set)
        ):
            interest_values = [
                str(x).strip()
                for x in interests
                if str(x).strip()
            ]

    if category_name:

        conditions.append(
            """
            LOWER(c.category_name)
            = LOWER(?)
            """
        )

        parameters.append(
            category_name
        )

    query = (
        PLACE_SELECT
    )

    if conditions:

        query += """
            WHERE
        """

        query += " AND ".join(
            conditions
        )

    # --------------------------------------------------------
    # INTEREST SCORING
    # --------------------------------------------------------

    interest_cases = []

    for interest in interest_values:

        pattern = f"%{interest}%"

        interest_cases.append(
            """
            CASE
                WHEN LOWER(COALESCE(
                    c.category_name, ''
                )) LIKE LOWER(?)
                OR LOWER(COALESCE(
                    p.subcategory, ''
                )) LIKE LOWER(?)
                OR LOWER(COALESCE(
                    p.description, ''
                )) LIKE LOWER(?)
                THEN 1
                ELSE 0
            END
            """
        )

        parameters.extend(
            [
                pattern,
                pattern,
                pattern,
            ]
        )

    if interest_cases:

        interest_score = " + ".join(
            interest_cases
        )

        query += f"""
            ORDER BY
                ({interest_score}) DESC,
                p.tourism_relevance DESC,
                p.popularity_score DESC,
                weighted_rating DESC,
                p.place_name
        """

    else:

        query += """
            ORDER BY
                p.tourism_relevance DESC,
                p.popularity_score DESC,
                weighted_rating DESC,
                p.place_name
        """

    query += """
        LIMIT ?
    """

    parameters.append(
        limit
    )

    return fetch_all(
        query,
        tuple(parameters),
    )


# ============================================================
# PLACE IMAGES
# ============================================================

def get_place_images(
    place_id
):
    """
    Return all images belonging to a place.
    """

    query = """
        SELECT
            image_id,
            place_id,
            image_url,
            image_source,
            image_license,
            image_author,
            is_primary,
            source_id
        FROM images
        WHERE place_id = ?
        ORDER BY
            is_primary DESC,
            image_id ASC
    """

    return fetch_all(
        query,
        (place_id,),
    )


def find_places(district=None, category_name=None, name_like=None, limit=8):
    """Most prominent places matching an optional district, category and name."""
    conditions, parameters = [], []
    if district:
        conditions.append("p.district = ?")
        parameters.append(district)
    if category_name:
        conditions.append("c.category_name = ?")
        parameters.append(category_name)
    if name_like:
        conditions.append("LOWER(p.place_name) LIKE LOWER(?)")
        parameters.append(f"%{name_like}%")
    query = PLACE_SELECT
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY p.popularity_score DESC, p.place_name LIMIT ?"
    parameters.append(_safe_limit(limit, 8))
    return fetch_all(query, tuple(parameters))


def get_place_sources(place_id):
    """Sources that list a place, with the page each one published it on."""
    return fetch_all(
        """SELECT s.source_name, s.license, ps.source_url, ps.last_seen
           FROM place_sources ps
           JOIN sources s ON s.source_id = ps.source_id
           WHERE ps.place_id = ?
           ORDER BY s.source_id""",
        (place_id,),
    )


def get_festivals_for_place(place_id, district):
    """Festivals linked to the place, held in its district, or statewide.

    Ordered by relevance (place, then district, then statewide) and then by
    the month they fall in.
    """
    return fetch_all(
        """SELECT f.*,
                  CASE WHEN f.associated_place_id = ? THEN 0
                       WHEN f.district = ? THEN 1 ELSE 2 END AS relevance
           FROM festivals f
           WHERE f.associated_place_id = ? OR f.district = ? OR f.district IS NULL
           ORDER BY relevance, COALESCE(f.month, CAST(SUBSTR(f.start_date, 6, 2) AS INTEGER), 13),
                    f.start_date, f.festival_name""",
        (place_id, district, place_id, district),
    )


def get_primary_image(
    place_id
):
    """
    Return the primary image URL for a place.
    """

    query = """
        SELECT
            image_url
        FROM images
        WHERE
            place_id = ?
        ORDER BY
            is_primary DESC,
            image_id ASC
        LIMIT 1
    """

    row = fetch_one(
        query,
        (place_id,),
    )

    if row:
        return row["image_url"]

    return None


# ============================================================
# RATINGS
# ============================================================

def get_place_ratings(
    place_id
):
    """
    Return rating records for a place.
    """

    query = """
        SELECT
            rating_id,
            place_id,
            rating,
            rating_count,
            rating_source,
            rating_date,
            review,
            source_id
        FROM ratings
        WHERE place_id = ?
        ORDER BY rating_date DESC
    """

    return fetch_all(
        query,
        (place_id,),
    )


def add_place_rating(place_id, rating, review=None):
    """Store one traveller's 1-5 star rating (and optional short review)."""
    rating = int(rating)
    if not 1 <= rating <= 5:
        raise ValueError("rating must be between 1 and 5")
    review = (str(review or "").strip()[:500]) or None
    execute_query(
        """INSERT INTO ratings (place_id, rating, rating_count, rating_source, rating_date, review)
           VALUES (?, ?, 1, 'Traveller rating (this app)', CURRENT_TIMESTAMP, ?)""",
        (place_id, rating, review),
    )


# ============================================================
# FESTIVALS
# ============================================================

def get_place_festivals(
    place_id
):
    """
    Return festivals associated with a place.
    """

    query = """
        SELECT
            festival_id,
            festival_name,
            district,
            associated_place_id,
            start_date,
            end_date,
            month,
            festival_type,
            importance,
            expected_tourism_impact,
            source_id
        FROM festivals
        WHERE associated_place_id = ?
        ORDER BY
            start_date
    """

    return fetch_all(
        query,
        (place_id,),
    )


def get_all_festivals():
    """
    Return all festivals.
    """

    query = """
        SELECT
            f.*,
            p.place_name
        FROM festivals f

        LEFT JOIN places p
            ON f.associated_place_id = p.place_id

        ORDER BY
            f.start_date,
            f.festival_name
    """

    return fetch_all(query)


def search_festivals(
    search_query
):
    """
    Search festivals.
    """

    if not search_query:
        return get_all_festivals()

    pattern = (
        f"%{str(search_query).strip()}%"
    )

    query = """
        SELECT
            f.*,
            p.place_name
        FROM festivals f

        LEFT JOIN places p
            ON f.associated_place_id = p.place_id

        WHERE
            LOWER(f.festival_name)
                LIKE LOWER(?)

            OR LOWER(
                COALESCE(
                    f.district,
                    ''
                )
            ) LIKE LOWER(?)

            OR LOWER(
                COALESCE(
                    f.festival_type,
                    ''
                )
            ) LIKE LOWER(?)

        ORDER BY
            f.start_date
    """

    return fetch_all(
        query,
        (
            pattern,
            pattern,
            pattern,
        ),
    )


# ============================================================
# HOLIDAYS
# ============================================================

def get_holidays():
    """
    Return all holidays.
    """

    query = """
        SELECT
            holiday_id,
            holiday_name,
            date,
            year,
            applicability,
            holiday_type,
            source_id
        FROM holidays
        ORDER BY
            date
    """

    return fetch_all(query)


def get_all_holidays():
    """
    Alias for get_holidays().
    """

    return get_holidays()


def search_holidays(
    search_query
):
    """
    Search holidays by name/type/applicability.
    """

    if not search_query:
        return get_holidays()

    pattern = (
        f"%{str(search_query).strip()}%"
    )

    query = """
        SELECT
            holiday_id,
            holiday_name,
            date,
            year,
            applicability,
            holiday_type,
            source_id
        FROM holidays
        WHERE
            LOWER(holiday_name)
                LIKE LOWER(?)

            OR LOWER(
                COALESCE(
                    applicability,
                    ''
                )
            ) LIKE LOWER(?)

            OR LOWER(
                COALESCE(
                    holiday_type,
                    ''
                )
            ) LIKE LOWER(?)

        ORDER BY
            date
    """

    return fetch_all(
        query,
        (
            pattern,
            pattern,
            pattern,
        ),
    )


# ============================================================
# CROWD DATA
# ============================================================

def get_crowd_data(
    place_id
):
    """
    Return historical crowd data for a place.
    """

    query = """
        SELECT
            crowd_id,
            place_id,
            date,
            month,
            season,
            day_type,
            holiday_flag,
            festival_flag,
            festival_importance,
            tourism_period,
            historical_signal,
            crowd_level,
            source_id
        FROM crowd_data
        WHERE place_id = ?
        ORDER BY
            date DESC
    """

    return fetch_all(
        query,
        (place_id,),
    )


def get_latest_crowd_data(
    place_id
):
    """
    Return the latest crowd record.
    """

    query = """
        SELECT
            *
        FROM crowd_data
        WHERE place_id = ?
        ORDER BY
            date DESC
        LIMIT 1
    """

    return fetch_one(
        query,
        (place_id,),
    )


# ============================================================
# SEARCH HISTORY
# ============================================================

def add_search_history(
    search_query
):
    """
    Store a search query.
    """

    if not search_query:
        return None

    query = """
        INSERT INTO search_history (
            search_query
        )
        VALUES (?)
    """

    return execute_query(
        query,
        (
            str(search_query).strip(),
        ),
    )


def get_search_history(
    limit=20
):
    """
    Return recent search history.
    """

    limit = _safe_limit(
        limit,
        20
    )

    query = """
        SELECT
            search_id,
            search_query,
            searched_at
        FROM search_history
        ORDER BY
            searched_at DESC
        LIMIT ?
    """

    return fetch_all(
        query,
        (limit,),
    )


# ============================================================
# USER PREFERENCES
# ============================================================

def get_user_preferences(
    user_id
):
    """
    Return user preferences.
    """

    query = """
        SELECT
            user_id,
            interests,
            preferred_budget,
            preferred_crowd_level,
            preferred_distance,
            created_at
        FROM user_preferences
        WHERE user_id = ?
    """

    return fetch_one(
        query,
        (user_id,),
    )


def save_user_preferences(
    interests=None,
    preferred_budget=None,
    preferred_crowd_level=None,
    preferred_distance=None,
    user_id=None,
):
    """
    Create or update user preferences.
    """

    if user_id is None:

        query = """
            INSERT INTO user_preferences (
                interests,
                preferred_budget,
                preferred_crowd_level,
                preferred_distance
            )
            VALUES (?, ?, ?, ?)
        """

        return execute_query(
            query,
            (
                interests,
                preferred_budget,
                preferred_crowd_level,
                preferred_distance,
            ),
        )

    query = """
        UPDATE user_preferences
        SET
            interests = ?,
            preferred_budget = ?,
            preferred_crowd_level = ?,
            preferred_distance = ?
        WHERE user_id = ?
    """

    execute_query(
        query,
        (
            interests,
            preferred_budget,
            preferred_crowd_level,
            preferred_distance,
            user_id,
        ),
    )

    return user_id


# ============================================================
# SOURCES
# ============================================================

def get_sources():
    """
    Return tourism data sources.
    """

    query = """
        SELECT
            source_id,
            source_name,
            source_url,
            description
        FROM sources
        ORDER BY
            source_name
    """

    return fetch_all(query)


# ============================================================
# PLACE FEATURES
# ============================================================

def get_place_features(
    place_id
):
    """
    Return features associated with a place.
    """

    query = """
        SELECT
            feature_id,
            place_id,
            feature_name,
            feature_value
        FROM place_features
        WHERE place_id = ?
        ORDER BY
            feature_name
    """

    return fetch_all(
        query,
        (place_id,),
    )


# ============================================================
# DISTRICTS
# ============================================================

def get_districts():
    """
    Return unique districts.
    """

    # Return the authoritative 38-district list even when a district currently
    # has zero collected places.  This prevents the UI from silently dropping
    # South Tamil Nadu districts simply because the database is not populated yet.
    rows = []
    for district in TN_DISTRICTS:
        rows.append({"district": district})
    return rows


# ============================================================
# CITIES
# ============================================================

def get_cities():
    """
    Return unique cities/towns.
    """

    query = """
        SELECT DISTINCT
            city_town AS city
        FROM places
        WHERE
            city_town IS NOT NULL
            AND TRIM(city_town) != ''
        ORDER BY
            city_town
    """

    return fetch_all(query)


# ============================================================
# CHATBOT SEARCH
# ============================================================

def chatbot_search(
    message,
    limit=10
):
    """
    Search the tourism database using
    a chatbot message.

    This is a database-backed chatbot search,
    not an external AI API.

    Example:

        "places in Madurai"

        "Marina Beach"

        "temples in Coimbatore"
    """

    if not message:
        return []

    message = str(
        message
    ).strip()

    if not message:
        return []

    limit = _safe_limit(limit)

    # --------------------------------------------------------
    # FIRST: SEARCH COMPLETE MESSAGE
    # --------------------------------------------------------

    results = search_places(
        search_text=message,
        limit=limit,
    )

    if results:
        return results

    # --------------------------------------------------------
    # SECOND: SEARCH IMPORTANT WORDS
    # --------------------------------------------------------

    stop_words = {
        "the",
        "a",
        "an",
        "in",
        "near",
        "nearby",
        "place",
        "places",
        "tourist",
        "tourism",
        "visit",
        "visiting",
        "show",
        "me",
        "give",
        "some",
        "best",
        "good",
        "for",
        "to",
        "of",
        "is",
        "are",
        "what",
        "where",
        "which",
        "can",
        "i",
        "want",
        "tell",
        "about",
        "please",
    }

    words = [
        word.strip(
            ".,!?;:()[]{}"
        )
        for word in message.lower().split()
    ]

    words = [
        word
        for word in words
        if len(word) >= 3
        and word not in stop_words
    ]

    if not words:
        return []

    # Search each meaningful word
    # and remove duplicate place IDs.
    collected = {}

    for word in words:

        matches = search_places(
            search_text=word,
            limit=limit,
        )

        for row in matches:

            place_id = row["place_id"]

            if place_id not in collected:
                collected[place_id] = row

    return list(
        collected.values()
    )[:limit]


# ============================================================
# DATABASE COUNTS
# ============================================================

def get_place_count():
    """
    Return number of tourist places.
    """

    row = fetch_one(
        "SELECT COUNT(*) AS total FROM places"
    )

    return int(
        row["total"]
    ) if row else 0


def get_category_count():
    """
    Return number of categories.
    """

    row = fetch_one(
        "SELECT COUNT(*) AS total FROM categories"
    )

    return int(
        row["total"]
    ) if row else 0


# ============================================================
# DATABASE QUICK TEST
# ============================================================

def test_queries():

    print("=" * 40)
    print(
        "SMART TAMILNADU TOURISM - QUERY TEST"
    )
    print("=" * 40)

    # --------------------------------------------------------
    # CATEGORIES
    # --------------------------------------------------------

    categories = get_categories()

    print(
        f"Total categories: {len(categories)}"
    )

    # --------------------------------------------------------
    # PLACES
    # --------------------------------------------------------

    places = get_all_places(
        limit=10
    )

    total_places = get_place_count()

    print(
        f"Total places: {total_places}"
    )

    print(
        f"Places loaded: {len(places)}"
    )

    # --------------------------------------------------------
    # SEARCH
    # --------------------------------------------------------

    print(
        "\nSearch test: Marina"
    )

    results = search_places(
        search_text="Marina",
        limit=10,
    )

    print(
        f"Results: {len(results)}"
    )

    if results:

        print(
            "First result:",
            dict(results[0])
        )

    # --------------------------------------------------------
    # RECOMMENDATIONS
    # --------------------------------------------------------

    print(
        "\nRecommendation test:"
    )

    recommendations = get_recommendations(
        limit=10
    )

    print(
        f"Recommendations: {len(recommendations)}"
    )

    # --------------------------------------------------------
    # POPULAR
    # --------------------------------------------------------

    print(
        "\nPopular places:"
    )

    popular = get_popular_places(
        limit=10
    )

    print(
        f"Popular: {len(popular)}"
    )

    # --------------------------------------------------------
    # CHATBOT
    # --------------------------------------------------------

    print(
        "\nChatbot search:"
    )

    chatbot_results = chatbot_search(
        "Marina Beach",
        limit=10,
    )

    print(
        f"Chatbot results: {len(chatbot_results)}"
    )

    # --------------------------------------------------------
    # FINAL STATUS
    # --------------------------------------------------------

    print(
        "\nQuery test completed."
    )

    if total_places == 0:

        print()
        print(
            "WARNING:"
        )

        print(
            "The places table is EMPTY."
        )

        print(
            "Queries are working, but the application "
            "cannot show destinations until places "
            "are inserted into the database."
        )

    print("=" * 40)


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    test_queries()
