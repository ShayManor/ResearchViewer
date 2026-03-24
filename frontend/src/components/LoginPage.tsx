/**
 * Login Page Component
 *
 * Handles user authentication flow:
 * 1. Google sign-in for unauthenticated users
 * 2. Username registration for authenticated but unregistered users
 * 3. Redirects to main app once fully authenticated
 */

import { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { LogIn, Loader2 } from 'lucide-react';

export function LoginPage() {
  const { signInWithGoogle, registerUser, user, userId, loading, needsRegistration, error: authError, retryAuth } = useAuth();
  const [username, setUsername] = useState('');
  const [registering, setRegistering] = useState(false);
  const [localError, setLocalError] = useState('');

  const handleGoogleSignIn = async () => {
    try {
      setLocalError('');
      await signInWithGoogle();
    } catch (err) {
      console.error('Sign in failed:', err);
      setLocalError('Sign in failed. Please try again.');
    }
  };

  const handleRegister = async () => {
    if (!username.trim()) {
      setLocalError('Please enter a username');
      return;
    }

    setRegistering(true);
    setLocalError('');

    try {
      await registerUser(username);
    } catch (err) {
      console.error('Registration failed:', err);
      setLocalError('Registration failed. Username may already be taken.');
    } finally {
      setRegistering(false);
    }
  };

  // Show loading spinner while checking auth state
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <Loader2 size={32} className="animate-spin text-gray-400" />
      </div>
    );
  }

  // Show error screen with retry if there was a connection issue
  if (user && authError) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="w-full max-w-md p-8 bg-white rounded-2xl shadow-lg border border-gray-200">
          <h1 className="text-2xl font-bold text-gray-800 mb-2">Connection Error</h1>
          <p className="text-sm text-gray-500 mb-6">{authError}</p>

          <div className="space-y-3">
            <button
              onClick={retryAuth}
              className="w-full py-3 bg-gray-800 text-white rounded-lg font-medium hover:bg-gray-700 transition-colors"
            >
              Retry
            </button>
            <button
              onClick={() => signInWithGoogle()}
              className="w-full py-3 border border-gray-300 text-gray-700 rounded-lg font-medium hover:bg-gray-50 transition-colors"
            >
              Sign In Again
            </button>
          </div>
        </div>
      </div>
    );
  }

  // User is signed in with Google but needs to register (new user)
  if (user && needsRegistration) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="w-full max-w-md p-8 bg-white rounded-2xl shadow-lg border border-gray-200">
          <h1 className="text-2xl font-bold text-gray-800 mb-2">Create Your Account</h1>
          <p className="text-sm text-gray-500 mb-6">Welcome! Choose a username to get started</p>

          {localError && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">
              {localError}
            </div>
          )}

          <div className="space-y-4">
            <div>
              <label className="text-xs font-medium text-gray-600 mb-1 block">Email</label>
              <p className="text-sm text-gray-800">{user.email}</p>
            </div>

            <div>
              <label className="text-xs font-medium text-gray-600 mb-1 block">Username</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !registering) {
                    handleRegister();
                  }
                }}
                placeholder="Choose a username"
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-gray-500"
                disabled={registering}
              />
            </div>

            <button
              onClick={handleRegister}
              disabled={registering || !username.trim()}
              className="w-full py-3 bg-gray-800 text-white rounded-lg font-medium hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {registering ? (
                <Loader2 size={18} className="animate-spin mx-auto" />
              ) : (
                'Complete Registration'
              )}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Not signed in at all - show Google sign-in button
  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-50">
      <div className="w-full max-w-md p-8 bg-white rounded-2xl shadow-lg border border-gray-200">
        <h1 className="text-3xl font-bold text-gray-800 mb-2 font-serif">ResearchViewer</h1>
        <p className="text-sm text-gray-500 mb-8">Explore and organize research papers</p>

        {localError && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">
            {localError}
          </div>
        )}

        <button
          onClick={handleGoogleSignIn}
          className="w-full flex items-center justify-center gap-3 px-6 py-3 bg-white border-2 border-gray-300 rounded-lg font-medium text-gray-700 hover:bg-gray-50 transition-colors"
        >
          <LogIn size={20} />
          Sign in with Google
        </button>
      </div>
    </div>
  );
}
