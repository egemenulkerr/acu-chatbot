import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import './App.css';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000';
const LS_KEY = 'acu_chat_history';
const LS_THEME = 'acu_theme';
const MAX_STORED = 60;
const MAX_CHARS = 500;

const INITIAL_BOT_MESSAGE = {
  id: 1, sender: 'bot', feedback: null, streaming: false,
  text: 'Merhaba! Ben **AÇÜ Asistan**\'ım.\n\nYemek menüsü, akademik takvim, lab cihazları, burs, yurt, OBS ve daha fazlası için buradayım. 👋',
};

const QUICK_REPLY_CATEGORIES = [
  {
    label: 'Günlük',
    items: [
      { label: '🍽️ Bugünün menüsü', text: 'Bugün yemek ne?' },
      { label: '🌤️ Hava durumu', text: 'Artvin hava durumu' },
      { label: '📢 Duyurular', text: 'Son duyurular neler?' },
    ]
  },
  {
    label: 'Akademik',
    items: [
      { label: '📅 Akademik takvim', text: 'Akademik takvim' },
      { label: '📝 Ders kaydı', text: 'Ders kaydı nasıl yapılır?' },
      { label: '📊 Sınav sonuçları', text: 'Sınav sonuçlarım nasıl görürüm?' },
    ]
  },
  {
    label: 'Kampüs',
    items: [
      { label: '🔬 Lab cihazları', text: 'Laboratuvar cihazları neler?' },
      { label: '📚 Kütüphane', text: 'Kütüphane saatleri ne?' },
      { label: '🚌 Servis saatleri', text: 'Kampüs servis saatleri' },
    ]
  },
  {
    label: 'Destek',
    items: [
      { label: '💰 Burs bilgisi', text: 'Hangi burslar mevcut?' },
      { label: '🏠 Yurt bilgisi', text: 'KYK yurt başvurusu nasıl?' },
      { label: '💻 OBS girişi', text: 'OBS şifremi unuttum' },
    ]
  }
];

const SUGGESTIONS = [
  'Yemek menüsü nedir?',
  'Akademik takvim ne zaman?',
  'Ders kaydı nasıl yapılır?',
  'Kütüphane saatleri?',
  'Burs başvurusu nasıl?',
  'Erasmus programı nedir?',
  'OBS şifremi unuttum',
  'Staj nasıl yapılır?',
  'Yurt başvurusu ne zaman?',
  'Mazeret sınavına nasıl girerim?',
  'Hava durumu nasıl?',
  'Kampüs servisi kaçta kalkıyor?',
];

const ERROR_MESSAGES = {
  SPEECH_NOT_SUPPORTED: 'Tarayıcınız ses tanımayı desteklemiyor.',
  NO_SPEECH: 'Ses algılanamadı, tekrar deneyin.',
  API_ERROR: 'Bağlantı hatası. Lütfen tekrar deneyin.',
  INVALID_INPUT: 'Mesaj boş olamaz.',
  RATE_LIMIT: 'Çok fazla mesaj. Lütfen bir an bekleyin.',
  TOO_LONG: `Mesaj ${MAX_CHARS} karakteri aşamaz.`,
};

// ── Helpers ───────────────────────────────────────────────────────────────────

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

function loadHistory() {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed) || parsed.length === 0) return null;
    return parsed.map(m => ({ ...m, streaming: false }));
  } catch { return null; }
}

function saveHistory(messages) {
  try {
    const toSave = messages.slice(-MAX_STORED).map(m => ({ ...m, streaming: false }));
    localStorage.setItem(LS_KEY, JSON.stringify(toSave));
  } catch { /* QuotaExceededError */ }
}

