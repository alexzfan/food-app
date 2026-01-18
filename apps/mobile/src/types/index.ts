export interface Ingredient {
  name: string;
  amount: string;
  unit?: string;
  notes?: string;
}

export interface Instruction {
  step: number;
  text: string;
  duration?: string;
}

export interface Recipe {
  id: string;
  user_id: string;
  youtube_video_id: string;
  title: string;
  description: string;
  thumbnail_url: string;
  channel_name: string;
  channel_id: string;
  ingredients: Ingredient[];
  instructions: Instruction[];
  tags: string[];
  cuisine?: string;
  cook_time_minutes?: number;
  prep_time_minutes?: number;
  servings?: number;
  difficulty?: "easy" | "medium" | "hard";
  created_at: string;
  updated_at: string;
  is_favorite?: boolean;
}

export interface YouTubeVideo {
  id: string;
  title: string;
  description: string;
  thumbnailUrl: string;
  channelTitle: string;
  channelId: string;
  publishedAt: string;
}

export interface YouTubeSearchResult {
  videos: YouTubeVideo[];
  nextPageToken?: string;
}

/**
 * Recipe summary extracted by Gemma 3n (before saving to DB)
 */
export interface RecipeSummary {
  title: string;
  description?: string;
  ingredients: Ingredient[];
  instructions: Instruction[];
  tags: string[];
  cuisine?: string;
  cook_time_minutes?: number;
  prep_time_minutes?: number;
  servings?: number;
  difficulty?: "easy" | "medium" | "hard";
}
