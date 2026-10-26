"""Today page: the games on a date, the players whose birthday falls within 3 days of it, and
how each of them has played around his birthday in past years."""
from datetime import date, timedelta

import altair as alt
import pandas as pd
import streamlit as st

import queries
from common import NEUTRAL, PHASES, STATS, birthday_label, birthday_on, require_data

DAY_KEY = "today_page_day"
BIRTHDAY_WINDOW = 3     # players whose birthday is this many days either side of the chosen date
HISTORY_WINDOW = 4      # past games shown this many days either side of each birthday
PHASE_LABELS = ["Before", "On birthday", "After"]
PHASE_COLORS = [PHASES[p][1] for p in ("before", "on", "after")]

st.sidebar.title("🎂 Today")
require_data()


# ---------------------------------------------------------------- choosing the date
def shift_day(days: int) -> None:
    st.session_state[DAY_KEY] = st.session_state[DAY_KEY] + timedelta(days=days)


def go_to(day: date) -> None:
    st.session_state[DAY_KEY] = day


st.session_state.setdefault(DAY_KEY, date.today())
c_prev, c_date, c_next, c_today = st.columns([1, 3, 1, 1], vertical_alignment="bottom")
c_prev.button("← Previous day", on_click=shift_day, args=(-1,), width="stretch")
c_date.date_input("Date", key=DAY_KEY, format="YYYY-MM-DD")
c_next.button("Next day →", on_click=shift_day, args=(1,), width="stretch")
c_today.button("Today", on_click=go_to, args=(date.today(),), width="stretch")
day = st.session_state[DAY_KEY]

st.title(day.strftime("%A %d %B %Y"))
st.caption("Dates and tip-off times follow the NBA schedule, which uses US Eastern time. Teams are today's rosters, "
           "so for past dates a traded player shows with his current team.")

# ---------------------------------------------------------------- data for the day
players = queries.players()
games = queries.games_on(day)


def nearest_birthday(birthdate: date) -> date:
    """His birthday closest to the chosen day (it can fall in the previous or next year near New Year)."""
    candidates = [birthday_on(birthdate, year) for year in (day.year - 1, day.year, day.year + 1)]
    return min(candidates, key=lambda b: abs((b - day).days))


def when_from_day(offset: int) -> str:
    if offset == 0:
        return "Today"
    days = f"{abs(offset)} day{'s' if abs(offset) != 1 else ''}"
    return f"In {days}" if offset > 0 else f"{days} ago"


born = players[players["birthdate"].notna()].copy()
born["birthdate"] = pd.to_datetime(born["birthdate"]).dt.date
born["birthday"] = born["birthdate"].map(nearest_birthday)
born["offset"] = born["birthday"].map(lambda b: (b - day).days)       # + = still to come, - = already passed
birthdays = born[born["offset"].abs() <= BIRTHDAY_WINDOW].copy()
birthdays["turns"] = birthdays.apply(lambda r: r["birthday"].year - r["birthdate"].year, axis=1)
birthdays["when"] = birthdays["offset"].map(when_from_day)

# Which birthday players' teams play on the chosen day, and in which game.
team_games = {}
for g in games.itertuples():
    matchup = f"{g.away_team_tricode} @ {g.home_team_tricode}"
    team_games[g.away_team_tricode] = (matchup, g.game_status_text)
    team_games[g.home_team_tricode] = (matchup, g.game_status_text)
birthdays["game"] = birthdays["team"].map(lambda t: team_games.get(t, (None, None))[0])
birthdays["status"] = birthdays["team"].map(lambda t: team_games.get(t, (None, None))[1])
birthdays["playing"] = birthdays["game"].notna()
birthdays["sort_key"] = birthdays["offset"].abs()
birthdays = birthdays.sort_values(["sort_key", "offset", "playing", "full_name"], ascending=[True, True, False, True])

m1, m2, m3, m4 = st.columns(4)
m1.metric("Games scheduled", len(games))
m2.metric("Birthdays today", int((birthdays["offset"] == 0).sum()))
m3.metric(f"Birthdays within {BIRTHDAY_WINDOW} days", len(birthdays))
m4.metric("Of those, playing today", int(birthdays["playing"].sum()))

