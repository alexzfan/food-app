import Constants from "expo-constants";

// Configure your API URL here
// In development, this should point to your local backend
// In production, update this to your deployed API URL

const ENV = {
  development: {
    apiUrl: "http://localhost:3000/api",
  },
  production: {
    apiUrl: "https://your-production-api.com/api",
  },
};

const getEnvVars = () => {
  const releaseChannel = Constants.expoConfig?.extra?.releaseChannel;

  if (releaseChannel === "production") {
    return ENV.production;
  }

  return ENV.development;
};

export const env = getEnvVars();
