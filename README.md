# Smart Tamilnadu Tourism

Smart Tamilnadu Tourism is an intelligent tourism platform designed to help users discover tourist destinations across Tamil Nadu, get personalized recommendations, estimate crowd levels, plan itineraries, calculate travel budgets, and interact with a tourism chatbot.

## Features

- Tourist place exploration
- Search and category-based filtering
- Destination recommendations
- Crowd prediction
- Personalized itinerary generation
- Travel budget estimation
- Interactive destination map
- Tourist place ratings
- Festival and holiday information
- Tourism chatbot
- User preference support
- SQLite database
- Responsive Streamlit interface

## Project Structure

```text
Smart Tamilnadu Tourism/
│
├── app.py
├── requirements.txt
├── README.md
│
├── config/
│
├── database/
│
├── models/
│   ├── crowd_prediction/
│   │   ├── train.py
│   │   ├── evaluate.py
│   │   ├── predict.py
│   │   └── saved/
│   │
│   └── recommendation/
│       ├── model.py
│       ├── train.py
│       └── saved/
│
├── services/
│   ├── budget/
│   ├── chatbot/
│   ├── itinerary/
│   └── recommendation/
│
├── ui/
│   ├── components/
│   └── styles/
│
├── pages/
│   ├── explore.py
│   ├── recommendations.py
│   ├── itinerary.py
│   ├── budget.py
│   └── chatbot.py
│
├── docs/
│   ├── data_sources.md
│   ├── algorithms.md
│   ├── database_schema.md
│   ├── architecture.md
│   └── project_documentation.md
│
└── database/
    └── tourism.db

## Fresh Tourism Data Rebuild

This version is packaged without the old `tourism.db` so the tourism database starts clean.

From the project root run:

```powershell
python -m database.database
python -m scripts.refresh_data --reset
```

The refresh collects from the configured Tamil Nadu government/district/HR&CE/archaeology/wetlands sources plus OSM and Wikidata where available. A source failing does not stop the other sources.

### Recommendation radius

The recommendation flow has a hard geographic gate. When a radius such as 50 km is selected, only places whose calculated great-circle distance is `<= 50 km` can reach the ranking/rendering stage. There is no fallback to statewide results when no nearby destinations exist.
