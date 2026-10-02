PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS categories (category_id INTEGER PRIMARY KEY AUTOINCREMENT, category_name TEXT NOT NULL UNIQUE, description TEXT);
CREATE TABLE IF NOT EXISTS sources (source_id INTEGER PRIMARY KEY AUTOINCREMENT, source_name TEXT NOT NULL, source_url TEXT, source_type TEXT NOT NULL, license TEXT, collection_method TEXT, reliability_level TEXT DEFAULT 'MEDIUM', last_checked TEXT, notes TEXT);
CREATE TABLE IF NOT EXISTS places (
    place_id INTEGER PRIMARY KEY AUTOINCREMENT, place_name TEXT NOT NULL, district TEXT NOT NULL,
    city_town TEXT, state TEXT NOT NULL DEFAULT 'Tamil Nadu', category_id INTEGER NOT NULL,
    subcategory TEXT, description TEXT, latitude REAL, longitude REAL, address TEXT,
    opening_time TEXT, closing_time TEXT, opening_days TEXT, avg_visit_duration REAL,
    entry_fee REAL, best_season TEXT, popularity_score REAL DEFAULT 0,
    tourism_relevance REAL DEFAULT 0, verified INTEGER DEFAULT 0, source_id INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES categories(category_id), FOREIGN KEY (source_id) REFERENCES sources(source_id)
);
CREATE TABLE IF NOT EXISTS images (image_id INTEGER PRIMARY KEY AUTOINCREMENT, place_id INTEGER NOT NULL, image_url TEXT NOT NULL, image_source TEXT, image_license TEXT, image_author TEXT, is_primary INTEGER DEFAULT 0, source_id INTEGER, FOREIGN KEY (place_id) REFERENCES places(place_id) ON DELETE CASCADE, FOREIGN KEY (source_id) REFERENCES sources(source_id));
CREATE TABLE IF NOT EXISTS ratings (rating_id INTEGER PRIMARY KEY AUTOINCREMENT, place_id INTEGER NOT NULL, rating REAL, rating_count INTEGER DEFAULT 0, rating_source TEXT, rating_date TEXT, source_id INTEGER, FOREIGN KEY (place_id) REFERENCES places(place_id) ON DELETE CASCADE, FOREIGN KEY (source_id) REFERENCES sources(source_id));
CREATE TABLE IF NOT EXISTS festivals (festival_id INTEGER PRIMARY KEY AUTOINCREMENT, festival_name TEXT NOT NULL, district TEXT, associated_place_id INTEGER, start_date TEXT, end_date TEXT, month INTEGER, festival_type TEXT, importance TEXT DEFAULT 'MEDIUM', expected_tourism_impact TEXT, source_id INTEGER, FOREIGN KEY (associated_place_id) REFERENCES places(place_id) ON DELETE SET NULL, FOREIGN KEY (source_id) REFERENCES sources(source_id));
CREATE TABLE IF NOT EXISTS holidays (holiday_id INTEGER PRIMARY KEY AUTOINCREMENT, holiday_name TEXT NOT NULL, date TEXT NOT NULL, year INTEGER NOT NULL, applicability TEXT, holiday_type TEXT, source_id INTEGER, FOREIGN KEY (source_id) REFERENCES sources(source_id), UNIQUE (holiday_name, date));
CREATE TABLE IF NOT EXISTS crowd_data (crowd_id INTEGER PRIMARY KEY AUTOINCREMENT, place_id INTEGER NOT NULL, date TEXT, month INTEGER, season TEXT, day_type TEXT, holiday_flag INTEGER DEFAULT 0, festival_flag INTEGER DEFAULT 0, festival_importance TEXT, tourism_period TEXT, historical_signal REAL, crowd_level TEXT, source_id INTEGER, FOREIGN KEY (place_id) REFERENCES places(place_id) ON DELETE CASCADE, FOREIGN KEY (source_id) REFERENCES sources(source_id));
CREATE TABLE IF NOT EXISTS search_history (search_id INTEGER PRIMARY KEY AUTOINCREMENT, query_location TEXT NOT NULL, latitude REAL, longitude REAL, initial_radius REAL, final_radius REAL, places_found INTEGER DEFAULT 0, search_timestamp TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS user_preferences (preference_id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL, interests TEXT, budget_level TEXT, trip_duration INTEGER, travel_style TEXT, preferred_crowd TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS place_features (place_id INTEGER PRIMARY KEY, rating_confidence REAL DEFAULT 0, review_confidence REAL DEFAULT 0, distance_score REAL DEFAULT 0, popularity_score REAL DEFAULT 0, season_score REAL DEFAULT 0, interest_score REAL DEFAULT 0, quality_score REAL DEFAULT 0, last_calculated TEXT DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (place_id) REFERENCES places(place_id) ON DELETE CASCADE);
CREATE INDEX IF NOT EXISTS idx_places_category ON places(category_id);
CREATE INDEX IF NOT EXISTS idx_places_district ON places(district);
CREATE INDEX IF NOT EXISTS idx_ratings_place ON ratings(place_id);
CREATE INDEX IF NOT EXISTS idx_images_place ON images(place_id);
CREATE INDEX IF NOT EXISTS idx_crowd_place ON crowd_data(place_id);
