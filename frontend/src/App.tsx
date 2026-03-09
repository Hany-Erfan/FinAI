import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { useCallback, useEffect, useRef, useState } from "react";
import LoginForm from './pages/LoginForm';
import ProtectedRoute from './pages/ProtectedRoute';
import ChatPage from './pages/ChatPage';
import Backoffice from './pages/Backoffice';
import SessionExplorer from './pages/SessionExplorer';
import { getCurrentUser, login } from './api/login';
import { logout, summary } from './api/logout';

const TAB_SESSION_KEY = "chat_tab_session_id";
// ⚠️ INACTIVITY_TIMEOUT_MS must always be less than the server-side session TTL.
// If you change this value, update the backend session expiry accordingly. 
// Add a 1 minute buffer in the backend (auth_config.py) for the summary to be executed
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
  const sessionId = generateUUID();
  sessionStorage.setItem(TAB_SESSION_KEY, sessionId);
  return sessionId;
}


export default function App() {
  const [auth, setAuth] = useState(null);
  const [checking, setChecking] = useState(true);
  const [sessionId, setSessionId] = useState(() => getOrCreateTabSessionId());
  const inactivityTimerRef = useRef(null);
  const sessionIdRef = useRef(sessionId);
  useEffect(() => {
    sessionIdRef.current = sessionId;
    }, [sessionId]); 

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
    await summary(sessionIdRef.current);  
    logout(sessionIdRef.current);   
  } catch(err) {
    console.error('err on logout', err);
  } finally {
    setAuth(null);                       
    setSessionId(createNewTabSessionId());
  }
  }, []);

  const handleLogoutRef = useRef(handleLogout);
  useEffect(() => {
    handleLogoutRef.current = handleLogout;
  }, [handleLogout]); 

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

    const events = ["mousemove", "mousedown", "keydown", "touchstart", "scroll"];
    events.forEach((e) => window.addEventListener(e, scheduleLogout, { passive: true }));
    scheduleLogout();

    return () => {
        events.forEach((e) => window.removeEventListener(e, scheduleLogout));
        if (inactivityTimerRef.current) {
          clearTimeout(inactivityTimerRef.current);
          inactivityTimerRef.current = null;
        }
      };
    }, [auth?.username]);

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
              <ChatPage auth={auth} onLogout={handleLogout} sessionId={sessionId} 
              inactivityTimeout={INACTIVITY_TIMEOUT_MS} />
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
        <Route
          path="/session-explorer"
          element={
            <ProtectedRoute isAuthenticated={isAuthenticated} requiredRole="admin" userRole={auth?.role}>
              <SessionExplorer sessionId={sessionId} />
            </ProtectedRoute>
          }
        />
      </Routes>
      </Router>
    </div>
  );
}

