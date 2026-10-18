-- Tables for the nba database. Safe to re-run: every object is created only if missing.

IF SCHEMA_ID('stg') IS NULL EXEC('CREATE SCHEMA stg');   -- staging tables used by the upsert
GO
IF SCHEMA_ID('etl') IS NULL EXEC('CREATE SCHEMA etl');   -- pipeline metadata
GO

IF OBJECT_ID('dbo.team') IS NULL
CREATE TABLE dbo.team (
    team_id       INT           NOT NULL CONSTRAINT pk_team PRIMARY KEY,
    abbreviation  VARCHAR(5)    NOT NULL,
    full_name     NVARCHAR(100) NOT NULL,
    nickname      NVARCHAR(50)  NULL,
    city          NVARCHAR(50)  NULL,
    state         NVARCHAR(50)  NULL,
    year_founded  SMALLINT      NULL,
    updated_at    DATETIME2(0)  NOT NULL CONSTRAINT df_team_updated DEFAULT SYSUTCDATETIME()
);
GO

IF OBJECT_ID('dbo.player') IS NULL
CREATE TABLE dbo.player (
    player_id   INT           NOT NULL CONSTRAINT pk_player PRIMARY KEY,
    full_name   NVARCHAR(100) NOT NULL,
    birthdate   DATE          NULL,
    team_id     INT           NULL CONSTRAINT fk_player_team REFERENCES dbo.team (team_id),
    position    NVARCHAR(30)  NULL,
    height      VARCHAR(10)   NULL,
    weight_lbs  SMALLINT      NULL,
    country     NVARCHAR(60)  NULL,
    from_year   SMALLINT      NULL,
    to_year     SMALLINT      NULL,
    is_active   BIT           NOT NULL CONSTRAINT df_player_active DEFAULT 1,
    updated_at  DATETIME2(0)  NOT NULL CONSTRAINT df_player_updated DEFAULT SYSUTCDATETIME()
);
GO

-- birthdate stays a real DATE so date maths and sorting work; this is the MM-DD-YYYY text form of it.
IF COL_LENGTH('dbo.player', 'birthdate_mdy') IS NULL
ALTER TABLE dbo.player ADD birthdate_mdy AS CONVERT(CHAR(10), birthdate, 110);
GO

-- Team ids are not foreign keys here: preseason games include non-NBA opponents.
IF OBJECT_ID('dbo.schedule') IS NULL
CREATE TABLE dbo.schedule (
    game_id            CHAR(10)      NOT NULL CONSTRAINT pk_schedule PRIMARY KEY,
    season             CHAR(7)       NOT NULL,
    game_date          DATE          NOT NULL,
    game_datetime_est  DATETIME2(0)  NULL,
    day                VARCHAR(5)    NULL,
    week_number        SMALLINT      NULL,
    week_name          NVARCHAR(50)  NULL,
    game_label         NVARCHAR(100) NULL,
    game_sub_label     NVARCHAR(100) NULL,
    game_status_text   NVARCHAR(50)  NULL,
    arena_name         NVARCHAR(100) NULL,
    arena_city         NVARCHAR(100) NULL,
    arena_state        NVARCHAR(50)  NULL,
    home_team_id       INT           NULL,
    home_team_tricode  VARCHAR(5)    NULL,
    away_team_id       INT           NULL,
    away_team_tricode  VARCHAR(5)    NULL,
    updated_at         DATETIME2(0)  NOT NULL CONSTRAINT df_schedule_updated DEFAULT SYSUTCDATETIME()
);
GO

