// ============================================================================
// frontend/chatbot-arayuzu/src/App.js - React Chat Widget
// ============================================================================

import React, { useState, useEffect, useRef, useCallback } from 'react';
import './App.css';


// ============================================================================
// CONSTANTS
// ============================================================================

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000';

const INITIAL_BOT_MESSAGE = {
  id: 1,
  sender: 'bot',
  text: 'Size nasıl yardımcı olabilirim?',
  timestamp: new Date().toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' })
};

const QUICK_REPLIES = [
  { label: '🍽️ Bugün yemek ne?', text: 'Bugün yemek ne?' },
  { label: '📅 Akademik takvim', text: 'Akademik takvim' },
  { label: '🔬 Lab cihazları', text: 'Laboratuvar cihazları hakkında bilgi ver' },
];

const ERROR_MESSAGES = {
  SPEECH_NOT_SUPPORTED: 'Tarayıcınız ses tanımayı desteklemiyor. Chrome veya Edge kullanın.',
  NO_SPEECH: 'Konuşma algılanamadı. Lütfen tekrar deneyin.',
  API_ERROR: 'Üzgünüm, bir hata oluştu. Lütfen daha sonra tekrar deneyin.',
  INVALID_INPUT: 'Boş mesaj gönderilemez.',
  RATE_LIMIT: 'Çok fazla mesaj gönderdiniz. Lütfen bir dakika bekleyin.',
};

const MAX_HISTORY = 10;


// ============================================================================
// UTILITIES
// ============================================================================

function getOrCreateSessionId() {
  const key = 'acu_chatbot_session_id';
  let id = sessionStorage.getItem(key);
  if (!id) {
    id = `session_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
    sessionStorage.setItem(key, id);
  }
  return id;
}

function now() {
  return new Date().toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' });
}

function renderMarkdown(text) {
  if (!text) return null;
  return text.split('\n').map((line, lineIdx, arr) => {
    const parts = line.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
      part.startsWith('**') && part.endsWith('**')
        ? <strong key={i}>{part.slice(2, -2)}</strong>
        : part
    );
    return (
      <React.Fragment key={lineIdx}>
        {parts}
        {lineIdx < arr.length - 1 && <br />}
      </React.Fragment>
    );
  });
}


// ============================================================================
// SPEECH RECOGNITION
// ============================================================================

function initializeSpeechRecognition(onTranscript, onListeningChange, onError) {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) return null;

  const recognition = new SR();
  recognition.continuous = false;
  recognition.interimResults = false;
  recognition.lang = 'tr-TR';

  recognition.onstart = () => onListeningChange(true);
  recognition.onresult = (e) => {
    onTranscript(e.results[0][0].transcript);
    onListeningChange(false);
  };
  recognition.onerror = (e) => {
    onListeningChange(false);
    if (e.error === 'no-speech') onError(ERROR_MESSAGES.NO_SPEECH);
  };
  recognition.onend = () => onListeningChange(false);

  return recognition;
}


// ============================================================================
// API
// ============================================================================

async function sendMessageToAPI(message, sessionId, history, backendUrl) {
  const limitedHistory = history.slice(-MAX_HISTORY).map(m => ({
    role: m.sender === 'user' ? 'user' : 'bot',
    text: m.text,
  }));

  const response = await fetch(`${backendUrl}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId, history: limitedHistory }),
  });

  if (response.status === 429) throw new Error('RATE_LIMIT');
  if (!response.ok) throw new Error(`HTTP ${response.status}`);

  return response.json();
}

async function checkHealth(backendUrl) {
  try {
    const res = await fetch(`${backendUrl}/health`, { signal: AbortSignal.timeout(3000) });
    return res.ok;
  } catch {
    return false;
  }
}


// ============================================================================
// MAIN COMPONENT
// ============================================================================

