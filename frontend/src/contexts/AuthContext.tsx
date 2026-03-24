/**
 * Authentication Context
 *
 * Provides authentication state and methods throughout the app.
 * Manages Firebase auth state and syncs with backend user profile.
 */

import { createContext, useContext, useEffect, useState } from 'react';
import { User, onAuthStateChanged, signInWithPopup, signOut as firebaseSignOut } from 'firebase/auth';
import { auth, googleProvider } from '../lib/firebase';
import { api } from '../lib/api';

interface AuthContextType {
  user: User | null;
  userId: number | null;
  username: string | null;
  loading: boolean;
  needsRegistration: boolean;
  error: string | null;
  signInWithGoogle: () => Promise<void>;
  signOut: () => Promise<void>;
  registerUser: (username: string) => Promise<void>;
  retryAuth: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [userId, setUserId] = useState<number | null>(null);
  const [username, setUsername] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [needsRegistration, setNeedsRegistration] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const checkUserProfile = async (firebaseUser: User) => {
    try {
      // Get and store Firebase ID token
      const token = await firebaseUser.getIdToken(true); // Force refresh
      console.log('Got Firebase token, length:', token.length, 'first 50 chars:', token.substring(0, 50));
      localStorage.setItem('authToken', token);

      // Try to get user profile from backend
      const profile = await api.getAuthenticatedUser();
      setUserId(profile.user_id);
      setUsername(profile.username);
      setNeedsRegistration(false);
      setError(null);
    } catch (err: any) {
      // Check if user doesn't exist (404) vs other errors
      const errorMessage = err?.message || String(err);

      if (errorMessage.includes('404') || errorMessage.includes('User not found')) {
        // User authenticated with Google but not registered in backend
        console.log('New user - needs registration');
        setUserId(null);
        setUsername(null);
        setNeedsRegistration(true);
        setError(null);
      } else {
        // Other error (network, server down, etc.) - don't clear existing state
        console.error('Error checking user profile:', err);
        setError('Failed to connect to server. Please check your connection and try again.');
        setNeedsRegistration(false);
      }
    }
  };

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, async (firebaseUser) => {
      setLoading(true);
      setUser(firebaseUser);

      if (firebaseUser) {
        await checkUserProfile(firebaseUser);
      } else {
        // User signed out
        localStorage.removeItem('authToken');
        setUserId(null);
        setUsername(null);
        setNeedsRegistration(false);
        setError(null);
      }

      setLoading(false);
    });

    return unsubscribe;
  }, []);

  const signInWithGoogle = async () => {
    try {
      await signInWithPopup(auth, googleProvider);
      // onAuthStateChanged will handle the rest
    } catch (error) {
      console.error('Sign in error:', error);
      throw error;
    }
  };

  const signOut = async () => {
    try {
      await firebaseSignOut(auth);
      // onAuthStateChanged will handle clearing state
    } catch (error) {
      console.error('Sign out error:', error);
      throw error;
    }
  };

  const registerUser = async (username: string) => {
    if (!user) {
      throw new Error('No Firebase user');
    }

    try {
      // Get fresh token before registration
      const token = await user.getIdToken(true);
      localStorage.setItem('authToken', token);

      const data = await api.registerUser({
        firebase_uid: user.uid,
        email: user.email!,
        username,
      });

      setUserId(data.user_id);
      setUsername(data.username);
      setNeedsRegistration(false);
      setError(null);
    } catch (error) {
      console.error('Registration error:', error);
      throw error;
    }
  };

  const retryAuth = async () => {
    if (user) {
      setLoading(true);
      setError(null);
      await checkUserProfile(user);
      setLoading(false);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        userId,
        username,
        loading,
        needsRegistration,
        error,
        signInWithGoogle,
        signOut,
        registerUser,
        retryAuth
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}
