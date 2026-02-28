import React, { useState, useEffect, useRef, useCallback } from 'react';
import './App.css';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000';

const INITIAL_BOT_MESSAGE = {
  id: 1, sender: 'bot',
  text: 'Merhaba! Ben AÇÜ Asistan\'ım. Yemek menüsü, akademik takvim, laboratuvar cihazları ve kampüs hakkında sana yardımcı olabilirim. 👋',
  timestamp: new Date().toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' })
};

const QUICK_REPLIES = [
  { label: '🍽️ Bugünün menüsü', text: 'Bugün yemek ne?' },
  { label: '📅 Akademik takvim', text: 'Akademik takvim ne zaman?' },
  { label: '🔬 Lab cihazları', text: 'Laboratuvar cihazları hakkında bilgi ver' },
];

const ERROR_MESSAGES = {
  SPEECH_NOT_SUPPORTED: 'Tarayıcınız ses tanımayı desteklemiyor.',
  NO_SPEECH: 'Ses algılanamadı, tekrar deneyin.',
  API_ERROR: 'Bağlantı hatası oluştu. Lütfen tekrar deneyin.',
  INVALID_INPUT: 'Mesaj boş olamaz.',
  RATE_LIMIT: 'Çok fazla mesaj gönderildi. Lütfen bekleyin.',
};

