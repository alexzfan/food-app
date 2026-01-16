import { useEffect } from "react";
import { View, ActivityIndicator, StyleSheet, Text } from "react-native";
import { useRouter } from "expo-router";
import { useAuthStore } from "../../src/store/auth";

// This screen handles the redirect after clicking email verification link
export default function VerifyRedirectScreen() {
  const router = useRouter();
  const { refreshSession } = useAuthStore();

  useEffect(() => {
    const handleVerification = async () => {
      try {
        // Refresh the session to get updated email_confirmed_at
        await refreshSession();

        // Small delay to ensure state is updated
        setTimeout(() => {
          router.replace("/(tabs)");
        }, 500);
      } catch (error) {
        console.error("Verification redirect error:", error);
        router.replace("/auth/login");
      }
    };

    handleVerification();
  }, [router, refreshSession]);

  return (
    <View style={styles.container}>
      <ActivityIndicator size="large" color="#FF6B35" />
      <Text style={styles.text}>Verifying your email...</Text>
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
