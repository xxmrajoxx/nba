"""Player explorer page: pick a player, filter his games, and see how he plays around his birthday."""
from datetime import date

import altair as alt
import pandas as pd
import streamlit as st

import model_results
import queries
from common import (NEUTRAL, PHASE_ORDER, PHASES, SERIES, STATS, birthday_label,
                    next_birthday, require_data)

# Game log column groups, and fractions shown as percentages.
LOG_GROUPS = {
    "Box score": ["minutes", "pts", "reb", "ast", "stl", "blk", "tov", "pf", "plus_minus"],
    "Shooting": ["fgm", "fga", "fg_pct", "fg3m", "fg3a", "fg3_pct", "ftm", "fta", "ft_pct", "ts_pct", "efg_pct"],
    "Advanced": ["usg_pct", "off_rating", "def_rating", "net_rating", "pie"],
    "Usage splits": ["pct_fga", "pct_pts", "pct_ast_fgm"],
    "Context": ["days_rest", "back_to_back", "key_teammates_out", "top_scorer_out", "tipoff_hour_et", "arena_city", "is_starter"],
    "Tracking": ["dist_miles", "avg_speed", "passes_received", "touches", "deflections"],
}
PCT_COLUMNS = ["fg_pct", "fg3_pct", "ft_pct", "ts_pct", "efg_pct", "usg_pct", "pct_fga", "pct_pts", "pct_ast_fgm"]
LOG_LABELS = {
    "minutes": "Min", "pts": "Pts", "reb": "Reb", "ast": "Ast", "stl": "Stl", "blk": "Blk", "tov": "TOV", "pf": "PF",
    "plus_minus": "+/-", "fgm": "FGM", "fga": "FGA", "fg_pct": "FG %", "fg3m": "3PM", "fg3a": "3PA", "fg3_pct": "3P %",
    "ftm": "FTM", "fta": "FTA", "ft_pct": "FT %", "ts_pct": "TS %", "efg_pct": "eFG %", "usg_pct": "Usage %",
    "off_rating": "Off rating", "def_rating": "Def rating", "net_rating": "Net rating", "pie": "PIE",
    "pct_fga": "Team shot share %", "pct_pts": "Team points share %", "pct_ast_fgm": "Assisted makes %",
    "days_rest": "Days rest", "back_to_back": "Back-to-back", "key_teammates_out": "Key teammates out",
    "top_scorer_out": "Top scorer out", "tipoff_hour_et": "Tip-off hour (ET)", "arena_city": "Arena city",
    "is_starter": "Starter", "dist_miles": "Miles run", "avg_speed": "Avg speed (mph)",
    "passes_received": "Passes received", "touches": "Touches", "deflections": "Deflections",
}


MODEL_PHASES = {"before": "1-3 days before", "on": "On birthday", "after": "1-3 days after"}
MODEL_PHASE_ORDER = list(MODEL_PHASES.values())
AGE_GROUPS = ["Under 25", "25-29", "30+"]
AGE_COLORS = ["#2a78d6", "#eb6834", "#1baf7a"]


def zero_line():
    return alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color=NEUTRAL).encode(y="y:Q")


def interval_tooltip(unit: str) -> list:
    return [alt.Tooltip("estimate:Q", title=f"Estimate ({unit})", format="+.2f"),
            alt.Tooltip("ci_low:Q", title="95% interval from", format="+.2f"),
            alt.Tooltip("ci_high:Q", title="95% interval to", format="+.2f"),
            alt.Tooltip("games:Q", title="Games", format=","),
            alt.Tooltip("q_value:Q", title="q-value", format=".2f")]


