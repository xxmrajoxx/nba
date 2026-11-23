"""Game logs page: one player's games in a season with every stat the pipeline loads (box score,
shooting, advanced, share of team, scoring, speed and distance, passing, touches and hustle),
charts of any of them game by game, his splits, his career season by season, and his team's
stats and game log."""
from datetime import date

import altair as alt
import pandas as pd
import streamlit as st

import queries
from common import LOCAL_NAME, NEUTRAL, SERIES, chart_grid, require_data, style_page, to_local
from team_stats import show_team_stats

# Every stat, grouped by the dataset it comes from: column -> label.
DATASETS = {
    "Box score": {
        "minutes": "Min", "pts": "Pts", "reb": "Reb", "oreb": "Off reb", "dreb": "Def reb", "ast": "Ast",
        "stl": "Stl", "blk": "Blk", "tov": "TOV", "pf": "Fouls", "plus_minus": "+/-",
    },
    "Shooting": {
        "fgm": "FGM", "fga": "FGA", "fg_pct": "FG %", "fg3m": "3PM", "fg3a": "3PA", "fg3_pct": "3P %",
        "ftm": "FTM", "fta": "FTA", "ft_pct": "FT %", "efg_pct": "eFG %", "ts_pct": "TS %",
    },
    "Advanced": {
        "usg_pct": "Usage %", "off_rating": "Off rating", "def_rating": "Def rating", "net_rating": "Net rating",
        "ast_pct": "Ast %", "ast_to": "Ast/TOV", "ast_ratio": "Ast ratio", "oreb_pct": "Off reb %",
        "dreb_pct": "Def reb %", "reb_pct": "Reb %", "tm_tov_pct": "TOV ratio", "pie": "PIE", "pace": "Pace",
        "poss": "Possessions",
    },
    "Share of team": {
        "pct_pts": "% of team pts", "pct_fgm": "% of team FGM", "pct_fga": "% of team FGA",
        "pct_fg3m": "% of team 3PM", "pct_fg3a": "% of team 3PA", "pct_ftm": "% of team FTM",
        "pct_fta": "% of team FTA", "pct_reb": "% of team reb", "pct_oreb": "% of team off reb",
        "pct_dreb": "% of team def reb", "pct_ast": "% of team ast", "pct_tov": "% of team TOV",
        "pct_stl": "% of team stl", "pct_blk": "% of team blk", "pct_pf": "% of team fouls",
    },
    "Scoring": {
        "pct_fga_2pt": "Shots that are 2s %", "pct_fga_3pt": "Shots that are 3s %",
        "pct_pts_2pt": "Pts from 2s %", "pct_pts_2pt_mr": "Pts from mid-range %", "pct_pts_3pt": "Pts from 3s %",
        "pct_pts_paint": "Pts in the paint %", "pct_pts_ft": "Pts from free throws %",
        "pct_pts_fb": "Fast-break pts %", "pct_pts_off_tov": "Pts off turnovers %",
        "pct_ast_fgm": "Makes assisted %", "pct_uast_fgm": "Makes unassisted %",
        "pct_ast_2pm": "2s assisted %", "pct_uast_2pm": "2s unassisted %",
        "pct_ast_3pm": "3s assisted %", "pct_uast_3pm": "3s unassisted %",
    },
    "Speed & distance": {
        "dist_miles": "Miles", "dist_miles_off": "Miles on offence", "dist_miles_def": "Miles on defence",
        "avg_speed": "Speed (mph)", "avg_speed_off": "Speed on offence", "avg_speed_def": "Speed on defence",
    },
    "Passing": {
        "passes_made": "Passes made", "passes_received": "Passes received", "potential_ast": "Potential ast",
        "secondary_ast": "Secondary ast", "ft_ast": "Free-throw ast", "ast_pts_created": "Pts created by ast",
    },
    "Touches": {
        "touches": "Touches", "front_ct_touches": "Front-court touches", "time_of_poss": "Time on ball (min)",
        "avg_sec_per_touch": "Sec per touch", "avg_drib_per_touch": "Dribbles per touch",
        "pts_per_touch": "Pts per touch", "elbow_touches": "Elbow touches", "post_touches": "Post touches",
        "paint_touches": "Paint touches",
    },
    "Hustle": {
        "contested_shots": "Contested shots", "contested_shots_2pt": "Contested 2s",
        "contested_shots_3pt": "Contested 3s", "deflections": "Deflections", "charges_drawn": "Charges drawn",
        "screen_assists": "Screen ast", "screen_ast_pts": "Screen ast pts",
        "loose_balls_recovered": "Loose balls", "off_loose_balls_recovered": "Loose balls on offence",
        "def_loose_balls_recovered": "Loose balls on defence", "box_outs": "Box-outs",
        "off_boxouts": "Box-outs on offence", "def_boxouts": "Box-outs on defence",
    },
}
LABELS = {column: label for columns in DATASETS.values() for column, label in columns.items()}
DATASET_OF = {column: name for name, columns in DATASETS.items() for column in columns}
# Stored as fractions (0.25) and shown as percentages (25.0%). TOV ratio is already per 100 plays.
FRACTIONS = ({c for c in LABELS if c.endswith("_pct") or c.startswith("pct_")} - {"tm_tov_pct"}) | {"pie"}
# Stats that aren't whole numbers even in a single game, and their decimal places.
DECIMALS = {
    "minutes": 1, "off_rating": 1, "def_rating": 1, "net_rating": 1, "ast_to": 2, "ast_ratio": 1,
    "tm_tov_pct": 1, "pace": 1, "dist_miles": 2, "dist_miles_off": 2, "dist_miles_def": 2,
    "avg_speed": 2, "avg_speed_off": 2, "avg_speed_def": 2, "time_of_poss": 1,
    "avg_sec_per_touch": 2, "avg_drib_per_touch": 2, "pts_per_touch": 2,
}
TRACKING_DATASETS = ["Speed & distance", "Passing", "Touches", "Hustle"]
DEFAULT_DATASETS = ["Box score", "Shooting"]
DEFAULT_CHART_STATS = ["pts", "reb", "ast", "ts_pct"]
SEASON_TYPES = {"Regular season": ["Regular Season"], "Playoffs": ["Playoffs"], "Both": ["Regular Season", "Playoffs"]}
SEASON_TYPE_TEXT = {"Regular season": "regular-season", "Playoffs": "playoff", "Both": "regular-season and playoff"}
ROLLING = {"Off": 1, "3": 3, "5": 5, "10": 10}
LOSS_COLOR = "#d95926"          # the palette's second categorical colour, next to SERIES blue for wins
ROW_HEIGHT = 35                 # Streamlit's table row height, to size a table to its rows
TEAM_COLUMNS = ["pts", "opp_pts", "fgm", "fga", "fg_pct", "fg3m", "fg3a", "fg3_pct", "ftm", "fta", "ft_pct",
                "reb", "oreb", "ast", "stl", "blk", "tov", "pf", "off_rating", "def_rating", "net_rating", "pace"]

