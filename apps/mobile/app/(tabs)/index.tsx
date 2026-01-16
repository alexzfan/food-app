import { useState, useCallback } from "react";
import {
  View,
  FlatList,
  ActivityIndicator,
  StyleSheet,
  Alert,
} from "react-native";
import { useRouter } from "expo-router";
import { SearchBar, VideoCard, EmptyState } from "../../src/components";
import { searchYouTubeVideos, extractRecipeFromVideo } from "../../src/services/api";
import type { YouTubeVideo } from "../../src/types";

export default function DiscoverScreen() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [videos, setVideos] = useState<YouTubeVideo[]>([]);
  const [loading, setLoading] = useState(false);
  const [extractingId, setExtractingId] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState(false);

  const handleSearch = useCallback(async () => {
    if (!query.trim()) return;

    setLoading(true);
    setHasSearched(true);
    try {
      const result = await searchYouTubeVideos(query.trim());
      setVideos(result.videos);
    } catch (error) {
      Alert.alert("Error", "Failed to search videos. Please try again.");
      console.error("Search error:", error);
    } finally {
      setLoading(false);
    }
  }, [query]);

  const handleVideoPress = useCallback(async (video: YouTubeVideo) => {
    setExtractingId(video.id);
    try {
      const { recipe } = await extractRecipeFromVideo(video.id);
      router.push(`/recipe/${recipe.id}`);
    } catch (error) {
      Alert.alert(
        "Extraction Failed",
        "Could not extract recipe from this video. It may not have captions available."
      );
      console.error("Extraction error:", error);
    } finally {
      setExtractingId(null);
    }
  }, [router]);

  const renderItem = useCallback(
    ({ item }: { item: YouTubeVideo }) => (
      <VideoCard
        video={item}
        onPress={() => handleVideoPress(item)}
        loading={extractingId === item.id}
      />
    ),
    [handleVideoPress, extractingId]
  );

  return (
    <View style={styles.container}>
      <SearchBar
        value={query}
        onChangeText={setQuery}
        onSubmit={handleSearch}
        placeholder="Search YouTube for recipes..."
      />

      {loading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#FF6B35" />
        </View>
      ) : videos.length === 0 ? (
        <EmptyState
          icon={hasSearched ? "search-outline" : "restaurant-outline"}
          title={hasSearched ? "No videos found" : "Discover Recipes"}
          message={
            hasSearched
              ? "Try a different search term"
              : "Search YouTube for recipe videos and save them to your collection"
          }
        />
      ) : (
        <FlatList
          data={videos}
          renderItem={renderItem}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.list}
          showsVerticalScrollIndicator={false}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#f8f8f8",
  },
  loadingContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
  },
  list: {
    paddingVertical: 8,
  },
});
