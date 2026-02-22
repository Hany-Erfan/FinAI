import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { Endpoints } from '../api/endpoints';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useAuth } from '../AuthContext';
import { useNavigate } from 'react-router-dom';

interface Message {
  text: string;
  sender: 'user' | 'agent';
  timestamp?: string;
}

interface Session {
  id: string;
  title: string;
  messages: Message[];
}

const formatMessageTimestamp = (timestamp?: string) => {
  if (!timestamp) return '';
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
};

const UserIcon = () => (
  <svg width="30" height="30" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className="icon">
    <path d="M12 12C14.2091 12 16 10.2091 16 8C16 5.79086 14.2091 4 12 4C9.79086 4 8 5.79086 8 8C8 10.2091 9.79086 12 12 12ZM12 14C8.68629 14 6 16.6863 6 20H18C18 16.6863 15.3137 14 12 14Z" fill="currentColor" />
  </svg>
);

const AgentIcon = () => (
  <svg width="30" height="30" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className="icon">
    <path d="M12 2C6.48 2 2 6.48 2 12C2 17.52 6.48 22 12 22C17.52 22 22 17.52 22 12C22 6.48 17.52 2 12 2ZM12 5C13.66 5 15 6.34 15 8C15 9.66 13.66 11 12 11C10.34 11 9 9.66 9 8C9 6.34 10.34 5 12 5ZM12 19.2C9.5 19.2 7.29 17.92 6 15.98C6.03 13.99 10 12.9 12 12.9C13.99 12.9 17.97 13.99 18 15.98C16.71 17.92 14.5 19.2 12 19.2Z" fill="currentColor" />
  </svg>
);

