// Test setup file
import { jest } from "@jest/globals";

// Mock environment variables
process.env.SUPABASE_URL = "http://localhost:8000";
process.env.SUPABASE_ANON_KEY = "test-anon-key";
process.env.SUPABASE_SERVICE_ROLE_KEY = "test-service-role-key";
process.env.YOUTUBE_API_KEY = "test-youtube-api-key";
process.env.AUDIO_SERVICE_URL = "http://localhost:8001";
process.env.PORT = "3000";

// Increase test timeout for async operations
jest.setTimeout(10000);

// Global fetch mock
global.fetch = jest.fn() as jest.MockedFunction<typeof fetch>;

// Reset mocks between tests
beforeEach(() => {
  jest.clearAllMocks();
});
