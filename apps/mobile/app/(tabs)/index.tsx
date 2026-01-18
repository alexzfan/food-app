import { useState, useCallback } from "react";
import {
  View,
  FlatList,
  ActivityIndicator,
  StyleSheet,
  Alert,
  Text,
  TouchableOpacity,
} from "react-native";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { SearchBar, VideoCard, EmptyState } from "../../src/components";
import {
  searchYouTubeVideos,
  checkRecipeExists,
  saveRecipe,
  getVideoTranscript,
} from "../../src/services/api";
import { useGemmaRecipe } from "../../src/hooks/useGemma";
import type { YouTubeVideo } from "../../src/types";

type ExtractionStep =
  | "checking"
  | "transcribing"
  | "extracting"
  | "saving"
  | null;

export default function DiscoverScreen() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [videos, setVideos] = useState<YouTubeVideo[]>([]);
  const [loading, setLoading] = useState(false);
  const [extractingId, setExtractingId] = useState<string | null>(null);
  const [extractionStep, setExtractionStep] = useState<ExtractionStep>(null);
  const [hasSearched, setHasSearched] = useState(false);

  const {
    isModelLoaded,
    isDownloading,
    downloadProgress,
    isExtracting,
    downloadModel,
    extractRecipe,
  } = useGemmaRecipe();

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

  const handleVideoPress = useCallback(
    async (video: YouTubeVideo) => {
      // Check if model is ready
      if (!isModelLoaded) {
        Alert.alert(
          "Model Not Ready",
          "The AI model needs to be downloaded first. This is a one-time download of approximately 1.5GB. Would you like to download it now?",
          [
            { text: "Cancel", style: "cancel" },
            { text: "Download", onPress: downloadModel },
          ]
        );
        return;
      }

      setExtractingId(video.id);

      try {
        // Step 1: Check if recipe already exists
        setExtractionStep("checking");
        const { recipe: existing, exists } = await checkRecipeExists(video.id);
        if (exists && existing) {
          router.push(`/recipe/${existing.id}`);
          return;
        }

        // Step 2: Get transcript (server does audio download + Whisper transcription)
        setExtractionStep("transcribing");
        const transcriptData = await getVideoTranscript(video.id);

        // Step 3: Extract recipe using Gemma on-device
        setExtractionStep("extracting");
        const recipeSummary = await extractRecipe(
          transcriptData.transcript,
          transcriptData.title
        );

        // Step 4: Save recipe to backend
        setExtractionStep("saving");
        const { recipe } = await saveRecipe({
          videoId: video.id,
          title: recipeSummary.title,
          description: recipeSummary.description,
          ingredients: recipeSummary.ingredients,
          instructions: recipeSummary.instructions,
          tags: recipeSummary.tags,
          cuisine: recipeSummary.cuisine,
          cook_time_minutes: recipeSummary.cook_time_minutes,
          prep_time_minutes: recipeSummary.prep_time_minutes,
          servings: recipeSummary.servings,
          difficulty: recipeSummary.difficulty,
        });

        router.push(`/recipe/${recipe.id}`);
      } catch (error) {
        console.error("Extraction error:", error);
        Alert.alert(
          "Extraction Failed",
          "Could not extract recipe from this video. Please try again."
        );
      } finally {
        setExtractingId(null);
        setExtractionStep(null);
      }
    },
    [router, isModelLoaded, downloadModel, extractRecipe]
  );

  const getExtractionStatusText = (step: ExtractionStep): string => {
    switch (step) {
      case "checking":
        return "Checking...";
      case "transcribing":
        return "Transcribing video...";
      case "extracting":
        return "Extracting recipe (on-device)...";
      case "saving":
        return "Saving recipe...";
      default:
        return "Processing...";
    }
  };

  const renderItem = useCallback(
    ({ item }: { item: YouTubeVideo }) => (
      <VideoCard
        video={item}
        onPress={() => handleVideoPress(item)}
        loading={extractingId === item.id}
        loadingText={
          extractingId === item.id
            ? getExtractionStatusText(extractionStep)
            : undefined
        }
      />
    ),
    [handleVideoPress, extractingId, extractionStep]
  );

  const renderModelStatus = () => {
    if (isModelLoaded) return null;

    return (
      <View style={styles.modelStatusContainer}>
        <Ionicons
          name="hardware-chip-outline"
          size={24}
          color="#FF6B35"
          style={styles.modelIcon}
        />
        <View style={styles.modelTextContainer}>
          {isDownloading ? (
            <>
              <Text style={styles.modelStatusText}>
                Downloading AI model... {Math.round(downloadProgress * 100)}%
              </Text>
              <View style={styles.progressBar}>
                <View
                  style={[
                    styles.progressFill,
                    { width: `${downloadProgress * 100}%` },
                  ]}
                />
              </View>
            </>
          ) : (
            <TouchableOpacity onPress={downloadModel}>
              <Text style={styles.modelActionText}>
                Tap to download AI model (~1.5GB)
              </Text>
              <Text style={styles.modelSubtext}>
                Required for on-device recipe extraction
              </Text>
            </TouchableOpacity>
          )}
        </View>
      </View>
    );
  };

  return (
    <View style={styles.container}>
      {renderModelStatus()}

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
  modelStatusContainer: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#FFF3E0",
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: "#FFE0B2",
  },
  modelIcon: {
    marginRight: 12,
  },
  modelTextContainer: {
    flex: 1,
  },
  modelStatusText: {
    fontSize: 14,
    color: "#E65100",
  },
  modelActionText: {
    fontSize: 14,
    color: "#FF6B35",
    fontWeight: "600",
  },
  modelSubtext: {
    fontSize: 12,
    color: "#999",
    marginTop: 2,
  },
  progressBar: {
    height: 4,
    backgroundColor: "#FFE0B2",
    borderRadius: 2,
    marginTop: 6,
    overflow: "hidden",
  },
  progressFill: {
    height: "100%",
    backgroundColor: "#FF6B35",
    borderRadius: 2,
  },
});
