# Smart Tamilnadu Tourism - Database Schema

## 1. Overview

Smart Tamilnadu Tourism uses SQLite as the primary database.

Database file:

`database/tourism.db`

The database stores tourism places, categories, ratings, images, festivals, holidays, crowd information, recommendation features, user preferences and search history.

## 2. Database Tables

The database contains the following main tables:

- `sources`
- `categories`
- `places`
- `ratings`
- `images`
- `festivals`
- `holidays`
- `crowd_data`
- `place_features`
- `user_preferences`
- `search_history`

SQLite may also create:

- `sqlite_sequence`

when `AUTOINCREMENT` is used.

## 3. Entity Relationship Overview

```text
                    sources
                       |
              +--------+--------+
              |        |        |
              v        v        v
          places    ratings    images
              |
       +------+------+------+
       |      |      |      |
       v      v      v      v
  categories festivals holidays place_features

places
   |
   +------------------+
   |                  |
   v                  v
crowd_data      search_history

user_preferences