IF OBJECT_ID('dbo.player_game_log') IS NULL
CREATE TABLE dbo.player_game_log (
    player_id              INT          NOT NULL CONSTRAINT fk_log_player REFERENCES dbo.player (player_id),
    game_id                CHAR(10)     NOT NULL,
    season                 CHAR(7)      NOT NULL,
    season_type            VARCHAR(20)  NOT NULL,
    game_date              DATE         NOT NULL,
    team_id                INT          NOT NULL,
    team_abbreviation      VARCHAR(5)   NULL,
    opponent_abbreviation  VARCHAR(5)   NULL,
    is_home                BIT          NULL,
    matchup                VARCHAR(20)  NULL,
    wl                     CHAR(1)      NULL,
    -- box score
    minutes     FLOAT NULL,
    fgm         SMALLINT NULL,
    fga         SMALLINT NULL,
    fg_pct      FLOAT NULL,
    fg3m        SMALLINT NULL,
    fg3a        SMALLINT NULL,
    fg3_pct     FLOAT NULL,
    ftm         SMALLINT NULL,
    fta         SMALLINT NULL,
    ft_pct      FLOAT NULL,
    oreb        SMALLINT NULL,
    dreb        SMALLINT NULL,
    reb         SMALLINT NULL,
    ast         SMALLINT NULL,
    tov         SMALLINT NULL,
    stl         SMALLINT NULL,
    blk         SMALLINT NULL,
    pf          SMALLINT NULL,
    pts         SMALLINT NULL,
    plus_minus  SMALLINT NULL,
    -- advanced
    off_rating  FLOAT NULL,
    def_rating  FLOAT NULL,
    net_rating  FLOAT NULL,
    ast_pct     FLOAT NULL,
    ast_to      FLOAT NULL,
    ast_ratio   FLOAT NULL,
    oreb_pct    FLOAT NULL,
    dreb_pct    FLOAT NULL,
    reb_pct     FLOAT NULL,
    tm_tov_pct  FLOAT NULL,
    efg_pct     FLOAT NULL,
    ts_pct      FLOAT NULL,
    usg_pct     FLOAT NULL,
    pace        FLOAT NULL,
    pie         FLOAT NULL,
    poss        SMALLINT NULL,
    updated_at  DATETIME2(0) NOT NULL CONSTRAINT df_log_updated DEFAULT SYSUTCDATETIME(),
    CONSTRAINT pk_player_game_log PRIMARY KEY (player_id, game_id)
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_player_game_log_game_date')
CREATE INDEX ix_player_game_log_game_date ON dbo.player_game_log (game_date);
GO

-- One row per job execution, so you can see what ran, when, and whether it worked.
IF OBJECT_ID('etl.job_run') IS NULL
CREATE TABLE etl.job_run (
    run_id       INT IDENTITY(1, 1) NOT NULL CONSTRAINT pk_job_run PRIMARY KEY,
    job_name     VARCHAR(50)   NOT NULL,
    started_at   DATETIME2(0)  NOT NULL CONSTRAINT df_job_run_started DEFAULT SYSUTCDATETIME(),
    finished_at  DATETIME2(0)  NULL,
    status       VARCHAR(10)   NOT NULL,   -- running | success | failed
    rows_loaded  INT           NULL,
    message      NVARCHAR(MAX) NULL
);
GO

-- Share-of-team and shot-profile splits per player per game (the API's "Usage" and "Scoring" stat sets).
-- pct_fga = share of the team's shot attempts taken by the player while on court, and so on.
IF OBJECT_ID('dbo.player_game_usage') IS NULL
CREATE TABLE dbo.player_game_usage (
    player_id        INT      NOT NULL CONSTRAINT fk_usage_player REFERENCES dbo.player (player_id),
    game_id          CHAR(10) NOT NULL,
    -- share of team totals
    pct_fgm          FLOAT NULL,
    pct_fga          FLOAT NULL,
    pct_fg3m         FLOAT NULL,
    pct_fg3a         FLOAT NULL,
    pct_ftm          FLOAT NULL,
    pct_fta          FLOAT NULL,
    pct_oreb         FLOAT NULL,
    pct_dreb         FLOAT NULL,
    pct_reb          FLOAT NULL,
    pct_ast          FLOAT NULL,
    pct_tov          FLOAT NULL,
    pct_stl          FLOAT NULL,
    pct_blk          FLOAT NULL,
    pct_pf           FLOAT NULL,
    pct_pts          FLOAT NULL,
    -- where the player's shots and points came from
    pct_fga_2pt      FLOAT NULL,
    pct_fga_3pt      FLOAT NULL,
    pct_pts_2pt      FLOAT NULL,
    pct_pts_2pt_mr   FLOAT NULL,
    pct_pts_3pt      FLOAT NULL,
    pct_pts_fb       FLOAT NULL,
    pct_pts_ft       FLOAT NULL,
    pct_pts_off_tov  FLOAT NULL,
    pct_pts_paint    FLOAT NULL,
    -- how many of the player's made shots were set up by a teammate
    pct_ast_2pm      FLOAT NULL,
    pct_uast_2pm     FLOAT NULL,
    pct_ast_3pm      FLOAT NULL,
    pct_uast_3pm     FLOAT NULL,
    pct_ast_fgm      FLOAT NULL,
    pct_uast_fgm     FLOAT NULL,
    updated_at       DATETIME2(0) NOT NULL CONSTRAINT df_usage_updated DEFAULT SYSUTCDATETIME(),
    CONSTRAINT pk_player_game_usage PRIMARY KEY (player_id, game_id)
);
GO

IF OBJECT_ID('dbo.team_game_log') IS NULL
CREATE TABLE dbo.team_game_log (
    team_id                INT          NOT NULL,
    game_id                CHAR(10)     NOT NULL,
    season                 CHAR(7)      NOT NULL,
    season_type            VARCHAR(20)  NOT NULL,
    game_date              DATE         NOT NULL,
    team_abbreviation      VARCHAR(5)   NULL,
    opponent_abbreviation  VARCHAR(5)   NULL,
    is_home                BIT          NULL,
    matchup                VARCHAR(20)  NULL,
    wl                     CHAR(1)      NULL,
    minutes     FLOAT NULL,
    fgm         SMALLINT NULL,
    fga         SMALLINT NULL,
    fg_pct      FLOAT NULL,
    fg3m        SMALLINT NULL,
    fg3a        SMALLINT NULL,
    fg3_pct     FLOAT NULL,
    ftm         SMALLINT NULL,
    fta         SMALLINT NULL,
    ft_pct      FLOAT NULL,
    oreb        SMALLINT NULL,
    dreb        SMALLINT NULL,
    reb         SMALLINT NULL,
    ast         SMALLINT NULL,
    tov         SMALLINT NULL,
    stl         SMALLINT NULL,
    blk         SMALLINT NULL,
    pf          SMALLINT NULL,
    pts         SMALLINT NULL,
    plus_minus  SMALLINT NULL,
    off_rating  FLOAT NULL,
    def_rating  FLOAT NULL,
    net_rating  FLOAT NULL,
    ast_pct     FLOAT NULL,
    ast_to      FLOAT NULL,
    ast_ratio   FLOAT NULL,
    oreb_pct    FLOAT NULL,
    dreb_pct    FLOAT NULL,
    reb_pct     FLOAT NULL,
    tm_tov_pct  FLOAT NULL,
    efg_pct     FLOAT NULL,
    ts_pct      FLOAT NULL,
    pace        FLOAT NULL,
    pie         FLOAT NULL,
    poss        SMALLINT NULL,
    updated_at  DATETIME2(0) NOT NULL CONSTRAINT df_team_log_updated DEFAULT SYSUTCDATETIME(),
    CONSTRAINT pk_team_game_log PRIMARY KEY (team_id, game_id)
);
GO

-- Optical tracking (distance, speed) and hustle stats per player per game.
-- Tracking exists from 2013-14 and hustle from 2015-16; earlier games have no rows.
IF OBJECT_ID('dbo.player_game_tracking') IS NULL
CREATE TABLE dbo.player_game_tracking (
    player_id       INT      NOT NULL CONSTRAINT fk_tracking_player REFERENCES dbo.player (player_id),
    game_id         CHAR(10) NOT NULL,
    game_date       DATE     NOT NULL,
    -- tracking
    dist_feet       FLOAT NULL,
    dist_miles      FLOAT NULL,
    dist_miles_off  FLOAT NULL,
    dist_miles_def  FLOAT NULL,
    avg_speed       FLOAT NULL,   -- miles per hour
    avg_speed_off   FLOAT NULL,
    avg_speed_def   FLOAT NULL,
    -- hustle
    contested_shots            SMALLINT NULL,
    contested_shots_2pt        SMALLINT NULL,
    contested_shots_3pt        SMALLINT NULL,
    deflections                SMALLINT NULL,
    charges_drawn              SMALLINT NULL,
    screen_assists             SMALLINT NULL,
    screen_ast_pts             SMALLINT NULL,
    off_loose_balls_recovered  SMALLINT NULL,
    def_loose_balls_recovered  SMALLINT NULL,
    loose_balls_recovered      SMALLINT NULL,
    off_boxouts                SMALLINT NULL,
    def_boxouts                SMALLINT NULL,
    box_outs                   SMALLINT NULL,
    updated_at      DATETIME2(0) NOT NULL CONSTRAINT df_tracking_updated DEFAULT SYSUTCDATETIME(),
    CONSTRAINT pk_player_game_tracking PRIMARY KEY (player_id, game_id)
);
GO

-- Which game dates a date-by-date job has already fetched, so an interrupted run resumes
-- where it stopped and dates that legitimately returned nothing are not fetched again.
IF OBJECT_ID('etl.date_load') IS NULL
CREATE TABLE etl.date_load (
    dataset      VARCHAR(30)  NOT NULL,
    game_date    DATE         NOT NULL,
    rows_loaded  INT          NOT NULL,
    loaded_at    DATETIME2(0) NOT NULL CONSTRAINT df_date_load_loaded DEFAULT SYSUTCDATETIME(),
    CONSTRAINT pk_date_load PRIMARY KEY (dataset, game_date)
);
GO

-- Passing, touches and starter columns added to the tracking table after it was first created.
IF COL_LENGTH('dbo.player_game_tracking', 'is_starter') IS NULL
ALTER TABLE dbo.player_game_tracking ADD
    is_starter          BIT   NULL,
    -- passing
    passes_made         SMALLINT NULL,
    passes_received     SMALLINT NULL,
    ft_ast              SMALLINT NULL,
    secondary_ast       SMALLINT NULL,
    potential_ast       SMALLINT NULL,
    ast_pts_created     SMALLINT NULL,
    -- possessions
    touches             SMALLINT NULL,
    front_ct_touches    SMALLINT NULL,
    time_of_poss        FLOAT NULL,   -- minutes with the ball
    avg_sec_per_touch   FLOAT NULL,
    avg_drib_per_touch  FLOAT NULL,
    pts_per_touch       FLOAT NULL,
    elbow_touches       SMALLINT NULL,
    post_touches        SMALLINT NULL,
    paint_touches       SMALLINT NULL;
GO

-- Window functions in the derived views look up a player's or team's games in date order.
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_player_game_log_player_date')
CREATE INDEX ix_player_game_log_player_date ON dbo.player_game_log (player_id, game_date) INCLUDE (team_id, season);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_team_game_log_team_date')
CREATE INDEX ix_team_game_log_team_date ON dbo.team_game_log (team_id, game_date);
GO
