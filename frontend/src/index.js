import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';

// Kendi container'ını oluşturur — dış sitedeki #root ile çakışmaz
let container = document.getElementById('acu-chatbot-root');
if (!container) {
  container = document.createElement('div');
  container.id = 'acu-chatbot-root';
  document.body.appendChild(container);
}

const root = ReactDOM.createRoot(container);
root.render(<App />);
