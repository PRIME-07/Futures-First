import React from 'react';
import { useApp } from '../../context/AppContext';
import { Plus, MessageSquare, HelpCircle, Trash2 } from 'lucide-react';
import LogoImg from '../../assets/logo.svg';

export default function Sidebar() {
  const {
    sessions,
    activeSessionId,
    selectSession,
    deleteSession,
    handleNewQueryClick,
    sidebarTab,
    setSidebarTab,
  } = useApp();

  return (
    <div className="w-68 min-w-68 h-screen bg-white dark:bg-[#0d0e12] border-r border-gray-100 dark:border-[#1e2026] text-gray-700 dark:text-gray-300 flex flex-col justify-between select-none shrink-0 font-sans transition-all duration-200">
      {/* Top Brand Block */}
      <div className="p-4 flex flex-col gap-5 overflow-y-auto flex-grow scrollbar-none">
        <div className="flex items-center gap-3 px-1">
          <img src={LogoImg} alt="Insight Monkey" className="w-8 h-8 rounded-lg object-cover" />
          <span className="font-geist text-lg font-bold text-gray-900 dark:text-white tracking-tight">Insight Monkey</span>
        </div>

        {/* New Session Button */}
        <button
          onClick={handleNewQueryClick}
          className="w-full py-2.5 px-4 rounded-lg bg-[#f97316] hover:bg-[#ea580c] text-white font-medium flex items-center justify-center gap-2 transition-colors cursor-pointer shadow-md shadow-orange-500/10 hover:shadow-orange-500/25"
        >
          <Plus size={18} />
          <span>New Session</span>
        </button>

        {/* Sidebar Menu Options */}
        <div className="flex flex-col gap-1 text-sm mt-2">
          <button
            onClick={() => setSidebarTab('conversations')}
            className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-all cursor-pointer ${
              sidebarTab === 'conversations' 
                ? 'bg-orange-500/10 text-orange-600 dark:bg-[#1e2026] dark:text-white font-medium' 
                : 'hover:bg-gray-50 dark:hover:bg-[#15161b] text-gray-500 dark:text-gray-400'
            }`}
          >
            <MessageSquare size={16} />
            <span>Conversations</span>
          </button>

          <button
            onClick={() => setSidebarTab('how-to-use')}
            className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-all cursor-pointer ${
              sidebarTab === 'how-to-use' 
                ? 'bg-orange-500/10 text-orange-600 dark:bg-[#1e2026] dark:text-white font-medium' 
                : 'hover:bg-gray-50 dark:hover:bg-[#15161b] text-gray-500 dark:text-gray-400'
            }`}
          >
            <HelpCircle size={16} />
            <span>How To Use?</span>
          </button>
        </div>

        {/* Previous Sessions Divider */}
        <div className="h-[1px] bg-gray-100 dark:bg-[#1e2026] my-2" />

        {/* Previous Sessions Header */}
        <div className="px-1 text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider mb-1">
          Previous Sessions
        </div>

        {/* Previous Sessions List */}
        <div className="flex flex-col gap-1 overflow-y-auto max-h-[calc(100vh-380px)] scrollbar-none pr-1">
          {sessions.length === 0 ? (
            <div className="text-xs text-gray-400 dark:text-gray-500 italic px-3 py-4 text-center">
              No active sessions. Start a new chat to begin exploring!
            </div>
          ) : (
            sessions.map((session) => {
              const isActive = activeSessionId === session.id;
              return (
                <div
                  key={session.id}
                  className={`group flex items-center justify-between px-3 py-2 rounded-lg cursor-pointer transition-all ${
                    isActive 
                      ? 'bg-orange-500/10 text-orange-600 dark:bg-[#1e2026] dark:text-white font-medium' 
                      : 'hover:bg-gray-50 dark:hover:bg-[#15161b] text-gray-600 dark:text-gray-400'
                  }`}
                  onClick={() => selectSession(session.id)}
                >
                  <div className="flex flex-col gap-0.5 truncate pr-2">
                    <div className={`text-sm truncate ${isActive ? 'font-semibold text-orange-600 dark:text-white' : 'text-gray-700 dark:text-gray-300'}`}>
                      {session.title}
                    </div>
                    <div className="text-[10px] text-gray-400 dark:text-gray-500 font-normal">
                      {session.timestamp}
                    </div>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      deleteSession(session.id);
                    }}
                    className="opacity-0 group-hover:opacity-100 p-1 text-gray-400 dark:text-gray-500 hover:text-red-500 rounded transition-opacity cursor-pointer"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Footer Profile Section */}
      <div className="p-4 border-t border-gray-100 dark:border-[#1e2026] bg-gray-50 dark:bg-[#090a0d] flex items-center justify-between text-xs text-gray-400 dark:text-gray-500 transition-all">
        <span className="font-light">Created by <span className="font-semibold text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors">Anuj Mankumare</span></span>
        <div className="flex items-center gap-1">
          <a
            href="https://github.com/PRIME-07/Futures-First"
            target="_blank"
            rel="noreferrer"
            className="p-1.5 text-gray-400 hover:text-blue-600 dark:text-gray-500 dark:hover:text-blue-400 hover:bg-gray-100 dark:hover:bg-[#1e2026] rounded-md transition-all cursor-pointer"
            title="LinkedIn Profile"
          >
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z" />
              <rect x="2" y="9" width="4" height="12" />
              <circle cx="4" cy="4" r="2" />
            </svg>
          </a>
          <a
            href="https://github.com/anujmankumare"
            target="_blank"
            rel="noreferrer"
            className="p-1.5 text-gray-400 hover:text-gray-900 dark:text-gray-500 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-[#1e2026] rounded-md transition-all cursor-pointer"
            title="GitHub Repository"
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4" />
              <path d="M9 18c-4.51 2-5-2-7-2" />
            </svg>
          </a>
        </div>
      </div>
    </div>
  );
}