def phase_interval_chart(data: pd.DataFrame, unit: str, by_age: bool = False):
    """Estimates as dots with 95% interval lines, one per birthday phase (and age group)."""
    data = data.assign(phase_name=data["phase"].map(MODEL_PHASES))
    x = alt.X("phase_name:N", title=None, sort=MODEL_PHASE_ORDER, axis=alt.Axis(labelAngle=0))
    y_title = f"vs his usual ({unit})"
    tooltip = [alt.Tooltip("phase_name:N", title="When")] + interval_tooltip(unit)
    extra = {}
    if by_age:
        tooltip.insert(1, alt.Tooltip("age_group:N", title="Turning"))
        extra = {"xOffset": alt.XOffset("age_group:N", sort=AGE_GROUPS),
                 "color": alt.Color("age_group:N", title="Age he turns", sort=AGE_GROUPS,
                                    scale=alt.Scale(domain=AGE_GROUPS, range=AGE_COLORS),
                                    legend=alt.Legend(orient="top"))}
    style = {} if by_age else {"color": SERIES}
    rules = alt.Chart(data).mark_rule(strokeWidth=2.5, opacity=0.5, **style).encode(
        x=x, y=alt.Y("ci_low:Q", title=y_title), y2="ci_high:Q", tooltip=tooltip, **extra)
    dots = alt.Chart(data).mark_circle(size=120, opacity=1, stroke="white", strokeWidth=1.5, **style).encode(
        x=x, y="estimate:Q", tooltip=tooltip, **extra)
    return zero_line() + rules + dots


def format_interval(row) -> str:
    return f"{row.estimate:+.2f} ({row.ci_low:+.2f} to {row.ci_high:+.2f})"


# ---------------------------------------------------------------- sidebar: player and filters
st.sidebar.title("🏀 Birthday Explorer")
require_data()
players = queries.players()

labels = players["full_name"] + players["team"].fillna("FA").map(lambda t: f"  ({t})")
default = players.index[players["full_name"] == "LeBron James"]
choice = st.sidebar.selectbox("Player", players.index, format_func=lambda i: labels[i],
                              index=int(default[0]) if len(default) else 0)
player = players.loc[choice]

games = queries.player_games(int(player["player_id"]))
if games.empty:
    st.title(player["full_name"])
    st.info("No games loaded for this player yet. Rookies appear once the game_logs job has loaded their games.")
    st.stop()

games["phase_label"] = games["birthday_phase"].map(lambda p: PHASES[p][0])
games["birthday_note"] = games["days_from_birthday"].map(birthday_label)

st.sidebar.header("Filters")
all_seasons = sorted(games["season"].unique())
seasons = st.sidebar.multiselect("Seasons", all_seasons, default=all_seasons)
season_types = st.sidebar.multiselect("Season type", ["Regular Season", "Playoffs"], default=["Regular Season", "Playoffs"])
phases = st.sidebar.multiselect("Birthday phase", PHASE_ORDER, default=PHASE_ORDER)
day_range = st.sidebar.slider("Days from birthday", -183, 183, (-183, 183),
                              help="Negative = before the birthday, 0 = on it, positive = after.")
location = st.sidebar.radio("Location", ["All", "Home", "Away"], horizontal=True)
result = st.sidebar.radio("Result", ["All", "Wins", "Losses"], horizontal=True)

mask = (
    games["season"].isin(seasons)
    & games["season_type"].isin(season_types)
    & games["phase_label"].isin(phases)
    & games["days_from_birthday"].between(*day_range)
)
if location != "All":
    mask &= games["is_home"] == (location == "Home")
if result != "All":
    mask &= games["wl"] == ("W" if result == "Wins" else "L")
filtered = games[mask]

st.sidebar.header("Charts")
stat = st.sidebar.selectbox("Stat", list(STATS), format_func=lambda s: STATS[s][0])
stat_label, stat_unit, stat_scale = STATS[stat]

# ---------------------------------------------------------------- header
today = date.today()
birthdate = pd.to_datetime(player["birthdate"]).date() if pd.notnull(player["birthdate"]) else None

st.title(player["full_name"])
details = [player["team_name"] or "Free agent", player["position"], player["height"],
           f"{int(player['weight_lbs'])} lbs" if pd.notnull(player["weight_lbs"]) else None, player["country"]]
st.caption(" · ".join(str(d) for d in details if pd.notnull(d) and d))

