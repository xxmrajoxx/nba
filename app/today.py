"""Today page: the games on a date, the players whose birthday falls within 3 days of it,
their form this season, and how each of them has played around his birthday in past years."""
from datetime import date, timedelta

import altair as alt
import pandas as pd
import streamlit as st

import queries
from common import (BACKGROUND, HIGHLIGHT, LOCAL_NAME, NEUTRAL, PHASES, STATS, birthday_label, birthday_on,
                    require_data, style_page, to_local)

DAY_KEY = "today_page_day"
BIRTHDAY_WINDOW = 3     # players whose birthday is this many days either side of the chosen date
HISTORY_WINDOW = 4      # past games shown this many days either side of each birthday
DEFAULT_STATS = ["pts", "fg3m"]
CHARTS_PER_ROW = 3
CHART_HEIGHT = 260
PHASE_LABELS = ["Before", "On birthday", "After"]
PHASE_COLORS = [PHASES[p][1] for p in ("before", "on", "after")]
BIRTHDAY_COLOR = PHASES["on"][1]
# Stats in the season summary, which reads box-score columns only.
BOX_SCORE_STATS = ["pts", "reb", "ast", "fg3m", "fg3a", "fgm", "fga", "minutes", "stl", "blk", "tov", "plus_minus", "ts_pct"]

style_page()
st.sidebar.title("🎂 Today")
require_data()


# ---------------------------------------------------------------- helpers
def shift_day(days: int) -> None:
    st.session_state[DAY_KEY] = st.session_state[DAY_KEY] + timedelta(days=days)


def go_to(day: date) -> None:
    st.session_state[DAY_KEY] = day


def set_panels(keys: list, open_: bool) -> None:
    for key in keys:
        st.session_state[key] = open_


def season_of(day: date) -> str:
    start = day.year if day.month >= 10 else day.year - 1
    return f"{start}-{str(start + 1)[-2:]}"


def when_from_day(offset: int) -> str:
    if offset == 0:
        return "Today"
    days = f"{abs(offset)} day{'s' if abs(offset) != 1 else ''}"
    return f"In {days}" if offset > 0 else f"{days} ago"


def highlight(table: pd.DataFrame, rows: pd.Series):
    """A pandas Styler that tints the rows where `rows` is True."""
    rows = rows.reindex(table.index).fillna(False).astype(bool)
    return table.style.apply(
        lambda row: [f"background-color: {HIGHLIGHT}" if rows[row.name] else "" for _ in row], axis=1)


def percent_or_blank(made: pd.Series, attempts: pd.Series, pct: pd.Series) -> pd.Series:
    """A shooting percentage, left blank when there were no attempts rather than showing 0%."""
    return (pct * 100).round(1).where(attempts > 0)


def game_log_table(df: pd.DataFrame, stats: list) -> pd.DataFrame:
    """One row per game: the fixed box-score columns, plus any selected stats not already in them."""
    local = to_local(df["tipoff_et"]).set_axis(df.index)
    table = pd.DataFrame({
        f"Date ({LOCAL_NAME})": local.dt.strftime("%Y-%m-%d"),
        "Day": local.dt.strftime("%A"),
        "Tip-off": local.dt.strftime("%I:%M %p").str.lstrip("0"),
        "Game": df["matchup"],
        "W/L": df["wl"],
        "US date": df["game_date"].dt.strftime("%Y-%m-%d"),
        "Birthday": df["days_from_birthday"].map(lambda d: birthday_label(int(d)) if abs(d) <= HISTORY_WINDOW else ""),
        "Min": df["minutes"].round(1),
        "Pts": df["pts"],
        "FGM": df["fgm"], "FGA": df["fga"], "FG %": percent_or_blank(df["fgm"], df["fga"], df["fg_pct"]),
        "3PM": df["fg3m"], "3PA": df["fg3a"], "3P %": percent_or_blank(df["fg3m"], df["fg3a"], df["fg3_pct"]),
        "Reb": df["reb"], "Ast": df["ast"], "Stl": df["stl"], "Blk": df["blk"], "TOV": df["tov"],
        "+/-": df["plus_minus"],
        "TS %": (df["ts_pct"] * 100).round(1).where((df["fga"] > 0) | (df["fta"] > 0)),
    }, index=df.index)
    for stat in stats:
        if stat in ("usg_pct", "pct_fga", "pct_ast_fgm") and stat in df:
            label, _, scale = STATS[stat]
            table[label] = (df[stat] * scale).round(1)
    return table


