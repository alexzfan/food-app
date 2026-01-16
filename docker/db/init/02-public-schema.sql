-- Set up public schema permissions for Supabase

-- Grant usage on public schema
GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;

-- Default privileges for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO anon, authenticated, service_role;

-- Extensions schema
GRANT USAGE ON SCHEMA extensions TO anon, authenticated, service_role;

-- Allow authenticated users to use uuid generation
GRANT EXECUTE ON FUNCTION extensions.uuid_generate_v4() TO anon, authenticated, service_role;