const ChatPage: React.FC = () => {
  const navigate = useNavigate();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { token, setToken } = useAuth();
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const chatInputRef = useRef<HTMLTextAreaElement | null>(null);
  const [showLoginModal, setShowLoginModal] = useState(false);

  // --- Login Modal Logic ---
  const [loginUsername, setLoginUsername] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [loginError, setLoginError] = useState('');
  const [showLoginPassword, setShowLoginPassword] = useState(false);
  const [currentUser, setCurrentUser] = useState<string | null>(localStorage.getItem('chatUser'));

  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError('');
    try {
      const response = await axios.post(Endpoints.LOGIN, new URLSearchParams({
        username: loginUsername,
        password: loginPassword,
      }));
      setToken(response.data.access_token);

      const username = response.data.username || loginUsername;
      setCurrentUser(username);
      localStorage.setItem('chatUser', username);

      setShowLoginModal(false);

      // Auto-resend logic: find last user message and resend it
      if (activeSessionId) {
        const currentSession = sessions.find(s => s.id === activeSessionId);
        if (currentSession && currentSession.messages.length > 0) {
          const reversedMsgs = [...currentSession.messages].reverse();
          // Find the last user message. Skip the very last message if it's the [AUTH_REQUIRED] one.
          const lastUserMsg = reversedMsgs.find(m => m.sender === 'user');
          if (lastUserMsg) {
            // Resend silently to get new response
            submitMessageToBackend(lastUserMsg.text, activeSessionId, response.data.access_token);
          }
        }
      }
    } catch (err) {
      console.error('Login failed:', err);
      setLoginError('Failed to login. Please check your credentials.');
    }
  };

  const submitMessageToBackend = async (text: string, sessionId: string, authToken: string | null) => {
    setIsLoading(true);
    // Note: specific logic to replace/remove the [AUTH_REQUIRED] message or just append could be complex.
    // For now, we append the new response.
    // Ideally we remove the [AUTH_REQUIRED] "error" message first.
    setSessions(prev => prev.map(s => {
      if (s.id === sessionId) {
        // Remove the [AUTH_REQUIRED] message if it exists at the end
        const msgs = [...s.messages];
        if (msgs.length > 0 && msgs[msgs.length - 1].text.includes('[AUTH_REQUIRED]')) {
          msgs.pop();
        }
        return { ...s, messages: msgs };
      }
      return s;
    }));

    try {
      const response = await axios.post(Endpoints.CHAT,
        {
          message: text,
          session_id: sessionId // Send session_id to backend
        },
        {
          headers: {
            Authorization: `Bearer ${authToken}`,
            'Content-Type': 'application/json'
          }
        }
      );
      const agentMessage: Message = { text: response.data.response, sender: 'agent', timestamp: new Date().toISOString() };
      setSessions(prev => prev.map(s =>
        s.id === sessionId ? { ...s, messages: [...s.messages, agentMessage] } : s
      ));
    } catch (error) {
      console.error('Error resending:', error);
      // Add error message?
    } finally {
      setIsLoading(false);
    }
  };

  const handleLogout = () => {
    setToken(null);
    setCurrentUser(null);
    localStorage.removeItem('chatUser');
    handleNewChat();
  };

  useEffect(() => {
    const savedSessions = localStorage.getItem('bankchatsessions');
    if (savedSessions) {
      setSessions(JSON.parse(savedSessions));
    }
  }, []);

  useEffect(() => {
    // Persist sessions to localStorage
    try {
      if (sessions.length > 0) {
        localStorage.setItem('bankchatsessions', JSON.stringify(sessions));
      }
    } catch (e) {
      // If storage fails (quota), ignore silently
    }
  }, [sessions]);

  // Auth Required Detector
  useEffect(() => {
    const session = getActiveSession();
    if (session && session.messages.length > 0) {
      const lastMsg = session.messages[session.messages.length - 1];
      if (lastMsg.sender === 'agent' && lastMsg.text.includes('[AUTH_REQUIRED]')) {
        setShowLoginModal(true);
      }
    }
  }, [sessions, activeSessionId]);

  const handleDeleteSession = (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation(); // Prevent the click from activating the session
    const updatedSessions = sessions.filter(s => s.id !== sessionId);
    setSessions(updatedSessions);
    if (activeSessionId === sessionId) {
      setActiveSessionId(null);
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [sessions, activeSessionId, isLoading]);

  const handleNewChat = () => {
    setActiveSessionId(null);
  };

  const getActiveSession = () => sessions.find(s => s.id === activeSessionId);

  // Helper to get initials
  const getInitials = (name: string | null) => {
    if (!name) return 'U';
    const parts = name.split(' ');
    if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
    return name.slice(0, 2).toUpperCase();
  };

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      text: input,
      sender: 'user',
      timestamp: new Date().toISOString(),
    };
    let currentSessionId = activeSessionId;
    let updatedSessions = [...sessions];

    if (!currentSessionId) {
      // Create a new session
      const title = input.split(' ').slice(0, 5).join(' ') + (input.split(' ').length > 5 ? '...' : '');

      const newSessionId = `session_${Date.now()}`;
      const newSession: Session = {
        id: newSessionId,
        title: title,
        messages: [userMessage],
      };
      updatedSessions = [newSession, ...sessions];
      currentSessionId = newSessionId;
      setActiveSessionId(newSessionId);
    } else {
      // Update existing session
      updatedSessions = sessions.map(s =>
        s.id === currentSessionId ? { ...s, messages: [...s.messages, userMessage] } : s
      );
    }

    setSessions(updatedSessions);
    setInput('');
    setIsLoading(true);

    try {
      const response = await axios.post(Endpoints.CHAT,
        {
          message: input,
          session_id: currentSessionId // Send session_id to backend
        },
        {
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        }
      );

      const agentMessage: Message = { text: response.data.response, sender: 'agent', timestamp: new Date().toISOString() };
      const finalSessions = updatedSessions.map(s =>
        s.id === currentSessionId ? { ...s, messages: [...s.messages, agentMessage] } : s
      );
      setSessions(finalSessions);

    } catch (error) {
      console.error('Error sending message:', error);
      const errorMessage: Message = { text: 'Error: Could not get a response from the agent.', sender: 'agent', timestamp: new Date().toISOString() };
      const errorSessions = updatedSessions.map(s =>
        s.id === currentSessionId ? { ...s, messages: [...s.messages, errorMessage] } : s
      );
      setSessions(errorSessions);
    } finally {
      setIsLoading(false);
      chatInputRef.current?.focus();
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    const textarea = e.target;
    textarea.style.height = 'auto';
    textarea.style.height = `${textarea.scrollHeight}px`;
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const activeMessages = getActiveSession()?.messages || [];

  useEffect(() => {
    if (!isLoading) {
      chatInputRef.current?.focus();
    }
  }, [activeMessages.length, activeSessionId, isLoading]);

  return (
    <div className="page-container">
      {/* Login Modal */}
      {showLoginModal && (
        <div className="modal-overlay">
          <div className="modal-content">
            <button onClick={() => setShowLoginModal(false)} style={{ position: 'absolute', top: '15px', right: '15px', background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: '1.5rem', zIndex: 10 }}>×</button>

            <h2 style={{ marginTop: 0 }}>Log In</h2>
            <p className="subtitle" style={{ marginBottom: '2rem' }}>Please log in to access retail banking features.</p>

            <form onSubmit={handleLoginSubmit}>
              <div className="input-group">
                <input
                  type="text"
                  id="modal-username"
                  value={loginUsername}
                  onChange={e => setLoginUsername(e.target.value)}
                  placeholder=" "
                  required
                />
                <label htmlFor="modal-username">Username</label>
              </div>

              <div className="input-group">
                <input
                  type={showLoginPassword ? "text" : "password"}
                  id="modal-password"
                  value={loginPassword}
                  onChange={e => setLoginPassword(e.target.value)}
                  placeholder=" "
                  required
                />
                <label htmlFor="modal-password">Password</label>
                <button type="button" onClick={() => setShowLoginPassword(!showLoginPassword)} className="password-toggle-icon">
                  {showLoginPassword ? (
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                      <circle cx="12" cy="12" r="3"></circle>
                    </svg>
                  ) : (
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path>
                      <line x1="1" y1="1" x2="23" y2="23"></line>
                    </svg>
                  )}
                </button>
              </div>

              {loginError && <p className="error-message" style={{ marginBottom: '1rem' }}>{loginError}</p>}

              <button type="submit" className="submit-btn">Sign In</button>
            </form>
          </div>
        </div>
      )}

      <div className="sidebar">
        <button className="new-chat-btn" onClick={handleNewChat}>
          <span className="new-chat-icon">+</span>
          <span className="new-chat-label">New Chat</span>
        </button>
        <button className="new-chat-btn" onClick={() => navigate('/backoffice')} style={{ marginTop: '0.5rem', backgroundColor: '#3a3b40' }}>
          <span className="new-chat-label">Document Backoffice</span>
        </button>
        <div className="chat-history" style={{ marginTop: '1rem' }}>
          {sessions.map(session => (
            <div
              key={session.id}
              className={`history-item ${session.id === activeSessionId ? 'active' : ''}`}
              onClick={() => setActiveSessionId(session.id)}
            >
              <span>{session.title}</span>
              <button className="delete-chat-btn" onClick={(e) => handleDeleteSession(e, session.id)}>×</button>
            </div>
          ))}
        </div>

        {/* Sidebar Login/Logout */}
        <div style={{ marginTop: 'auto', padding: '1rem', borderTop: '1px solid var(--border-color)' }}>
          {token && currentUser ? (
            <div className="user-profile-container">
              <div className="user-profile-left">
                <div className="user-avatar">{getInitials(currentUser)}</div>
                <div className="user-info">
                  <span className="user-name">{currentUser}</span>
                </div>
              </div>
              <button onClick={handleLogout} className="logout-pill-btn">
                Log Out
              </button>
            </div>
          ) : (
            <button onClick={() => setShowLoginModal(true)} className="submit-btn" style={{ width: '100%', borderRadius: '24px', padding: '10px', justifyContent: 'center' }}>
              Log In
            </button>
          )}
        </div>
      </div>
      <div className="chat-container">
        <div className="chat-header">
          <div className="header-placeholder"></div>
          <h2>AgentixBuddy</h2>
          <div className="header-placeholder"></div>
        </div>
        <div className="chat-body">
          <div className="chat-messages">
            {activeMessages.map((msg, index) => {
              // Hide [AUTH_REQUIRED] messages from view
              if (msg.text.includes('[AUTH_REQUIRED]')) return null;

              const formattedTimestamp = formatMessageTimestamp(msg.timestamp);
              return (
                <div key={index} className={`chat-message ${msg.sender}`}>
                  {msg.sender === 'agent' ? <AgentIcon /> : <UserIcon />}
                  <div className="message-wrapper">
                    <div className="message-bubble">
                      {msg.sender === 'agent' ? (
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {msg.text}
                        </ReactMarkdown>
                      ) : (
                        msg.text
                      )}
                    </div>
                    {formattedTimestamp && (
                      <span className="message-timestamp">{formattedTimestamp}</span>
                    )}
                  </div>
                </div>
              );
            })}
            {isLoading && (
              <div className="chat-message agent">
                <AgentIcon />
                <div className="message-bubble">
                  <div className="typing-indicator">
                    <span></span>
                    <span></span>
                    <span></span>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        </div>
        <div className="chat-input-area">
          <div className="chat-input-wrapper">
            <textarea
              ref={chatInputRef as React.RefObject<HTMLTextAreaElement>}
              value={input}
              onChange={handleInput}
              onKeyDown={handleKeyDown}
              placeholder="Type your message..."
              disabled={isLoading}
              rows={1}
            />
            <button className="send-btn" onClick={handleSend} disabled={!input.trim() || isLoading}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M7 11L12 6L17 11M12 18V7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          </div>
        </div>
      </div>

    </div>
  );
};

export default ChatPage;
