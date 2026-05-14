'use client';

import {useState} from 'react';
import styles from "./chat.module.css";

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string>('');

  const sendMessage = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date(),
    };

    setMessages([userMessage, ...messages]);
    setInput('');
    setIsLoading(true);

    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: input,
          session_id: sessionId || undefined,
        }),
      });

      if (!response.ok) throw new Error('Failed to send message');

      const data = await response.json();

      setSessionId(data.session_id);

      const assistantMessage: Message = {
        id: Date.now().toString(),
        role: 'assistant',
        content: data.response[1].content,
        timestamp: new Date(),
      };

      setMessages([assistantMessage, userMessage, ...messages]);

    } catch (error) {
      console.error('Error:', error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className={styles.chat}>
      <h1>Chat</h1>
      <form onSubmit={sendMessage}>
        <textarea placeholder="Ask a question" value={input} onChange={(e) => setInput(e.target.value)} />
        <button type="submit">Send</button>
      </form>
      <div className={styles.messages}>
        {messages.map((message, index) => (
          <div key={`${message.id}-${index}`} className={styles.message}>
            <p>{message.content}</p>
          </div>
        ))}
      </div>
    </div>
  );
}