function App() {
  const [messages, setMessages] = useState([INITIAL_BOT_MESSAGE]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [isSpeechSupported, setIsSpeechSupported] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const [inlineError, setInlineError] = useState('');
  const [isOnline, setIsOnline] = useState(true);

  const recognitionRef = useRef(null);
  const chatLogRef = useRef(null);
  const sessionIdRef = useRef(getOrCreateSessionId());


  // -------- AUTO-SCROLL --------
  useEffect(() => {
    if (chatLogRef.current) {
      chatLogRef.current.scrollTop = chatLogRef.current.scrollHeight;
    }
  }, [messages, isLoading]);


  // -------- HEALTH CHECK --------
  useEffect(() => {
    checkHealth(BACKEND_URL).then(setIsOnline);
    const interval = setInterval(() => checkHealth(BACKEND_URL).then(setIsOnline), 30000);
    return () => clearInterval(interval);
  }, []);


  // -------- SPEECH INIT --------
  useEffect(() => {
    const recognition = initializeSpeechRecognition(
      (t) => setInputValue(t),
      (l) => setIsListening(l),
      (e) => setInlineError(e)
    );
    if (recognition) {
      recognitionRef.current = recognition;
      setIsSpeechSupported(true);
    }
  }, []);


  // -------- CLEAR ERROR ON INPUT --------
  useEffect(() => {
    if (inputValue) setInlineError('');
  }, [inputValue]);


  // -------- HANDLERS --------

  const toggleListening = useCallback(() => {
    if (!isSpeechSupported) { setInlineError(ERROR_MESSAGES.SPEECH_NOT_SUPPORTED); return; }
    if (isListening) {
      recognitionRef.current?.stop();
    } else {
      setInlineError('');
      try { recognitionRef.current?.start(); } catch (e) { setIsListening(false); }
    }
  }, [isSpeechSupported, isListening]);


  const sendMessage = useCallback(async (text) => {
    const trimmed = text.trim();
    if (!trimmed) { setInlineError(ERROR_MESSAGES.INVALID_INPUT); return; }

    setInlineError('');
    const userMsg = { id: Date.now(), sender: 'user', text: trimmed, timestamp: now() };
    setMessages(prev => [...prev, userMsg]);
    setInputValue('');
    setIsLoading(true);

    try {
      const data = await sendMessageToAPI(trimmed, sessionIdRef.current, [...messages, userMsg], BACKEND_URL);
      setMessages(prev => [...prev, {
        id: Date.now() + 1,
        sender: 'bot',
        text: data.response || 'Yanıt alınamadı.',
        timestamp: now()
      }]);
    } catch (err) {
      const errText = err.message === 'RATE_LIMIT'
        ? ERROR_MESSAGES.RATE_LIMIT
        : ERROR_MESSAGES.API_ERROR;
      setMessages(prev => [...prev, { id: Date.now() + 1, sender: 'bot', text: errText, timestamp: now() }]);
    } finally {
      setIsLoading(false);
    }
  }, [messages]);


  const handleSend = useCallback((e) => {
    e.preventDefault();
    sendMessage(inputValue);
  }, [inputValue, sendMessage]);


  const handleQuickReply = useCallback((text) => {
    sendMessage(text);
  }, [sendMessage]);


  const clearChat = useCallback(() => {
    setMessages([INITIAL_BOT_MESSAGE]);
    sessionStorage.removeItem('acu_chatbot_session_id');
    sessionIdRef.current = getOrCreateSessionId();
    setInlineError('');
  }, []);


  const toggleChat = useCallback(() => {
    setIsOpen(prev => !prev);
    setInlineError('');
  }, []);


  // -------- RENDER --------

  const showQuickReplies = messages.length <= 2 && !isLoading;

  return (
    <div className="chatbot-widget-container">
      {isOpen && (
        <div className="chat-window">

          {/* HEADER */}
          <div className="chat-header">
            <div className="chat-header-left">
              <span className={`status-dot ${isOnline ? 'online' : 'offline'}`} title={isOnline ? 'Çevrimiçi' : 'Çevrimdışı'} />
              AÇÜ Chatbot
            </div>
            <div className="chat-header-actions">
              <button
                className="clear-btn"
                onClick={clearChat}
                title="Sohbeti temizle"
                aria-label="Sohbeti temizle"
              >
                🗑
              </button>
              <button
                className="close-btn"
                onClick={toggleChat}
                aria-label="Kapat"
                title="Kapat"
              >
                ×
              </button>
            </div>
          </div>

          {/* MESSAGE LOG */}
          <div className="chat-log" ref={chatLogRef}>
            {messages.map((msg) => (
              <div key={msg.id} className={`message message-${msg.sender}`}>
                <div className="message-bubble">
                  {msg.sender === 'bot' ? renderMarkdown(msg.text) : msg.text}
                </div>
                {msg.timestamp && (
                  <span className="message-timestamp">{msg.timestamp}</span>
                )}
              </div>
            ))}

            {/* TYPING INDICATOR */}
            {isLoading && (
              <div className="message message-bot">
                <div className="message-bubble typing-indicator">
                  <span /><span /><span />
                </div>
              </div>
            )}

            {/* QUICK REPLY BUTTONS */}
            {showQuickReplies && (
              <div className="quick-replies">
                {QUICK_REPLIES.map((qr) => (
                  <button
                    key={qr.text}
                    className="quick-reply-btn"
                    onClick={() => handleQuickReply(qr.text)}
                  >
                    {qr.label}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* INLINE ERROR */}
          {inlineError && (
            <div className="inline-error" role="alert">⚠️ {inlineError}</div>
          )}

          {/* INPUT */}
          <form className="chat-input-area" onSubmit={handleSend}>
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder="Mesajınızı yazın..."
              disabled={isLoading}
              autoFocus
            />
            {isSpeechSupported && (
              <button
                type="button"
                className={`mic-button ${isListening ? 'listening' : ''}`}
                onClick={toggleListening}
                disabled={isLoading}
                title={isListening ? 'Kaydı durdur' : 'Sesli mesaj'}
                aria-label="Mikrofon"
              >
                {isListening ? '🔴' : '🎤'}
              </button>
            )}
            <button
              type="submit"
              disabled={isLoading || isListening || !inputValue.trim()}
              title="Gönder"
              aria-label="Gönder"
            >
              {isLoading ? '⏳' : '➤'}
            </button>
          </form>
        </div>
      )}

      {!isOpen && (
        <button className="chat-bubble" onClick={toggleChat} title="Chatbot'u aç" aria-label="Chatbot'u aç">
          💬
        </button>
      )}
    </div>
  );
}

export default App;
