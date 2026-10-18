-- Derived context built from the loaded tables (no extra API calls), and the modelling view.
-- Everything in the *_context views is known before tip-off, so it is safe to use as a
-- model input. Safe to re-run.

-- Days from the nearest birthday (negative = before) and the before / on / after phase.
-- The nearest birthday can fall in the previous or next calendar year (a Dec 30 birthday
-- and a Jan 1 game), so three candidates are checked and the closest kept.
CREATE OR ALTER FUNCTION dbo.fn_birthday_distance (@birthdate DATE, @game_date DATE)
RETURNS TABLE
AS RETURN
SELECT TOP (1)
    DATEDIFF(DAY, c.birthday, @game_date) AS days_from_birthday,
    CASE
        WHEN DATEDIFF(DAY, c.birthday, @game_date) = 0 THEN 'on'
        WHEN DATEDIFF(DAY, c.birthday, @game_date) BETWEEN -3 AND -1 THEN 'before'
        WHEN DATEDIFF(DAY, c.birthday, @game_date) BETWEEN 1 AND 3 THEN 'after'
        ELSE 'none'
    END AS birthday_phase
FROM (VALUES
    (DATEADD(YEAR, DATEDIFF(YEAR, @birthdate, @game_date) - 1, @birthdate)),
    (DATEADD(YEAR, DATEDIFF(YEAR, @birthdate, @game_date),     @birthdate)),
    (DATEADD(YEAR, DATEDIFF(YEAR, @birthdate, @game_date) + 1, @birthdate))
) AS c (birthday)
ORDER BY ABS(DATEDIFF(DAY, c.birthday, @game_date));
GO

