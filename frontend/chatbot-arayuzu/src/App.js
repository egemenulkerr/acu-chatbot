import React, { useState, useEffect, useRef } from 'react';
import './App.css'; 

function App() {
  const [messages, setMessages] = useState([
    { id: 1, sender: 'bot', text: 'Size nasıl yardımcı olabilirim?' }
  ]);
  
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [isSpeechSupported, setIsSpeechSupported] = useState(false);
  
  const recognitionRef = useRef(null);
  
  // Backend URL'i - environment variable veya default
  const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000';
  
  // YENİ: Chat penceresinin açık (true) veya kapalı (false) olduğunu tutan state
  // Başlangıçta kapalı (false) olarak ayarlıyoruz.
  const [isOpen, setIsOpen] = useState(false);

  // Web Speech API desteğini kontrol et
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      setIsSpeechSupported(true);
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.lang = 'tr-TR'; // Türkçe

      recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        setInputValue(transcript);
        setIsListening(false);
      };

      recognition.onerror = (event) => {
        console.error('Speech recognition error:', event.error);
        setIsListening(false);
        if (event.error === 'no-speech') {
          alert('Konuşma algılanamadı. Lütfen tekrar deneyin.');
        }
      };

      recognition.onend = () => {
        setIsListening(false);
      };

      recognitionRef.current = recognition;
    }
  }, []);

  // Mikrofon butonuna tıklandığında
  const toggleListening = () => {
    if (!isSpeechSupported) {
      alert('Tarayıcınız ses tanımayı desteklemiyor. Chrome veya Edge kullanın.');
      return;
    }

    if (isListening) {
      recognitionRef.current?.stop();
      setIsListening(false);
    } else {
      try {
        recognitionRef.current?.start();
        setIsListening(true);
      } catch (error) {
        console.error('Speech recognition start error:', error);
        setIsListening(false);
      }
    }
  };

  const handleSend = async (e) => {
    e.preventDefault(); 
    const trimmedInput = inputValue.trim();
    if (trimmedInput === '') return; 

    const newUserMessage = {
      id: Date.now(),
      sender: 'user',
      text: trimmedInput
    };
    
    setMessages(prevMessages => [...prevMessages, newUserMessage]);
    setInputValue('');
    setIsLoading(true);

    try {
      const response = await fetch(`${BACKEND_URL}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ message: trimmedInput }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      
      const botResponse = {
        id: Date.now() + 1,
        sender: 'bot',
        text: data.response || 'Yanıt alınamadı.'
      };
      setMessages(prevMessages => [...prevMessages, botResponse]);
    } catch (error) {
      console.error('Chat hatası:', error);
      const errorMessage = {
        id: Date.now() + 1,
        sender: 'bot',
        text: 'Üzgünüm, bir hata oluştu. Lütfen daha sonra tekrar deneyin.'
      };
      setMessages(prevMessages => [...prevMessages, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  // YENİ: Chat penceresini açıp kapatan basit bir fonksiyon
  const toggleChat = () => {
    setIsOpen(!isOpen); // Durumu mevcut durumun tersine çevir
  };


  return (
    // YENİ: Bu ana taşıyıcı, hem baloncuk hem de chat penceresi için
    // sabit konumlandırmayı yönetecek.
    <div className="chatbot-widget-container">
      
      {/* YENİ: Sadece 'isOpen' state'i true ise chat penceresini göster */}
      {isOpen && (
        <div className="chat-window">
          
          <div className="chat-header">
            👤 ChatBot
            {/* YENİ: Kapatma butonu. Tıklandığında toggleChat'i çalıştırır. */}
            <button className="close-btn" onClick={toggleChat}>×</button>
          </div>
          
          <div className="chat-log">
            {messages.map(message => (
              <div 
                key={message.id} 
                className={`message ${message.sender}`}
              >
                <div className="message-bubble">
                  {message.text}
                </div>
              </div>
            ))}
          </div>
          
          <form className="chat-input-area" onSubmit={handleSend}>
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder="Mesajınızı buraya yazın..."
            />
            {isSpeechSupported && (
              <button
                type="button"
                className={`mic-button ${isListening ? 'listening' : ''}`}
                onClick={toggleListening}
                title={isListening ? 'Kaydı durdur' : 'Sesli mesaj gönder'}
              >
                {isListening ? '🔴' : '🎤'}
              </button>
            )}
            <button type="submit" disabled={isLoading || isListening}>
              {isLoading ? 'Gönderiliyor...' : 'Gönder'}
            </button>
          </form>
          
        </div>
      )}

      {/* YENİ: Sadece 'isOpen' state'i false ise (yani kapalıysa) baloncuk göster */}
      {!isOpen && (
        <button className="chat-bubble" onClick={toggleChat}>
          💬
        </button>
      )}

    </div>
  );
}

export default App;