# ---------------------------------------------------------------- games
st.subheader("Games")
if games.empty:
    st.info("No games scheduled on this date.")
    nearest = queries.nearest_game_dates(day).iloc[0]
    b1, b2 = st.columns(2)
    if pd.notna(nearest["previous_date"]):
        prev_day = pd.to_datetime(nearest["previous_date"]).date()
        b1.button(f"← Previous game day: {prev_day:%d %b %Y}", on_click=go_to, args=(prev_day,))
    if pd.notna(nearest["next_date"]):
        next_day = pd.to_datetime(nearest["next_date"]).date()
        b2.button(f"Next game day: {next_day:%d %b %Y} →", on_click=go_to, args=(next_day,))
else:
    playing = birthdays[birthdays["playing"]]
    names_by_team = {}
    for p in playing.itertuples():
        note = "" if p.offset == 0 else f" ({p.when.lower()})"
        names_by_team.setdefault(p.team, []).append(f"{p.full_name}{note}")
    table = pd.DataFrame({
        "Tip-off (ET)": games["game_datetime_est"].dt.strftime("%I:%M %p").str.lstrip("0"),
        "Game": games["away_team_tricode"] + " @ " + games["home_team_tricode"],
        "Type": games["game_label"].fillna(""),
        "Status": games["game_status_text"],
        "Arena": games["arena_name"],
        "City": games["arena_city"],
        "Birthday players": [
            ", ".join(names_by_team.get(g.away_team_tricode, []) + names_by_team.get(g.home_team_tricode, []))
            for g in games.itertuples()
        ],
    })
    st.dataframe(table, hide_index=True, width="stretch")
    st.caption(f"Birthday players: anyone whose birthday is within {BIRTHDAY_WINDOW} days of this date.")

# ---------------------------------------------------------------- birthdays
st.subheader(f"Birthdays within {BIRTHDAY_WINDOW} days")
if birthdays.empty:
    st.info(f"No active players have a birthday within {BIRTHDAY_WINDOW} days of {day:%d %B}.")
    st.stop()

st.dataframe(
    pd.DataFrame({
        "Player": birthdays["full_name"],
        "Team": birthdays["team"].fillna("Free agent"),
        "Birthday": birthdays["birthday"].map(lambda b: b.strftime("%a %d %b")),
        "When": birthdays["when"],
        "Turns": birthdays["turns"],
        "Born": pd.to_datetime(birthdays["birthdate"]).dt.strftime("%m-%d-%Y"),
        "Playing this day": birthdays["game"].fillna("—"),
        "Status": birthdays["status"].fillna(""),
    }),
    hide_index=True, width="stretch",
)

# ---------------------------------------------------------------- past birthdays
st.subheader("How they've played on past birthdays")
c_stat, c_window = st.columns(2)
stat = c_stat.selectbox("Stat", list(STATS), format_func=lambda s: STATS[s][0], key="today_stat")
window_choice = c_window.radio("Games", [f"{HISTORY_WINDOW} days either side of the birthday", "On the birthday only"],
                               horizontal=True, key="today_window")
window = 0 if window_choice == "On the birthday only" else HISTORY_WINDOW
stat_label, stat_unit, stat_scale = STATS[stat]
st.caption(f"Each year: his {stat_label.lower()} in games around his birthday (dots), against his regular-season "
           f"average that season (grey line). Hover for details. Single games are noisy; one big night says little.")