style_page()
st.sidebar.title("📋 Game logs")
require_data()


# ---------------------------------------------------------------- helpers
def ratio(top: float, bottom: float) -> float:
    return top / bottom if bottom else float("nan")


def averages(rows: pd.DataFrame, columns: list) -> dict:
    """Per-game averages over `rows`. Shooting percentages come from the totals, all his makes
    over all his attempts, rather than the average of each game's percentage, in which a
    1-for-1 night would count as much as a 10-for-25 one."""
    row = {"games": len(rows), **rows[columns].mean().to_dict()}
    t = rows[["pts", "fgm", "fga", "fg3m", "fg3a", "ftm", "fta"]].sum()
    from_totals = {
        "fg_pct": ratio(t["fgm"], t["fga"]),
        "fg3_pct": ratio(t["fg3m"], t["fg3a"]),
        "ft_pct": ratio(t["ftm"], t["fta"]),
        "efg_pct": ratio(t["fgm"] + 0.5 * t["fg3m"], t["fga"]),
        "ts_pct": ratio(t["pts"], 2 * (t["fga"] + 0.44 * t["fta"])),
    }
    row.update({c: v for c, v in from_totals.items() if c in columns})
    return row


def as_shown(df: pd.DataFrame, columns: list) -> pd.DataFrame:
    """The stat columns, with fractions turned into percentages for display."""
    shown = df[columns].copy()
    for column in FRACTIONS & set(columns):
        shown[column] = shown[column] * 100
    return shown


