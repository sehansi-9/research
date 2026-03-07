"use client";

import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type ChatMessage = { role: "user" | "assistant"; content: string };

export default function Home() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string>("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let storedId = localStorage.getItem("chat_session_id");
    if (!storedId) {
      storedId = crypto.randomUUID();
      localStorage.setItem("chat_session_id", storedId);
    }
    setSessionId(storedId);
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function sendMessage() {
    if (!input.trim()) return;

    const userMessage: ChatMessage = { role: "user", content: input };
    setMessages(prev => [...prev, userMessage]);

    try {
      const res = await fetch("http://localhost:9000/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: input,
          session_id: sessionId
        })
      });

      const data = await res.json();

      const assistantMessage: ChatMessage = {
        role: "assistant",
        content: data.answer || "No response available."
      };

      setMessages(prev => [...prev, assistantMessage]);
      setInput("");
    } catch (err) {
      console.error(err);
      setMessages(prev => [
        ...prev,
        { role: "assistant", content: "Error fetching response" }
      ]);
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-950 via-gray-900 to-black flex justify-center items-center p-6 text-gray-200">

      <div className="w-full max-w-3xl h-[85vh] flex flex-col backdrop-blur-xl bg-white/5 border border-white/10 rounded-3xl shadow-2xl overflow-hidden">

        {/* Header */}
        <header className="flex justify-between items-center px-6 py-4 border-b border-white/10 bg-white/5 backdrop-blur-md">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-green-400 rounded-full animate-pulse" />
            <span className="font-semibold text-lg tracking-wide">
              OpenGIN AI
            </span>
          </div>

          <button
            onClick={() => {
              const newId = crypto.randomUUID();
              localStorage.setItem("chat_session_id", newId);
              setSessionId(newId);
              setMessages([]);
            }}
            className="text-xs px-3 py-1 rounded-lg bg-white/10 hover:bg-white/20 transition"
          >
            New Chat
          </button>
        </header>

        {/* Chat Window */}
        <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
          {messages.map((m, i) => (
            <div
              key={i}
              className={`flex ${m.role === "user" ? "justify-end" : "justify-start"
                }`}
            >
              <div
                className={`max-w-[75%] px-4 py-3 rounded-2xl text-sm shadow-md transition-all duration-200 ${m.role === "user"
                  ? "bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-br-none"
                  : "bg-white/10 border border-white/10 text-gray-200 rounded-bl-none"
                  }`}
              >
                {m.role === "assistant" ? (
                  <div className="prose prose-invert prose-sm max-w-none">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {m.content}
                    </ReactMarkdown>
                  </div>
                ) : (
                  m.content
                )}
              </div>
            </div>
          ))}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="p-4 border-t border-white/10 bg-white/5 backdrop-blur-md">
          <div className="flex items-center gap-3 bg-white/10 rounded-2xl px-4 py-2 focus-within:ring-2 focus-within:ring-blue-500 transition">
            <input
              className="flex-1 bg-transparent outline-none text-sm placeholder-gray-400"
              value={input}
              onChange={e => setInput(e.target.value)}
              placeholder="Ask a question..."
              onKeyDown={e => e.key === "Enter" && sendMessage()}
            />
            <button
              onClick={sendMessage}
              className="bg-gradient-to-r from-blue-600 to-indigo-600 hover:opacity-90 px-4 py-2 rounded-xl text-sm font-medium transition shadow-lg"
            >
              Send
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}