PCT_COLUMNS = {"FG %", "3P %", "TS %", "Usage rate", "Share of team shot attempts", "% of made shots assisted"}


def show_table(table: pd.DataFrame, rows: pd.Series = None) -> None:
    """A table with optional highlighted rows. Number formats go through Streamlit's column
    settings (it shows raw numbers from a pandas Styler), and empty cells show a dash."""
    config = {}
    for column in table.columns:
        if column in PCT_COLUMNS:
            config[column] = st.column_config.NumberColumn(column, format="%.1f%%")
        elif pd.api.types.is_float_dtype(table[column]):
            config[column] = st.column_config.NumberColumn(column, format="%.1f")
    data = highlight(table, rows) if rows is not None else table
    st.dataframe(data, hide_index=True, width="stretch", column_config=config, placeholder="—")


def chart_grid(stats: list, make_chart) -> None:
    """Small multiples: one chart per stat, each with its own scale, CHARTS_PER_ROW to a row."""
    for start in range(0, len(stats), CHARTS_PER_ROW):
        columns = st.columns(CHARTS_PER_ROW)
        for column, stat in zip(columns, stats[start:start + CHARTS_PER_ROW]):
            with column:
                # An explicit element height: in narrow columns the chart's own height isn't kept.
                st.altair_chart(make_chart(stat), width="stretch", height=CHART_HEIGHT)


# ---------------------------------------------------------------- the date
st.session_state.setdefault(DAY_KEY, date.today())
c_prev, c_date, c_next, c_today = st.columns([1, 3, 1, 1], vertical_alignment="bottom")
c_prev.button("← Previous day", on_click=shift_day, args=(-1,), width="stretch")
c_date.date_input("NBA date (US)", key=DAY_KEY, format="YYYY-MM-DD",
                  help=f"The NBA dates games by US time. Evening games in the US are the next day in {LOCAL_NAME}.")
c_next.button("Next day →", on_click=shift_day, args=(1,), width="stretch")
c_today.button("Today", on_click=go_to, args=(date.today(),), width="stretch")
day = st.session_state[DAY_KEY]

# ---------------------------------------------------------------- data for the day
players = queries.players()
games = queries.games_on(day)
season = games["season"].iloc[0] if not games.empty else season_of(day)


def nearest_birthday(birthdate: date) -> date:
    """His birthday closest to the chosen day (it can fall in the previous or next year near New Year)."""
    candidates = [birthday_on(birthdate, year) for year in (day.year - 1, day.year, day.year + 1)]
    return min(candidates, key=lambda b: abs((b - day).days))


born = players[players["birthdate"].notna()].copy()
born["birthdate"] = pd.to_datetime(born["birthdate"]).dt.date
born["birthday"] = born["birthdate"].map(nearest_birthday)
born["offset"] = born["birthday"].map(lambda b: (b - day).days)       # + = still to come, - = already passed
birthdays = born[born["offset"].abs() <= BIRTHDAY_WINDOW].copy()
birthdays["turns"] = birthdays.apply(lambda r: r["birthday"].year - r["birthdate"].year, axis=1)
birthdays["when"] = birthdays["offset"].map(when_from_day)

team_games = {}
for g in games.itertuples():
    matchup = f"{g.away_team_tricode} @ {g.home_team_tricode}"
    team_games[g.away_team_tricode] = (matchup, g.game_status_text)
    team_games[g.home_team_tricode] = (matchup, g.game_status_text)
birthdays["game"] = birthdays["team"].map(lambda t: team_games.get(t, (None, None))[0])
birthdays["status"] = birthdays["team"].map(lambda t: team_games.get(t, (None, None))[1])
birthdays["playing"] = birthdays["game"].notna()
birthdays["distance"] = birthdays["offset"].abs()
# Players on the court that day first, then the closest birthdays.
birthdays = birthdays.sort_values(["playing", "distance", "offset", "full_name"],
                                  ascending=[False, True, True, True]).reset_index(drop=True)

# ---------------------------------------------------------------- header
st.title(day.strftime("%A %d %B %Y"))
if not games.empty:
    local_days = sorted(set(to_local(games["game_datetime_est"]).dt.date.dropna()))
    in_local = " and ".join(d.strftime("%A %d %B") for d in local_days)
    st.markdown(f"**US date.** In {LOCAL_NAME}, these games are on **{in_local}**.")
st.caption(f"Season {season}. The NBA dates games by US time, and the birthday analysis uses that date, the day the "
           f"game was played where it was played. Teams are today's rosters, so for past dates a traded player shows "
           f"with his current team. Highlighted rows: birthday players whose team plays on this day.")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Games scheduled", len(games))
