import React from 'react';
import { AppProvider, useApp } from './context/AppContext';
import Sidebar from './components/sidebar/Sidebar';
import RightSidebar from './components/sidebar/RightSidebar';
import MainChat from './components/chat/MainChat';
import ReportsView from './components/views/ReportsView';
import HowToUseView from './components/views/HowToUseView';
import './App.css';

function MainAppContent() {
  const { activeSessionId, sidebarTab } = useApp();

  // Render correct central panel based on active sidebar tab
  const renderCentralPanel = () => {
    switch (sidebarTab) {
      case 'conversations':
        return <MainChat />;
      case 'reports':
        return <ReportsView />;
      case 'how-to-use':
        return <HowToUseView />;
      default:
        return <MainChat />;
    }
  };

  return (
    <div className="w-screen h-screen flex overflow-hidden bg-gray-50 dark:bg-[#08080a] text-gray-900 dark:text-gray-100 transition-colors duration-200">
      {/* Left Sidebar */}
      <Sidebar />

      {/* Main Central Workspace */}
      <div className="flex-grow h-full flex flex-col overflow-hidden">
        {renderCentralPanel()}
      </div>

      {/* Right Sidebar - connected sources list, shown only during active chat and conversations tab */}
      {activeSessionId && sidebarTab === 'conversations' && (
        <RightSidebar />
      )}
    </div>
  );
}

export default function App() {
  return (
    <AppProvider>
      <MainAppContent />
    </AppProvider>
  );
}
