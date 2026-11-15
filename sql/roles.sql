-- Layers, roles and grants: privacy by permission, not by prompt (Phase 2).
--
-- Run as the owner (the database user that already exists) with `make roles`. Safe to run
-- again: nothing is duplicated, grants are re-stated, and the two passwords are reset to the
-- current DBT_PASSWORD and AGENT_PASSWORD, which is also how you rotate them.
--
-- Who may do what (full matrix: specs/003-roles-and-grants/contracts/roles-and-grants.md):
--   owner  owns the layers and the raw table; the only role that writes raw data.
--   dbt    reads raw; builds in staging, marts and semantic; owns what it builds.
--   agent  reads marts and semantic only. It has NO grant on raw or staging, so even
--          SELECT * and columns added later are refused: the restriction is the missing grant.
--
-- The passwords arrive as psql variables (-v dbt_password=... -v agent_password=...) and are
-- never echoed.

\set ON_ERROR_STOP on

-- Layers. raw may already exist (the raw table script creates it too).
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS marts;
CREATE SCHEMA IF NOT EXISTS semantic;

-- Roles. CREATE ROLE has no IF NOT EXISTS, so create only when missing (\gexec runs the
-- generated statement), then set the attributes and password on every run.
SELECT 'CREATE ROLE dbt LOGIN'
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'dbt') \gexec
SELECT 'CREATE ROLE agent LOGIN'
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'agent') \gexec

ALTER ROLE dbt   LOGIN PASSWORD :'dbt_password'   NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
ALTER ROLE agent LOGIN PASSWORD :'agent_password' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;

-- Database level: by default PUBLIC (everyone) may connect and create temporary tables.
-- Remove that, then give back only what each role needs. agent gets no TEMPORARY, which
-- keeps it strictly read-only.
SELECT format('REVOKE ALL ON DATABASE %I FROM PUBLIC', current_database()) \gexec
SELECT format('GRANT CONNECT ON DATABASE %I TO dbt, agent', current_database()) \gexec
SELECT format('GRANT TEMPORARY ON DATABASE %I TO dbt', current_database()) \gexec
REVOKE ALL ON SCHEMA public FROM PUBLIC;

-- Make the script authoritative: take back anything a past mistake or manual change may have
-- given, so a rerun restores the intended state instead of only adding to it.
REVOKE ALL ON SCHEMA raw, staging FROM agent;
REVOKE ALL ON ALL TABLES IN SCHEMA raw, staging FROM agent;
REVOKE CREATE ON SCHEMA raw FROM dbt;
REVOKE ALL ON SCHEMA marts, semantic, staging FROM PUBLIC;

-- Grants for agent: read-only access to the curated layers and nothing else.
-- There is deliberately NO grant on raw and NO grant on staging. Without USAGE on a schema
-- every read inside it is refused, including SELECT * and any column added later. That
-- missing grant is the privacy guarantee, not an omission.
GRANT USAGE ON SCHEMA marts, semantic TO agent;

-- Grants for dbt: reads the source, builds the curated layers.
-- USAGE on raw lets dbt see the source schema; it gets no CREATE there.
GRANT USAGE ON SCHEMA raw TO dbt;
GRANT SELECT ON ALL TABLES IN SCHEMA raw TO dbt;
-- dbt creates and replaces its own objects in these three layers (and owns them).
GRANT USAGE, CREATE ON SCHEMA staging, marts, semantic TO dbt;

-- Default privileges: apply to objects created LATER, so nothing is re-granted per object.
-- 1. A raw table the owner drops and recreates (make raw-table) stays readable by dbt.
ALTER DEFAULT PRIVILEGES FOR ROLE CURRENT_USER IN SCHEMA raw GRANT SELECT ON TABLES TO dbt;
-- 2. Tables and views dbt builds in marts and semantic are readable by agent. The same
--    does not exist for staging, so agent never sees staging objects.
ALTER DEFAULT PRIVILEGES FOR ROLE dbt IN SCHEMA marts, semantic GRANT SELECT ON TABLES TO agent;

-- Final report: names only.
SELECT 'layer ' || schema_name AS ensured
FROM information_schema.schemata
WHERE schema_name IN ('raw', 'staging', 'marts', 'semantic')
UNION ALL
SELECT 'role ' || rolname FROM pg_roles WHERE rolname IN ('dbt', 'agent')
ORDER BY 1;