if birthdate:
    upcoming, days_until, turning = next_birthday(birthdate, today)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Birthday", player["birthdate_mdy"])
    c2.metric("Next birthday", "Today! 🎂" if days_until == 0 else f"in {days_until} days",
              help=upcoming.strftime("%A %d %B %Y"))
    c3.metric("Turns", turning)
    c4.metric("Games in view", f"{len(filtered):,}", help="Games matching the filters, out of "
              f"{len(games):,} loaded for this player.")

if filtered.empty:
    st.warning("No games match the filters.")
    st.stop()

values = filtered[stat] * stat_scale
in_week = filtered["is_birthday_week"].astype(bool)
c1, c2, c3, c4 = st.columns(4)
c1.metric(f"{stat_label}: birthday week", f"{values[in_week].mean():.1f}" if in_week.any() else "–",
          delta=f"{values[in_week].mean() - values[~in_week].mean():+.1f} vs other games" if in_week.any() and (~in_week).any() else None)
c2.metric(f"{stat_label}: other games", f"{values[~in_week].mean():.1f}" if (~in_week).any() else "–")
c3.metric("Birthday-week games", int(in_week.sum()))
c4.metric("Games on his birthday", int(filtered["is_birthday"].astype(bool).sum()))

# ---------------------------------------------------------------- tabs
tab_effect, tab_model, tab_log, tab_seasons, tab_missed, tab_league, tab_pipeline = st.tabs(
    ["Birthday effect", "Model", "Game log", "Season by season", "Missed games", "League", "Pipeline"]
)

