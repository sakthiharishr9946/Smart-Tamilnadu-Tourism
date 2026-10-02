# Smart Tamilnadu Tourism - Data Sources

## 1. Overview

Smart Tamilnadu Tourism requires tourism-related data from multiple sources.

The collected data is organized into different categories so that the system can support:

- Tourist-place discovery
- Location-based search
- Personalized recommendations
- Rating analysis
- Crowd prediction
- Festival awareness
- Holiday awareness
- Tourism statistics
- Image display

The project maintains source information for data traceability.

---

## 2. Data Categories

The project collects the following major types of data:

| Data Category | Purpose |
|---|---|
| Tourism Places | Basic tourist-place information |
| Temples | Religious and temple destinations |
| Festivals | Festival and event information |
| Holidays | Holiday information affecting tourism |
| Ratings | Place ratings and review information |
| Images | Images associated with tourist places |
| Tourism Statistics | Tourism-related statistical information |

---

## 3. Tourism Places Data

Tourism-place data contains the core information required by the application.

Important fields include:

- Place name
- District
- City or town
- State
- Category
- Description
- Latitude
- Longitude
- Rating
- Rating count
- Popularity score
- Entry fee

This information is stored in the `places` table.

---

## 4. Temple Data

Temple data provides information about important religious destinations in Tamil Nadu.

Possible information includes:

- Temple name
- District
- City
- Location
- Description
- Temple type
- Opening hours
- Festival information
- Historical importance
- Tourism relevance

Temple information can contribute to:

- Tourism recommendations
- Religious tourism searches
- Festival awareness
- Itinerary generation

---

## 5. Festival Data

Festival information is used to identify periods when tourism activity may increase.

Important fields include:

- Festival name
- Associated tourist place
- Festival date
- Importance
- Description

Festival data is stored in the `festivals` table.

Festival information can also contribute to crowd prediction.

---

## 6. Holiday Data

Holiday information is used as a contextual factor in tourism and crowd analysis.

Important fields include:

- Holiday name
- Holiday date
- Description

Holiday data is stored in the `holidays` table.

Public holidays can influence:

- Tourist traffic
- Destination popularity
- Expected crowd levels
- Itinerary planning

---

## 7. Rating Data

Rating data is used for destination evaluation and recommendation.

Important fields include:

- Place
- Rating
- Review
- Rating date

Rating information is stored in the `ratings` table.

The recommendation system can use both rating value and rating count rather than relying only on the average rating.

---

## 8. Image Data

Image information is collected separately from general tourism data.

Important fields include:

- Place
- Image URL
- Image type

Image information is stored in the `images` table.

Images are used by the Streamlit interface to improve destination presentation.

---

## 9. Tourism Statistics

Tourism statistics provide broader information about tourism activity.

Possible information includes:

- Tourist arrivals
- Domestic tourist visits
- International tourist visits
- Yearly tourism statistics
- District-level tourism statistics
- Seasonal tourism trends
- Destination popularity

These statistics can support tourism analysis and model development.

---

## 10. Data Collection Methods

The project can use multiple collection methods depending on the source.

### 10.1 Public Datasets

Public datasets can be used when suitable tourism information is available.

Examples include:

- Government datasets
- Open-data portals
- Research datasets
- Public tourism datasets

### 10.2 Web Data Collection

Where permitted, relevant public tourism information can be collected from websites.

The data collection modules are located in:

```text
data/
└── collectors/
    ├── festival.py
    ├── holiday.py
    ├── image.py
    ├── rating.py
    ├── temple.py
    ├── tourism.py
    └── tourism_statistics.py