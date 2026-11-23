"""Team stats for the sidebar: a team's record, offensive and defensive ratings, and season
totals and per-game numbers up to a date, each ranked against the rest of the league.
Everything comes from dbo.team_game_log, which the daily load keeps up to date."""
from datetime import date

import pandas as pd
import streamlit as st

import queries

TEAM_KEY = "today_team"
# Summed over the season. The opponent's points and possessions give points allowed and the
# defensive rating.
COUNTING = ["pts", "opp_pts", "fgm", "fga", "fg3m", "fg3a", "ftm", "fta", "oreb", "dreb", "reb",
            "ast", "stl", "blk", "tov", "pf", "poss", "opp_poss"]
# Rows of the stats table: column -> (label, lower is better). Counting stats show a season
# total and a per-game average and rank on the average; the rest show their value only.
# Short labels, as in the game logs, so four columns fit in the sidebar.
TABLE_STATS = {
    "pts":     ("Pts", False),
    "opp_pts": ("Opp pts", True),
    "fga":     ("FGA", False),
    "fgm":     ("FGM", False),
    "fg_pct":  ("FG %", False),
    "fg3m":    ("3PM", False),
    "fg3a":    ("3PA", False),
    "fg3_pct": ("3P %", False),
    "ftm":     ("FTM", False),
    "ft_pct":  ("FT %", False),
    "reb":     ("Reb", False),
    "oreb":    ("Off reb", False),
    "dreb":    ("Def reb", False),
    "ast":     ("Ast", False),
    "stl":     ("Stl", False),
    "blk":     ("Blk", False),
    "tov":     ("TOV", True),
    "pf":      ("Fouls", True),
    "pace":    ("Pace", False),
}
PERCENTAGES = ["fg_pct", "fg3_pct", "ft_pct"]
ROW_HEIGHT = 35         # Streamlit's table row height, to show every row without scrolling


def league_table(logs: pd.DataFrame) -> pd.DataFrame:
    """One row per team: season totals, ratings, shooting percentages and win-loss record."""
    by_team = logs.groupby("team_id")
    table = by_team[COUNTING].sum()
    table["gp"] = by_team.size()
    table["wins"] = (logs["wl"] == "W").groupby(logs["team_id"]).sum()
    table["losses"] = table["gp"] - table["wins"]
    table["win_pct"] = table["wins"] / table["gp"]
    # Points per 100 possessions over the whole season, which is how NBA.com works out a
    # season rating (checked against its 2025-26 numbers). Averaging each game's rating instead
    # would give long games too little weight.
    table["off_rating"] = 100 * table["pts"] / table["poss"]
    table["def_rating"] = 100 * table["opp_pts"] / table["opp_poss"]
    table["net_rating"] = table["off_rating"] - table["def_rating"]
    table["fg_pct"] = table["fgm"] / table["fga"]
    table["fg3_pct"] = table["fg3m"] / table["fg3a"]
    table["ft_pct"] = table["ftm"] / table["fta"]
    table["pace"] = by_team["pace"].mean()
    return table


def ordinal(n: int) -> str:
    """1 -> "1st", 2 -> "2nd", 11 -> "11th", 23 -> "23rd"."""
    suffix = "th" if 11 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def record(games: pd.DataFrame) -> str:
    wins = int((games["wl"] == "W").sum())
    return f"{wins}–{len(games) - wins}"


def streak(results: list) -> str:
    """The current run of wins or losses, e.g. "W3", from results oldest first."""
    last = results[-1]
    count = 0
    for result in reversed(results):
        if result != last:
            break
        count += 1
    return f"{last}{count}"