with tab_effect:
    st.subheader(f"{stat_label} by days from birthday")
    st.caption(f"Average for each day within two weeks of his birthday, compared with his average across all games in view. "
               f"Shaded: the birthday week (±3 days). Hover a bar for details.")
    near = filtered[filtered["days_from_birthday"].between(-14, 14)].copy()
    if near.empty:
        st.info("No games within 14 days of his birthday match the filters. Off-season birthdays (roughly July to September) never do.")
    else:
        near["value"] = near[stat] * stat_scale
        by_day = near.groupby("days_from_birthday").agg(average=("value", "mean"), games=("value", "count")).reset_index()
        by_day["difference"] = by_day["average"] - values.mean()
        by_day["when"] = by_day["days_from_birthday"].map(birthday_label)

        band = alt.Chart(pd.DataFrame({"start": [-3.5], "end": [3.5]})).mark_rect(color=NEUTRAL, opacity=0.15).encode(
            x="start:Q", x2="end:Q")
        zero = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color=NEUTRAL).encode(y="y:Q")
        bars = alt.Chart(by_day).mark_bar(color=SERIES, size=16, cornerRadiusEnd=3).encode(
            x=alt.X("days_from_birthday:Q", title="Days from birthday (0 = birthday)",
                    scale=alt.Scale(domain=[-14.5, 14.5]), axis=alt.Axis(values=list(range(-14, 15, 2)))),
            y=alt.Y("difference:Q", title=f"vs his average ({stat_unit})"),
            tooltip=[alt.Tooltip("when:N", title="When"),
                     alt.Tooltip("average:Q", title=stat_label, format=".1f"),
                     alt.Tooltip("difference:Q", title="vs his average", format="+.1f"),
                     alt.Tooltip("games:Q", title="Games")],
        )
        st.altair_chart((band + zero + bars).properties(height=320), width="stretch")
        st.caption("Each bar is usually only a handful of games, so expect a lot of noise for a single player.")

    st.subheader(f"{stat_label}, game by game")
    timeline = filtered.assign(value=filtered[stat] * stat_scale)
    color = alt.Color("phase_label:N", title=None, sort=PHASE_ORDER,
                      scale=alt.Scale(domain=PHASE_ORDER, range=[c for _, c in PHASES.values()]),
                      legend=alt.Legend(orient="top"))
    tooltip = [alt.Tooltip("game_date:T", title="Date", format="%d %b %Y"), alt.Tooltip("matchup:N", title="Game"),
               alt.Tooltip("wl:N", title="Result"), alt.Tooltip("birthday_note:N", title="Birthday"),
               alt.Tooltip("value:Q", title=stat_label, format=".1f"), alt.Tooltip("minutes:Q", title="Minutes", format=".0f")]
    points = alt.Chart(timeline).mark_circle(size=45, opacity=0.85).encode(
        x=alt.X("game_date:T", title=None), y=alt.Y("value:Q", title=stat_label), color=color, tooltip=tooltip,
        order=alt.Order("is_birthday_week:Q"),          # birthday games drawn on top
    )
    st.altair_chart(points.properties(height=320).interactive(), width="stretch")
    st.caption("Scroll to zoom, drag to pan, double-click to reset.")

    st.subheader("Averages by birthday phase")
    summary_cols = ["minutes", "pts", "reb", "ast", "tov", "ts_pct", "usg_pct", "pct_fga"]
    summary = filtered.groupby("phase_label")[summary_cols].mean()
    summary[["ts_pct", "usg_pct", "pct_fga"]] *= 100
    summary.insert(0, "games", filtered.groupby("phase_label").size())
    summary = summary.reindex([p for p in PHASE_ORDER if p in summary.index])
    summary.index.name = "Phase"
    st.dataframe(summary.round(1), width="stretch", column_config={
        "games": "Games", "minutes": "Min", "pts": "Pts", "reb": "Reb", "ast": "Ast", "tov": "TOV",
        "ts_pct": "TS %", "usg_pct": "Usage %", "pct_fga": "Team shot share %",
    })

    st.subheader("What the model says about him")
    if not model_results.available():
        st.caption(f"Run the models to see this: `{model_results.RUN_COMMAND}`")
    else:
        effects = model_results.results()["player_effects"]
        mine = effects[(effects["player_id"] == player["player_id"]) & (effects["outcome"] == stat)]
        if stat not in set(effects["outcome"]):
            st.caption("The per-player model covers " + ", ".join(sorted(set(effects["label"])))
                       + ". Pick one of those as the chart stat in the sidebar.")
        elif mine.empty:
            st.caption("He has no birthday-week regular-season games in the model yet.")
        else:
            r = mine.iloc[0]
            st.caption(f"His regular-season birthday-week games (all seasons, ignoring the sidebar filters) against his "
                       f"games in the surrounding month. The raw figure is just his average; the adjusted figure "
                       f"accounts for how few birthday games he has played ({int(r.games)}).")
            m1, m2, m3 = st.columns(3)
            m1.metric("His raw birthday-week effect", f"{r.raw:+.2f} {r.unit}")
            m2.metric("Model-adjusted", f"{r.adjusted:+.2f} {r.unit}",
                      help="Shrunk towards the league figure in proportion to how little evidence there is.")
            m3.metric("League (all players)", f"{r.league:+.2f} {r.unit}")
            compare = pd.DataFrame({
                "what": ["His raw average", "Model-adjusted", "League"],
                "estimate": [r.raw, r.adjusted, r.league],
                "ci_low": [r.raw_low, r.adjusted_low, r.league],
                "ci_high": [r.raw_high, r.adjusted_high, r.league],
            })
            y = alt.Y("what:N", title=None, sort=list(compare["what"]))
            tip = [alt.Tooltip("what:N", title=" "), alt.Tooltip("estimate:Q", title=f"Estimate ({r.unit})", format="+.2f"),
                   alt.Tooltip("ci_low:Q", title="95% from", format="+.2f"), alt.Tooltip("ci_high:Q", title="95% to", format="+.2f")]
            chart = (
                alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(color=NEUTRAL).encode(x="x:Q")
                + alt.Chart(compare).mark_rule(strokeWidth=2.5, opacity=0.5, color=SERIES).encode(
                    y=y, x=alt.X("ci_low:Q", title=f"Birthday week vs nearby games ({r.unit})"), x2="ci_high:Q", tooltip=tip)
                + alt.Chart(compare).mark_circle(size=140, opacity=1, color=SERIES, stroke="white", strokeWidth=1.5).encode(
                    y=y, x="estimate:Q", tooltip=tip)
            )
            st.altair_chart(chart.properties(height=170), width="stretch")
            if r.weight < 0.05:
                st.info("Across all players, birthday-week differences are no bigger than luck would produce, so the "
                        "model's best estimate for him is the league figure. His raw number is mostly noise.")
            else:
                st.info(f"The model keeps {r.weight:.0%} of his own difference and fills the rest in from the league, "
                        f"because {int(r.games)} games is too few to trust on their own.")

