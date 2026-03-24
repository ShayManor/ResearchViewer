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
  signInWithGoogle: () => Promise<void>;
  signOut: () => Promise<void>;
  registerUser: (username: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [userId, setUserId] = useState<number | null>(null);
  const [username, setUsername] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, async (firebaseUser) => {
      setUser(firebaseUser);

      if (firebaseUser) {
        try {
          // Get and store Firebase ID token
          const token = await firebaseUser.getIdToken();
          localStorage.setItem('authToken', token);

          // Try to get user profile from backend
          const profile = await api.getAuthenticatedUser();
          setUserId(profile.user_id);
          setUsername(profile.username);
        } catch (err) {
          // User is authenticated with Firebase but not registered in backend yet
          console.log('User not registered in backend yet');
          setUserId(null);
          setUsername(null);
        }
      } else {
        // User signed out
        localStorage.removeItem('authToken');
        setUserId(null);
        setUsername(null);
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
      const data = await api.registerUser({
        firebase_uid: user.uid,
        email: user.email!,
        username,
      });

      setUserId(data.user_id);
      setUsername(data.username);
    } catch (error) {
      console.error('Registration error:', error);
      throw error;
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        userId,
        username,
        loading,
        signInWithGoogle,
        signOut,
        registerUser
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
