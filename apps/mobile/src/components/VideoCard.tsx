import { View, Text, Image, TouchableOpacity, StyleSheet } from "react-native";
import type { YouTubeVideo } from "../types";

interface VideoCardProps {
  video: YouTubeVideo;
  onPress: () => void;
  loading?: boolean;
  loadingText?: string;
}

export function VideoCard({ video, onPress, loading, loadingText }: VideoCardProps) {
  return (
    <TouchableOpacity
      style={styles.container}
      onPress={onPress}
      disabled={loading}
      activeOpacity={0.7}
    >
      <Image source={{ uri: video.thumbnailUrl }} style={styles.thumbnail} />
      <View style={styles.content}>
        <Text style={styles.title} numberOfLines={2}>
          {video.title}
        </Text>
        <Text style={styles.channel}>{video.channelTitle}</Text>
        {loading && (
          <Text style={styles.loading}>
            {loadingText || "Extracting recipe..."}
          </Text>
        )}
      </View>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: "row",
    padding: 12,
    backgroundColor: "#fff",
    borderRadius: 12,
    marginHorizontal: 16,
    marginVertical: 6,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  thumbnail: {
    width: 120,
    height: 68,
    borderRadius: 8,
    backgroundColor: "#eee",
  },
  content: {
    flex: 1,
    marginLeft: 12,
    justifyContent: "center",
  },
  title: {
    fontSize: 14,
    fontWeight: "600",
    color: "#333",
    marginBottom: 4,
  },
  channel: {
    fontSize: 12,
    color: "#666",
  },
  loading: {
    fontSize: 11,
    color: "#FF6B35",
    marginTop: 4,
    fontStyle: "italic",
  },
});