with tab_model:
    if not model_results.available():
        st.info("No model results yet. Run the models from the project folder, then press R to reload this page:\n\n"
                f"`{model_results.RUN_COMMAND}`")
    else:
        res = model_results.results()
        info, phase_df = res["info"], res["phase_effects"]
        st.caption(f"League-wide models from `src/models`, last run {info.get('run_at', '?').replace('T', ' ')} on "
                   f"{info.get('games', 0):,} regular-season games from {info.get('players', 0)} players "
                   f"({' to '.join(info.get('seasons', []))}). Each player is compared with himself in the same season, "
                   f"adjusted for week of season, home/away, back-to-backs, teammates out and opponent strength. "
                   f"The sidebar filters don't apply here.")

        significant = phase_df[phase_df["significant"]]
        if significant.empty:
            st.success(f"**No birthday effect found.** None of the {len(phase_df)} before / on / after estimates is "
                       f"significant once corrected for testing many stats at once.")
        else:
            found = ", ".join(f"{r.label} {MODEL_PHASES[r.phase].lower()}" for r in significant.itertuples())
            st.warning(f"**{len(significant)} significant result(s)** after correcting for multiple tests: {found}.")

        day_hits = res["event_study"][res["event_study"]["significant"]]
        if not day_hits.empty:
            hits = "; ".join(f"{r.label} {birthday_label(int(r.day))} ({r.estimate:+.1f} {r.unit}, q = {r.q_value:.2f})"
                             for r in day_hits.itertuples())
            st.info(f"**Worth watching:** in the day-by-day model, {hits} survives the correction. It doesn't show up "
                    f"in the pooled before / on / after model, so it's an isolated single day rather than a pattern. "
                    f"More seasons of data will show whether it holds up.")

        options = list(dict.fromkeys(phase_df["outcome"]))
        names = dict(zip(phase_df["outcome"], phase_df["label"]))
        model_stat = st.selectbox("Stat", options, index=options.index(stat) if stat in options else 0,
                                  format_func=names.get, key="model_stat")
        stat_rows = phase_df[phase_df["outcome"] == model_stat]
        unit = stat_rows["unit"].iloc[0]

        left, right = st.columns(2)
        with left:
            st.subheader(f"{names[model_stat]}: before, on and after")
            st.altair_chart(phase_interval_chart(stat_rows, unit).properties(height=300), width="stretch")
            hypothesis = stat_rows["hypothesis"].iloc[0]
            tests = "general performance" if hypothesis == "Overall" else f"\"{hypothesis.lower()}\""
            st.caption(f"Tests: {tests}. A dot whose line crosses zero is indistinguishable from no effect.")
        with right:
            availability = res["availability"]
            st.subheader("Did he play at all?")
            st.altair_chart(phase_interval_chart(availability, "% points").properties(height=300), width="stretch")
            st.caption(f"Change in the chance of playing, against a normal rate of "
                       f"{availability['normal_play_rate'].iloc[0]:.0f}% of team games. A hangover could show up "
                       f"as sitting out rather than playing badly.")

        st.subheader(f"{names[model_stat]}, day by day")
        days = res["event_study"]
        days = days[days["outcome"] == model_stat].assign(when=lambda d: d["day"].map(birthday_label))
        x = alt.X("day:Q", title="Days from birthday (0 = birthday)", scale=alt.Scale(domain=[-7.5, 7.5]),
                  axis=alt.Axis(values=list(range(-7, 8)), format="d"))
        tip = [alt.Tooltip("when:N", title="When")] + interval_tooltip(unit)
        band = alt.Chart(pd.DataFrame({"start": [-3.5], "end": [3.5]})).mark_rect(color=NEUTRAL, opacity=0.15).encode(
            x="start:Q", x2="end:Q")
        day_chart = (band + zero_line()
                     + alt.Chart(days).mark_rule(strokeWidth=2.5, opacity=0.5, color=SERIES).encode(
                         x=x, y=alt.Y("ci_low:Q", title=f"vs his usual ({unit})"), y2="ci_high:Q", tooltip=tip)
                     + alt.Chart(days).mark_circle(size=90, opacity=1, color=SERIES, stroke="white", strokeWidth=1.5).encode(
                         x=x, y="estimate:Q", tooltip=tip))
        st.altair_chart(day_chart.properties(height=300), width="stretch")
        st.caption("One estimate per day, so each rests on fewer games and has a wider interval than the pooled chart above.")

        st.subheader(f"{names[model_stat]}, by the age he turns")
        ages = res["phase_by_age"]
        st.altair_chart(phase_interval_chart(ages[ages["outcome"] == model_stat], unit, by_age=True)
                        .properties(height=320), width="stretch")
        st.caption("Does a 22nd birthday play differently from a 34th? Only a few dozen games per group on the day "
                   "itself, so these intervals are wide.")

        st.subheader("Every stat")
        table = phase_df.assign(text=phase_df.apply(format_interval, axis=1)).pivot_table(
            index=["label", "hypothesis"], columns="phase", values="text", aggfunc="first")
        table = table[["before", "on", "after"]].rename(columns=MODEL_PHASES)
        table["Lowest q-value"] = phase_df.groupby(["label", "hypothesis"])["q_value"].min().round(2)
        st.dataframe(table.reset_index().rename(columns={"label": "Stat", "hypothesis": "Tests"}),
                     hide_index=True, width="stretch")
        st.caption("Estimate and 95% interval, in each stat's own units. q-values below 0.05 would be significant.")
        if info.get("skipped_outcomes"):
            st.caption("Not modelled yet, waiting for the tracking job: " + ", ".join(info["skipped_outcomes"]) + ".")
        st.caption(f"To refresh after loading new data: `{model_results.RUN_COMMAND}`, then press R here.")

