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
