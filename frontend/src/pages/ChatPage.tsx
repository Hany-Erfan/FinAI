import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { getMessages, sendChatMessage } from '../api/chat';
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

const isArabicText = (text: string) => /[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]/.test(text);

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

const ChatPage = ({ auth, onLogout, sessionId, inactivityTimeout }) => {
  const INACTIVITY_MINUTES = inactivityTimeout / 1000 / 60;
  const navigate = useNavigate();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(sessionId);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const chatInputRef = useRef<HTMLTextAreaElement | null>(null);
  const [currentUser, setCurrentUser] = useState<string | null>(localStorage.getItem('chatUser'));

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom(); 
  }, [sessions, activeSessionId, isLoading]);

  useEffect(() => {
    function handleOutsideClick(e: MouseEvent) {
      const btn = document.getElementById('session-btn');
      const popover = document.getElementById('session-popover');
      if (btn && popover && !btn.contains(e.target as Node) && !popover.contains(e.target as Node)) {
        popover.classList.remove('open');
      }
    }
    document.addEventListener('click', handleOutsideClick);
    return () => document.removeEventListener('click', handleOutsideClick);
  }, []);

  // Fetch messages from DB whenever active session changes
  useEffect(() => {
    if (!sessionId) return;

      async function loadMessages() {
        try {
          const data: Message[] = await getMessages(sessionId);
          
          setSessions(prev => {
            const exists = prev.find(s => s.id === sessionId);
            if (exists) {
              // update existing session messages
              return prev.map(s => s.id === sessionId ? { ...s, messages: data } : s);
            }
            // session doesn't exist yet, create it
            return [{ id: sessionId, title: "", messages: data }, ...prev];
          });
        } catch (err) {
          console.error("Failed to load messages:", err);
        }
      }

    loadMessages();
  }, []);


  const getActiveSession = () => sessions.find(s => s.id === activeSessionId);

  // Helper to get initials
  const getInitials = (name: string | null) => {
    if (!name) return auth.role === "admin" ? 'A' : 'U';
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

      const newSessionId = sessionId;
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
      const result = await sendChatMessage(input, currentSessionId);

      // Support both possible return shapes:
      // 1) axios response: { data: { response: string } }
      // 2) direct JSON: { response: string }
      const reply = result?.data?.response ?? result?.response;

      if (!reply) {
        throw new Error('Unexpected chat response shape');
      }

      const agentMessage: Message = { text: reply, sender: 'agent', timestamp: new Date().toISOString() };
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
      <div className="sidebar">
        {auth.role === "admin" ? (
          <div className="admin-box">
            <button onClick={() => navigate('/backoffice')}>Manage FAQs</button>
            <button onClick={() => navigate('/session-explorer')}>Session Explorer</button>
            <button onClick={() => navigate('/analysis-dashboard')}>Analysis Dashboard</button>
          </div>
        ) : null}
        {/* Sidebar Login/Logout */}
        <div style={{ marginTop: 'auto', padding: '1rem', borderTop: '1px solid var(--border-color)' }}>
          <div className="user-profile-container">
            <div className="user-profile-left">
              <div className="user-avatar">{getInitials(currentUser)}</div>
              <div className="user-info">
                <span className="user-name">{currentUser}</span>
              </div>
            </div>
            <button onClick={onLogout}>Logout</button>
          </div>
        </div>
      </div>
      <div className="chat-container">
        <div className="chat-header">
          <div className="header-placeholder"></div>
          <h2>AgentixBuddy</h2>
          <div className="header-placeholder"></div>
           <div className="session-wrapper">
                <button
                  id="session-btn"
                  className="session-btn"
                  onClick={() => document.getElementById('session-popover')?.classList.toggle('open')}
                >
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
                <line x1="12" y1="9" x2="12" y2="13"/>
                <line x1="12" y1="17" x2="12.01" y2="17"/>
              </svg> Session security
                </button>
                <div id="session-popover" className="session-popover">
                  <div className="session-popover-arrow" />
                  <strong style={{ color: "#111827", display: "block", marginBottom: "4px" }}>
                    ⚠️ Auto logout enabled
                    </strong>
                    For your security, your session will automatically expire after{" "}
                    <strong>{INACTIVITY_MINUTES} minutes</strong> of inactivity.
                    Any unsaved progress will be lost.
                </div>
              </div>
        </div>
        <div className="chat-body">
          <div className="chat-messages">
            {activeMessages.map((msg, index) => {
              const formattedTimestamp = formatMessageTimestamp(msg.timestamp);
              const isArabic = isArabicText(msg.text);

              return (
                <div key={index} className={`chat-message ${msg.sender}`}>
                  {msg.sender === 'agent' ? <AgentIcon /> : <UserIcon />}
                  <div className="message-wrapper">
                    <div
                      className="message-bubble"
                      dir={isArabic ? 'rtl' : 'ltr'}
                      lang={isArabic ? 'ar' : 'en'}
                      style={{
                        textAlign: isArabic ? 'right' : 'left',
                        unicodeBidi: 'plaintext',
                      }}
                    >
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