// ============================================================================
// frontend/chatbot-arayuzu/src/App.js - React Chat Widget
// ============================================================================
// Açıklama:
//   Üniversite chatbot'unun React frontend'i. Widget tipi UI ile floating
//   chat baloncuğu ve pencereyi sağlar. Backend'le REST API üzerinden
//   iletişim kurar. Web Speech API ile sesli komut destekler.
//
//   Features:
//     - Floating chat widget
//     - Conversation history
//     - Voice input (microphone)
//     - Loading states
//     - Inline error handling
//     - Markdown rendering (bold, newline)
//     - Auto-scroll on new message
//     - Per-session unique ID for device confirmation flow
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
  text: 'Size nasıl yardımcı olabilirim?'
};

const ERROR_MESSAGES = {
  SPEECH_NOT_SUPPORTED: 'Tarayıcınız ses tanımayı desteklemiyor. Chrome veya Edge kullanın.',
  NO_SPEECH: 'Konuşma algılanamadı. Lütfen tekrar deneyin.',
  API_ERROR: 'Üzgünüm, bir hata oluştu. Lütfen daha sonra tekrar deneyin.',
  INVALID_INPUT: 'Boş mesaj gönderilemez.'
};


// ============================================================================
// UTILITIES
// ============================================================================

/**
 * Tarayıcı oturumu için kalıcı bir session ID üretir veya mevcut olanı döndürür.
 * Bu sayede cihaz onay akışı doğru kullanıcıya bağlı kalır.
 */
function getOrCreateSessionId() {
  const storageKey = 'acu_chatbot_session_id';
  let sessionId = sessionStorage.getItem(storageKey);
  if (!sessionId) {
    sessionId = `session_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
    sessionStorage.setItem(storageKey, sessionId);
  }
  return sessionId;
}

/**
 * Metindeki markdown formatlarını JSX'e dönüştürür.
 * Desteklenen: **bold**, \n (satır sonu)
 */
function renderMarkdown(text) {
  if (!text) return null;

  const lines = text.split('\n');
  return lines.map((line, lineIdx) => {
    const parts = line.split(/(\*\*[^*]+\*\*)/g);
    const rendered = parts.map((part, partIdx) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={partIdx}>{part.slice(2, -2)}</strong>;
      }
      return part;
    });
    return (
      <React.Fragment key={lineIdx}>
        {rendered}
        {lineIdx < lines.length - 1 && <br />}
      </React.Fragment>
    );
  });
}


// ============================================================================
// SPEECH RECOGNITION SETUP HELPER
// ============================================================================

function initializeSpeechRecognition(onTranscript, onListeningChange, onError) {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

  if (!SpeechRecognition) {
    console.warn('Web Speech API not supported in this browser');
    return null;
  }

  const recognition = new SpeechRecognition();
  recognition.continuous = false;
  recognition.interimResults = false;
  recognition.lang = 'tr-TR';

  recognition.onstart = () => onListeningChange(true);

  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    onTranscript(transcript);
    onListeningChange(false);
  };

  recognition.onerror = (event) => {
    console.error('Speech recognition error:', event.error);
    onListeningChange(false);
    if (event.error === 'no-speech') {
      onError(ERROR_MESSAGES.NO_SPEECH);
    }
  };

  recognition.onend = () => onListeningChange(false);

  return recognition;
}


// ============================================================================
// API COMMUNICATION
// ============================================================================

async function sendMessageToAPI(message, sessionId, backendUrl) {
  const response = await fetch(`${backendUrl}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId }),
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return await response.json();
}


// ============================================================================
// MAIN APP COMPONENT
// ============================================================================

