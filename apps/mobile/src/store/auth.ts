import { create } from "zustand";
import { supabase } from "../lib/supabase";
import type { Session, User } from "@supabase/supabase-js";

interface AuthState {
  session: Session | null;
  user: User | null;
  loading: boolean;
  initialized: boolean;
  emailVerified: boolean;

  initialize: () => Promise<void>;
  signInWithEmail: (email: string, password: string) => Promise<void>;
  signUpWithEmail: (email: string, password: string) => Promise<{ needsVerification: boolean }>;
  signInWithGoogle: () => Promise<void>;
  signOut: () => Promise<void>;
  setSession: (session: Session | null) => void;
  refreshSession: () => Promise<void>;
  resendVerification: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  session: null,
  user: null,
  loading: false,
  initialized: false,
  emailVerified: false,

  initialize: async () => {
    try {
      const {
        data: { session },
      } = await supabase.auth.getSession();

      const emailVerified = !!session?.user?.email_confirmed_at;

      set({
        session,
        user: session?.user ?? null,
        emailVerified,
        initialized: true,
      });

      // Listen for auth changes
      supabase.auth.onAuthStateChange((_event, session) => {
        const emailVerified = !!session?.user?.email_confirmed_at;
        set({
          session,
          user: session?.user ?? null,
          emailVerified,
        });
      });
    } catch (error) {
      console.error("Auth initialization error:", error);
      set({ initialized: true });
    }
  },

  signInWithEmail: async (email: string, password: string) => {
    set({ loading: true });
    try {
      const { data, error } = await supabase.auth.signInWithPassword({
        email,
        password,
      });

      if (error) throw error;

      const emailVerified = !!data.user?.email_confirmed_at;

      set({
        session: data.session,
        user: data.user,
        emailVerified,
      });
    } finally {
      set({ loading: false });
    }
  },

  signUpWithEmail: async (email: string, password: string) => {
    set({ loading: true });
    try {
      const { data, error } = await supabase.auth.signUp({
        email,
        password,
        options: {
          emailRedirectTo: "recipefinder://auth/verify",
        },
      });

      if (error) throw error;

      // If session exists, user is logged in (email verification might be disabled)
      // If no session, user needs to verify email
      if (data.session) {
        const emailVerified = !!data.user?.email_confirmed_at;
        set({
          session: data.session,
          user: data.user,
          emailVerified,
        });
        return { needsVerification: !emailVerified };
      }

      // User created but needs verification - store user for reference
      set({
        user: data.user,
        emailVerified: false,
      });

      return { needsVerification: true };
    } finally {
      set({ loading: false });
    }
  },

  signInWithGoogle: async () => {
    set({ loading: true });
    try {
      const { error } = await supabase.auth.signInWithOAuth({
        provider: "google",
        options: {
          redirectTo: "recipefinder://auth/callback",
        },
      });

      if (error) throw error;
    } finally {
      set({ loading: false });
    }
  },

  signOut: async () => {
    set({ loading: true });
    try {
      const { error } = await supabase.auth.signOut();
      if (error) throw error;

      set({
        session: null,
        user: null,
        emailVerified: false,
      });
    } finally {
      set({ loading: false });
    }
  },

  setSession: (session: Session | null) => {
    const emailVerified = !!session?.user?.email_confirmed_at;
    set({
      session,
      user: session?.user ?? null,
      emailVerified,
    });
  },

  refreshSession: async () => {
    try {
      const { data, error } = await supabase.auth.refreshSession();

      if (error) throw error;

      const emailVerified = !!data.session?.user?.email_confirmed_at;

      set({
        session: data.session,
        user: data.session?.user ?? null,
        emailVerified,
      });
    } catch (error) {
      console.error("Failed to refresh session:", error);
    }
  },

  resendVerification: async () => {
    const { user } = get();
    if (!user?.email) throw new Error("No email address found");

    set({ loading: true });
    try {
      const { error } = await supabase.auth.resend({
        type: "signup",
        email: user.email,
        options: {
          emailRedirectTo: "recipefinder://auth/verify",
        },
      });

      if (error) throw error;
    } finally {
      set({ loading: false });
    }
  },
}));
