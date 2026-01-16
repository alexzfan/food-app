// Shared types between frontend and backend
// Add shared types here as the app grows

export interface ApiResponse<T> {
  data?: T;
  error?: string;
}
