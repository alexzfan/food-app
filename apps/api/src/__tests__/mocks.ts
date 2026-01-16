import type { Recipe, YouTubeVideo, RecipeSummary, Ingredient, Instruction } from "../types/recipe";

export const mockIngredients: Ingredient[] = [
  { name: "pasta", amount: "400", unit: "g" },
  { name: "olive oil", amount: "2", unit: "tbsp" },
  { name: "garlic", amount: "4", unit: "cloves", notes: "minced" },
  { name: "parmesan cheese", amount: "100", unit: "g", notes: "grated" },
];

export const mockInstructions: Instruction[] = [
  { step: 1, text: "Boil water and cook pasta according to package directions", duration: "10 minutes" },
  { step: 2, text: "Heat olive oil in a pan and sauté garlic until fragrant", duration: "2 minutes" },
  { step: 3, text: "Toss pasta with garlic oil and parmesan" },
];

export const mockRecipe: Recipe = {
  id: "123e4567-e89b-12d3-a456-426614174000",
  youtube_video_id: "dQw4w9WgXcQ",
  title: "Easy Garlic Parmesan Pasta",
  description: "A quick and delicious pasta dish",
  thumbnail_url: "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg",
  channel_name: "Cooking Channel",
  channel_id: "UC123456",
  ingredients: mockIngredients,
  instructions: mockInstructions,
  tags: ["pasta", "italian", "quick", "vegetarian"],
  cuisine: "Italian",
  cook_time_minutes: 15,
  prep_time_minutes: 5,
  servings: 4,
  difficulty: "easy",
  created_at: "2024-01-15T10:00:00Z",
  updated_at: "2024-01-15T10:00:00Z",
};

export const mockYouTubeVideo: YouTubeVideo = {
  id: "dQw4w9WgXcQ",
  title: "Easy Garlic Parmesan Pasta Recipe",
  description: "Learn how to make this delicious pasta dish in under 20 minutes!",
  thumbnailUrl: "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg",
  channelTitle: "Cooking Channel",
  channelId: "UC123456",
  publishedAt: "2024-01-10T12:00:00Z",
};

export const mockRecipeSummary: RecipeSummary = {
  title: "Easy Garlic Parmesan Pasta",
  description: "A quick and delicious pasta dish",
  ingredients: mockIngredients,
  instructions: mockInstructions,
  tags: ["pasta", "italian", "quick", "vegetarian"],
  cuisine: "Italian",
  cook_time_minutes: 15,
  prep_time_minutes: 5,
  servings: 4,
  difficulty: "easy",
};

export const mockTranscript = `
Today we're making an easy garlic parmesan pasta. You'll need 400 grams of pasta,
2 tablespoons of olive oil, 4 cloves of garlic minced, and 100 grams of grated parmesan.
First, boil water and cook your pasta according to package directions, about 10 minutes.
While that's cooking, heat olive oil in a pan and sauté the garlic until fragrant, about 2 minutes.
Finally, toss the pasta with the garlic oil and parmesan. Season to taste and serve immediately.
This serves 4 people and takes only 15 minutes to cook with 5 minutes of prep.
`;

export const mockYouTubeSearchResponse = {
  items: [
    {
      id: { videoId: "dQw4w9WgXcQ" },
      snippet: {
        title: "Easy Garlic Parmesan Pasta Recipe",
        description: "Learn how to make this delicious pasta dish",
        thumbnails: { high: { url: "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg" } },
        channelTitle: "Cooking Channel",
        channelId: "UC123456",
        publishedAt: "2024-01-10T12:00:00Z",
      },
    },
  ],
  nextPageToken: "NEXT_PAGE_TOKEN",
};

export const mockYouTubeVideoResponse = {
  items: [
    {
      snippet: {
        title: "Easy Garlic Parmesan Pasta Recipe",
        description: "Learn how to make this delicious pasta dish in under 20 minutes!",
        thumbnails: {
          high: { url: "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg" },
          default: { url: "https://i.ytimg.com/vi/dQw4w9WgXcQ/default.jpg" },
        },
        channelTitle: "Cooking Channel",
        channelId: "UC123456",
        publishedAt: "2024-01-10T12:00:00Z",
      },
    },
  ],
};