function App() {
  const [messages, setMessages] = useState([INITIAL_BOT_MESSAGE]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [isSpeechSupported, setIsSpeechSupported] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const [inlineError, setInlineError] = useState('');

  const recognitionRef = useRef(null);
  const chatLogRef = useRef(null);
  const sessionIdRef = useRef(getOrCreateSessionId());


  // -------- AUTO-SCROLL --------
  useEffect(() => {
    if (chatLogRef.current) {
      chatLogRef.current.scrollTop = chatLogRef.current.scrollHeight;
    }
  }, [messages, isLoading]);


  // -------- SPEECH RECOGNITION INIT --------
  useEffect(() => {
    const recognition = initializeSpeechRecognition(
      (transcript) => setInputValue(transcript),
      (listening) => setIsListening(listening),
      (error) => setInlineError(error)
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


  // -------- EVENT HANDLERS --------

  const toggleListening = useCallback(() => {
    if (!isSpeechSupported) {
      setInlineError(ERROR_MESSAGES.SPEECH_NOT_SUPPORTED);
      return;
    }

    if (isListening) {
      recognitionRef.current?.stop();
      setIsListening(false);
    } else {
      try {
        setInlineError('');
        recognitionRef.current?.start();
        setIsListening(true);
      } catch (error) {
        console.error('Speech recognition start error:', error);
        setIsListening(false);
      }
    }
  }, [isSpeechSupported, isListening]);


  const handleSend = useCallback(async (e) => {
    e.preventDefault();

    const trimmedInput = inputValue.trim();
    if (!trimmedInput) {
      setInlineError(ERROR_MESSAGES.INVALID_INPUT);
      return;
    }

    setInlineError('');

    const newUserMessage = {
      id: Date.now(),
      sender: 'user',
      text: trimmedInput
    };

    setMessages((prev) => [...prev, newUserMessage]);
    setInputValue('');
    setIsLoading(true);

    try {
      const data = await sendMessageToAPI(trimmedInput, sessionIdRef.current, BACKEND_URL);

      const botResponse = {
        id: Date.now() + 1,
        sender: 'bot',
        text: data.response || 'Yanıt alınamadı.'
      };

      setMessages((prev) => [...prev, botResponse]);
    } catch (error) {
      console.error('Chat error:', error);

      const errorMessage = {
        id: Date.now() + 1,
        sender: 'bot',
        text: ERROR_MESSAGES.API_ERROR
      };

      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  }, [inputValue]);


  const toggleChat = useCallback(() => {
    setIsOpen((prev) => !prev);
    setInlineError('');
  }, []);


  // -------- RENDER --------

  return (
    <div className="chatbot-widget-container">
      {isOpen && (
        <div className="chat-window">
          {/* HEADER */}
          <div className="chat-header">
            👤 AÇÜ Chatbot
            <button
              className="close-btn"
              onClick={toggleChat}
              aria-label="Chat penceresini kapat"
              title="Kapat"
            >
              ×
            </button>
          </div>

          {/* MESSAGE LOG */}
          <div className="chat-log" ref={chatLogRef}>
            {messages.map((message) => (
              <div
                key={message.id}
                className={`message message-${message.sender}`}
              >
                <div className="message-bubble">
                  {message.sender === 'bot'
                    ? renderMarkdown(message.text)
                    : message.text}
                </div>
              </div>
            ))}
            {isLoading && (
              <div className="message message-bot">
                <div className="message-bubble loading">
                  ⏳ Yanıt bekleniyor...
                </div>
              </div>
            )}
          </div>

          {/* INLINE ERROR */}
          {inlineError && (
            <div className="inline-error" role="alert">
              ⚠️ {inlineError}
            </div>
          )}

          {/* INPUT AREA */}
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
                title={isListening ? 'Kaydı durdur' : 'Sesli mesaj gönder'}
                aria-label="Mikrofon"
              >
                {isListening ? '🔴' : '🎤'}
              </button>
            )}

            <button
              type="submit"
              disabled={isLoading || isListening || !inputValue.trim()}
              title="Mesajı gönder"
              aria-label="Mesajı gönder"
            >
              {isLoading ? '⏳' : '➤'}
            </button>
          </form>
        </div>
      )}

      {!isOpen && (
        <button
          className="chat-bubble"
          onClick={toggleChat}
          title="Chat'i aç"
          aria-label="Chatbot'u aç"
        >
          💬
        </button>
      )}
    </div>
  );
}

export default App;
