import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import ChatPage from './pages/ChatPage';


const App: React.FC = () => {

  return (
    <Router>
      <Routes>
        <Route path="/chat" element={<ChatPage />} />
        <Route path="*" element={<Navigate to="/chat" />} />
      </Routes>
    </Router>
  );
};

export default App;