for p in birthdays.itertuples():
    playing_note = f" · plays this day: {p.game}" if p.playing else ""
    title = f"**{p.full_name}** ({p.team or 'FA'}) · birthday {p.when.lower()} · turns {p.turns}{playing_note}"
    with st.expander(title, expanded=bool(p.playing or p.offset == 0)):
        games_p = queries.player_games(int(p.player_id))
        if games_p.empty:
            st.info("No games loaded for him yet.")
            continue

        regular = games_p[games_p["season_type"] == "Regular Season"]
        season_avg = (regular.groupby("season")[stat].mean() * stat_scale).rename("season_avg")

        hist = games_p[games_p["days_from_birthday"].abs() <= window].copy()
        if hist.empty:
            st.info("No games this close to his birthday in the data. Birthdays from about July to September fall "
                    "in the off-season, and early-to-mid October ones in the preseason, which isn't loaded.")
            continue

        hist["value"] = hist[stat] * stat_scale
        hist["birthday_year"] = (hist["game_date"] - pd.to_timedelta(hist["days_from_birthday"], unit="D")).dt.year
        hist = hist.join(season_avg, on="season")
        hist["difference"] = hist["value"] - hist["season_avg"]
        hist["when"] = hist["days_from_birthday"].map(birthday_label)
        # Phase from the day itself: the views' phases stop at 3 days, this page goes to HISTORY_WINDOW.
        hist["phase_label"] = hist["days_from_birthday"].map(
            lambda d: PHASE_LABELS[0] if d < 0 else PHASE_LABELS[1] if d == 0 else PHASE_LABELS[2])
        hist = hist.sort_values("game_date")

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Birthday games", len(hist), help=f"Games within {window} days of his birthday" if window else None)
        k2.metric(f"{stat_label} in those games", f"{hist['value'].mean():.1f}")
        k3.metric("His season averages", f"{hist['season_avg'].mean():.1f}",
                  help="His regular-season average in the same seasons, weighted by those games.")
        k4.metric("Difference", f"{hist['difference'].mean():+.1f}",
                  help="A handful of games, so mostly luck. The Model tab on the Player explorer page tests this properly.")

        years = [str(y) for y in sorted(hist["birthday_year"].unique())]
        hist["year"] = hist["birthday_year"].astype(str)
        averages = hist.groupby("year", as_index=False)["season_avg"].mean()
        x = alt.X("year:O", title="Birthday year", sort=years, axis=alt.Axis(labelAngle=0))
        ticks = alt.Chart(averages).mark_tick(color=NEUTRAL, thickness=3, size=70).encode(
            x=x, y=alt.Y("season_avg:Q", title=stat_label),
            tooltip=[alt.Tooltip("year:O", title="Year"), alt.Tooltip("season_avg:Q", title="Season average", format=".1f")])
        dots = alt.Chart(hist).mark_circle(size=110, opacity=0.9, stroke="white", strokeWidth=1).encode(
            x=x, y="value:Q",
            color=alt.Color("phase_label:N", title=None, sort=PHASE_LABELS,
                            scale=alt.Scale(domain=PHASE_LABELS, range=PHASE_COLORS), legend=alt.Legend(orient="top")),
            xOffset=alt.XOffset("days_from_birthday:O"),
            tooltip=[alt.Tooltip("game_date:T", title="Date", format="%a %d %b %Y"), alt.Tooltip("when:N", title="When"),
                     alt.Tooltip("matchup:N", title="Game"), alt.Tooltip("wl:N", title="Result"),
                     alt.Tooltip("value:Q", title=stat_label, format=".1f"),
                     alt.Tooltip("season_avg:Q", title="Season average", format=".1f"),
                     alt.Tooltip("difference:Q", title="Difference", format="+.1f")])
        st.altair_chart((ticks + dots).properties(height=260), width="stretch")

        table = pd.DataFrame({
            "Year": hist["birthday_year"],
            "Date": hist["game_date"].dt.strftime("%Y-%m-%d"),
            "Day": hist["game_date"].dt.strftime("%A"),
            "When": hist["when"],
            "Game": hist["matchup"],
            "W/L": hist["wl"],
            "Min": hist["minutes"].round(1),
            "Pts": hist["pts"],
            # Percentages are left blank when there were no attempts, rather than showing 0%.
            "FGM": hist["fgm"], "FGA": hist["fga"], "FG %": (hist["fg_pct"] * 100).round(1).where(hist["fga"] > 0),
            "3PM": hist["fg3m"], "3PA": hist["fg3a"], "3P %": (hist["fg3_pct"] * 100).round(1).where(hist["fg3a"] > 0),
            "Reb": hist["reb"], "Ast": hist["ast"],
            "TS %": (hist["ts_pct"] * 100).round(1).where((hist["fga"] > 0) | (hist["fta"] > 0)),
        })
        if stat not in ("pts", "reb", "ast", "minutes", "ts_pct", "fga"):     # not already a column above
            table[stat_label] = hist["value"].round(1)
        table[f"{stat_label}: season avg"] = hist["season_avg"].round(1)
        table[f"{stat_label}: difference"] = hist["difference"].round(1)
        st.dataframe(table.sort_values("Date", ascending=False), hide_index=True, width="stretch",
                     column_config={"FG %": st.column_config.NumberColumn(format="%.1f%%"),
                                    "3P %": st.column_config.NumberColumn(format="%.1f%%"),
                                    "TS %": st.column_config.NumberColumn(format="%.1f%%")})
