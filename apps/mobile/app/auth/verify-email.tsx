import { useState, useCallback, useEffect } from "react";
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Alert,
  ActivityIndicator,
} from "react-native";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useAuthStore } from "../../src/store/auth";

export default function VerifyEmailScreen() {
  const router = useRouter();
  const { user, loading, resendVerification, refreshSession, signOut, emailVerified } =
    useAuthStore();

  const [resendCooldown, setResendCooldown] = useState(0);
  const [checking, setChecking] = useState(false);

  // Check if email was verified
  useEffect(() => {
    if (emailVerified) {
      router.replace("/(tabs)");
    }
  }, [emailVerified, router]);

  // Cooldown timer for resend button
  useEffect(() => {
    if (resendCooldown > 0) {
      const timer = setTimeout(() => setResendCooldown(resendCooldown - 1), 1000);
      return () => clearTimeout(timer);
    }
  }, [resendCooldown]);

  const handleResend = useCallback(async () => {
    try {
      await resendVerification();
      setResendCooldown(60); // 60 second cooldown
      Alert.alert("Email Sent", "A new verification email has been sent.");
    } catch (error: any) {
      Alert.alert("Error", error.message || "Failed to resend verification email");
    }
  }, [resendVerification]);

  const handleCheckVerification = useCallback(async () => {
    setChecking(true);
    try {
      await refreshSession();
      // The useEffect will handle navigation if verified
      if (!emailVerified) {
        Alert.alert(
          "Not Verified Yet",
          "Please check your email and click the verification link."
        );
      }
    } catch (error) {
      Alert.alert("Error", "Failed to check verification status");
    } finally {
      setChecking(false);
    }
  }, [refreshSession, emailVerified]);

  const handleSignOut = useCallback(async () => {
    await signOut();
    router.replace("/auth/login");
  }, [signOut, router]);

  return (
    <View style={styles.container}>
      <View style={styles.content}>
        <View style={styles.iconContainer}>
          <Ionicons name="mail-unread" size={80} color="#FF6B35" />
        </View>

        <Text style={styles.title}>Verify Your Email</Text>

        <Text style={styles.description}>
          We've sent a verification email to:
        </Text>

        <Text style={styles.email}>{user?.email}</Text>

        <Text style={styles.instructions}>
          Please check your inbox and click the verification link to continue.
          Don't forget to check your spam folder!
        </Text>

        <TouchableOpacity
          style={styles.checkButton}
          onPress={handleCheckVerification}
          disabled={checking}
        >
          {checking ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <>
              <Ionicons name="refresh" size={20} color="#fff" />
              <Text style={styles.checkButtonText}>I've Verified My Email</Text>
            </>
          )}
        </TouchableOpacity>

        <TouchableOpacity
          style={[
            styles.resendButton,
            resendCooldown > 0 && styles.resendButtonDisabled,
          ]}
          onPress={handleResend}
          disabled={loading || resendCooldown > 0}
        >
          {loading ? (
            <ActivityIndicator color="#FF6B35" />
          ) : (
            <Text
              style={[
                styles.resendButtonText,
                resendCooldown > 0 && styles.resendButtonTextDisabled,
              ]}
            >
              {resendCooldown > 0
                ? `Resend in ${resendCooldown}s`
                : "Resend Verification Email"}
            </Text>
          )}
        </TouchableOpacity>

        <TouchableOpacity style={styles.signOutButton} onPress={handleSignOut}>
          <Text style={styles.signOutText}>Use a different email</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#fff",
  },
  content: {
    flex: 1,
    padding: 24,
    justifyContent: "center",
    alignItems: "center",
  },
  iconContainer: {
    marginBottom: 24,
  },
  title: {
    fontSize: 28,
    fontWeight: "bold",
    color: "#333",
    marginBottom: 16,
    textAlign: "center",
  },
  description: {
    fontSize: 16,
    color: "#666",
    textAlign: "center",
  },
  email: {
    fontSize: 16,
    fontWeight: "600",
    color: "#333",
    marginTop: 8,
    marginBottom: 24,
  },
  instructions: {
    fontSize: 14,
    color: "#888",
    textAlign: "center",
    lineHeight: 20,
    marginBottom: 32,
    paddingHorizontal: 16,
  },
  checkButton: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#FF6B35",
    paddingVertical: 14,
    paddingHorizontal: 24,
    borderRadius: 12,
    width: "100%",
    gap: 8,
  },
  checkButtonText: {
    color: "#fff",
    fontSize: 16,
    fontWeight: "600",
  },
  resendButton: {
    marginTop: 16,
    paddingVertical: 14,
    paddingHorizontal: 24,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#FF6B35",
    width: "100%",
    alignItems: "center",
  },
  resendButtonDisabled: {
    borderColor: "#ccc",
  },
  resendButtonText: {
    color: "#FF6B35",
    fontSize: 16,
    fontWeight: "500",
  },
  resendButtonTextDisabled: {
    color: "#999",
  },
  signOutButton: {
    marginTop: 24,
    padding: 12,
  },
  signOutText: {
    color: "#666",
    fontSize: 14,
  },
});