def number_format(column: str, averaged: bool) -> str:
    """Percentages to 1 decimal place; counts as whole numbers in a single game, to 1 decimal averaged."""
    if column in FRACTIONS:
        return "%.1f%%"
    if column in DECIMALS:
        return f"%.{DECIMALS[column]}f"
    return "%.1f" if averaged else "%d"


def stat_config(columns: list, averaged: bool) -> dict:
    return {c: st.column_config.NumberColumn(LABELS.get(c, c), format=number_format(c, averaged)) for c in columns}


def splits(df: pd.DataFrame) -> list:
    """(label, games) for each split of the season's games, leaving out any with no games."""
    home = df["is_home"].astype(bool)
    pairs = [
        ("All games", df), ("Home", df[home]), ("Away", df[~home]),
        ("Wins", df[df["wl"] == "W"]), ("Losses", df[df["wl"] == "L"]),
        ("Started", df[df["started"] == "Yes"]), ("Off the bench", df[df["started"] == "No"]),
        ("Back-to-back", df[df["days_rest"] == 0]), ("1 day of rest", df[df["days_rest"] == 1]),
        ("2+ days of rest", df[df["days_rest"] >= 2]),
        ("Last 5 games", df.tail(5)), ("Last 10 games", df.tail(10)),
    ]
    for month, rows in df.groupby(df["game_date"].dt.to_period("M")):
        pairs.append((month.strftime("%B %Y"), rows))
    return [(label, rows) for label, rows in pairs if not rows.empty]


# ---------------------------------------------------------------- sidebar: player, season, team
players = queries.players()
labels = players["full_name"] + players["team"].fillna("FA").map(lambda t: f"  ({t})")
default = players.index[players["full_name"] == "LeBron James"]
choice = st.sidebar.selectbox("Player", players.index, format_func=lambda i: labels[i],
                              index=int(default[0]) if len(default) else 0, key="game_logs_player")
player = players.loc[choice]
player_id = int(player["player_id"])

games = queries.player_game_logs(player_id)
if games.empty:
    st.title(player["full_name"])
    st.info("No games loaded for this player yet. Rookies appear once the game_logs job has loaded their games.")
    st.stop()

# Days off before each game: 0 = the second night of a back-to-back. Blank for a season's first game.
games["days_rest"] = games.groupby("season")["game_date"].diff().dt.days - 1
games["started"] = games["is_starter"].map({True: "Yes", False: "No"})
local = to_local(games["tipoff_et"]).set_axis(games.index)
us_date = games["game_date"].dt.strftime("%Y-%m-%d")
games["local_date"] = local.dt.strftime("%Y-%m-%d").fillna(us_date)
games["local_label"] = local.dt.strftime(f"%a %d %b %Y ({LOCAL_NAME})").fillna(us_date)
score = games["team_pts"].astype("Int64").astype(str) + "–" + games["opp_pts"].astype("Int64").astype(str)
games["result"] = (games["wl"] + " " + score).where(games["team_pts"].notna() & games["opp_pts"].notna(), games["wl"])

season = st.sidebar.selectbox("Season", sorted(games["season"].unique(), reverse=True))
season_type = st.sidebar.radio("Season type", list(SEASON_TYPES), horizontal=True)