def show_team_stats(season: str, day: date, games_today: pd.DataFrame = None, key: str = TEAM_KEY,
                    default_team: str = None) -> str:
    """The sidebar section: pick a team and see its season up to `day`, ranked against the league.
    Teams in `games_today` (the games on `day`) are listed first; otherwise `default_team` is
    picked to start with. Returns the chosen team's abbreviation."""
    teams = queries.teams()
    names = dict(zip(teams["abbreviation"], teams["full_name"]))
    team_ids = dict(zip(teams["abbreviation"], teams["team_id"]))
    if games_today is None:
        games_today = pd.DataFrame()
    playing = [t for g in games_today.itertuples() for t in (g.away_team_tricode, g.home_team_tricode) if t in names]
    options = playing + [t for t in teams["abbreviation"] if t not in playing]

    sidebar = st.sidebar
    sidebar.subheader("Team stats")
    abbr = sidebar.selectbox("Team", options, key=key,
                             index=options.index(default_team) if default_team in options else 0,
                             format_func=lambda t: ("🏀 " if t in playing else "") + names[t],
                             help="🏀 = plays on this day. Those teams are listed first." if playing else None)
    for g in games_today.itertuples():
        if abbr in (g.away_team_tricode, g.home_team_tricode):
            score = f" {int(g.away_pts)}–{int(g.home_pts)}," if pd.notna(g.away_pts) and pd.notna(g.home_pts) else ""
            sidebar.caption(f"Plays on this day: {g.away_team_tricode} @ {g.home_team_tricode},{score} "
                            f"{g.game_status_text}")

    logs = queries.team_season_games(season)
    logs = logs[logs["game_date"] <= pd.Timestamp(day)]
    team_id = team_ids[abbr]
    if team_id not in set(logs["team_id"]):
        sidebar.info(f"No {season} regular-season games loaded for {abbr} up to {day:%d %b %Y}.")
        return abbr

    table = league_table(logs)
    team = table.loc[team_id]
    n_teams = len(table)

    def rank(values: pd.Series, lower_is_better: bool = False) -> str:
        return f"{ordinal(int(values.rank(ascending=lower_is_better, method='min')[team_id]))} of {n_teams}"

    # ---- the headline numbers, each with its league rank underneath
    cards = [
        ("Record", f"{int(team['wins'])}–{int(team['losses'])}", rank(table["win_pct"]),
         "Wins–losses. Ranked by winning percentage."),
        ("Net rating", f"{team['net_rating']:+.1f}", rank(table["net_rating"]),
         "Offensive minus defensive rating: how many points per 100 possessions better than its opponents."),
        ("Off rating", f"{team['off_rating']:.1f}", rank(table["off_rating"]),
         "Points scored per 100 possessions. Higher is better."),
        ("Def rating", f"{team['def_rating']:.1f}", rank(table["def_rating"], lower_is_better=True),
         "Points allowed per 100 possessions. Lower is better, so 1st is the best defence."),
    ]
    for row in (cards[:2], cards[2:]):
        for column, (label, value, its_rank, help_text) in zip(sidebar.columns(2), row):
            column.metric(label, value, delta=its_rank, delta_color="off", delta_arrow="off", help=help_text)

    games = logs[logs["team_id"] == team_id].sort_values("game_date")
    sidebar.caption(f"Home {record(games[games['is_home'].astype(bool)])} · "
                    f"Away {record(games[~games['is_home'].astype(bool)])} · "
                    f"Last 10 {record(games.tail(10))} · Streak {streak(list(games['wl']))}")

    # ---- every other stat: per game, season total, league rank
    rows = []
    for stat, (label, lower_is_better) in TABLE_STATS.items():
        counting = stat in COUNTING
        values = table[stat] / table["gp"] if counting else table[stat]
        scale = 100 if stat in PERCENTAGES else 1
        rows.append({
            "Stat": label,
            "Per game": values[team_id] * scale,
            "Total": team[stat] if counting else None,
            "Rank": int(values.rank(ascending=lower_is_better, method="min")[team_id]),
        })
    sidebar.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", placeholder="—",
                      height=ROW_HEIGHT * (len(rows) + 1) + 3, column_config={
                          "Per game": st.column_config.NumberColumn(format="%.1f"),
                          "Total": st.column_config.NumberColumn(format="%d"),
                          "Rank": st.column_config.NumberColumn(
                              format="%d", help=f"Out of {n_teams} teams. 1 = best."),
                      })
    sidebar.caption(f"{season} regular season, {int(team['gp'])} games, the last on "
                    f"{games['game_date'].max():%d %b %Y}. Ranks are out of "
                    f"{n_teams} teams, 1 = best: most of everything, except fewest points allowed (Opp pts), "
                    f"turnovers (TOV) and fouls. FGA / FGM = shots taken / made; 3PM / 3PA = threes made / "
                    f"attempted; FTM = free throws made. Pace = possessions per 48 minutes.")
    return abbr