m2.metric("Birthdays today", int((birthdays["offset"] == 0).sum()))
m3.metric(f"Birthdays within {BIRTHDAY_WINDOW} days", len(birthdays))
m4.metric("Birthday players in action", int(birthdays["playing"].sum()))

# ---------------------------------------------------------------- games and birthdays, side by side
left, right = st.columns([1.15, 1], gap="large")
with left:
    st.subheader("Games")
    if games.empty:
        st.info("No games scheduled on this date.")
        nearest = queries.nearest_game_dates(day).iloc[0]
        if pd.notna(nearest["previous_date"]):
            prev_day = pd.to_datetime(nearest["previous_date"]).date()
            st.button(f"← Previous game day: {prev_day:%d %b %Y}", on_click=go_to, args=(prev_day,))
        if pd.notna(nearest["next_date"]):
            next_day = pd.to_datetime(nearest["next_date"]).date()
            st.button(f"Next game day: {next_day:%d %b %Y} →", on_click=go_to, args=(next_day,))
    else:
        names_by_team = {}
        for p in birthdays[birthdays["playing"]].itertuples():
            note = "" if p.offset == 0 else f" ({p.when.lower()})"
            names_by_team.setdefault(p.team, []).append(f"{p.full_name}{note}")
        local_tipoff = to_local(games["game_datetime_est"])
        game_table = pd.DataFrame({
            f"{LOCAL_NAME} time": local_tipoff.dt.strftime("%a %I:%M %p").str.replace(" 0", " ", regex=False),
            "US (ET)": games["game_datetime_est"].dt.strftime("%I:%M %p").str.lstrip("0"),
            "Game": games["away_team_tricode"] + " @ " + games["home_team_tricode"],
            "Score": [f"{int(a)}–{int(h)}" if pd.notna(a) and pd.notna(h) else ""
                      for a, h in zip(games["away_pts"], games["home_pts"])],
            "Status": games["game_status_text"],
            "Birthday players": [
                ", ".join(names_by_team.get(g.away_team_tricode, []) + names_by_team.get(g.home_team_tricode, []))
                for g in games.itertuples()
            ],
        })
        st.dataframe(highlight(game_table, game_table["Birthday players"] != ""), hide_index=True, width="stretch")
        if games["game_label"].notna().any():
            st.caption("Special games: " + ", ".join(sorted(set(games["game_label"].dropna()))))

with right:
    st.subheader(f"Birthdays within {BIRTHDAY_WINDOW} days")
    if birthdays.empty:
        st.info(f"No active players have a birthday within {BIRTHDAY_WINDOW} days of {day:%d %B}.")
    else:
        bday_table = pd.DataFrame({
            "Player": birthdays["full_name"],
            "Team": birthdays["team"].fillna("FA"),
            "Birthday": birthdays["birthday"].map(lambda b: b.strftime("%a %d %b")),
            "When": birthdays["when"],
            "Turns": birthdays["turns"],
            "Playing": birthdays["game"].fillna(""),
        })
        st.dataframe(highlight(bday_table, birthdays["playing"]), hide_index=True, width="stretch")

if birthdays.empty:
    st.stop()

# ---------------------------------------------------------------- this season so far
season_df = queries.season_games(season)
season_df = season_df[season_df["game_date"] <= pd.Timestamp(day)]
mine = season_df[season_df["player_id"].isin(birthdays["player_id"])]

st.subheader(f"This season so far: {season}")
if mine.empty:
    st.info(f"None of these players has a {season} game loaded up to {day:%d %b %Y}. Load the season with "
            f"`run_job.py game_logs --season {season}`.")
