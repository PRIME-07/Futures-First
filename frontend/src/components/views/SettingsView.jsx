import React, { useState } from 'react';
import { useApp } from '../../context/AppContext';
import { Settings, User, Sliders, Key, Server, ToggleLeft, ToggleRight, Sun, Moon, Check } from 'lucide-react';

export default function SettingsView() {
  const { theme, toggleTheme, apiOnline } = useApp();
  const isDark = theme === 'dark';
  const [profileName, setProfileName] = useState('John Doe');
  const [profileEmail, setProfileEmail] = useState('john@example.com');
  const [apiKey, setApiKey] = useState('••••••••••••••••••••••••••••••••');
  const [saved, setSaved] = useState(false);

  const handleSave = (e) => {
    e.preventDefault();
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="flex-grow h-screen overflow-y-auto p-6 md:p-12 bg-transparent flex flex-col gap-6 font-sans relative">
      {/* Background Grid Pattern */}
      <div className="absolute inset-0 bg-grid-pattern pointer-events-none -z-10" />

      {/* Header */}
      <div className="flex justify-between items-center border-b border-gray-100 dark:border-[#1e2026] pb-4 shrink-0">
        <div className="flex flex-col gap-1">
          <h2 className="text-xl font-bold font-geist text-gray-900 dark:text-white leading-tight">Platform Settings</h2>
          <p className="text-xs text-gray-500">Configure your profile, connect database settings, and manage security keys.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-4xl mt-2">
        {/* Profile Card */}
        <div className={`p-5 rounded-xl border flex flex-col gap-4 ${isDark ? 'bg-[#0d0e12] border-[#1e2026]' : 'bg-white border-gray-100'}`}>
          <div className="flex items-center gap-2 border-b border-gray-100 dark:border-[#1e2026]/40 pb-2">
            <User size={16} className="text-orange-500" />
            <span className="text-sm font-semibold text-gray-800 dark:text-white">Profile Preferences</span>
          </div>

          <form onSubmit={handleSave} className="flex flex-col gap-3">
            <div className="flex flex-col gap-1 text-xs">
              <label className="text-gray-500 font-medium">Display Name</label>
              <input
                type="text"
                value={profileName}
                onChange={(e) => setProfileName(e.target.value)}
                className="bg-[#14151b] border border-[#1e2026] rounded-lg px-3 py-2 text-white focus:outline-none focus:border-orange-500 transition-colors"
              />
            </div>

            <div className="flex flex-col gap-1 text-xs">
              <label className="text-gray-500 font-medium">Email Address</label>
              <input
                type="email"
                value={profileEmail}
                onChange={(e) => setProfileEmail(e.target.value)}
                className="bg-[#14151b] border border-[#1e2026] rounded-lg px-3 py-2 text-white focus:outline-none focus:border-orange-500 transition-colors"
              />
            </div>

            <button
              type="submit"
              className="py-2 px-4 rounded-lg bg-[#f97316] hover:bg-[#ea580c] text-white text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors cursor-pointer self-start mt-1"
            >
              {saved ? <Check size={14} className="text-white" /> : null}
              <span>{saved ? 'Changes Saved!' : 'Save Changes'}</span>
            </button>
          </form>
        </div>

        {/* Global Settings & Theming */}
        <div className={`p-5 rounded-xl border flex flex-col gap-4 ${isDark ? 'bg-[#0d0e12] border-[#1e2026]' : 'bg-white border-gray-100'}`}>
          <div className="flex items-center gap-2 border-b border-gray-100 dark:border-[#1e2026]/40 pb-2">
            <Sliders size={16} className="text-orange-500" />
            <span className="text-sm font-semibold text-gray-800 dark:text-white">Visual & System Options</span>
          </div>

          <div className="flex flex-col gap-4 text-xs">
            {/* Dark Mode toggle */}
            <div className="flex justify-between items-center py-1">
              <div className="flex flex-col gap-0.5">
                <span className="font-semibold text-gray-800 dark:text-gray-200">Visual Styling Palette</span>
                <span className="text-[10px] text-gray-400">Toggle dark mode or light mode visual systems.</span>
              </div>
              <button
                onClick={toggleTheme}
                className="p-2 hover:bg-[#1e2026] rounded-lg text-orange-500 border border-[#1e2026] flex items-center gap-1.5 cursor-pointer transition-colors"
              >
                {isDark ? <Sun size={14} /> : <Moon size={14} />}
                <span>{isDark ? 'Light' : 'Dark'}</span>
              </button>
            </div>

            <div className="h-[1px] bg-gray-100 dark:bg-[#1e2026]/40 my-1" />

            {/* Connection settings */}
            <div className="flex justify-between items-center py-1">
              <div className="flex flex-col gap-0.5">
                <span className="font-semibold text-gray-800 dark:text-gray-200">Local API Services</span>
                <span className="text-[10px] text-gray-400">Status of connected pipeline routers on local servers.</span>
              </div>
              <span className={`text-[10px] font-semibold px-2.5 py-0.5 rounded-full ${
                apiOnline ? 'bg-green-500/15 text-green-400' : 'bg-gray-500/15 text-gray-400'
              }`}>
                {apiOnline ? 'Online' : 'Offline'}
              </span>
            </div>
          </div>
        </div>

        {/* API Credentials & Keys */}
        <div className={`p-5 rounded-xl border flex flex-col gap-4 md:col-span-2 ${isDark ? 'bg-[#0d0e12] border-[#1e2026]' : 'bg-white border-gray-100'}`}>
          <div className="flex items-center gap-2 border-b border-gray-100 dark:border-[#1e2026]/40 pb-2">
            <Key size={16} className="text-orange-500" />
            <span className="text-sm font-semibold text-gray-800 dark:text-white">API Keys & Security Tokens</span>
          </div>

          <div className="flex flex-col gap-3 text-xs">
            <p className="text-gray-400 font-light text-[11px]">Specify credentials for LLM endpoints and external integration tokens below:</p>
            <div className="flex gap-3">
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                className="bg-[#14151b] border border-[#1e2026] rounded-lg px-3 py-2 text-white focus:outline-none focus:border-orange-500 transition-colors flex-grow text-xs"
              />
              <button
                onClick={() => alert('API Key verified!')}
                className="py-2 px-4 rounded-lg bg-transparent border border-orange-500/20 text-orange-400 hover:bg-[#f97316] hover:text-white transition-all text-xs font-semibold cursor-pointer"
              >
                Update Key
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
