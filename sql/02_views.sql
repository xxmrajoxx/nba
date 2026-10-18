-- Analysis views for the birthday-week question. Safe to re-run.
-- "Birthday week" = a game played within 3 days either side of the player's birthday (a 7-day window).

-- Every game log row, tagged with how far the game was from the player's nearest birthday.
CREATE OR ALTER VIEW dbo.v_player_game_birthday AS
SELECT
    l.*,
    p.full_name,
    p.birthdate,
    CASE WHEN DATEADD(YEAR, y.yrs, p.birthdate) > l.game_date THEN y.yrs - 1 ELSE y.yrs END AS age_at_game,
    b.days_from_birthday,   -- negative = before the birthday, 0 = on it, positive = after
    CAST(CASE WHEN ABS(b.days_from_birthday) <= 3 THEN 1 ELSE 0 END AS BIT) AS is_birthday_week,
    CAST(CASE WHEN b.days_from_birthday = 0 THEN 1 ELSE 0 END AS BIT) AS is_birthday
FROM dbo.player_game_log AS l
JOIN dbo.player AS p ON p.player_id = l.player_id
CROSS APPLY (SELECT DATEDIFF(YEAR, p.birthdate, l.game_date) AS yrs) AS y
-- The nearest birthday can fall in the previous or next calendar year (e.g. a Dec 30
-- birthday and a Jan 1 game), so check three candidates and keep the closest.
CROSS APPLY (
    SELECT TOP (1) DATEDIFF(DAY, c.birthday, l.game_date) AS days_from_birthday
    FROM (VALUES
        (DATEADD(YEAR, y.yrs - 1, p.birthdate)),
        (DATEADD(YEAR, y.yrs,     p.birthdate)),
        (DATEADD(YEAR, y.yrs + 1, p.birthdate))
    ) AS c (birthday)
    ORDER BY ABS(DATEDIFF(DAY, c.birthday, l.game_date))
) AS b
WHERE p.birthdate IS NOT NULL;
GO

-- One row per player-season: birthday-week averages next to the same player's averages
-- in the rest of that season. Comparing within a season keeps career arcs (rookie vs
-- prime vs veteran) from masquerading as a birthday effect.
CREATE OR ALTER VIEW dbo.v_birthday_week_vs_season AS
SELECT
    player_id,
    full_name,
    season,
    SUM(CASE WHEN is_birthday_week = 1 THEN 1 ELSE 0 END) AS birthday_week_games,
    SUM(CASE WHEN is_birthday_week = 0 THEN 1 ELSE 0 END) AS other_games,
    AVG(CASE WHEN is_birthday_week = 1 THEN CAST(pts AS FLOAT) END)        AS birthday_week_pts,
    AVG(CASE WHEN is_birthday_week = 0 THEN CAST(pts AS FLOAT) END)        AS other_pts,
    AVG(CASE WHEN is_birthday_week = 1 THEN CAST(reb AS FLOAT) END)        AS birthday_week_reb,
    AVG(CASE WHEN is_birthday_week = 0 THEN CAST(reb AS FLOAT) END)        AS other_reb,
    AVG(CASE WHEN is_birthday_week = 1 THEN CAST(ast AS FLOAT) END)        AS birthday_week_ast,
    AVG(CASE WHEN is_birthday_week = 0 THEN CAST(ast AS FLOAT) END)        AS other_ast,
    AVG(CASE WHEN is_birthday_week = 1 THEN minutes END)                   AS birthday_week_minutes,
    AVG(CASE WHEN is_birthday_week = 0 THEN minutes END)                   AS other_minutes,
    AVG(CASE WHEN is_birthday_week = 1 THEN ts_pct END)                    AS birthday_week_ts_pct,
    AVG(CASE WHEN is_birthday_week = 0 THEN ts_pct END)                    AS other_ts_pct,
    AVG(CASE WHEN is_birthday_week = 1 THEN CAST(plus_minus AS FLOAT) END) AS birthday_week_plus_minus,
    AVG(CASE WHEN is_birthday_week = 0 THEN CAST(plus_minus AS FLOAT) END) AS other_plus_minus
FROM dbo.v_player_game_birthday
WHERE season_type = 'Regular Season'
  AND minutes > 0
GROUP BY player_id, full_name, season
HAVING SUM(CASE WHEN is_birthday_week = 1 THEN 1 ELSE 0 END) > 0
   AND SUM(CASE WHEN is_birthday_week = 0 THEN 1 ELSE 0 END) > 0;
GO

-- Scheduled games that fall in an active player's birthday week.
CREATE OR ALTER VIEW dbo.v_upcoming_birthday_week_games AS
SELECT
    p.player_id,
    p.full_name,
    p.birthdate,
    s.game_id,
    s.game_date,
    s.game_label,
    s.away_team_tricode,
    s.home_team_tricode,
    b.days_from_birthday
FROM dbo.schedule AS s
JOIN dbo.player AS p
    ON p.team_id IN (s.home_team_id, s.away_team_id)
   AND p.is_active = 1
CROSS APPLY (SELECT DATEDIFF(YEAR, p.birthdate, s.game_date) AS yrs) AS y
CROSS APPLY (
    SELECT TOP (1) DATEDIFF(DAY, c.birthday, s.game_date) AS days_from_birthday
    FROM (VALUES
        (DATEADD(YEAR, y.yrs - 1, p.birthdate)),
        (DATEADD(YEAR, y.yrs,     p.birthdate)),
        (DATEADD(YEAR, y.yrs + 1, p.birthdate))
    ) AS c (birthday)
    ORDER BY ABS(DATEDIFF(DAY, c.birthday, s.game_date))
) AS b
WHERE s.game_date >= CAST(GETDATE() AS DATE)
  AND ABS(b.days_from_birthday) <= 3;
GO