# His team that season: the one he played his last game of it for (he may have been traded).
his_team = games.loc[games["season"] == season, "team_abbreviation"].iloc[-1]
team_abbr = show_team_stats(season, date.today(), key=f"game_logs_team_{player_id}_{season}", default_team=his_team)

# ---------------------------------------------------------------- header
view = games[(games["season"] == season) & games["season_type"].isin(SEASON_TYPES[season_type])]
st.title(player["full_name"])
teams_played = " → ".join(dict.fromkeys(games.loc[games["season"] == season, "team_abbreviation"]))
details = [teams_played, player["position"], f"{season} {SEASON_TYPE_TEXT[season_type]} games"]
st.caption(" · ".join(str(d) for d in details if pd.notna(d) and d))
if view.empty:
    st.info(f"He has no {SEASON_TYPE_TEXT[season_type]} games in {season}.")
    st.stop()

top = averages(view, ["minutes", "pts", "reb", "ast", "ts_pct"])
cards = st.columns(6)
cards[0].metric("Games", top["games"])
cards[1].metric("Minutes", f"{top['minutes']:.1f}")
cards[2].metric("Points", f"{top['pts']:.1f}")
cards[3].metric("Rebounds", f"{top['reb']:.1f}")
cards[4].metric("Assists", f"{top['ast']:.1f}")
cards[5].metric("True shooting", f"{top['ts_pct'] * 100:.1f}%",
                help="Points per shooting possession, counting threes and free throws: his scoring efficiency.")

picked = st.pills("Columns (game log, averages and career)", list(DATASETS), selection_mode="multi",
                  default=DEFAULT_DATASETS, key="game_logs_datasets") or ["Box score"]
columns = [c for name in picked for c in DATASETS[name]]
if set(picked) & set(TRACKING_DATASETS) and view[queries.TRACKING_STATS].isna().all().all():
    st.info("No speed and distance, passing, touches or hustle data for these games yet: the tracking job has "
            "loaded 2025-26 onwards so far. `run_job.py tracking` fills in older seasons (about 3.5 hours).")

tab_log, tab_charts, tab_splits, tab_career, tab_team = st.tabs(
    ["Game log", "Charts", "Averages & splits", "Career", "Team"])

# ---------------------------------------------------------------- game log
with tab_log:
    log = view.sort_values("game_date", ascending=False)
    fixed = {"local_date": f"Date ({LOCAL_NAME})", "game_date": "US date", "matchup": "Game", "result": "Result"}
    if season_type == "Both":
        fixed["season_type"] = "Type"
    if log["started"].notna().any():
        fixed["started"] = "Started"
    table = pd.concat([log[list(fixed)], as_shown(log, columns)], axis=1)
    config = {**fixed, "game_date": st.column_config.DateColumn("US date", format="YYYY-MM-DD"),
              **stat_config(columns, averaged=False)}
    st.dataframe(table, hide_index=True, width="stretch", height=560, column_config=config, placeholder="—")
    csv = table.rename(columns={**fixed, **{c: LABELS[c] for c in columns}})
    st.download_button("Download as CSV", csv.to_csv(index=False).encode("utf-8"), mime="text/csv",
                       file_name=f"{player['full_name'].replace(' ', '_').lower()}_{season}_games.csv")
    st.caption(f"Newest first. Date ({LOCAL_NAME}) is when the game happened in {LOCAL_NAME}; the NBA dates games "
               f"by US time (US date). Pick more datasets with the Columns buttons above. Share of team: his share "
               f"of the team's total while he was on the court.")

