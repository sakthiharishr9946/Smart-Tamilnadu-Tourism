# Smart Tamilnadu Tourism - System Architecture

## 1. Overview

Smart Tamilnadu Tourism is a Streamlit-based intelligent tourism application designed to help users discover tourist destinations, receive personalized recommendations, identify nearby places, understand crowd conditions, generate itineraries, estimate trip budgets, and interact with a tourism chatbot.

The system follows a modular architecture in which the user interface, business logic, machine learning models, database, data collection, and utility components are separated.

## 2. High-Level Architecture

```text
                         SMART TAMILNADU TOURISM
                                  |
                                  v
                         Streamlit Application
                                  |
              +-------------------+-------------------+
              |                   |                   |
              v                   v                   v
             UI                Services           Chatbot
              |                   |                   |
              |          +--------+--------+          |
              |          |        |        |          |
              |          v        v        v          |
              |      Location  Recommendation Crowd    |
              |          |        |        |          |
              |          |        |        |          |
              |          +--------+--------+          |
              |                   |                   |
              |                   v                   |
              |              ML Models                |
              |                   |                   |
              +-------------------+-------------------+
                                  |
                                  v
                              Database
                                  |
                                  v
                              SQLite