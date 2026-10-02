import sqlite3
from pathlib import Path


# ============================================================
# PROJECT PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DATABASE_PATH = (
    BASE_DIR
    / "database"
    / "tourism.db"
)

SCHEMA_PATH = (
    BASE_DIR
    / "database"
    / "schema.sql"
)


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_connection():
    """
    Create and return a SQLite database connection.

    Row factory is enabled so database rows can be accessed
    like dictionaries.
    """

    connection = sqlite3.connect(
        DATABASE_PATH
    )

    connection.row_factory = sqlite3.Row

    # Enable foreign key constraints
    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    return connection


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def initialize_database():
    """
    Create the database and tables using schema.sql.
    """

    DATABASE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(
            f"Schema file not found: {SCHEMA_PATH}"
        )

    connection = get_connection()

    try:
        with open(
            SCHEMA_PATH,
            "r",
            encoding="utf-8",
        ) as file:
            schema = file.read()

        connection.executescript(
            schema
        )

        connection.commit()

    finally:
        connection.close()

    from database.migrations import apply_migrations
    apply_migrations()


# ============================================================
# FETCH ALL
# ============================================================

def fetch_all(
    query,
    parameters=(),
):
    """
    Execute a SELECT query and return all rows.
    """

    connection = get_connection()

    try:
        cursor = connection.execute(
            query,
            parameters,
        )

        return cursor.fetchall()

    finally:
        connection.close()


# ============================================================
# FETCH ONE
# ============================================================

def fetch_one(
    query,
    parameters=(),
):
    """
    Execute a SELECT query and return one row.
    """

    connection = get_connection()

    try:
        cursor = connection.execute(
            query,
            parameters,
        )

        return cursor.fetchone()

    finally:
        connection.close()


# ============================================================
# EXECUTE INSERT / UPDATE / DELETE
# ============================================================

def execute_query(
    query,
    parameters=(),
):
    """
    Execute INSERT, UPDATE or DELETE query.

    Returns:
        Last inserted row ID.
    """

    connection = get_connection()

    try:
        cursor = connection.execute(
            query,
            parameters,
        )

        connection.commit()

        return cursor.lastrowid

    finally:
        connection.close()


# ============================================================
# EXECUTE MANY
# ============================================================

def execute_many(
    query,
    parameters_list,
):
    """
    Execute the same query for multiple records.
    """

    connection = get_connection()

    try:
        connection.executemany(
            query,
            parameters_list,
        )

        connection.commit()

    finally:
        connection.close()


# ============================================================
# DATABASE STATUS
# ============================================================

def database_exists():
    """
    Check whether the SQLite database exists.
    """

    return DATABASE_PATH.exists()


# ============================================================
# DATABASE TEST
# ============================================================

def test_connection():
    """
    Test whether the database can be opened.
    """

    try:
        connection = get_connection()

        connection.execute(
            "SELECT 1"
        )

        connection.close()

        return True

    except sqlite3.Error:
        return False


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    try:
        initialize_database()

        print(
            "Database initialized successfully."
        )

        print(
            f"Database: {DATABASE_PATH}"
        )

        if test_connection():
            print(
                "Database connection: OK"
            )
        else:
            print(
                "Database connection: FAILED"
            )

    except Exception as error:

        print(
            f"Database initialization failed: {error}"
        )