# ---------------------------------------------------------------- charts
with tab_charts:
    c_stats, c_rolling = st.columns([3, 1], vertical_alignment="bottom")
    chart_stats = c_stats.multiselect("Stats to chart (type to search every dataset)", list(LABELS),
                                      default=DEFAULT_CHART_STATS, key="game_logs_chart_stats",
                                      format_func=lambda c: f"{LABELS[c]} · {DATASET_OF[c]}")
    rolling = c_rolling.segmented_control("Rolling average (games)", list(ROLLING), default="5",
                                          key="game_logs_rolling")
    window = ROLLING.get(rolling, 1)

    def game_chart(stat):
        label = LABELS[stat]
        data = view.assign(value=view[stat] * (100 if stat in FRACTIONS else 1))
        data["rolling"] = data["value"].rolling(window, min_periods=1).mean()
        x = alt.X("game_date:T", title=None)
        tooltip = [alt.Tooltip("local_label:N", title="Date"), alt.Tooltip("matchup:N", title="Game"),
                   alt.Tooltip("result:N", title="Result"), alt.Tooltip("value:Q", title=label, format=".1f"),
                   alt.Tooltip("minutes:Q", title="Minutes", format=".0f")]
        if window > 1:
            tooltip.insert(4, alt.Tooltip("rolling:Q", title=f"{window}-game average", format=".1f"))
        average = alt.Chart(pd.DataFrame({"avg": [data["value"].mean()]})).mark_rule(
            color=NEUTRAL, strokeDash=[4, 4]).encode(y="avg:Q")
        dots = alt.Chart(data).mark_circle(size=45, color=NEUTRAL, opacity=0.9).encode(
            x=x, y=alt.Y("value:Q", title=label), tooltip=tooltip)
        layers = average + dots
        if window > 1:
            layers += alt.Chart(data).mark_line(color=SERIES, strokeWidth=2.5).encode(x=x, y="rolling:Q")
        return layers.properties(title=label)

    if not chart_stats:
        st.info("Pick at least one stat to chart.")
    chart_grid(chart_stats, game_chart, per_row=2, height=300)
    rolling_note = f" Blue line: the average of his last {window} games." if window > 1 else ""
    st.caption(f"Grey dots: each game. Dashed line: his average over these games.{rolling_note} "
               f"Hover a dot for the game.")

# ---------------------------------------------------------------- averages and splits
with tab_splits:
    rows = pd.DataFrame([{"split": label, **averages(split_games, columns)} for label, split_games in splits(view)])
    st.dataframe(pd.concat([rows[["split", "games"]], as_shown(rows, columns)], axis=1), hide_index=True,
                 width="stretch", height=ROW_HEIGHT * (len(rows) + 1) + 3, placeholder="—",
                 column_config={"split": "Split", "games": "Games", **stat_config(columns, averaged=True)})
    st.caption("Per-game averages. Shooting percentages are from his totals (all makes over all attempts); other "
               "percentages and ratings are averages of each game's figure. Rest = full days off before the game. "
               "Started / off the bench needs the tracking job's data for the season.")

