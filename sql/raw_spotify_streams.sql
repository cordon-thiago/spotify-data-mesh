-- raw.spotify_streams: the source-aligned table that holds the Spotify streaming history.
--
-- One row per record of the export, kept as it arrives: no deduplication, no filtering,
-- no time-zone conversion, no business rule. Those are Phase 3 (dbt staging).
-- The loader (ingest/load.py) empties and refills this table; it never creates or alters it.
--
-- Column names are exactly the JSON keys. Types follow what the real export contains
-- (docs/real-export-findings.md), so a value that does not fit fails the load loudly
-- instead of being stored wrong. There are no NOT NULL or CHECK constraints on purpose:
-- raw data accepts what arrives, and quality tests belong to Phase 3.
--
-- Safe to run again: it drops and recreates the table, and the data is reloaded with
-- `make load`. Apply with: make raw-table
--
-- This table holds ip_addr, which is restricted personal data. Until Phase 2 adds roles
-- it is owner-only because only the owner user exists (a new schema grants nothing to PUBLIC).

CREATE SCHEMA IF NOT EXISTS raw;

DROP TABLE IF EXISTS raw.spotify_streams;

CREATE TABLE raw.spotify_streams (
    -- When the stream ENDED, in UTC. Every value in the export is 'YYYY-MM-DDTHH:MM:SSZ'.
    -- timestamptz keeps the instant exact; the local-time conversion is Phase 3.
    ts                                  timestamptz,
    platform                            text,           -- up to 54 characters, 17 distinct values
    ms_played                           integer,        -- whole milliseconds, never negative, at most 7 digits
    conn_country                        text,           -- two uppercase letters
    -- Restricted. IPv4 and IPv6 both occur in the export; inet accepts both and rejects non-IPs.
    ip_addr                             inet,

    -- Music fields: filled for music records, otherwise null.
    master_metadata_track_name          text,
    master_metadata_album_artist_name   text,
    master_metadata_album_album_name    text,
    spotify_track_uri                   text,

    -- Podcast fields: filled for episodes, otherwise null. The show name is sometimes an
    -- empty string (not null); text keeps the two apart.
    episode_name                        text,
    episode_show_name                   text,
    spotify_episode_uri                 text,

    -- Audiobook fields: always null in this export, kept because the schema defines them.
    audiobook_title                     text,
    audiobook_uri                       text,
    audiobook_chapter_uri               text,
    audiobook_chapter_title             text,

    reason_start                        text,           -- 9 distinct values in the export
    reason_end                          text,           -- 12 distinct values in the export

    -- Booleans stay nullable: null, false and true are three different states. In the
    -- export only offline is ever null, but the loader compares all four.
    shuffle                             boolean,
    skipped                             boolean,
    offline                             boolean,
    -- Epoch time of offline use. The export mixes seconds (10 digits) and milliseconds
    -- (13 digits), which does not fit in 4 bytes, so bigint. Reading the unit is Phase 3.
    offline_timestamp                   bigint,
    incognito_mode                      boolean,

    -- Filled by the loader: the file this row came from, relative to the source folder.
    source_file                         text,
    -- Filled by the database; the loader leaves it alone because it has a default.
    loaded_at                           timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE raw.spotify_streams IS
    'Source-aligned Spotify streaming history, one row per export record, unchanged. Restricted: contains ip_addr.';
COMMENT ON COLUMN raw.spotify_streams.ip_addr IS 'Restricted personal data (direct identifier). Never exposed to the agent.';
COMMENT ON COLUMN raw.spotify_streams.source_file IS 'Path of the export file this row was loaded from.';