function renderMarkdown(text) {
  if (!text) return null;
  const URL_RE = /(https?:\/\/[^\s]+)/g;

  return text.split('\n').map((line, i, arr) => {
    // Bullet points
    if (line.match(/^[•\-*] /)) {
      const content = line.replace(/^[•\-*] /, '');
      return (
        <React.Fragment key={i}>
          <span className="acu-bullet">
            <span className="acu-bullet-dot">•</span>
            <span>{renderInline(content)}</span>
          </span>
          {i < arr.length - 1 && <br />}
        </React.Fragment>
      );
    }
    // Numbered lists
    if (line.match(/^\d+[️⃣]? /)) {
      return (
        <React.Fragment key={i}>
          <span className="acu-bullet">{renderInline(line)}</span>
          {i < arr.length - 1 && <br />}
        </React.Fragment>
      );
    }
    return (
      <React.Fragment key={i}>
        {renderInline(line)}
        {i < arr.length - 1 && <br />}
      </React.Fragment>
    );
  });

  function renderInline(line) {
    const tokens = line.split(/(\*\*[^*]+\*\*|`[^`]+`|https?:\/\/[^\s]+)/g);
    return tokens.map((token, j) => {
      if (token.startsWith('**') && token.endsWith('**'))
        return <strong key={j}>{token.slice(2, -2)}</strong>;
      if (token.startsWith('`') && token.endsWith('`'))
        return <code key={j} className="acu-code">{token.slice(1, -1)}</code>;
      if (URL_RE.test(token)) {
        URL_RE.lastIndex = 0;
        const label = token.length > 45 ? token.slice(0, 45) + '…' : token;
        return (
          <a key={j} href={token} target="_blank" rel="noopener noreferrer" className="acu-link">
            🔗 {label}
          </a>
        );
      }
      return token;
    });
  }
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

// ── Streaming fetch ───────────────────────────────────────────────────────────

async function streamMessage(message, sessionId, history, onToken, onDone, onError, signal) {
  try {
    const res = await fetch(`${BACKEND_URL}/api/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        session_id: sessionId,
        history: history.slice(-10).map(m => ({ role: m.sender === 'user' ? 'user' : 'bot', text: m.text })),
      }),
      signal,
    });

    if (res.status === 429) { onError('RATE_LIMIT'); return; }
    if (!res.ok) { onError('API_ERROR'); return; }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const lines = buf.split('\n');
      buf = lines.pop();
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        try {
          const ev = JSON.parse(line.slice(6));
          if (ev.token) onToken(ev.token);
          if (ev.done) { onDone(); return; }
        } catch { /* skip malformed */ }
      }
    }
    onDone();
  } catch (err) {
    if (err.name === 'AbortError') return;
    onError('API_ERROR');
  }
}

// ── Sub-components ────────────────────────────────────────────────────────────

function TypingIndicator() {
  return (
    <div className="acu-msg acu-msg--bot">
      <div className="acu-msg-avatar">🎓</div>
      <div className="acu-msg-body">
        <div className="acu-bubble acu-typing">
          <span /><span /><span />
        </div>
      </div>
    </div>
  );
}

function ScrollToBottom({ onClick }) {
  return (
    <button className="acu-scroll-btn" onClick={onClick} title="En alta git">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
        <polyline points="6 9 12 15 18 9" />
      </svg>
    </button>
  );
}

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);
  const copy = useCallback(() => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }, [text]);
  return (
    <button className="acu-copy-btn" onClick={copy} title="Kopyala">
      {copied
        ? <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="20 6 9 17 4 12" /></svg>
        : <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="9" y="9" width="13" height="13" rx="2" /><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" /></svg>
      }
    </button>
  );
}

// ── Main Component ─────────────────────────────────────────────────────────────

