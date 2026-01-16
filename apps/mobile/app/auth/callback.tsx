import { useEffect } from "react";
import { View, ActivityIndicator, StyleSheet, Text } from "react-native";
import { useRouter, useLocalSearchParams } from "expo-router";
import * as Linking from "expo-linking";
import { supabase } from "../../src/lib/supabase";
import { useAuthStore } from "../../src/store/auth";

export default function AuthCallbackScreen() {
  const router = useRouter();
  const params = useLocalSearchParams();
  const { refreshSession } = useAuthStore();

  useEffect(() => {
    const handleCallback = async () => {
      try {
        // Get the URL that opened the app
        const url = await Linking.getInitialURL();

        if (url) {
          // Parse the URL for tokens (Supabase sends them as hash fragments)
          const { data, error } = await supabase.auth.getSession();

          if (error) {
            console.error("Auth callback error:", error);
            router.replace("/auth/login");
            return;
          }

          if (data.session) {
            // Refresh to get latest user data including email_confirmed_at
            await refreshSession();

            // Check if email is verified
            const { data: userData } = await supabase.auth.getUser();
            if (userData.user?.email_confirmed_at) {
              router.replace("/(tabs)");
            } else {
              router.replace("/auth/verify-email");
            }
          } else {
            router.replace("/auth/login");
          }
        } else {
          router.replace("/auth/login");
        }
      } catch (error) {
        console.error("Callback handling error:", error);
        router.replace("/auth/login");
      }
    };

    handleCallback();
  }, [router, refreshSession]);

  return (
    <View style={styles.container}>
      <ActivityIndicator size="large" color="#FF6B35" />
      <Text style={styles.text}>Completing sign in...</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "#fff",
  },
  text: {
    marginTop: 16,
    fontSize: 16,
    color: "#666",
  },
});
