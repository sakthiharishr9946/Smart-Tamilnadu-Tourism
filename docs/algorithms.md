# Smart Tamilnadu Tourism - Algorithms

## 1. Overview

Smart Tamilnadu Tourism uses multiple algorithms and scoring techniques to provide intelligent tourism recommendations, nearby-place discovery, crowd prediction, itinerary generation, route optimization and budget estimation.

The main algorithmic components are:

1. Distance Calculation
2. Adaptive Radius Search
3. Recommendation Scoring
4. Rating Confidence
5. Popularity Scoring
6. Interest Matching
7. Crowd Prediction
8. Crowd Classification
9. Itinerary Generation
10. Route Optimization
11. Schedule Optimization
12. Budget Calculation

---

## 2. Distance Calculation

### Purpose

Distance calculation is used to identify tourist places near the user's current or selected location.

The system uses geographical coordinates:

- Latitude
- Longitude

### Haversine Formula

For two geographical points:

```text
(lat1, lon1)
(lat2, lon2)