-- Each team's form going into each game: averages over its earlier games that season.
CREATE OR ALTER VIEW dbo.v_team_game_context AS
SELECT
    team_id,
    game_id,
    season,
    game_date,
    COUNT(*)        OVER (PARTITION BY team_id, season ORDER BY game_date ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS games_before,
    AVG(off_rating) OVER (PARTITION BY team_id, season ORDER BY game_date ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS off_rating_to_date,
    AVG(def_rating) OVER (PARTITION BY team_id, season ORDER BY game_date ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS def_rating_to_date,
    AVG(net_rating) OVER (PARTITION BY team_id, season ORDER BY game_date ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS net_rating_to_date,
    AVG(pace)       OVER (PARTITION BY team_id, season ORDER BY game_date ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS pace_to_date,
    AVG(CASE WHEN wl = 'W' THEN 1.0 ELSE 0.0 END)
                    OVER (PARTITION BY team_id, season ORDER BY game_date ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS win_pct_to_date
FROM dbo.team_game_log;
GO

-- Each team's three highest scorers per season (players with 10+ games for that team),
-- and the date range they were on the team, so a traded player is not counted as
-- "missing" after he left.
-- Only players in dbo.player are in the game logs, so in older seasons a top scorer who
-- has since retired is not counted here.
CREATE OR ALTER VIEW dbo.v_team_key_players AS
WITH per_team AS (
    SELECT
        season,
        team_id,
        player_id,
        COUNT(*) AS games,
        AVG(CAST(pts AS FLOAT)) AS ppg,
        MIN(game_date) AS first_game,
        MAX(game_date) AS last_game
    FROM dbo.player_game_log
    WHERE minutes > 0
    GROUP BY season, team_id, player_id
    HAVING COUNT(*) >= 10
)
SELECT *
FROM (
    SELECT per_team.*, ROW_NUMBER() OVER (PARTITION BY season, team_id ORDER BY ppg DESC) AS scorer_rank
    FROM per_team
) AS ranked
WHERE scorer_rank <= 3;
GO

-- How many of each team's key players sat out each game. When a star sits, everyone
-- else's usage rises, which would otherwise look like "teammates feeding" a player.
-- Written as joins plus GROUP BY (not a per-game subquery) so the key players are worked
-- out once for all games instead of once per game.
CREATE OR ALTER VIEW dbo.v_team_game_absences AS
SELECT
    g.team_id,
    g.game_id,
    COUNT(CASE WHEN k.player_id IS NOT NULL AND x.player_id IS NULL THEN 1 END) AS key_players_out,
    CAST(MAX(CASE WHEN k.scorer_rank = 1 AND x.player_id IS NULL THEN 1 ELSE 0 END) AS BIT) AS top_scorer_out
FROM dbo.team_game_log AS g
LEFT JOIN dbo.v_team_key_players AS k
    ON k.season = g.season
   AND k.team_id = g.team_id
   AND g.game_date BETWEEN k.first_game AND k.last_game
LEFT JOIN dbo.player_game_log AS x
    ON x.player_id = k.player_id
   AND x.game_id = g.game_id
   AND x.minutes > 0
GROUP BY g.team_id, g.game_id;
GO

-- Games a player's team played, while he was on that team, that he did not play in.
-- Players who skip the game after their birthday drop out of the game logs, so without
-- this the tiredest players would silently disappear from the "after" phase.
-- Includes rest days, injuries, suspensions and G League assignments alike.
CREATE OR ALTER VIEW dbo.v_player_missed_games AS
WITH stints AS (
    SELECT player_id, team_id, season, MIN(game_date) AS first_game, MAX(game_date) AS last_game
    FROM dbo.player_game_log
    GROUP BY player_id, team_id, season
)
SELECT
    s.player_id,
    p.full_name,
    g.team_id,
    g.game_id,
    g.season,
    g.season_type,
    g.game_date,
    b.days_from_birthday,
    b.birthday_phase
FROM stints AS s
JOIN dbo.team_game_log AS g
    ON g.team_id = s.team_id
   AND g.season = s.season
   AND g.game_date BETWEEN s.first_game AND s.last_game
JOIN dbo.player AS p ON p.player_id = s.player_id
CROSS APPLY dbo.fn_birthday_distance(p.birthdate, g.game_date) AS b
WHERE NOT EXISTS (
    SELECT 1 FROM dbo.player_game_log AS x WHERE x.player_id = s.player_id AND x.game_id = g.game_id
);
GO

-- Everything known about a player going into a game: rest and schedule load, recent form,
-- whether key teammates are out, opponent strength so far, tip-off time and venue.
CREATE OR ALTER VIEW dbo.v_player_game_context AS
SELECT
    l.player_id,
    l.game_id,
    -- rest and schedule load (NULL for a player's first game of the season)
    DATEDIFF(DAY, LAG(l.game_date) OVER (PARTITION BY l.player_id, l.season ORDER BY l.game_date), l.game_date) AS days_rest,
    CAST(CASE WHEN DATEDIFF(DAY, LAG(l.game_date) OVER (PARTITION BY l.player_id, l.season ORDER BY l.game_date), l.game_date) = 1
              THEN 1 ELSE 0 END AS BIT) AS back_to_back,
    (SELECT COUNT(*) FROM dbo.player_game_log AS x
     WHERE x.player_id = l.player_id AND x.game_date >= DATEADD(DAY, -7, l.game_date) AND x.game_date < l.game_date) AS games_last_7_days,
    -- recent form: last 10 games and season to date, both excluding this game
    AVG(CAST(l.pts AS FLOAT)) OVER (PARTITION BY l.player_id, l.season ORDER BY l.game_date ROWS BETWEEN 10 PRECEDING AND 1 PRECEDING)        AS pts_last10,
    AVG(l.minutes)            OVER (PARTITION BY l.player_id, l.season ORDER BY l.game_date ROWS BETWEEN 10 PRECEDING AND 1 PRECEDING)        AS minutes_last10,
    AVG(CAST(l.fga AS FLOAT)) OVER (PARTITION BY l.player_id, l.season ORDER BY l.game_date ROWS BETWEEN 10 PRECEDING AND 1 PRECEDING)        AS fga_last10,
    AVG(l.usg_pct)            OVER (PARTITION BY l.player_id, l.season ORDER BY l.game_date ROWS BETWEEN 10 PRECEDING AND 1 PRECEDING)        AS usg_pct_last10,
    AVG(l.ts_pct)             OVER (PARTITION BY l.player_id, l.season ORDER BY l.game_date ROWS BETWEEN 10 PRECEDING AND 1 PRECEDING)        AS ts_pct_last10,
    AVG(CAST(l.pts AS FLOAT)) OVER (PARTITION BY l.player_id, l.season ORDER BY l.game_date ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS pts_to_date,
    AVG(l.minutes)            OVER (PARTITION BY l.player_id, l.season ORDER BY l.game_date ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS minutes_to_date,
    AVG(CAST(l.fga AS FLOAT)) OVER (PARTITION BY l.player_id, l.season ORDER BY l.game_date ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS fga_to_date,
    AVG(l.usg_pct)            OVER (PARTITION BY l.player_id, l.season ORDER BY l.game_date ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS usg_pct_to_date,
    AVG(l.ts_pct)             OVER (PARTITION BY l.player_id, l.season ORDER BY l.game_date ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS ts_pct_to_date,
    -- teammates: key players out (he played, so he is never counted among them)
    ab.key_players_out AS key_teammates_out,
    ab.top_scorer_out,
    -- opponent and own team form going into the game
    oc.def_rating_to_date AS opponent_def_rating_to_date,
    oc.off_rating_to_date AS opponent_off_rating_to_date,
    oc.net_rating_to_date AS opponent_net_rating_to_date,
    oc.pace_to_date       AS opponent_pace_to_date,
    oc.win_pct_to_date    AS opponent_win_pct_to_date,
    tc.net_rating_to_date AS team_net_rating_to_date,
    tc.win_pct_to_date    AS team_win_pct_to_date,
    -- tip-off time (US Eastern) and venue, from dbo.schedule
    s.game_datetime_est AS tipoff_et,
    DATEPART(HOUR, s.game_datetime_est) AS tipoff_hour_et,
    s.arena_city,
    s.arena_state,
    LAG(s.arena_city) OVER (PARTITION BY l.player_id, l.season ORDER BY l.game_date) AS previous_arena_city
FROM dbo.player_game_log AS l
LEFT JOIN dbo.v_team_game_absences AS ab ON ab.team_id = l.team_id AND ab.game_id = l.game_id
LEFT JOIN dbo.v_team_game_context AS tc ON tc.team_id = l.team_id AND tc.game_id = l.game_id
LEFT JOIN dbo.team_game_log AS opp ON opp.game_id = l.game_id AND opp.team_id <> l.team_id
LEFT JOIN dbo.v_team_game_context AS oc ON oc.team_id = opp.team_id AND oc.game_id = l.game_id
LEFT JOIN dbo.schedule AS s ON s.game_id = l.game_id;
GO

-- One wide row per player per game for modelling.
--   * birthday columns, box score and advanced stats (v_player_game_birthday)
--   * pre-game context (v_player_game_context): safe as model inputs
--   * usage, tracking, passing, touches, hustle, team and opponent totals: these describe
--     the game itself, so they are outcomes to explain, not inputs to predict with
-- Columns from a job that has not loaded a game yet are NULL.
CREATE OR ALTER VIEW dbo.v_player_game_features AS
SELECT
    b.*,
    bd.birthday_phase,
    -- pre-game context
    c.days_rest, c.back_to_back, c.games_last_7_days,
    c.pts_last10, c.minutes_last10, c.fga_last10, c.usg_pct_last10, c.ts_pct_last10,
    c.pts_to_date, c.minutes_to_date, c.fga_to_date, c.usg_pct_to_date, c.ts_pct_to_date,
    c.key_teammates_out, c.top_scorer_out,
    c.opponent_def_rating_to_date, c.opponent_off_rating_to_date, c.opponent_net_rating_to_date,
    c.opponent_pace_to_date, c.opponent_win_pct_to_date, c.team_net_rating_to_date, c.team_win_pct_to_date,
    c.tipoff_et, c.tipoff_hour_et, c.arena_city, c.arena_state, c.previous_arena_city,
    t.is_starter,
    -- usage and scoring splits
    u.pct_fga, u.pct_fg3a, u.pct_fta, u.pct_pts, u.pct_ast, u.pct_reb, u.pct_tov,
    u.pct_fga_3pt, u.pct_pts_paint, u.pct_pts_fb, u.pct_pts_ft,
    u.pct_ast_fgm, u.pct_uast_fgm, u.pct_ast_2pm, u.pct_ast_3pm,
    -- tracking, passing, touches, hustle
    t.dist_miles, t.dist_miles_off, t.dist_miles_def, t.avg_speed, t.avg_speed_off, t.avg_speed_def,
    t.passes_made, t.passes_received, t.potential_ast, t.secondary_ast, t.ast_pts_created,
    t.touches, t.front_ct_touches, t.time_of_poss, t.avg_sec_per_touch, t.avg_drib_per_touch, t.pts_per_touch,
    t.elbow_touches, t.post_touches, t.paint_touches,
    t.contested_shots, t.deflections, t.charges_drawn, t.screen_assists, t.loose_balls_recovered, t.box_outs,
    -- same-game team and opponent totals
    tm.pts AS team_pts, tm.fga AS team_fga, tm.ast AS team_ast, tm.pace AS team_pace, tm.off_rating AS team_off_rating,
    opp.team_id AS opponent_team_id, opp.pts AS opponent_pts, opp.off_rating AS opponent_off_rating
FROM dbo.v_player_game_birthday AS b
CROSS APPLY dbo.fn_birthday_distance(b.birthdate, b.game_date) AS bd
LEFT JOIN dbo.v_player_game_context AS c ON c.player_id = b.player_id AND c.game_id = b.game_id
LEFT JOIN dbo.player_game_usage AS u ON u.player_id = b.player_id AND u.game_id = b.game_id
LEFT JOIN dbo.player_game_tracking AS t ON t.player_id = b.player_id AND t.game_id = b.game_id
LEFT JOIN dbo.team_game_log AS tm ON tm.game_id = b.game_id AND tm.team_id = b.team_id
LEFT JOIN dbo.team_game_log AS opp ON opp.game_id = b.game_id AND opp.team_id <> b.team_id;
GO
