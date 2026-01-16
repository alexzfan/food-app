import { useState, useCallback, useEffect } from "react";
import {
  View,
  FlatList,
  ActivityIndicator,
  StyleSheet,
  RefreshControl,
  Alert,
} from "react-native";
import { useRouter } from "expo-router";
import { SearchBar, RecipeCard, EmptyState } from "../../src/components";
import {
  getAllRecipes,
  searchRecipes,
  addFavorite,
  removeFavorite,
} from "../../src/services/api";
import type { Recipe } from "../../src/types";

export default function SavedRecipesScreen() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadRecipes = useCallback(async (searchQuery?: string) => {
    try {
      const data = searchQuery
        ? await searchRecipes(searchQuery)
        : await getAllRecipes();
      setRecipes(data);
    } catch (error) {
      Alert.alert("Error", "Failed to load recipes");
      console.error("Load error:", error);
    }
  }, []);

  useEffect(() => {
    loadRecipes().finally(() => setLoading(false));
  }, [loadRecipes]);

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadRecipes(query || undefined);
    setRefreshing(false);
  }, [loadRecipes, query]);

  const handleSearch = useCallback(() => {
    setLoading(true);
    loadRecipes(query || undefined).finally(() => setLoading(false));
  }, [loadRecipes, query]);

  const handleFavoritePress = useCallback(async (recipe: Recipe) => {
    try {
      if (recipe.is_favorite) {
        await removeFavorite(recipe.id);
        setRecipes((prev) =>
          prev.map((r) =>
            r.id === recipe.id ? { ...r, is_favorite: false } : r
          )
        );
      } else {
        await addFavorite(recipe.id);
        setRecipes((prev) =>
          prev.map((r) =>
            r.id === recipe.id ? { ...r, is_favorite: true } : r
          )
        );
      }
    } catch (error) {
      Alert.alert("Error", "Failed to update favorite");
    }
  }, []);

  const renderItem = useCallback(
    ({ item }: { item: Recipe }) => (
      <RecipeCard
        recipe={item}
        onPress={() => router.push(`/recipe/${item.id}`)}
        onFavoritePress={() => handleFavoritePress(item)}
        isFavorite={item.is_favorite}
      />
    ),
    [router, handleFavoritePress]
  );

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#FF6B35" />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <SearchBar
        value={query}
        onChangeText={setQuery}
        onSubmit={handleSearch}
        placeholder="Search saved recipes..."
      />

      {recipes.length === 0 ? (
        <EmptyState
          icon="book-outline"
          title="No recipes yet"
          message="Extract recipes from YouTube videos on the Discover tab to see them here"
        />
      ) : (
        <FlatList
          data={recipes}
          renderItem={renderItem}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.list}
          showsVerticalScrollIndicator={false}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={handleRefresh}
              tintColor="#FF6B35"
            />
          }
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
    backgroundColor: "#f8f8f8",
  },
  list: {
    paddingVertical: 8,
  },
});
