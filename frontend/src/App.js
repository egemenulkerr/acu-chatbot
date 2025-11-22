import { useState, useEffect, useRef } from 'react';
import './App.css';

// Mesaj metnindeki URL'leri bulup tıklanabilir linke çeviren fonksiyon
const renderMessageWithLinks = (text) => {
  // URL'leri yakalayan Regex deseni
  const urlRegex = /(https?:\/\/[^\s]+)/g;
  
  // Metni URL'lere göre parçala
  const parts = text.split(urlRegex);

  return parts.map((part, index) => {
    // Eğer parça bir URL ise <a> etiketi döndür
    if (part.match(urlRegex)) {
      return (
        <a 
          key={index} 
          href={part} 
          target="_blank" 
          rel="noopener noreferrer"
          onClick={(e) => e.stopPropagation()} // Balona tıklamayı engelle
        >
          {part}
        </a>
      );
    }
    // Değilse normal metin döndür
    return part;
  });
};

function App() {
  // --- STATE'LER ---
  const [isOpen, setIsOpen] = useState(false); // Widget açık mı kapalı mı?
  const [messages, setMessages] = useState([
    { text: "Merhaba! Ben AÇÜ Asistan. Size nasıl yardımcı olabilirim?", sender: "bot" }
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  
  // Otomatik kaydırma için referans
  const messagesEndRef = useRef(null);

  // Mesaj geldiğinde en alta kaydır
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };
  useEffect(scrollToBottom, [messages, isOpen]);

  // --- FONKSİYONLAR ---
  
  const toggleChat = () => setIsOpen(!isOpen);

  const sendMessage = async () => {
    if (!input.trim()) return;

    const userMessage = { text: input, sender: "user" };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    try {
      // Backend isteği
      const response = await fetch("http://localhost:8000/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMessage.text }),
      });
      
      if (!response.ok) throw new Error("Sunucu hatası");

      const data = await response.json();
      
      setMessages((prev) => [...prev, { 
        text: data.response, 
        sender: "bot",
        source: data.source 
      }]);

    } catch (error) {
      setMessages((prev) => [...prev, { 
        text: "Üzgünüm, şu an sunucuya ulaşamıyorum. Lütfen daha sonra tekrar deneyin.", 
        sender: "bot" 
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') sendMessage();
  };

  // --- RENDER ---
  return (
    <div className="widget-container">
      
      {/* 1. SOHBET PENCERESİ (Sadece isOpen true ise görünür) */}
      {isOpen && (
        <div className="chat-window">
          {/* Header */}
          <div className="chat-header">
            <h3>🎓 AÇÜ Asistan</h3>
            <button className="close-btn" onClick={toggleChat}>×</button>
          </div>

          {/* Mesajlar */}
          <div className="messages-area">
            {messages.map((msg, index) => (
              <div key={index} className={`message-bubble ${msg.sender}`}>
                {renderMessageWithLinks(msg.text)}
                {msg.source && <span className="message-source">{msg.source}</span>}
              </div>
            ))}
            {isLoading && <div className="message-bubble bot loading">Yazıyor...</div>}
            <div ref={messagesEndRef} /> {/* Kaydırma referansı */}
          </div>

          {/* Input */}
          <div className="input-area">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Sorunuzu yazın..."
              autoFocus
            />
            <button onClick={sendMessage}>➤</button>
          </div>
        </div>
      )}

      {/* 2. AÇMA BUTONU (LAUNCHER) - Her zaman görünür */}
      <button className="launcher-btn" onClick={toggleChat}>
        {isOpen ? (
          // Kapat ikonu (Açıksa)
          <svg viewBox="0 0 24 24" width="24" height="24" stroke="white" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        ) : (
          // Mesaj ikonu (Kapalıysa)
          <svg viewBox="0 0 24 24" className="launcher-icon">
            <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"></path>
          </svg>
        )}
      </button>

    </div>
  );
}

export default App;