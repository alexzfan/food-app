import { useState, useCallback, useEffect } from "react";
import {
  View,
  FlatList,
  StyleSheet,
  ActivityIndicator,
  RefreshControl,
  Alert,
} from "react-native";
import { useRouter } from "expo-router";
import { RecipeCard, EmptyState } from "../../src/components";
import { getFavorites, removeFavorite } from "../../src/services/api";
import type { Recipe } from "../../src/types";

export default function FavoritesScreen() {
  const router = useRouter();
  const [favorites, setFavorites] = useState<Recipe[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadFavorites = useCallback(async () => {
    try {
      const data = await getFavorites();
      setFavorites(data);
    } catch (error) {
      console.error("Failed to load favorites:", error);
      Alert.alert("Error", "Failed to load favorites");
    }
  }, []);

  useEffect(() => {
    loadFavorites().finally(() => setLoading(false));
  }, [loadFavorites]);

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadFavorites();
    setRefreshing(false);
  }, [loadFavorites]);

  const handleRemoveFavorite = useCallback(
    async (recipeId: string) => {
      try {
        await removeFavorite(recipeId);
        setFavorites((prev) => prev.filter((r) => r.id !== recipeId));
      } catch (error) {
        Alert.alert("Error", "Failed to remove from favorites");
      }
    },
    []
  );

  const renderItem = useCallback(
    ({ item }: { item: Recipe }) => (
      <RecipeCard
        recipe={item}
        onPress={() => router.push(`/recipe/${item.id}`)}
        onFavoritePress={() => handleRemoveFavorite(item.id)}
        isFavorite={true}
      />
    ),
    [router, handleRemoveFavorite]
  );

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#FF6B35" />
      </View>
    );
  }

  if (favorites.length === 0) {
    return (
      <View style={styles.container}>
        <EmptyState
          icon="heart-outline"
          title="No favorites yet"
          message="Tap the heart icon on any recipe to add it to your favorites"
        />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <FlatList
        data={favorites}
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