function getOrCreateSessionId() {
  const key = 'acu_session';
  let id = sessionStorage.getItem(key);
  if (!id) {
    id = `s_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    sessionStorage.setItem(key, id);
  }
  return id;
}

function nowTime() {
  return new Date().toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' });
}

function renderMarkdown(text) {
  if (!text) return null;

  // URL regex — http(s) ile başlayan linkleri yakala
  const URL_RE = /(https?:\/\/[^\s]+)/g;

  return text.split('\n').map((line, i, arr) => {
    // Önce bold'ları, sonra URL'leri ayır
    const tokens = line.split(/(\*\*[^*]+\*\*|https?:\/\/[^\s]+)/g);
    const rendered = tokens.map((token, j) => {
      if (token.startsWith('**') && token.endsWith('**')) {
        return <strong key={j}>{token.slice(2, -2)}</strong>;
      }
      if (URL_RE.test(token)) {
        URL_RE.lastIndex = 0; // regex state sıfırla
        // URL'yi kısalt — 45 karakterden uzunsa "…" ekle
        const label = token.length > 45 ? token.slice(0, 45) + '…' : token;
        return (
          <a key={j} href={token} target="_blank" rel="noopener noreferrer"
            style={{ color: '#059669', textDecoration: 'underline', wordBreak: 'break-all' }}>
            🔗 {label}
          </a>
        );
      }
      return token;
    });

    return (
      <React.Fragment key={i}>
        {rendered}
        {i < arr.length - 1 && <br />}
      </React.Fragment>
    );
  });
}

function initSpeech(onResult, onListening, onError) {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) return null;
  const r = new SR();
  r.continuous = false; r.interimResults = false; r.lang = 'tr-TR';
  r.onstart = () => onListening(true);
  r.onresult = e => { onResult(e.results[0][0].transcript); onListening(false); };
  r.onerror = e => { onListening(false); if (e.error === 'no-speech') onError(ERROR_MESSAGES.NO_SPEECH); };
  r.onend = () => onListening(false);
  return r;
}

async function callAPI(message, sessionId, history, url) {
  const res = await fetch(`${url}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      session_id: sessionId,
      history: history.slice(-10).map(m => ({ role: m.sender === 'user' ? 'user' : 'bot', text: m.text }))
    }),
  });
  if (res.status === 429) throw new Error('RATE_LIMIT');
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export default function App() {
  const [messages, setMessages] = useState([INITIAL_BOT_MESSAGE]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [listening, setListening] = useState(false);
  const [speechOk, setSpeechOk] = useState(false);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState('');
  const [online, setOnline] = useState(true);
  const [unread, setUnread] = useState(0);

  const srRef = useRef(null);
  const logRef = useRef(null);
  const sessionRef = useRef(getOrCreateSessionId());

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [messages, loading]);

  useEffect(() => {
    const check = () => fetch(`${BACKEND_URL}/health`, { signal: AbortSignal.timeout(3000) })
      .then(r => setOnline(r.ok)).catch(() => setOnline(false));
    check();
    const t = setInterval(check, 30000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    const sr = initSpeech(t => setInput(t), setListening, e => setError(e));
    if (sr) { srRef.current = sr; setSpeechOk(true); }
  }, []);

  useEffect(() => { if (input) setError(''); }, [input]);

  // Chatbot açıkken unread sıfırla
  useEffect(() => { if (open) setUnread(0); }, [open]);

  const send = useCallback(async (text) => {
    const t = text.trim();
    if (!t) { setError(ERROR_MESSAGES.INVALID_INPUT); return; }
    setError('');

    const userMsg = { id: Date.now(), sender: 'user', text: t, timestamp: nowTime() };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const data = await callAPI(t, sessionRef.current, [...messages, userMsg], BACKEND_URL);
      const botMsg = { id: Date.now() + 1, sender: 'bot', text: data.response || '…', timestamp: nowTime() };
      setMessages(prev => [...prev, botMsg]);
      if (!open) setUnread(n => n + 1);
    } catch (e) {
      const msg = e.message === 'RATE_LIMIT' ? ERROR_MESSAGES.RATE_LIMIT : ERROR_MESSAGES.API_ERROR;
      setMessages(prev => [...prev, { id: Date.now() + 1, sender: 'bot', text: msg, timestamp: nowTime() }]);
    } finally {
      setLoading(false);
    }
  }, [messages, open]);

  const handleSubmit = useCallback(e => { e.preventDefault(); send(input); }, [input, send]);

  const toggleMic = useCallback(() => {
    if (!speechOk) { setError(ERROR_MESSAGES.SPEECH_NOT_SUPPORTED); return; }
    if (listening) { srRef.current?.stop(); }
    else { setError(''); try { srRef.current?.start(); } catch { setListening(false); } }
  }, [speechOk, listening]);

  const clearChat = useCallback(() => {
    setMessages([INITIAL_BOT_MESSAGE]);
    sessionStorage.removeItem('acu_session');
    sessionRef.current = getOrCreateSessionId();
    setError('');
    setUnread(0);
  }, []);

  const showQuickReplies = messages.length <= 2 && !loading;

  return (
    <div className="acu-widget">

      {/* ── CHAT WINDOW ── */}
      {open && (
        <div className="acu-window">

          {/* Header */}
          <header className="acu-header">
            <div className="acu-header-glow" />
            <div className="acu-header-left">
              <div className="acu-avatar">
                <span>🎓</span>
                <span className={`acu-badge ${online ? 'on' : 'off'}`} />
              </div>
              <div className="acu-title-group">
                <p className="acu-title">AÇÜ Asistan</p>
                <p className="acu-subtitle">{online ? '● Çevrimiçi' : '● Çevrimdışı'}</p>
              </div>
            </div>
            <div className="acu-header-right">
              <button className="acu-icon-btn" onClick={clearChat} title="Temizle">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4h6v2"/></svg>
              </button>
              <button className="acu-icon-btn" onClick={() => setOpen(false)} title="Kapat">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              </button>
            </div>
          </header>

          {/* Messages */}
          <div className="acu-log" ref={logRef}>
            {messages.map((m, idx) => {
              const prevSame = idx > 0 && messages[idx - 1].sender === m.sender;
              return (
                <div key={m.id} className={`acu-msg acu-msg--${m.sender} ${prevSame ? 'acu-msg--cont' : ''}`}>
                  {m.sender === 'bot' && !prevSame && (
                    <div className="acu-msg-avatar">🎓</div>
                  )}
                  {m.sender === 'bot' && prevSame && <div className="acu-msg-avatar-spacer" />}
                  <div className="acu-msg-body">
                    <div className="acu-bubble">
                      {m.sender === 'bot' ? renderMarkdown(m.text) : m.text}
                    </div>
                    <span className="acu-time">{m.timestamp}</span>
                  </div>
                </div>
              );
            })}

            {loading && (
              <div className="acu-msg acu-msg--bot">
                <div className="acu-msg-avatar">🎓</div>
                <div className="acu-msg-body">
                  <div className="acu-bubble acu-typing">
                    <span /><span /><span />
                  </div>
                </div>
              </div>
            )}

            {showQuickReplies && (
              <div className="acu-quick">
                {QUICK_REPLIES.map(q => (
                  <button key={q.text} className="acu-chip" onClick={() => send(q.text)}>{q.label}</button>
                ))}
              </div>
            )}
          </div>

          {/* Error */}
          {error && <div className="acu-error">⚠ {error}</div>}

          {/* Input */}
          <form className="acu-input-bar" onSubmit={handleSubmit}>
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              placeholder="Bir şeyler yazın…"
              disabled={loading}
              autoFocus
            />
            {speechOk && (
              <button type="button" className={`acu-mic ${listening ? 'active' : ''}`} onClick={toggleMic} disabled={loading}>
                {listening
                  ? <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>
                  : <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>
                }
              </button>
            )}
            <button type="submit" className="acu-send" disabled={loading || listening || !input.trim()}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
              </svg>
            </button>
          </form>

        </div>
      )}

      {/* ── LAUNCH BUTTON ── */}
      <button className="acu-launcher" onClick={() => setOpen(o => !o)} aria-label="Chatbot">
        {open
          ? <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          : <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
        }
        {!open && unread > 0 && <span className="acu-unread">{unread}</span>}
      </button>

    </div>
  );
}
