import React, { useState, useRef, useEffect } from 'react';
import { useApp } from '../../context/AppContext';
import { Sun, Moon, Paperclip, Sliders, Send, MoreHorizontal, Server, Terminal, Sparkles } from 'lucide-react';
import LineChartComponent from '../charts/LineChartComponent';
import DynamicChartComponent from '../charts/DynamicChartComponent';
import LogoImg from '../../assets/logo.svg';

const READY_PHRASES = [
  "How can I help you with your data today? ",
  "Ready to dive into your business insights? ",
  "Let's explore your data. What's on your mind?",
  "Ask me anything about your databases or files. ",
  "Which business question are we tackling today? "
];

export default function MainChat() {
  const {
    theme,
    toggleTheme,
    chats,
    activeSessionId,
    isStreaming,
    currentStreamingText,
    currentStreamingEvents,
    sendMessage,
    createSession,
    apiOnline,
    sessions,
    sessionCharts,
  } = useApp();

  const [inputText, setInputText] = useState('');
  const [currentGreeting, setCurrentGreeting] = useState('');
  const chatEndRef = useRef(null);
  const isDark = theme === 'dark';

  // Randomize greeting phrase whenever starting a new chat
  useEffect(() => {
    if (!activeSessionId) {
      const randomPhrase = READY_PHRASES[Math.floor(Math.random() * READY_PHRASES.length)];
      setCurrentGreeting(randomPhrase);
    }
  }, [activeSessionId]);

  // Get current session messages
  const activeMessages = chats[activeSessionId] || [];
  const currentSession = sessions.find((s) => s.id === activeSessionId);
  const sessionTitle = currentSession ? currentSession.title : 'New Query';

  // Auto scroll to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [activeMessages, currentStreamingText]);

  const parseInlineStyles = (text) => {
    if (!text) return '';
    
    // Support streaming unclosed bold asterisks
    let processedText = text;
    const occurrences = (text.match(/\*\*/g) || []).length;
    if (occurrences % 2 !== 0) {
      processedText += '**';
    }

    const parts = processedText.split(/(\*\*[^*]+\*\*)/g);
    return parts.map((part, i) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return (
          <strong key={i} className="font-bold text-gray-950 dark:text-white break-words">
            {part.slice(2, -2)}
          </strong>
        );
      }
      return part;
    });
  };

  const renderFormattedMessage = (text) => {
    if (!text) return null;
    
    // Remove UUID bracket references
    let cleanedText = text.replace(/\[([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})\]/gi, '');
    
    const segments = cleanedText.split(/\r?\n/g);
    
    return (
      <div className="flex flex-col gap-3 leading-relaxed font-sans max-w-full break-words whitespace-pre-wrap overflow-hidden">
        {segments.map((seg, idx) => {
          let line = seg;
          let trimmed = line.trim();
          if (!trimmed && idx > 0 && idx < segments.length - 1) {
            return <div key={idx} className="h-2 shrink-0" />;
          }
          if (!trimmed) return null;
          
          // Headings
          if (trimmed.startsWith('###')) {
            return (
              <h4 key={idx} className="font-geist text-sm font-semibold text-orange-500 mt-2 mb-0.5 break-words">
                {parseInlineStyles(trimmed.replace(/^###\s*/, ''))}
              </h4>
            );
          }
          if (trimmed.startsWith('##')) {
            return (
              <h3 key={idx} className="font-geist text-base font-bold text-gray-950 dark:text-white mt-3 mb-1 break-words">
                {parseInlineStyles(trimmed.replace(/^##\s*/, ''))}
              </h3>
            );
          }
          if (trimmed.startsWith('#')) {
            return (
              <h2 key={idx} className="font-geist text-lg font-extrabold text-gray-950 dark:text-white mt-4 mb-1 break-words">
                {parseInlineStyles(trimmed.replace(/^#\s*/, ''))}
              </h2>
            );
          }
          
          // Horizontal divider
          if (trimmed === '---') {
            return <hr key={idx} className="border-orange-500/20 dark:border-orange-500/15 my-3 shrink-0" />;
          }
          
          // Bullet points
          if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
            return (
              <ul key={idx} className="list-disc pl-5 my-0.5 text-sm text-gray-700 dark:text-gray-300 break-words">
                <li className="font-light">
                  {parseInlineStyles(trimmed.replace(/^[-*]\s*/, ''))}
                </li>
              </ul>
            );
          }
          
          // Paragraphs
          return (
            <p key={idx} className="text-sm text-gray-700 dark:text-gray-300 font-light select-text break-words">
              {parseInlineStyles(line)}
            </p>
          );
        })}
      </div>
    );
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!inputText.trim()) return;

    if (!activeSessionId) {
      // Create new session from landing page
      createSession(inputText);
    } else {
      // Send message to active session
      sendMessage(inputText);
    }
    setInputText('');
  };

  return (
    <div className="flex-grow h-screen flex flex-col bg-transparent font-sans relative">
      {/* Background Grid Pattern */}
      <div className="absolute inset-0 bg-grid-pattern pointer-events-none -z-10" />

      {/* Header */}
      <div className="h-14 px-6 border-b border-orange-500/20 dark:border-orange-500/15 flex items-center justify-between shrink-0 select-none bg-white/40 dark:bg-[#08080a]/40 backdrop-blur-md">
        <div className="flex items-center gap-2">
          {activeSessionId ? (
            <div className="flex items-center gap-1.5 cursor-pointer hover:opacity-80">
              <span className="font-geist text-sm font-semibold text-gray-800 dark:text-white">
                {sessionTitle}
              </span>
              <ChevronDownSmall />
            </div>
          ) : (
            <span className="text-xs font-semibold text-orange-500 uppercase tracking-widest font-geist">
              Insight Workspace
            </span>
          )}
        </div>

        {/* Header Right Actions */}
        <div className="flex items-center gap-4">
          {/* API Connection Indicator */}
          <div className="flex items-center gap-1.5 text-[10px] font-medium px-2 py-0.5 rounded-full bg-gray-100 dark:bg-[#14151b] border border-orange-500/20 dark:border-orange-500/15">
            <Server size={10} className={apiOnline ? 'text-green-500 animate-pulse' : 'text-gray-400'} />
            <span className={apiOnline ? 'text-green-600 dark:text-green-400' : 'text-gray-500'}>
              {apiOnline ? 'Live API Connected' : 'Offline Mode (Mock)'}
            </span>
          </div>

          {/* Theme Toggle Button */}
          <button
            onClick={toggleTheme}
            className="p-1.5 hover:bg-gray-100 dark:hover:bg-[#1e2026] rounded-lg text-gray-500 dark:text-gray-400 hover:text-orange-500 transition-colors cursor-pointer"
            title={isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
          >
            {isDark ? <Sun size={16} /> : <Moon size={16} />}
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-grow overflow-y-auto px-4 md:px-12 py-6 flex flex-col gap-6 scrollbar-none pb-32">
        {activeMessages.length === 0 ? (
          /* ================= LANDING PAGE ================= */
          <div className="flex-grow flex flex-col items-center justify-center w-full max-w-4xl mx-auto text-center gap-6 mt-12 md:mt-24">
            <div className="flex flex-col items-center gap-4">
              <div className="relative">
                <img src={LogoImg} alt="Insight Monkey" className="w-16 h-16 rounded-2xl object-cover border border-orange-500/20 shadow-xl" />
                <span className="absolute -top-1 -right-1 w-3 h-3 bg-orange-500 rounded-full animate-ping" />
                <span className="absolute -top-1 -right-1 w-3 h-3 bg-orange-500 rounded-full" />
              </div>
              <h1 className="font-geist text-2xl md:text-3xl font-extrabold tracking-tight text-gray-900 dark:text-white mt-2 leading-tight px-4">
                {currentGreeting || "How can I help you with your data today? "}
              </h1>
              <p className="text-sm md:text-base text-gray-500 dark:text-gray-400 font-light max-w-md">
                Ask anything about your business data. Insight Monkey will synthesize your metrics instantly.
              </p>
            </div>

            {/* Single Large Landing Chat Input - 70% width */}
            <form onSubmit={handleSubmit} className="w-[70%] mx-auto relative group mt-4">
              <div className="w-full bg-white dark:bg-[#0c0d12]/90 border border-orange-500/20 dark:border-orange-500/15 rounded-2xl px-5 py-3 flex items-center gap-3 shadow-lg hover:border-orange-500/40 dark:hover:border-orange-500/40 transition-all focus-within:ring-2 focus-within:ring-orange-500/10 focus-within:border-orange-500/40">
                <input
                  type="text"
                  value={inputText}
                  onChange={(e) => setInputText(e.target.value)}
                  placeholder="Ask a question..."
                  className="flex-grow bg-transparent border-none text-sm focus:outline-none placeholder-gray-400 text-gray-800 dark:text-white py-1"
                />
                <button
                  type="submit"
                  className="p-2 rounded-xl bg-[#f97316] hover:bg-[#ea580c] text-white transition-all cursor-pointer hover:scale-[1.03] shrink-0"
                >
                  <Send size={15} />
                </button>
              </div>
            </form>
          </div>
        ) : (
          /* ================= ACTIVE CHAT SESSION ================= */
          <div className="max-w-3xl mx-auto w-full flex flex-col gap-6">
            {activeMessages.map((msg) => {
              const isUser = msg.sender === 'user';
              return (
                <div
                  key={msg.id}
                  className={`flex gap-4 p-4 rounded-xl border transition-all ${
                    isUser
                      ? 'bg-transparent border-transparent'
                      : 'bg-white dark:bg-[#0c0d12]/60 border-orange-500/20 dark:border-orange-500/15 shadow-sm'
                  }`}
                >
                  {/* Avatar */}
                  <div className="w-8 h-8 rounded-lg shrink-0 overflow-hidden flex items-center justify-center border border-orange-500/20">
                    {isUser ? (
                      <div className="w-full h-full bg-[#ea580c] text-white font-bold text-xs flex items-center justify-center">
                        J
                      </div>
                    ) : (
                      <img src={LogoImg} alt="Insight Monkey" className="w-full h-full object-cover" />
                    )}
                  </div>

                  {/* Message Content */}
                  <div className="flex-grow flex flex-col gap-2.5 max-w-full overflow-hidden break-words">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-gray-700 dark:text-gray-300">
                        {isUser ? 'You' : 'Insight Monkey'}
                      </span>
                      <span className="text-[10px] text-gray-400">{msg.timestamp}</span>
                    </div>

                    {(() => {
                      if (isUser) {
                        return (
                          <div className="text-sm leading-relaxed text-gray-800 dark:text-gray-200 font-light select-text break-words">
                            {msg.text}
                          </div>
                        );
                      }

                      // Find any charts created during this session that match by UUID, title, or are featured in the latest response
                      const activeSessionCharts = Array.isArray(sessionCharts) ? sessionCharts : [];
                      const bracketRegex = /\[([^\]]+)\]/g;
                      const bracketTerms = [];
                      let match;
                      while ((match = bracketRegex.exec(msg.text)) !== null) {
                        bracketTerms.push(match[1].toLowerCase().trim());
                      }
                      
                      const turnCharts = activeSessionCharts.filter(c => {
                        const chartId = c._id ? c._id.toLowerCase() : '';
                        const chartTitle = c.title ? c.title.toLowerCase() : '';
                        const configX = c.config && c.config.x_key ? c.config.x_key.toLowerCase() : '';
                        
                        return bracketTerms.some(term => 
                           chartId.includes(term) || 
                           chartTitle.includes(term) || 
                           term.includes(chartTitle) ||
                           configX.includes(term)
                        );
                      });

                      // Fallback: if it's the last AI message in the session, and no charts matched yet, show all active session charts so they are guaranteed to be seen!
                      const isLastAiMessage = activeMessages.filter(m => m.sender === 'ai').pop()?.id === msg.id;
                      const chartsToShow = turnCharts.length > 0 
                        ? turnCharts 
                        : (isLastAiMessage ? activeSessionCharts : []);

                      return (
                        <>
                          {/* Display the charts made during that turn on TOP of the bot response */}
                          {chartsToShow.length > 0 && (
                            <div className="flex flex-col gap-4 mb-4 mt-1 max-w-full overflow-hidden">
                              {chartsToShow.map((chart) => (
                                <DynamicChartComponent key={chart._id} chart={chart} />
                              ))}
                            </div>
                          )}

                          <div className="select-text max-w-full overflow-hidden">
                            {renderFormattedMessage(msg.text)}
                          </div>
                        </>
                      );
                    })()}

                    {/* Optional embedded category table */}
                    {msg.table && (
                      <div className="mt-3 overflow-hidden border border-orange-500/20 dark:border-orange-500/15 rounded-lg">
                        <table className="w-full text-left border-collapse text-xs">
                          <thead>
                            <tr className="bg-gray-50 dark:bg-[#14151b] border-b border-orange-500/20 dark:border-orange-500/15 text-gray-500">
                              {msg.table.columns.map((col, idx) => (
                                <th key={idx} className="p-3 font-semibold">{col}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-orange-500/10">
                            {msg.table.rows.map((row, idx) => (
                              <tr
                                key={idx}
                                className="hover:bg-gray-50/50 dark:hover:bg-[#14151b]/25 bg-transparent"
                              >
                                <td className="p-3 text-gray-700 dark:text-gray-300 font-medium">
                                  {row.category}
                                </td>
                                <td className={`p-3 font-semibold ${row.highlight ? 'text-green-500' : 'text-gray-600 dark:text-gray-400'}`}>
                                  {row.growth}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}

            {/* LIVE STREAMING PROGRESS TIMELINE */}
            {isStreaming && (
              <div className="flex flex-col gap-4 p-4 rounded-xl border border-orange-500/25 bg-[#f97316]/5 dark:bg-[#f97316]/2 shadow-md max-w-full overflow-hidden break-words">
                <div className="flex gap-4 max-w-full">
                  <div className="w-8 h-8 rounded-lg shrink-0 overflow-hidden flex items-center justify-center border border-orange-500/30 bg-orange-500/5">
                    <img src={LogoImg} alt="Insight Monkey" className="w-full h-full object-cover animate-pulse" />
                  </div>
                  <div className="flex-grow flex flex-col gap-2 max-w-full overflow-hidden break-words">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-orange-500 flex items-center gap-1.5">
                        <Sparkles size={12} className="animate-spin" />
                        <span>Insight Monkey is thinking...</span>
                      </span>
                    </div>

                    {/* Dynamic Pipeline Logs */}
                    <div className="flex flex-col gap-1.5 py-1 text-[11px] font-mono border-l-2 border-orange-500/25 pl-3 text-gray-400 mt-1 max-w-full overflow-hidden break-words">
                      {currentStreamingEvents.map((evt, idx) => (
                        <div key={idx} className="flex items-center gap-1.5 animate-pulse break-words">
                          <Terminal size={10} className="text-orange-400 shrink-0" />
                          <span className="break-words">{evt.message}</span>
                        </div>
                      ))}
                    </div>

                    {/* Live typed streaming response */}
                    {currentStreamingText && (
                      <div className="select-text mt-1.5 relative max-w-full overflow-hidden break-words">
                        {renderFormattedMessage(currentStreamingText)}
                        <span className="inline-block w-1.5 h-3.5 ml-1 bg-orange-500 animate-pulse shrink-0" />
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            <div ref={chatEndRef} />
          </div>
        )}
      </div>

      {/* Sticky Bottom Chat Input for Active Sessions */}
      {activeSessionId && activeMessages.length > 0 && (
        <div className="absolute bottom-0 left-0 right-0 p-4 md:p-6 bg-gradient-to-t from-gray-50/90 dark:from-[#08080a]/90 via-gray-50/50 dark:via-[#08080a]/50 to-transparent pointer-events-none">
          <div className="w-[70%] mx-auto pointer-events-auto">
            <form onSubmit={handleSubmit} className="relative group">
              <div className="w-full bg-white/80 dark:bg-[#0c0d12]/90 border border-orange-500/20 dark:border-orange-500/15 rounded-xl px-4 py-2 flex items-center gap-3 shadow-lg backdrop-blur-md hover:border-orange-500/40 dark:hover:border-orange-500/40 transition-all focus-within:ring-2 focus-within:ring-orange-500/10 focus-within:border-orange-500/40">
                <input
                  type="text"
                  value={inputText}
                  onChange={(e) => setInputText(e.target.value)}
                  placeholder="Ask anything about your business data..."
                  className="flex-grow bg-transparent border-none text-sm focus:outline-none placeholder-gray-400 text-gray-800 dark:text-white py-1"
                />
                <button
                  type="submit"
                  className="p-1.5 rounded-lg bg-[#f97316] hover:bg-[#ea580c] text-white transition-all cursor-pointer hover:scale-[1.03] shrink-0"
                >
                  <Send size={14} />
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

// Chevron Down Icon
function ChevronDownSmall() {
  return (
    <svg className="w-3 h-3 text-gray-400" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
    </svg>
  );
}
