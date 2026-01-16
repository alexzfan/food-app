import { useState, useEffect, useCallback } from "react";
import {
  View,
  Text,
  ScrollView,
  Image,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Linking,
  Alert,
} from "react-native";
import { useLocalSearchParams, Stack } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import {
  getRecipeById,
  addFavorite,
  removeFavorite,
} from "../../src/services/api";
import type { Recipe, Ingredient, Instruction } from "../../src/types";

export default function RecipeDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [recipe, setRecipe] = useState<Recipe | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (id) {
      getRecipeById(id)
        .then(setRecipe)
        .catch((error) => {
          console.error("Failed to load recipe:", error);
          Alert.alert("Error", "Failed to load recipe");
        })
        .finally(() => setLoading(false));
    }
  }, [id]);

  const handleFavoritePress = useCallback(async () => {
    if (!recipe) return;

    try {
      if (recipe.is_favorite) {
        await removeFavorite(recipe.id);
        setRecipe({ ...recipe, is_favorite: false });
      } else {
        await addFavorite(recipe.id);
        setRecipe({ ...recipe, is_favorite: true });
      }
    } catch (error) {
      Alert.alert("Error", "Failed to update favorite");
    }
  }, [recipe]);

  const handleWatchVideo = useCallback(() => {
    if (recipe?.youtube_video_id) {
      Linking.openURL(`https://youtube.com/watch?v=${recipe.youtube_video_id}`);
    }
  }, [recipe]);

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#FF6B35" />
      </View>
    );
  }

  if (!recipe) {
    return (
      <View style={styles.loadingContainer}>
        <Text style={styles.errorText}>Recipe not found</Text>
      </View>
    );
  }

  return (
    <>
      <Stack.Screen
        options={{
          title: recipe.title,
          headerRight: () => (
            <TouchableOpacity onPress={handleFavoritePress}>
              <Ionicons
                name={recipe.is_favorite ? "heart" : "heart-outline"}
                size={24}
                color={recipe.is_favorite ? "#FF6B35" : "#333"}
              />
            </TouchableOpacity>
          ),
        }}
      />
      <ScrollView style={styles.container} showsVerticalScrollIndicator={false}>
        <Image source={{ uri: recipe.thumbnail_url }} style={styles.image} />

        <View style={styles.content}>
          <Text style={styles.title}>{recipe.title}</Text>
          <Text style={styles.channel}>by {recipe.channel_name}</Text>

          {recipe.description && (
            <Text style={styles.description}>{recipe.description}</Text>
          )}

          <View style={styles.metaRow}>
            {recipe.prep_time_minutes && (
              <View style={styles.metaItem}>
                <Ionicons name="timer-outline" size={18} color="#666" />
                <Text style={styles.metaLabel}>Prep</Text>
                <Text style={styles.metaValue}>{recipe.prep_time_minutes}m</Text>
              </View>
            )}
            {recipe.cook_time_minutes && (
              <View style={styles.metaItem}>
                <Ionicons name="flame-outline" size={18} color="#666" />
                <Text style={styles.metaLabel}>Cook</Text>
                <Text style={styles.metaValue}>{recipe.cook_time_minutes}m</Text>
              </View>
            )}
            {recipe.servings && (
              <View style={styles.metaItem}>
                <Ionicons name="people-outline" size={18} color="#666" />
                <Text style={styles.metaLabel}>Serves</Text>
                <Text style={styles.metaValue}>{recipe.servings}</Text>
              </View>
            )}
            {recipe.difficulty && (
              <View style={styles.metaItem}>
                <Ionicons name="speedometer-outline" size={18} color="#666" />
                <Text style={styles.metaLabel}>Level</Text>
                <Text style={styles.metaValue}>{recipe.difficulty}</Text>
              </View>
            )}
          </View>

          {recipe.tags && recipe.tags.length > 0 && (
            <View style={styles.tagsContainer}>
              {recipe.tags.map((tag, index) => (
                <View key={index} style={styles.tag}>
                  <Text style={styles.tagText}>{tag}</Text>
                </View>
              ))}
            </View>
          )}

          <TouchableOpacity style={styles.watchButton} onPress={handleWatchVideo}>
            <Ionicons name="logo-youtube" size={20} color="#fff" />
            <Text style={styles.watchButtonText}>Watch on YouTube</Text>
          </TouchableOpacity>

          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Ingredients</Text>
            {recipe.ingredients.map((ingredient: Ingredient, index: number) => (
              <View key={index} style={styles.ingredientRow}>
                <View style={styles.bullet} />
                <Text style={styles.ingredientText}>
                  <Text style={styles.ingredientAmount}>
                    {ingredient.amount}
                    {ingredient.unit ? ` ${ingredient.unit}` : ""}
                  </Text>
                  {"  "}
                  {ingredient.name}
                  {ingredient.notes && (
                    <Text style={styles.ingredientNotes}> ({ingredient.notes})</Text>
                  )}
                </Text>
              </View>
            ))}
          </View>

          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Instructions</Text>
            {recipe.instructions.map((instruction: Instruction, index: number) => (
              <View key={index} style={styles.instructionRow}>
                <View style={styles.stepNumber}>
                  <Text style={styles.stepNumberText}>{instruction.step}</Text>
                </View>
                <View style={styles.instructionContent}>
                  <Text style={styles.instructionText}>{instruction.text}</Text>
                  {instruction.duration && (
                    <Text style={styles.instructionDuration}>
                      <Ionicons name="time-outline" size={12} color="#888" />{" "}
                      {instruction.duration}
                    </Text>
                  )}
                </View>
              </View>
            ))}
          </View>
        </View>
      </ScrollView>
    </>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#fff",
  },
  loadingContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "#fff",
  },
  errorText: {
    fontSize: 16,
    color: "#666",
  },
  image: {
    width: "100%",
    height: 220,
    backgroundColor: "#eee",
  },
  content: {
    padding: 20,
  },
  title: {
    fontSize: 24,
    fontWeight: "bold",
    color: "#333",
    marginBottom: 4,
  },
  channel: {
    fontSize: 14,
    color: "#666",
    marginBottom: 12,
  },
  description: {
    fontSize: 15,
    color: "#555",
    lineHeight: 22,
    marginBottom: 16,
  },
  metaRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 16,
    marginBottom: 16,
    paddingVertical: 12,
    borderTopWidth: 1,
    borderBottomWidth: 1,
    borderColor: "#eee",
  },
  metaItem: {
    alignItems: "center",
    minWidth: 60,
  },
  metaLabel: {
    fontSize: 11,
    color: "#888",
    marginTop: 4,
  },
  metaValue: {
    fontSize: 14,
    fontWeight: "600",
    color: "#333",
  },
  tagsContainer: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
    marginBottom: 20,
  },
  tag: {
    backgroundColor: "#f0f0f0",
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
  },
  tagText: {
    fontSize: 12,
    color: "#666",
  },
  watchButton: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#FF0000",
    paddingVertical: 12,
    borderRadius: 8,
    marginBottom: 24,
    gap: 8,
  },
  watchButtonText: {
    color: "#fff",
    fontSize: 16,
    fontWeight: "600",
  },
  section: {
    marginBottom: 24,
  },
  sectionTitle: {
    fontSize: 20,
    fontWeight: "bold",
    color: "#333",
    marginBottom: 16,
  },
  ingredientRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    marginBottom: 10,
  },
  bullet: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: "#FF6B35",
    marginTop: 7,
    marginRight: 12,
  },
  ingredientText: {
    flex: 1,
    fontSize: 15,
    color: "#444",
    lineHeight: 20,
  },
  ingredientAmount: {
    fontWeight: "600",
    color: "#333",
  },
  ingredientNotes: {
    fontStyle: "italic",
    color: "#888",
  },
  instructionRow: {
    flexDirection: "row",
    marginBottom: 16,
  },
  stepNumber: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: "#FF6B35",
    justifyContent: "center",
    alignItems: "center",
    marginRight: 12,
  },
  stepNumberText: {
    color: "#fff",
    fontSize: 14,
    fontWeight: "bold",
  },
  instructionContent: {
    flex: 1,
  },
  instructionText: {
    fontSize: 15,
    color: "#444",
    lineHeight: 22,
  },
  instructionDuration: {
    fontSize: 12,
    color: "#888",
    marginTop: 4,
  },
});
