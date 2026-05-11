# NBA Data Engineering & Machine Learning Project

## Overview

This project is an end-to-end **NBA data engineering + machine learning pipeline** built to:

* Learn how basketball works (playmaking, spacing, team dynamics)
* Build a **data warehouse (SQL Server)**
* Engineer advanced features (rolling averages, usage metrics, pace adjustments)
* Train a **machine learning model to predict player assists**

---

## Objective

The primary goal is to:

> **Predict how many assists a player will record in a game against a specific opponent**

This is done by combining:

* Player recent assist performance
* Usage rate and minutes trends
* Team pace and offensive system
* Opponent defensive tendencies
* Rest days and schedule context

---

## Tech Stack

* **Python**: `3.12.7`
* **Database**: SQL Server (ODBC Driver 17)
* **IDE**: VS Code / PyCharm
* **ML Library**: XGBoost
* **Data Sources**:

    * NBA Stats API (`nba_api`)
    * GitHub Actions (weekly automation)

---

## Prerequisites

Install required packages:

```bash
pip install nba-api
pip install pandas
pip install numpy
pip install python-dotenv
pip install scikit-learn
pip install sqlalchemy
pip install xgboost
```

---

## Project Structure

```
nba/
|
|-- .github/workflows/
|   |-- game_logs.yml
|   |-- player_game_logs.yml
|   |-- sentence_generator.yml
|
|-- src/
|   |-- ingestion/
|   |-- features/
|   |-- models/
|   |-- utils/
|
|-- outputs/
|-- .env
|-- README.md
```

---

## Data Pipeline Architecture

### Game Selection

* `LeagueGameFinder` endpoint
* Filters to **completed regular season games only**

### Data Ingestion

* Player game logs (assists, points, minutes, usage)
* Team game logs (pace, offensive rating, assists)
* Player advanced stats (assist percentage, usage rate)
* Opponent defensive stats (opponent assist rate, pace)

### SQL Loader

Reusable helper:

* `load_dataframe()`
* `execute_sql()`
* `truncate_table()`

---

## Data Warehouse Design

### Core Feature Tables

#### Player

* `fact_player_assist_model_features`

    * Rolling averages (3, 5, 10)
    * Weighted averages
    * Rest days
    * Minutes trends
    * Usage rate

* `fact_player_advanced_stats`

    * Assist percentage (`AST%`)
    * Usage rate (`USG%`)
    * True shooting percentage
    * Net rating

---

#### Team

* `fact_team_pace_features`

    * Pace (possessions per 48 minutes)
    * Offensive rating
    * Team assist ratio
    * Passes per game

---

#### Opponent

* `fact_opponent_defensive_features`

    * Opponent assist rate allowed
    * Defensive rating
    * Opponent pace

---

#### Matchup (Most Important Table)

* `fact_player_opponent_matchup_model_features`

This combines:

* Player assist features
* Team offensive context
* Opponent defensive context
* Historical matchup assist stats

This is your **final ML dataset**

---

## Table Relationships

```
Player Assist Model Features
        |
Player vs Opponent Features
        |
Player Opponent Matchup Model Features (FINAL DATASET)
        |
Team Pace Features + Opponent Defensive Features
```

---

## Feature Engineering Summary

### Key Player Features

* `ast` (assists per game)
* `min` (minutes played)
* `usg_pct` (usage rate)
* `ast_pct` (assist percentage)
* `avg_ast_last_3/5/10`
* `weighted_avg_ast_last_3/5/10`
* `days_since_last_game`

---

### Team Context Features

* `team_pace`
* `team_offensive_rating`
* `team_ast_ratio`
* `team_passes_per_game`

---

### Opponent Defensive Features

* `opp_defensive_rating`
* `opp_pace`
* `opp_ast_allowed_per_game`
* `opp_assist_rate_allowed`

---

### Matchup Features

* `games_vs_opponent`
* `avg_ast_vs_opponent`
* `matchup_pace_factor`

---

## Machine Learning Model

### Model: **XGBoost Regressor**

### Target:

```
player_assists
```

---

### How It Works

1. Build **feature tables**
2. Join into:

      ```
      fact_player_opponent_matchup_model_features
      ```
3. Remove leakage columns
4. Train model:

      * Inputs → engineered features
      * Output → predicted assists

---

### Evaluation Metrics

* MAE (Mean Absolute Error)
* RMSE (Root Mean Squared Error)

---

## How to Run Pipelines

### Data Ingestion

```bash
python -m src.ingestion.nba_player_game_logs
python -m src.ingestion.nba_team_game_logs
python -m src.ingestion.nba_player_advanced_stats
python -m src.ingestion.nba_opponent_stats
```

---

### Feature Engineering

```bash
python -m src.features.player_assist_features
python -m src.features.team_pace_features
python -m src.features.opponent_defensive_features
python -m src.features.player_opponent_matchup_features
```

---

## NBA Stats API Endpoints Used

| Endpoint | Purpose |
|---|---|
| `PlayerGameLog` | Player game-by-game stats (AST, MIN, PTS) |
| `TeamGameLog` | Team game-by-game stats (pace, AST) |
| `LeagueDashPlayerStats` | League-wide player averages |
| `LeagueDashTeamStats` | League-wide team pace and ratings |
| `PlayerDashboardByGeneralSplits` | Player splits (home/away, rest) |
| `LeagueGameFinder` | Find completed games by date range |
| `BoxScoreAdvancedV2` | Advanced per-game stats (USG%, AST%) |

Full endpoint reference: [nba_api Stats Endpoints](https://github.com/swar/nba_api/tree/master/docs/nba_api/stats/endpoints)

---

## Automation

### GitHub Actions Workflows

* **`game_logs.yml`**: Weekly team game log refresh (Sunday 9:00 AM AEST)
* **`player_game_logs.yml`**: Weekly player game log refresh (Friday 11:00 PM AEST)
* **`sentence_generator.yml`**: Weekly model summary output

---

## Future Enhancements

* Improve feature selection with SHAP values
* Add home/away split features
* Add back-to-back game fatigue flags
* Add betting odds integration
* Hyperparameter tuning (XGBoost)
* Build classification model (Over/Under assists)
* Deploy model (API / dashboard)

---

## References

* NBA Stats API (via nba_api)
    [https://github.com/swar/nba_api](https://github.com/swar/nba_api)

* nba_api Endpoints Documentation
    [https://github.com/swar/nba_api/tree/master/docs/nba_api/stats/endpoints](https://github.com/swar/nba_api/tree/master/docs/nba_api/stats/endpoints)

* XGBoost Documentation
    [https://xgboost.readthedocs.io/](https://xgboost.readthedocs.io/)

---

## Final Notes

This project is designed to:

* Combine **data engineering + machine learning**
* Build a **real-world sports analytics pipeline**
* Create a foundation for **predictive analytics / betting models** targeting NBA player assists for the 2026-27 season
