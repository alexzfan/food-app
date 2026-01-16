import { useEffect } from "react";
import { Stack, useRouter, useSegments } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { View, ActivityIndicator, StyleSheet } from "react-native";
import * as Linking from "expo-linking";
import { supabase } from "../src/lib/supabase";
import { useAuthStore } from "../src/store/auth";

function AuthGate({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const segments = useSegments();
  const { session, initialized, initialize, emailVerified, setSession } = useAuthStore();

  // Initialize auth
  useEffect(() => {
    initialize();
  }, [initialize]);

  // Handle deep links for auth
  useEffect(() => {
    const handleDeepLink = async (url: string) => {
      if (url.includes("auth/callback") || url.includes("auth/verify")) {
        // Supabase will handle the token exchange
        const { data, error } = await supabase.auth.getSession();
        if (data.session && !error) {
          setSession(data.session);
        }
      }
    };

    // Handle initial URL
    Linking.getInitialURL().then((url) => {
      if (url) handleDeepLink(url);
    });

    // Handle URLs while app is open
    const subscription = Linking.addEventListener("url", ({ url }) => {
      handleDeepLink(url);
    });

    return () => subscription.remove();
  }, [setSession]);

  // Handle navigation based on auth state
  useEffect(() => {
    if (!initialized) return;

    const inAuthGroup = segments[0] === "auth";
    const inVerifyScreen = segments[1] === "verify-email";
    const inCallbackScreen = segments[1] === "callback" || segments[1] === "verify";

    // Don't redirect if we're handling a callback
    if (inCallbackScreen) return;

    if (!session && !inAuthGroup) {
      // Not authenticated, redirect to login
      router.replace("/auth/login");
    } else if (session && !emailVerified && !inVerifyScreen && !inCallbackScreen) {
      // Authenticated but email not verified
      router.replace("/auth/verify-email");
    } else if (session && emailVerified && inAuthGroup) {
      // Authenticated and verified, redirect to main app
      router.replace("/(tabs)");
    }
  }, [session, initialized, emailVerified, segments, router]);

  if (!initialized) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#FF6B35" />
      </View>
    );
  }

  return <>{children}</>;
}

export default function RootLayout() {
  return (
    <AuthGate>
      <StatusBar style="auto" />
      <Stack>
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen name="auth/login" options={{ headerShown: false }} />
        <Stack.Screen name="auth/signup" options={{ headerShown: false }} />
        <Stack.Screen name="auth/verify-email" options={{ headerShown: false }} />
        <Stack.Screen name="auth/callback" options={{ headerShown: false }} />
        <Stack.Screen name="auth/verify" options={{ headerShown: false }} />
        <Stack.Screen
          name="recipe/[id]"
          options={{
            title: "Recipe",
            headerBackTitle: "Back",
          }}
        />
      </Stack>
    </AuthGate>
  );
}

const styles = StyleSheet.create({
  loadingContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "#fff",
  },
});