with tab_log:
    groups = st.multiselect("Columns", list(LOG_GROUPS), default=["Box score", "Shooting"])
    birthday_only = st.toggle("Birthday week only")
    log = filtered[filtered["is_birthday_week"].astype(bool)] if birthday_only else filtered
    columns = ["game_date", "season", "matchup", "wl", "birthday_note"] + [c for g in groups for c in LOG_GROUPS[g]]
    table = log[columns].copy()
    for col in set(PCT_COLUMNS) & set(table.columns):
        table[col] = table[col] * 100
    config = {"game_date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
              "season": "Season", "matchup": "Game", "wl": "W/L", "birthday_note": "Birthday"}
    for col in table.columns:
        if col in PCT_COLUMNS:
            config[col] = st.column_config.NumberColumn(LOG_LABELS[col], format="%.1f%%")
        elif col in ("minutes", "pie", "off_rating", "def_rating", "net_rating", "dist_miles", "avg_speed"):
            config[col] = st.column_config.NumberColumn(LOG_LABELS[col], format="%.1f")
        elif col in LOG_LABELS:
            config[col] = LOG_LABELS[col]
    st.dataframe(table, width="stretch", hide_index=True, column_config=config, height=520)
    st.download_button("Download as CSV", table.to_csv(index=False).encode("utf-8"),
                       file_name=f"{player['full_name'].replace(' ', '_').lower()}_games.csv", mime="text/csv")
    if "Tracking" in groups:
        st.caption("Tracking columns stay empty until the tracking job has loaded those dates.")