else:
    totals = mine.groupby("player_id").agg(
        gp=("game_id", "count"), minutes=("minutes", "mean"), pts=("pts", "mean"), reb=("reb", "mean"),
        ast=("ast", "mean"), fg3m=("fg3m", "mean"), fg3a=("fg3a", "mean"), fgm=("fgm", "mean"), fga=("fga", "mean"),
        stl=("stl", "mean"), blk=("blk", "mean"), tov=("tov", "mean"), plus_minus=("plus_minus", "mean"),
        pts_sum=("pts", "sum"), fgm_sum=("fgm", "sum"), fga_sum=("fga", "sum"), fg3m_sum=("fg3m", "sum"),
        fg3a_sum=("fg3a", "sum"), fta_sum=("fta", "sum"))
    totals["fg_pct"] = (totals["fgm_sum"] / totals["fga_sum"]).where(totals["fga_sum"] > 0)
    totals["fg3_pct"] = (totals["fg3m_sum"] / totals["fg3a_sum"]).where(totals["fg3a_sum"] > 0)
    shots = 2 * (totals["fga_sum"] + 0.44 * totals["fta_sum"])
    totals["ts_pct"] = (totals["pts_sum"] / shots).where(shots > 0)
    last = mine.sort_values("game_date").groupby("player_id").tail(1)
    last = last.assign(local_date=to_local(last["tipoff_et"]).set_axis(last.index)).set_index("player_id")
    summary = birthdays[["player_id", "full_name", "team", "playing"]].join(totals, on="player_id")
    summary["last_game"] = summary["player_id"].map(
        lambda pid: f"{last.loc[pid, 'local_date']:%d %b}: {last.loc[pid, 'matchup']}, {int(last.loc[pid, 'pts'])} pts"
        if pid in last.index and pd.notna(last.loc[pid, 'local_date']) else "")

    summary_table = pd.DataFrame({
        "Player": summary["full_name"],
        "GP": summary["gp"].fillna(0).astype(int),
        "Min": summary["minutes"].round(1), "Pts": summary["pts"].round(1), "Reb": summary["reb"].round(1),
        "Ast": summary["ast"].round(1), "3PM": summary["fg3m"].round(1), "3PA": summary["fg3a"].round(1),
        "3P %": (summary["fg3_pct"] * 100).round(1), "FG %": (summary["fg_pct"] * 100).round(1),
        f"Last game ({LOCAL_NAME} date)": summary["last_game"],
    })
    t_left, t_right = st.columns([1.9, 1], gap="large")
    with t_left:
        show_table(summary_table, summary["playing"])
        st.caption(f"Per-game averages over {season} games up to {day:%d %b %Y}.")
    with t_right:
        chart_stat = st.selectbox("Chart", BOX_SCORE_STATS, format_func=lambda s: STATS[s][0] + " per game",
                                  key="today_season_chart", label_visibility="collapsed")
        label, unit, scale = STATS[chart_stat]
        bars = summary[summary["gp"].fillna(0) > 0].assign(
            value=lambda d: d[chart_stat] * scale,
            status=lambda d: d["playing"].map({True: "Plays on this day", False: "Not playing"}))
        chart = alt.Chart(bars).mark_bar(cornerRadiusEnd=4).encode(
            x=alt.X("value:Q", title=f"{label} per game"),
            y=alt.Y("full_name:N", title=None, sort="-x"),
            color=alt.Color("status:N", title=None,
                            scale=alt.Scale(domain=["Plays on this day", "Not playing"], range=[BIRTHDAY_COLOR, NEUTRAL]),
                            legend=alt.Legend(orient="top")),
            tooltip=[alt.Tooltip("full_name:N", title="Player"), alt.Tooltip("team:N", title="Team"),
                     alt.Tooltip("value:Q", title=f"{label} per game", format=".1f"),
                     alt.Tooltip("gp:Q", title="Games")])
        st.altair_chart(chart.properties(height=alt.Step(30)), width="stretch", height=max(170, 32 * len(bars) + 90))

# ---------------------------------------------------------------- the players, one panel each
st.subheader("Birthday players: this season and past birthdays")
panel_keys = [f"today_panel_{int(pid)}" for pid in birthdays["player_id"]]
# Open by default: players in action on their actual birthday, or the top panel if there are
# none. Each open panel loads his whole career, so busy dates stay quick; "Expand all" opens the rest.
open_by_default = set(birthdays.loc[birthdays["playing"] & (birthdays["offset"] == 0), "player_id"])
if not open_by_default:
    open_by_default = {birthdays["player_id"].iloc[0]}
for key, pid in zip(panel_keys, birthdays["player_id"]):
    st.session_state.setdefault(key, pid in open_by_default)

with st.container(border=True):
    chosen = st.pills("Stats to chart (pick any number)", list(STATS), selection_mode="multi", default=DEFAULT_STATS,
                      format_func=lambda s: STATS[s][0], key="today_stats")
    c_all, c_window, c_filter, c_open, c_close = st.columns([1, 2.4, 1.8, 0.9, 0.9], vertical_alignment="bottom")
    all_stats = c_all.toggle("All stats", key="today_all_stats")
    window_choice = c_window.segmented_control(
        "Past games", [f"{HISTORY_WINDOW} days either side of the birthday", "On the birthday only"],
        default=f"{HISTORY_WINDOW} days either side of the birthday", key="today_window")
    only_playing = c_filter.toggle("Only players in action on this day", key="today_only_playing")
    c_open.button("Expand all", on_click=set_panels, args=(panel_keys, True), width="stretch")
    c_close.button("Collapse all", on_click=set_panels, args=(panel_keys, False), width="stretch")

