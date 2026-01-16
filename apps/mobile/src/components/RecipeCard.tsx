import { View, Text, Image, TouchableOpacity, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import type { Recipe } from "../types";

interface RecipeCardProps {
  recipe: Recipe;
  onPress: () => void;
  onFavoritePress?: () => void;
  isFavorite?: boolean;
}

export function RecipeCard({
  recipe,
  onPress,
  onFavoritePress,
  isFavorite,
}: RecipeCardProps) {
  return (
    <TouchableOpacity
      style={styles.container}
      onPress={onPress}
      activeOpacity={0.7}
    >
      <Image source={{ uri: recipe.thumbnail_url }} style={styles.thumbnail} />
      <View style={styles.content}>
        <View style={styles.header}>
          <Text style={styles.title} numberOfLines={2}>
            {recipe.title}
          </Text>
          {onFavoritePress && (
            <TouchableOpacity onPress={onFavoritePress} style={styles.favoriteBtn}>
              <Ionicons
                name={isFavorite ? "heart" : "heart-outline"}
                size={22}
                color={isFavorite ? "#FF6B35" : "#888"}
              />
            </TouchableOpacity>
          )}
        </View>
        <Text style={styles.channel}>{recipe.channel_name}</Text>
        <View style={styles.meta}>
          {recipe.cook_time_minutes && (
            <View style={styles.metaItem}>
              <Ionicons name="time-outline" size={14} color="#666" />
              <Text style={styles.metaText}>{recipe.cook_time_minutes} min</Text>
            </View>
          )}
          {recipe.servings && (
            <View style={styles.metaItem}>
              <Ionicons name="people-outline" size={14} color="#666" />
              <Text style={styles.metaText}>{recipe.servings} servings</Text>
            </View>
          )}
          {recipe.difficulty && (
            <View style={[styles.difficultyBadge, styles[recipe.difficulty]]}>
              <Text style={styles.difficultyText}>{recipe.difficulty}</Text>
            </View>
          )}
        </View>
      </View>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: "#fff",
    borderRadius: 12,
    marginHorizontal: 16,
    marginVertical: 6,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
    overflow: "hidden",
  },
  thumbnail: {
    width: "100%",
    height: 160,
    backgroundColor: "#eee",
  },
  content: {
    padding: 12,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
  },
  title: {
    flex: 1,
    fontSize: 16,
    fontWeight: "600",
    color: "#333",
    marginBottom: 4,
  },
  favoriteBtn: {
    padding: 4,
    marginLeft: 8,
  },
  channel: {
    fontSize: 13,
    color: "#666",
    marginBottom: 8,
  },
  meta: {
    flexDirection: "row",
    alignItems: "center",
    flexWrap: "wrap",
    gap: 12,
  },
  metaItem: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  metaText: {
    fontSize: 12,
    color: "#666",
  },
  difficultyBadge: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 10,
  },
  easy: {
    backgroundColor: "#E8F5E9",
  },
  medium: {
    backgroundColor: "#FFF3E0",
  },
  hard: {
    backgroundColor: "#FFEBEE",
  },
  difficultyText: {
    fontSize: 11,
    fontWeight: "500",
    textTransform: "capitalize",
  },
});
