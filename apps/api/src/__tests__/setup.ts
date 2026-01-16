// Mock environment variables before any imports
process.env.PORT = "3000";
process.env.SUPABASE_URL = "https://test-project.supabase.co";
process.env.SUPABASE_ANON_KEY = "test-anon-key";
process.env.SUPABASE_SERVICE_ROLE_KEY = "test-service-role-key";
process.env.ANTHROPIC_API_KEY = "test-anthropic-key";
process.env.YOUTUBE_API_KEY = "test-youtube-key";

// Global test timeout
jest.setTimeout(10000);