stats = list(STATS) if all_stats else (chosen or ["pts"])
window = 0 if window_choice == "On the birthday only" else HISTORY_WINDOW
st.caption("Panels load their data when opened. Highlighted rows in the game logs are games around his birthday.")

shown = birthdays[birthdays["playing"]] if only_playing else birthdays
if shown.empty:
    st.info("None of these players' teams plays on this day.")

for key, p in zip(panel_keys, birthdays.itertuples()):
    if only_playing and not p.playing:
        continue
    label = f"**{p.full_name}** · {p.team or 'FA'} · birthday {p.when.lower()} · turns {p.turns}"
    if p.playing:
        label += f" · plays {p.game}"
    icon = ":material/sports_basketball:" if p.playing else ":material/cake:"
    with st.expander(label, key=key, on_change="rerun", icon=icon):
        if not st.session_state.get(key):
            continue                                   # closed: don't load anything
        with st.container(horizontal=True):
            if p.playing:
                st.badge(f"Plays on this day: {p.game} · {p.status}", color="orange",
                         icon=":material/sports_basketball:")
            st.badge(f"Birthday {p.birthday:%a %d %b} ({p.when.lower()})", color="violet", icon=":material/cake:")
            st.badge(f"Turns {p.turns}", color="gray")

        games_p = queries.player_games(int(p.player_id))
        if games_p.empty:
            st.info("No games loaded for him yet.")
            continue
        regular = games_p[games_p["season_type"] == "Regular Season"]
        tab_season, tab_history = st.tabs([f"This season ({season})", "Past birthdays"])

        # ---- this season: every game so far, newest first
        with tab_season:
            this = games_p[(games_p["season"] == season) & (games_p["game_date"] <= pd.Timestamp(day))]
            if this.empty:
                st.info(f"No {season} games loaded for him up to this date.")
            else:
                this = this.sort_values("game_date")
                cards = st.columns(min(len(stats), 6))
                for i, stat in enumerate(stats):
                    stat_label, _, scale = STATS[stat]
                    cards[i % len(cards)].metric(f"{stat_label} per game", f"{(this[stat] * scale).mean():.1f}")

                opponent = this["matchup"].map(lambda m: ("@ " if "@" in m else "vs ") + m.split()[-1])
                local_date = to_local(this["tipoff_et"]).set_axis(this.index)
                this = this.assign(near_birthday=this["days_from_birthday"].abs() <= HISTORY_WINDOW,
                                   game=local_date.dt.strftime("%d %b") + " " + opponent,
                                   local_label=local_date.dt.strftime(f"%a %d %b %Y, %I:%M %p ({LOCAL_NAME})"))
                this["kind"] = this["near_birthday"].map({True: "Around his birthday", False: "Other games"})
                order = list(this["game"])

                def season_chart(stat):
                    stat_label, unit, scale = STATS[stat]
                    data = this.assign(value=this[stat] * scale)
                    average = alt.Chart(pd.DataFrame({"avg": [data["value"].mean()]})).mark_rule(
                        color=NEUTRAL, strokeDash=[4, 4]).encode(y="avg:Q")
                    bars = alt.Chart(data).mark_bar(cornerRadiusEnd=3).encode(
                        x=alt.X("game:N", title=None, sort=order, axis=alt.Axis(labelAngle=-45, labelLimit=80)),
                        y=alt.Y("value:Q", title=stat_label),
                        color=alt.Color("kind:N", title=None,
                                        scale=alt.Scale(domain=["Around his birthday", "Other games"],
                                                        range=[BIRTHDAY_COLOR, "#5b5a55"]),
                                        legend=alt.Legend(orient="top")),
                        tooltip=[alt.Tooltip("local_label:N", title="Date"),
                                 alt.Tooltip("matchup:N", title="Game"), alt.Tooltip("wl:N", title="Result"),
                                 alt.Tooltip("value:Q", title=stat_label, format=".1f")])
                    return (bars + average).properties(title=stat_label)

                chart_grid(stats, season_chart)
                st.caption(f"Dashed line: his average so far this season. Dates are {LOCAL_NAME} dates.")
                log = this.sort_values("game_date", ascending=False)
                show_table(game_log_table(log, stats), log["near_birthday"])

        # ---- past birthdays: games around each birthday, every year
        with tab_history:
            hist = games_p[games_p["days_from_birthday"].abs() <= window].copy()
            if hist.empty:
                st.info("No games this close to his birthday in the data. Birthdays from about July to September "
                        "fall in the off-season, and early-to-mid October ones in the preseason, which isn't loaded.")
                continue
            hist["birthday_year"] = (hist["game_date"] - pd.to_timedelta(hist["days_from_birthday"], unit="D")).dt.year
            hist["year"] = hist["birthday_year"].astype(str)
            hist["when"] = hist["days_from_birthday"].map(birthday_label)
            hist["phase_label"] = hist["days_from_birthday"].map(
                lambda d: PHASE_LABELS[0] if d < 0 else PHASE_LABELS[1] if d == 0 else PHASE_LABELS[2])
            hist = hist.sort_values("game_date")
            hist["local_label"] = to_local(hist["tipoff_et"]).set_axis(hist.index).dt.strftime(
                f"%a %d %b %Y, %I:%M %p ({LOCAL_NAME})")
            years = sorted(hist["year"].unique())

            rows = []
            for stat in stats:
                stat_label, unit, scale = STATS[stat]
                averages = regular.groupby("season")[stat].mean() * scale
                in_games = hist[stat] * scale
                season_avg = hist["season"].map(averages)
                rows.append({"Stat": stat_label, "Birthday games": len(hist),
                             "In those games": in_games.mean(), "His season averages": season_avg.mean(),
                             "Difference": (in_games - season_avg).mean()})
            compare = pd.DataFrame(rows).round(1)
            st.dataframe(compare, hide_index=True, width="stretch", placeholder="—", column_config={
                "In those games": st.column_config.NumberColumn(format="%.1f"),
                "His season averages": st.column_config.NumberColumn(format="%.1f"),
                "Difference": st.column_config.NumberColumn(format="%+.1f")})
            st.caption("Season averages are his regular-season averages in the same seasons, weighted by those games. "
                       "A handful of games, so mostly luck; the Model tab on the Player explorer page tests it properly.")

            def history_chart(stat):
                stat_label, unit, scale = STATS[stat]
                averages = regular.groupby("season")[stat].mean() * scale
                data = hist.assign(value=hist[stat] * scale, season_avg=hist["season"].map(averages))
                avg_by_year = data.groupby("year", as_index=False)["season_avg"].mean()
                x = alt.X("year:O", title=None, sort=years, axis=alt.Axis(labelAngle=0))
                ticks = alt.Chart(avg_by_year).mark_tick(color=NEUTRAL, thickness=3, size=40).encode(
                    x=x, y=alt.Y("season_avg:Q", title=stat_label),
                    tooltip=[alt.Tooltip("year:O", title="Year"),
                             alt.Tooltip("season_avg:Q", title="Season average", format=".1f")])
                dots = alt.Chart(data).mark_circle(size=90, opacity=0.95, stroke=BACKGROUND, strokeWidth=1).encode(
                    x=x, y="value:Q", xOffset=alt.XOffset("days_from_birthday:O"),
                    color=alt.Color("phase_label:N", title=None, sort=PHASE_LABELS,
                                    scale=alt.Scale(domain=PHASE_LABELS, range=PHASE_COLORS),
                                    legend=alt.Legend(orient="top")),
                    tooltip=[alt.Tooltip("local_label:N", title="Date"),
                             alt.Tooltip("when:N", title="When"), alt.Tooltip("matchup:N", title="Game"),
                             alt.Tooltip("wl:N", title="Result"), alt.Tooltip("value:Q", title=stat_label, format=".1f"),
                             alt.Tooltip("season_avg:Q", title="Season average", format=".1f")])
                return (ticks + dots).properties(title=stat_label)

            chart_grid(stats, history_chart)
            st.caption("Each birthday year: a dot per game (blue before, orange on the day, green after) against a "
                       "grey line for his regular-season average that season.")
            log = hist.sort_values("game_date", ascending=False)
            table = game_log_table(log, stats)
            table.insert(0, "Year", log["birthday_year"])
            show_table(table, log["days_from_birthday"] == 0)
            st.caption(f"Highlighted: games on his birthday itself. Dates are {LOCAL_NAME} dates; "
                       f"\"Birthday\" counts from the US date the game was played.")