export default function App() {
  const [messages, setMessages] = useState(() => loadHistory() || [{ ...INITIAL_BOT_MESSAGE, timestamp: new Date().toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' }) }]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [listening, setListening] = useState(false);
  const [speechOk, setSpeechOk] = useState(false);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState('');
  const [online, setOnline] = useState(true);
  const [unread, setUnread] = useState(0);
  const [darkMode, setDarkMode] = useState(() => localStorage.getItem(LS_THEME) === 'dark');
  const [activeCategory, setActiveCategory] = useState(0);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [filteredSuggestions, setFilteredSuggestions] = useState([]);
  const [atBottom, setAtBottom] = useState(true);
  const [selectedSuggestion, setSelectedSuggestion] = useState(-1);
  const [showMenu, setShowMenu] = useState(false);

  const srRef = useRef(null);
  const logRef = useRef(null);
  const inputRef = useRef(null);
  const sessionRef = useRef(getOrCreateSessionId());
  const isMobile = useRef(typeof window !== 'undefined' && window.innerWidth <= 480);
  const abortRef = useRef(null);

  // Theme
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', darkMode ? 'dark' : 'light');
    localStorage.setItem(LS_THEME, darkMode ? 'dark' : 'light');
  }, [darkMode]);

  // Visual Viewport API: klavye açıkken pencere yüksekliğini güncelle
  useEffect(() => {
    const vv = window.visualViewport;
    if (!vv) return;

    const onResize = () => {
      // Klavye açıldığında visual viewport daralır; bunu CSS değişkenine yansıt
      document.documentElement.style.setProperty(
        '--acu-window-height',
        `${vv.height}px`
      );
      // Açık pencerede log'u scroll et
      if (open && logRef.current) {
        setTimeout(() => {
          logRef.current.scrollTop = logRef.current.scrollHeight;
        }, 100);
      }
    };

    vv.addEventListener('resize', onResize);
    return () => vv.removeEventListener('resize', onResize);
  }, [open]);

  // Body scroll lock: chat açıkken sayfanın kaymasını engelle (iOS)
  useEffect(() => {
    if (!isMobile.current) return;
    if (open) {
      const scrollY = window.scrollY;
      document.body.style.position = 'fixed';
      document.body.style.top = `-${scrollY}px`;
      document.body.style.width = '100%';
      document.body.style.overflow = 'hidden';
    } else {
      const top = document.body.style.top;
      document.body.style.position = '';
      document.body.style.top = '';
      document.body.style.width = '';
      document.body.style.overflow = '';
      if (top) window.scrollTo(0, -parseInt(top, 10));
    }
    return () => {
      document.body.style.position = '';
      document.body.style.top = '';
      document.body.style.width = '';
      document.body.style.overflow = '';
    };
  }, [open]);

  // LocalStorage sync — debounced to avoid per-token saves during streaming
  useEffect(() => {
    const isStreaming = messages.some(m => m.streaming);
    if (isStreaming) return;
    const t = setTimeout(() => saveHistory(messages), 300);
    return () => clearTimeout(t);
  }, [messages]);

  // Auto-scroll
  useEffect(() => {
    if (atBottom && logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [messages, loading, atBottom]);

  // Scroll listener
  const handleScroll = useCallback(() => {
    if (!logRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = logRef.current;
    setAtBottom(scrollHeight - scrollTop - clientHeight < 60);
  }, []);

  // Health check — uzun timeout + ilk yüklemede birkaç deneme (backend soğuk başlangıç için)
  const HEALTH_TIMEOUT_MS = 10000;
  const HEALTH_INTERVAL_MS = 30000;
  useEffect(() => {
    let cancelled = false;
    const doCheck = (retries = 2) => {
      if (cancelled) return;
      const ctrl = new AbortController();
      const to = setTimeout(() => ctrl.abort(), HEALTH_TIMEOUT_MS);
      fetch(`${BACKEND_URL}/health`, { signal: ctrl.signal })
        .then(r => {
          if (!cancelled) setOnline(r.ok);
        })
        .catch(() => {
          if (cancelled) return;
          if (retries > 0) setTimeout(() => doCheck(retries - 1), 2000);
          else setOnline(false);
        })
        .finally(() => clearTimeout(to));
    };
    doCheck();
    const t = setInterval(() => doCheck(0), HEALTH_INTERVAL_MS);
    return () => { cancelled = true; clearInterval(t); };
  }, []);

  // Speech
  useEffect(() => {
    const sr = initSpeech(t => setInput(t), setListening, e => setError(e));
    if (sr) { srRef.current = sr; setSpeechOk(true); }
  }, []);

  useEffect(() => { if (input) setError(''); }, [input]);
  useEffect(() => {
    if (open) setUnread(0);
    // Pencere kapanırken aktif stream'i durdur
    if (!open && abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
      setLoading(false);
    }
  }, [open]);

  // Open → focus input (mobilede klavye settle için daha uzun delay)
  useEffect(() => {
    if (open) {
      const delay = isMobile.current ? 300 : 80;
      setTimeout(() => inputRef.current?.focus(), delay);
    }
  }, [open]);

  // Suggestions filter
  useEffect(() => {
    if (!input.trim() || input.length < 2) {
      setShowSuggestions(false);
      setFilteredSuggestions([]);
      return;
    }
    const q = input.toLowerCase();
    const matches = SUGGESTIONS.filter(s => s.toLowerCase().includes(q)).slice(0, 4);
    setFilteredSuggestions(matches);
    setShowSuggestions(matches.length > 0);
    setSelectedSuggestion(-1);
  }, [input]);

  // ── Feedback ──
  const handleFeedback = useCallback((msgId, value) => {
    setMessages(prev => {
      const updated = prev.map(m =>
        m.id === msgId ? { ...m, feedback: m.feedback === value ? null : value } : m
      );
      const msg = updated.find(m => m.id === msgId);
      if (msg) {
        const newValue = msg.feedback;
        fetch(`${BACKEND_URL}/api/feedback`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-Session-Id': sessionRef.current },
          body: JSON.stringify({ msg_id: msgId, value: newValue, text: msg.text }),
        }).catch(() => {});
      }
      return updated;
    });
  }, []);

  // ── Send ──
  const send = useCallback(async (text) => {
    const t = (text || input).trim();
    if (!t) { setError(ERROR_MESSAGES.INVALID_INPUT); return; }
    if (t.length > MAX_CHARS) { setError(ERROR_MESSAGES.TOO_LONG); return; }
    setError('');
    setShowSuggestions(false);

    // Önceki stream varsa iptal et
    if (abortRef.current) abortRef.current.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    const userMsg = { id: Date.now(), sender: 'user', text: t, timestamp: nowTime(), feedback: null, streaming: false };
    const botId = Date.now() + 1;
    const botPlaceholder = { id: botId, sender: 'bot', text: '', timestamp: nowTime(), feedback: null, streaming: true };

    setMessages(prev => [...prev, userMsg, botPlaceholder]);
    setInput('');
    setLoading(true);
    setAtBottom(true);
    setShowMenu(false);

    await streamMessage(
      t, sessionRef.current,
      [...messages, userMsg],
      (token) => setMessages(prev => prev.map(m => m.id === botId ? { ...m, text: m.text + token } : m)),
      () => {
        abortRef.current = null;
        setMessages(prev => prev.map(m => m.id === botId ? { ...m, streaming: false } : m));
        setLoading(false);
        if (!open) setUnread(n => n + 1);
        setAtBottom(true);
      },
      (errKey) => {
        abortRef.current = null;
        const msg = ERROR_MESSAGES[errKey] || ERROR_MESSAGES.API_ERROR;
        setMessages(prev => prev.map(m => m.id === botId ? { ...m, text: `⚠️ ${msg}`, streaming: false, error: true } : m));
        setLoading(false);
      },
      controller.signal,
    );
  }, [messages, open, input]);

  const handleSubmit = useCallback(e => { e.preventDefault(); send(); }, [send]);

  const handleKeyDown = useCallback(e => {
    if (showSuggestions) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedSuggestion(s => Math.min(s + 1, filteredSuggestions.length - 1));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedSuggestion(s => Math.max(s - 1, -1));
      } else if (e.key === 'Enter' && selectedSuggestion >= 0) {
        e.preventDefault();
        setInput(filteredSuggestions[selectedSuggestion]);
        setShowSuggestions(false);
        setSelectedSuggestion(-1);
      } else if (e.key === 'Escape') {
        setShowSuggestions(false);
      }
    }
  }, [showSuggestions, selectedSuggestion, filteredSuggestions]);

  const toggleMic = useCallback(() => {
    if (!speechOk) { setError(ERROR_MESSAGES.SPEECH_NOT_SUPPORTED); return; }
    if (listening) srRef.current?.stop();
    else { setError(''); try { srRef.current?.start(); } catch { setListening(false); } }
  }, [speechOk, listening]);

  const clearChat = useCallback(() => {
    setMessages([INITIAL_BOT_MESSAGE]);
    localStorage.removeItem(LS_KEY);
    sessionStorage.removeItem('acu_session');
    sessionRef.current = getOrCreateSessionId();
    setError('');
    setUnread(0);
    setShowMenu(false);
    setActiveCategory(0);
  }, []);

  const goToMenu = useCallback(() => {
    setShowMenu(true);
    setActiveCategory(0);
    setTimeout(() => {
      if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
    }, 50);
  }, []);

  const charCount = input.length;
  const showCharWarning = charCount > MAX_CHARS * 0.8;
  const isNewChat = messages.length <= 2;
  const showQuickReplies = (isNewChat || showMenu) && !loading;

  const currentCategory = QUICK_REPLY_CATEGORIES[activeCategory];

  // Group messages by date (simple: consecutive same-sender)
  const groupedMessages = useMemo(() => {
    return messages.map((m, i) => ({
      ...m,
      prevSame: i > 0 && messages[i - 1].sender === m.sender,
      nextSame: i < messages.length - 1 && messages[i + 1].sender === m.sender,
    }));
  }, [messages]);

  return (
    <div className={`acu-widget${darkMode ? ' dark' : ''}`}>

      {/* ── CHAT WINDOW ── */}
      {open && (
        <div
          id="acu-chat-window"
          className="acu-window"
          role="dialog"
          aria-label="AÇÜ Asistan sohbet penceresi"
          aria-modal="true"
        >

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
              {messages.length > 2 && (
                <button
                  className="acu-icon-btn"
                  onClick={goToMenu}
                  title="Ana Menü"
                  aria-label="Ana menüye git"
                >
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
                </button>
              )}
              <button
                className="acu-icon-btn"
                onClick={() => setDarkMode(d => !d)}
                title={darkMode ? 'Açık mod' : 'Koyu mod'}
                aria-label={darkMode ? 'Açık moda geç' : 'Koyu moda geç'}
                aria-pressed={darkMode}
              >
                {darkMode
                  ? <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>
                  : <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
                }
              </button>
              <button className="acu-icon-btn" onClick={clearChat} title="Sohbeti temizle" aria-label="Sohbeti temizle">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4h6v2"/></svg>
              </button>
              <button className="acu-icon-btn" onClick={() => setOpen(false)} title="Kapat" aria-label="Sohbeti kapat">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              </button>
            </div>
          </header>

          {/* Messages */}
          <div
            className="acu-log"
            ref={logRef}
            onScroll={handleScroll}
            role="log"
            aria-live="polite"
            aria-label="Sohbet mesajları"
          >
            {groupedMessages.map((m) => (
              <div
                key={m.id}
                className={[
                  'acu-msg',
                  `acu-msg--${m.sender}`,
                  m.prevSame ? 'acu-msg--cont' : '',
                  m.nextSame ? 'acu-msg--group' : '',
                ].filter(Boolean).join(' ')}
              >
                {m.sender === 'bot' && !m.prevSame && <div className="acu-msg-avatar">🎓</div>}
                {m.sender === 'bot' && m.prevSame && <div className="acu-msg-avatar-spacer" />}

                <div className="acu-msg-body">
                  <div className={`acu-bubble${m.streaming && !m.text ? ' acu-typing' : ''}`}>
                    {m.streaming && !m.text
                      ? <><span /><span /><span /></>
                      : (m.sender === 'bot' ? renderMarkdown(m.text) : m.text)
                    }
                    {m.streaming && m.text && <span className="acu-cursor">▌</span>}
                  </div>

                  <div className="acu-msg-footer">
                    <span className="acu-time">{m.timestamp}</span>
                    {m.sender === 'bot' && !m.streaming && m.text && (
                      <div className="acu-actions">
                        {m.error ? (
                          <button
                            className="acu-retry-btn"
                            onClick={() => {
                              const lastUser = [...messages].reverse().find(msg => msg.sender === 'user');
                              if (lastUser) send(lastUser.text);
                            }}
                            title="Tekrar dene"
                          >↺ Tekrar Dene</button>
                        ) : (
                          <>
                            <CopyButton text={m.text} />
                            <div className="acu-feedback">
                              <button
                                className={`acu-fb-btn${m.feedback === 'up' ? ' active-up' : ''}`}
                                onClick={() => handleFeedback(m.id, 'up')}
                                title="Yardımcı oldu"
                              >👍</button>
                              <button
                                className={`acu-fb-btn${m.feedback === 'down' ? ' active-down' : ''}`}
                                onClick={() => handleFeedback(m.id, 'down')}
                                title="Yardımcı olmadı"
                              >👎</button>
                            </div>
                          </>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}

            {/* Typing indicator when loading but no placeholder yet */}
            {loading && messages[messages.length - 1]?.sender === 'user' && <TypingIndicator />}

            {/* Quick replies */}
            {showQuickReplies && (
              <div className="acu-quick-wrap">
                <div className="acu-quick-header">
                  <span className="acu-quick-title">Ne sormak istersin?</span>
                  {showMenu && (
                    <button className="acu-quick-close" onClick={() => setShowMenu(false)} title="Kapat">
                      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                    </button>
                  )}
                </div>
                <div className="acu-quick-tabs">
                  {QUICK_REPLY_CATEGORIES.map((cat, i) => (
                    <button
                      key={cat.label}
                      className={`acu-tab${activeCategory === i ? ' active' : ''}`}
                      onClick={() => setActiveCategory(i)}
                    >
                      {cat.label}
                    </button>
                  ))}
                </div>
                <div className="acu-quick">
                  {currentCategory.items.map(q => (
                    <button key={q.text} className="acu-chip" onClick={() => send(q.text)}>
                      <span>{q.label}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Scroll to bottom */}
          {!atBottom && <ScrollToBottom onClick={() => {
            if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
            setAtBottom(true);
          }} />}

          {/* Error */}
          {error && (
            <div className="acu-error">
              <span>⚠ {error}</span>
              <button className="acu-error-close" onClick={() => setError('')}>✕</button>
            </div>
          )}

          {/* Suggestions dropdown */}
          {showSuggestions && (
            <div className="acu-suggestions" id="acu-suggestions-list" role="listbox">
              {filteredSuggestions.map((s, i) => (
                <button
                  key={s}
                  role="option"
                  aria-selected={i === selectedSuggestion}
                  className={`acu-suggestion-item${i === selectedSuggestion ? ' selected' : ''}`}
                  onMouseDown={e => { e.preventDefault(); setInput(s); setShowSuggestions(false); }}
                  onTouchEnd={e => { e.preventDefault(); setInput(s); setShowSuggestions(false); inputRef.current?.focus(); }}
                >
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="acu-suggest-icon"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                  {s}
                </button>
              ))}
            </div>
          )}

          {/* Input */}
          <form className="acu-input-bar" onSubmit={handleSubmit}>
            <div className="acu-input-wrap">
              <input
                ref={inputRef}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                onBlur={() => setTimeout(() => setShowSuggestions(false), 150)}
                placeholder="Bir şeyler yazın…"
                disabled={loading}
                maxLength={MAX_CHARS + 50}
                autoComplete="off"
                role="combobox"
                aria-label="Mesaj yaz"
                aria-autocomplete="list"
                aria-expanded={showSuggestions}
                aria-controls="acu-suggestions-list"
                aria-haspopup="listbox"
              />
              {input && (
                <button
                  type="button"
                  className="acu-input-clear"
                  onClick={() => { setInput(''); setShowSuggestions(false); inputRef.current?.focus(); }}
                  tabIndex={-1}
                >
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                </button>
              )}
              {showCharWarning && (
                <span
                  className={`acu-char-count${charCount > MAX_CHARS ? ' over' : ''}`}
                  role="status"
                  aria-live="polite"
                >
                  {charCount}/{MAX_CHARS}
                </span>
              )}
            </div>

            {speechOk && (
              <button
                type="button"
                className={`acu-mic ${listening ? 'active' : ''}`}
                onClick={toggleMic}
                disabled={loading}
                title={listening ? 'Durdur' : 'Sesle yaz'}
                aria-label={listening ? 'Sesi durdur' : 'Sesle mesaj yaz'}
                aria-pressed={listening}
              >
                {listening
                  ? <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2" /></svg>
                  : <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>
                }
              </button>
            )}

            <button
              type="submit"
              className={`acu-send${loading ? ' sending' : ''}`}
              disabled={loading || listening || !input.trim() || charCount > MAX_CHARS}
              title="Gönder"
              aria-label="Mesajı gönder"
            >
              {loading
                ? <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="acu-spin"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg>
                : <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
              }
            </button>
          </form>

          {/* Footer */}
          <div className="acu-footer">
            AÇÜ Asistan · Artvin Çoruh Üniversitesi
          </div>

        </div>
      )}

      {/* ── LAUNCH BUTTON ── */}
      <button
        className="acu-launcher"
        onClick={() => setOpen(o => !o)}
        aria-label={open ? 'Chatbotu kapat' : 'Chatbotu aç'}
        aria-expanded={open}
        aria-controls="acu-chat-window"
      >
        <div className={`acu-launcher-icon${open ? ' rotated' : ''}`}>
          {open
            ? <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            : <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
          }
        </div>
        {!open && unread > 0 && (
          <span className="acu-unread">{unread > 9 ? '9+' : unread}</span>
        )}
      </button>

    </div>
  );
}
