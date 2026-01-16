-- Supabase super admin
CREATE USER supabase_admin;
ALTER USER supabase_admin WITH SUPERUSER CREATEDB CREATEROLE REPLICATION BYPASSRLS;

-- Extension namespacing
CREATE SCHEMA IF NOT EXISTS extensions;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA extensions;
CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA extensions;
CREATE EXTENSION IF NOT EXISTS pgjwt WITH SCHEMA extensions;

-- Set up auth schema
CREATE SCHEMA IF NOT EXISTS auth AUTHORIZATION supabase_admin;

-- Create auth roles
CREATE ROLE anon NOLOGIN NOINHERIT;
CREATE ROLE authenticated NOLOGIN NOINHERIT;
CREATE ROLE service_role NOLOGIN NOINHERIT BYPASSRLS;
CREATE ROLE authenticator NOINHERIT LOGIN PASSWORD 'postgres';
CREATE ROLE supabase_auth_admin NOINHERIT CREATEROLE LOGIN PASSWORD 'postgres';

GRANT anon TO authenticator;
GRANT authenticated TO authenticator;
GRANT service_role TO authenticator;
GRANT supabase_admin TO authenticator;

GRANT ALL ON SCHEMA auth TO supabase_admin;
GRANT ALL ON SCHEMA auth TO supabase_auth_admin;

ALTER USER supabase_auth_admin SET search_path = 'auth';

-- Auth tables will be created by GoTrue on first run
