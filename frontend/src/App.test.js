import { render, screen } from '@testing-library/react';
import App from './App';

// Mock fetch to avoid real network calls during tests
beforeEach(() => {
  global.fetch = jest.fn(() =>
    Promise.resolve({ ok: true, json: () => Promise.resolve({}) })
  );
});

afterEach(() => {
  jest.restoreAllMocks();
});

test('renders chatbot launcher button', () => {
  render(<App />);
  const launcher = screen.getByRole('button', { name: /chatbotu aç/i });
  expect(launcher).toBeInTheDocument();
});

test('launcher button has correct aria-label', () => {
  render(<App />);
  const launcher = screen.getByLabelText(/chatbotu aç/i);
  expect(launcher).toBeInTheDocument();
});

test('chat window is not visible initially', () => {
  render(<App />);
  const chatWindow = document.getElementById('acu-chat-window');
  expect(chatWindow).toBeNull();
});