# ---------------------------------------------------------------- career
with tab_career:
    career = games[games["season_type"].isin(SEASON_TYPES[season_type])]
    by_season = pd.DataFrame([{"season": s, **averages(g, list(LABELS))} for s, g in career.groupby("season")])
    st.dataframe(pd.concat([by_season[["season", "games"]], as_shown(by_season, columns)], axis=1),
                 hide_index=True, width="stretch", placeholder="—",
                 column_config={"season": "Season", "games": "Games", **stat_config(columns, averaged=True)})

    career_stat = st.selectbox("Chart", list(LABELS), index=list(LABELS).index("pts"), key="game_logs_career_stat",
                               format_func=lambda c: f"{LABELS[c]} · {DATASET_OF[c]}")
    label = LABELS[career_stat]
    bars = by_season.assign(
        value=by_season[career_stat] * (100 if career_stat in FRACTIONS else 1),
        which=(by_season["season"] == season).map({True: "Selected season", False: "Other seasons"}))
    chart = alt.Chart(bars).mark_bar(cornerRadiusEnd=3).encode(
        x=alt.X("season:N", title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("value:Q", title=f"{label} per game"),
        color=alt.Color("which:N", title=None, scale=alt.Scale(domain=["Selected season", "Other seasons"],
                                                               range=[SERIES, NEUTRAL]),
                        legend=alt.Legend(orient="top")),
        tooltip=[alt.Tooltip("season:N", title="Season"), alt.Tooltip("value:Q", title=label, format=".1f"),
                 alt.Tooltip("games:Q", title="Games")])
    st.altair_chart(chart.properties(height=300), width="stretch")
    st.caption(f"Per-game averages in {SEASON_TYPE_TEXT[season_type]} games, season by season. The database holds "
               f"2017-18 onwards; tracking, "
               f"passing, touches and hustle start in 2025-26 until the tracking backfill runs.")

# ---------------------------------------------------------------- team
with tab_team:
    teams = queries.teams()
    team = teams[teams["abbreviation"] == team_abbr].iloc[0]
    team_games = queries.team_season_games(season)
    team_games = team_games[team_games["team_id"] == team["team_id"]].sort_values("game_date")
    st.subheader(f"{team['full_name']}: {season} regular season")
    if team_games.empty:
        st.info(f"No {season} regular-season games loaded for {team_abbr}.")
    else:
        team_games = team_games.assign(
            result=team_games["wl"] + " " + team_games["pts"].astype(int).astype(str) + "–"
            + team_games["opp_pts"].astype(int).astype(str),
            fg_pct=team_games["fgm"] / team_games["fga"],
            fg3_pct=team_games["fg3m"] / team_games["fg3a"],
            ft_pct=(team_games["ftm"] / team_games["fta"]).where(team_games["fta"] > 0))

        margins = team_games.assign(game_no=range(1, len(team_games) + 1),
                                    margin=team_games["pts"] - team_games["opp_pts"],
                                    outcome=team_games["wl"].map({"W": "Win", "L": "Loss"}))
        chart = alt.Chart(margins).mark_bar(cornerRadiusEnd=2).encode(
            x=alt.X("game_no:O", title="Game", axis=alt.Axis(values=list(range(1, 83, 5)), labelAngle=0)),
            y=alt.Y("margin:Q", title="Points won or lost by"),
            color=alt.Color("outcome:N", title=None, scale=alt.Scale(domain=["Win", "Loss"],
                                                                     range=[SERIES, LOSS_COLOR]),
                            legend=alt.Legend(orient="top")),
            tooltip=[alt.Tooltip("game_no:O", title="Game"),
                     alt.Tooltip("game_date:T", title="US date", format="%a %d %b %Y"),
                     alt.Tooltip("matchup:N", title="Game"), alt.Tooltip("result:N", title="Result"),
                     alt.Tooltip("margin:Q", title="Margin", format="+d")])
        st.altair_chart(chart.properties(height=260), width="stretch")

        fixed = {"game_date": "US date", "matchup": "Game", "result": "Result"}
        if team_abbr in set(games.loc[games["season"] == season, "team_abbreviation"]):
            played = set(games.loc[games["season"] == season, "game_id"])
            team_games["played"] = team_games["game_id"].isin(played).map({True: "Yes", False: "No"})
            fixed["played"] = "He played"
        log = team_games.sort_values("game_date", ascending=False)
        st.dataframe(pd.concat([log[list(fixed)], as_shown(log, TEAM_COLUMNS)], axis=1), hide_index=True,
                     width="stretch", height=480, placeholder="—", column_config={
                         **fixed, "game_date": st.column_config.DateColumn("US date", format="YYYY-MM-DD"),
                         **stat_config(TEAM_COLUMNS, averaged=False),
                         "opp_pts": st.column_config.NumberColumn("Opp pts", format="%d")})
        st.caption("Regular season only, like the Team stats in the sidebar; pick another team there. Ratings are "
                   "points scored (off) or allowed (def) per 100 possessions in that game.")
