import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { useCallback, useEffect, useRef, useState } from "react";
import LoginForm from './pages/LoginForm';
import ProtectedRoute from './pages/ProtectedRoute';
import ChatPage from './pages/ChatPage';
import Backoffice from './pages/Backoffice';
import { getCurrentUser, login } from './api/login';
import { logout, summary } from './api/logout';

const TAB_SESSION_KEY = "chat_tab_session_id";
const INACTIVITY_TIMEOUT_MS = 5 * 60 * 1000;

// Fallback for crypto.randomUUID (not available on HTTP non-localhost)
function generateUUID(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  // Fallback implementation
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

function getOrCreateTabSessionId() {
  let sessionId = sessionStorage.getItem(TAB_SESSION_KEY);
  if (!sessionId) {
    sessionId = createNewTabSessionId();
  }
  return sessionId;
}

function createNewTabSessionId() {
  const sessionId = crypto.randomUUID();
  sessionStorage.setItem(TAB_SESSION_KEY, sessionId);
  return sessionId;
}


export default function App() {
  const [auth, setAuth] = useState(null);
  const [checking, setChecking] = useState(true);
  const [sessionId, setSessionId] = useState(() => getOrCreateTabSessionId());
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
      await summary(sessionId);
      logout(sessionId);
    } catch(err) {
      console.error('err on logout', err);
    }
    setAuth(null);
    setSessionId(createNewTabSessionId())
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
        <Route
          path="/backoffice"
          element={
            <ProtectedRoute isAuthenticated={isAuthenticated} requiredRole="admin" userRole={auth?.role}>
              <Backoffice sessionId={sessionId} />
            </ProtectedRoute>
          }
        />
      </Routes>
      </Router>
    </div>
  );
}

