import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { useCallback, useEffect, useRef, useState } from "react";
import LoginForm from './pages/LoginForm';
import ProtectedRoute from './pages/ProtectedRoute';
import ChatPage from './pages/ChatPage';
import { getCurrentUser, login, logout } from './api/login';

const TAB_SESSION_KEY = "chat_tab_session_id";
const INACTIVITY_TIMEOUT_MS = 5 * 60 * 1000;

function getOrCreateTabSessionId() {
  let sessionId = sessionStorage.getItem(TAB_SESSION_KEY);
  if (!sessionId) {
    sessionId = crypto.randomUUID();
    sessionStorage.setItem(TAB_SESSION_KEY, sessionId);
  }
  return sessionId;
}

export default function App() {
  const [auth, setAuth] = useState(null);
  const [checking, setChecking] = useState(true);
  const [sessionId] = useState(() => getOrCreateTabSessionId());
  const inactivityTimerRef = useRef(null);

  useEffect(() => {
    async function validate() {
      try {
        const profile = await getCurrentUser(sessionId);
        setAuth({
          userId: profile.user_id,
          role: profile.role,
          username: profile.username,
        });
      } catch {
        setAuth(null);
      } finally {
        setChecking(false);
      }
    }

    validate();
  }, [sessionId]);

  const handleLogin = async (username, password) => {
    await login(username, password, sessionId);
    const profile = await getCurrentUser(sessionId);
    setAuth({
      userId: profile.user_id,
      role: profile.role,
      username: profile.username,
    });
  };

  const handleLogout = useCallback(async () => {
    try {
      await logout(sessionId);
    } catch {
      // Ignore network/logout race errors and force local logout state.
    }
    setAuth(null);
  }, [sessionId]);

  useEffect(() => {
    if (!auth?.username) {
      if (inactivityTimerRef.current) {
        clearTimeout(inactivityTimerRef.current);
        inactivityTimerRef.current = null;
      }
      return;
    }

    function scheduleLogout() {
      if (inactivityTimerRef.current) {
        clearTimeout(inactivityTimerRef.current);
      }
      inactivityTimerRef.current = setTimeout(() => {
        handleLogout();
      }, INACTIVITY_TIMEOUT_MS);
    }

    function onActivity() {
      scheduleLogout();
    }

    const events = ["mousemove", "mousedown", "keydown", "touchstart", "scroll"];
    events.forEach((eventName) => {
      window.addEventListener(eventName, onActivity, { passive: true });
    });
    scheduleLogout();

    return () => {
      events.forEach((eventName) => {
        window.removeEventListener(eventName, onActivity);
      });
      if (inactivityTimerRef.current) {
        clearTimeout(inactivityTimerRef.current);
        inactivityTimerRef.current = null;
      }
    };
  }, [auth?.username, handleLogout]);

  if (checking) {
    return <div className="page">Checking session...</div>;
  }

  const isAuthenticated = Boolean(auth?.username);

  return (
    <div className="page">
      <Router>
      <Routes>
        <Route
          path="/"
          element={
            isAuthenticated ? (
              <Navigate to="/chat" replace />
            ) : (
              <LoginForm onLogin={handleLogin} />
            )
          }
        />
         <Route
          path="/chat"
          element={
            <ProtectedRoute isAuthenticated={isAuthenticated}>
              <ChatPage auth={auth} onLogout={handleLogout} sessionId={sessionId} />
            </ProtectedRoute>
          }
        />
      </Routes>
      </Router>
    </div>
  );
}