with tab_seasons:
    st.caption("Regular season only. Birthday-week averages against the rest of the same season (from dbo.v_birthday_week_vs_season).")
    seasons_df = queries.player_seasons(int(player["player_id"]))
    if seasons_df.empty:
        st.info("No season has both birthday-week games and other games for this player.")
    else:
        for s in ["pts", "reb", "ast", "minutes", "ts_pct", "plus_minus"]:
            seasons_df[f"{s}_diff"] = seasons_df[f"birthday_week_{s}"] - seasons_df[f"other_{s}"]
        st.dataframe(
            seasons_df[["season", "birthday_week_games", "other_games", "birthday_week_pts", "other_pts", "pts_diff",
                        "birthday_week_minutes", "other_minutes", "minutes_diff", "ts_pct_diff"]].round(2),
            width="stretch", hide_index=True,
            column_config={"season": "Season", "birthday_week_games": "B'day wk games", "other_games": "Other games",
                           "birthday_week_pts": "B'day wk pts", "other_pts": "Other pts", "pts_diff": "Pts diff",
                           "birthday_week_minutes": "B'day wk min", "other_minutes": "Other min",
                           "minutes_diff": "Min diff", "ts_pct_diff": "TS % diff (fraction)"},
        )

with tab_missed:
    missed = queries.player_missed_games(int(player["player_id"]))
    st.caption("Games his team played, while he was on it, that he did not play in. Can't tell rest from injury, "
               "suspension or a G League assignment.")
    if missed.empty:
        st.info("No missed games found.")
    else:
        missed["phase_label"] = missed["birthday_phase"].map(lambda p: PHASES[p][0])
        counts = missed.groupby("phase_label").size().reindex(PHASE_ORDER, fill_value=0)
        cols = st.columns(4)
        for col, (label, n) in zip(cols, counts.items()):
            col.metric(f"Missed: {label.lower()}", int(n))
        missed["birthday_note"] = missed["days_from_birthday"].map(birthday_label)
        st.dataframe(missed[["game_date", "season", "season_type", "birthday_note"]], width="stretch", hide_index=True,
                     column_config={"game_date": "Date", "season": "Season", "season_type": "Type", "birthday_note": "Birthday"})

with tab_league:
    st.subheader("Upcoming birthday-week games")
    upcoming_df = queries.upcoming_birthday_games()
    if upcoming_df.empty:
        st.info("No upcoming games in anyone's birthday week. Load the schedule with the schedule job.")
    else:
        upcoming_df["birthday_note"] = upcoming_df["days_from_birthday"].map(birthday_label)
        upcoming_df["game_label"] = upcoming_df["game_label"].fillna("")   # empty for ordinary regular-season games
        on_day_only = st.toggle("Only games on the birthday itself")
        shown = upcoming_df[upcoming_df["days_from_birthday"] == 0] if on_day_only else upcoming_df
        st.dataframe(shown[["game_date", "full_name", "game", "game_label", "birthday_note"]], width="stretch",
                     hide_index=True, height=360,
                     column_config={"game_date": "Date", "full_name": "Player", "game": "Game",
                                    "game_label": "Type", "birthday_note": "Birthday"})

    st.subheader("Biggest birthday-week scorers, against their own average")
    min_games = st.slider("Minimum birthday-week games", 3, 20, 8)
    leaders = queries.league_birthday_leaders(min_games)
    if leaders.empty:
        st.info("No players with that many birthday-week games.")
    else:
        leaders = leaders.sort_values("pts_difference", ascending=False).round(2)
        cfg = {"full_name": "Player", "seasons": "Seasons", "birthday_week_games": "B'day wk games",
               "birthday_week_pts": "B'day wk pts", "other_pts": "Other pts", "pts_difference": "Difference"}
        left, right = st.columns(2)
        left.markdown("**Score more in their birthday week**")
        left.dataframe(leaders.head(10), hide_index=True, width="stretch", column_config=cfg)
        right.markdown("**Score less in their birthday week**")
        right.dataframe(leaders.tail(10).iloc[::-1], hide_index=True, width="stretch", column_config=cfg)
        st.caption("Small samples: most of these differences are luck. The league-wide event study "
                   "(src/models/event_study.py) found no overall birthday effect.")

with tab_pipeline:
    st.caption(f"The last 10 pipeline jobs, from etl.job_run. Data source: {queries.source_description()}. "
               "Data is cached in the app for 10 minutes.")
    st.dataframe(queries.pipeline_status(), width="stretch", hide_index=True)
    if st.button("Clear cache and reload data"):
        st.cache_data.clear()
        st.cache_resource.clear()    # also re-checks which data source to use
        st.rerun()
