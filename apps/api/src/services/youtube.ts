import { env } from "../config/env.js";
import { YoutubeTranscript } from "youtube-transcript";
import type { YouTubeVideo, YouTubeSearchResult } from "../types/recipe.js";

const YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3";

interface YouTubeSearchResponse {
  items: Array<{
    id: { videoId: string };
    snippet: {
      title: string;
      description: string;
      thumbnails: { high: { url: string } };
      channelTitle: string;
      channelId: string;
      publishedAt: string;
    };
  }>;
  nextPageToken?: string;
}

export async function searchRecipeVideos(
  query: string,
  maxResults = 10,
  pageToken?: string
): Promise<YouTubeSearchResult> {
  const params = new URLSearchParams({
    part: "snippet",
    q: `${query} recipe`,
    type: "video",
    maxResults: maxResults.toString(),
    key: env.YOUTUBE_API_KEY,
    videoDuration: "medium",
    relevanceLanguage: "en",
  });

  if (pageToken) {
    params.set("pageToken", pageToken);
  }

  const response = await fetch(`${YOUTUBE_API_BASE}/search?${params}`);

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`YouTube API error: ${error}`);
  }

  const data: YouTubeSearchResponse = await response.json();

  const videos: YouTubeVideo[] = data.items.map((item) => ({
    id: item.id.videoId,
    title: item.snippet.title,
    description: item.snippet.description,
    thumbnailUrl: item.snippet.thumbnails.high.url,
    channelTitle: item.snippet.channelTitle,
    channelId: item.snippet.channelId,
    publishedAt: item.snippet.publishedAt,
  }));

  return {
    videos,
    nextPageToken: data.nextPageToken,
  };
}

export async function getVideoDetails(videoId: string): Promise<YouTubeVideo> {
  const params = new URLSearchParams({
    part: "snippet",
    id: videoId,
    key: env.YOUTUBE_API_KEY,
  });

  const response = await fetch(`${YOUTUBE_API_BASE}/videos?${params}`);

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`YouTube API error: ${error}`);
  }

  const data = await response.json();

  if (!data.items || data.items.length === 0) {
    throw new Error(`Video not found: ${videoId}`);
  }

  const item = data.items[0];

  return {
    id: videoId,
    title: item.snippet.title,
    description: item.snippet.description,
    thumbnailUrl: item.snippet.thumbnails.high?.url || item.snippet.thumbnails.default?.url,
    channelTitle: item.snippet.channelTitle,
    channelId: item.snippet.channelId,
    publishedAt: item.snippet.publishedAt,
  };
}

export async function getVideoTranscript(videoId: string): Promise<string> {
  try {
    const transcript = await YoutubeTranscript.fetchTranscript(videoId);
    return transcript.map((item) => item.text).join(" ");
  } catch (error) {
    throw new Error(
      `Failed to fetch transcript for video ${videoId}. The video may not have captions available.`
    );
  }
}
