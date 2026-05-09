import React, { createContext, useContext, useState, useEffect } from 'react';

const AppContext = createContext();

export const useApp = () => useContext(AppContext);

// Prefilled sessions list matching the screenshot
const DEFAULT_SESSIONS = [
  { id: 'q2_revenue_analysis', title: 'Q2 Revenue Analysis', timestamp: 'May 12, 2024 • 2:30 PM' },
  { id: 'marketing_performance', title: 'Marketing Performance Review', timestamp: 'May 11, 2024 • 4:15 PM' },
  { id: 'customer_churn', title: 'Customer Churn Insights', timestamp: 'May 10, 2024 • 11:20 AM' },
  { id: 'sales_trend', title: 'Sales Trend Analysis', timestamp: 'May 9, 2024 • 9:45 AM' },
  { id: 'product_analytics', title: 'Product Analytics Overview', timestamp: 'May 8, 2024 • 3:05 PM' },
  { id: 'operational_efficiency', title: 'Operational Efficiency Report', timestamp: 'May 7, 2024 • 10:10 AM' },
  { id: 'financial_summary', title: 'Financial Summary Q1', timestamp: 'May 6, 2024 • 1:25 PM' },
  { id: 'supply_chain', title: 'Supply Chain Analysis', timestamp: 'May 5, 2024 • 5:50 PM' },
];

const REVENUE_CHART_DATA = [
  { name: 'May', value: 1000000 },
  { name: 'Jun', value: 850000 },
  { name: 'Jul', value: 1000000 },
  { name: 'Aug', value: 750000 },
  { name: 'Sep', value: 1150000 },
  { name: 'Oct', value: 1050000 },
  { name: 'Nov', value: 1500000 },
  { name: 'Dec', value: 1200000 },
  { name: 'Jan', value: 1500000 },
  { name: 'Feb', value: 1450000 },
  { name: 'Mar', value: 1850000 },
];

const CATEGORY_GROWTH_TABLE = [
  { category: 'Electronics', growth: '18.7%', highlight: true },
  { category: 'Home & Kitchen', growth: '12.3%', highlight: false },
  { category: 'Apparel', growth: '7.8%', highlight: false },
  { category: 'Beauty', growth: '5.1%', highlight: false },
  { category: 'Others', growth: '2.4%', highlight: false },
];

// Default messages for the 'Q2 Revenue Analysis' session matching screenshot
const DEFAULT_CHATS = {
  q2_revenue_analysis: [
    {
      id: 'msg_1',
      sender: 'user',
      text: 'Show me the total revenue trend over time for the last 12 months.',
      timestamp: '10:15 AM'
    },
    {
      id: 'msg_2',
      sender: 'ai',
      text: 'Here is the total revenue trend over the last 12 months.',
      timestamp: '10:15 AM',
      chart: {
        type: 'line',
        title: 'Total Revenue Over Time',
        data: REVENUE_CHART_DATA
      }
    },
    {
      id: 'msg_3',
      sender: 'user',
      text: 'Which product category had the highest growth in Q2?',
      timestamp: '10:18 AM'
    },
    {
      id: 'msg_4',
      sender: 'ai',
      text: 'The Electronics category had the highest growth in Q2 with 18.7% increase.',
      timestamp: '10:18 AM',
      table: {
        columns: ['Category', 'Growth (Q2)'],
        rows: CATEGORY_GROWTH_TABLE
      }
    }
  ]
};

// Default data sources for the session
const DEFAULT_DATA_SOURCES = {
  q2_revenue_analysis: [
    { id: 'src_1', name: 'Sales Database', type: 'PostgreSQL' },
    { id: 'src_2', name: 'Marketing DB', type: 'MySQL' },
    { id: 'src_3', name: 'Q2_Sales_Data.xlsx', type: 'Spreadsheet' },
    { id: 'src_4', name: 'Customer_Insights.csv', type: 'Spreadsheet' },
    { id: 'src_5', name: 'Product_Manual.pdf', type: 'PDF' },
    { id: 'src_6', name: 'Market_Research.pdf', type: 'PDF' },
  ]
};

export const AppProvider = ({ children }) => {
  const [theme, setTheme] = useState(() => localStorage.getItem('theme') || 'dark');
  const [sessions, setSessions] = useState([]);
  const [chats, setChats] = useState({});
  const [dataSources, setDataSources] = useState({});
  const [sessionCharts, setSessionCharts] = useState({});
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentStreamingText, setCurrentStreamingText] = useState('');
  const [currentStreamingEvents, setCurrentStreamingEvents] = useState([]); // SSE event logs
  const [sidebarTab, setSidebarTab] = useState('conversations'); // conversations, reports, settings
  const [apiOnline, setApiOnline] = useState(false);

  // Sync theme with DOM and localStorage
  useEffect(() => {
    localStorage.setItem('theme', theme);
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [theme]);

  // Check backend health on mount
  useEffect(() => {
    fetch('http://localhost:8000/health')
      .then(res => res.json())
      .then(data => {
        if (data.status === 'ok') setApiOnline(true);
      })
      .catch(() => setApiOnline(false));
  }, []);

  const fetchSessions = () => {
    if (apiOnline) {
      fetch('http://localhost:8000/ingest/sessions')
        .then(res => res.json())
        .then(res => {
          if (res.status === 'success' && res.data) {
            const fetchedSessions = res.data.map(s => ({
              id: s.session_id,
              title: s.session_id,
              timestamp: `Mounted Sources: ${s.dataset_count + s.pdf_count + s.connection_count}`
            }));
            setSessions(fetchedSessions);
          }
        })
        .catch(err => console.error('Error fetching backend sessions:', err));
    } else {
      setSessions([]);
    }
  };

  useEffect(() => {
    fetchSessions();
  }, [apiOnline]);

  const fetchSessionChats = async (sessionId) => {
    if (apiOnline && sessionId) {
      try {
        const response = await fetch(`http://localhost:8000/stream/sessions/${sessionId}/chats`);
        const res = await response.json();
        if (res.status === 'success' && res.data) {
          const formattedChats = [];
          res.data.forEach((c, idx) => {
            const timeStr = c.timestamp ? new Date(c.timestamp).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' }) : '';
            if (c.query) {
              formattedChats.push({
                id: `${c._id || idx}_user`,
                sender: 'user',
                text: c.query,
                timestamp: timeStr
              });
            }
            if (c.answer) {
              formattedChats.push({
                id: `${c._id || idx}_ai`,
                sender: 'ai',
                text: c.answer,
                timestamp: timeStr
              });
            }
          });
          setChats(prev => ({
            ...prev,
            [sessionId]: formattedChats
          }));
        }
      } catch (err) {
        console.error(`Error fetching chats for session ${sessionId}:`, err);
      }
    }
  };

  const fetchSessionConnections = async (sessionId) => {
    if (apiOnline && sessionId) {
      try {
        const response = await fetch(`http://localhost:8000/ingest/sessions/${sessionId}/sources`);
        const res = await response.json();
        if (res.status === 'success' && res.data) {
          const formattedSources = [];
          
          // 1. Add SQL Connections
          if (res.data.sql_connections && res.data.sql_connections.length > 0) {
            res.data.sql_connections.forEach(conn => {
              let dbType = 'PostgreSQL';
              if (conn.db_type?.toLowerCase() === 'mysql') dbType = 'MySQL';
              else if (conn.db_type?.toLowerCase() === 'sqlite') dbType = 'SQLite';
              
              formattedSources.push({
                id: conn.connection_id,
                name: conn.database_name || 'Database Connection',
                type: dbType
              });
            });
          }
          
          // 2. Add Datasets (CSV/Excel)
          if (res.data.datasets && res.data.datasets.length > 0) {
            res.data.datasets.forEach(ds => {
              if (ds.source_type !== 'database') {
                const isExcel = ds.dataset_name?.endsWith('.xlsx') || ds.dataset_name?.endsWith('.xls') || ds.original_filename?.endsWith('.xlsx') || ds.original_filename?.endsWith('.xls');
                formattedSources.push({
                  id: ds.dataset_uuid,
                  name: ds.dataset_name || ds.original_filename,
                  type: isExcel ? 'Excel' : 'CSV'
                });
              } else {
                formattedSources.push({
                  id: ds.dataset_uuid,
                  name: `${ds.dataset_name} (Table)`,
                  type: ds.external_db_type?.toLowerCase() === 'mysql' ? 'MySQL' : (ds.external_db_type?.toLowerCase() === 'sqlite' ? 'SQLite' : 'PostgreSQL')
                });
              }
            });
          }
          
          // 3. Add PDFs
          if (res.data.pdfs && res.data.pdfs.length > 0) {
            res.data.pdfs.forEach(pdf => {
              formattedSources.push({
                id: pdf._id,
                name: pdf.filename,
                type: 'PDF'
              });
            });
          }

          setDataSources(prev => ({
            ...prev,
            [sessionId]: formattedSources
          }));
        }
      } catch (err) {
        console.error(`Error fetching sources for session ${sessionId}:`, err);
      }
    }
  };

  const fetchSessionChartsData = async (sessionId) => {
    if (apiOnline && sessionId) {
      try {
        const response = await fetch(`http://localhost:8000/analytics/sessions/${sessionId}/charts`);
        const res = await response.json();
        if (res.status === 'success' && res.data) {
          setSessionCharts(prev => ({
            ...prev,
            [sessionId]: res.data
          }));
        }
      } catch (err) {
        console.error(`Error fetching charts for session ${sessionId}:`, err);
      }
    }
  };

  useEffect(() => {
    if (activeSessionId) {
      fetchSessionChats(activeSessionId);
      fetchSessionConnections(activeSessionId);
      fetchSessionChartsData(activeSessionId);
    }
  }, [activeSessionId, apiOnline]);

  const toggleTheme = () => {
    setTheme(prev => (prev === 'dark' ? 'light' : 'dark'));
  };

  const createSession = (initialQuery) => {
    const newId = `session_${Date.now()}`;
    const timestamp = new Date().toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    }) + ' • ' + new Date().toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
    });

    const newSession = {
      id: newId,
      title: initialQuery.length > 25 ? initialQuery.substring(0, 25) + '...' : initialQuery,
      timestamp,
    };

    setSessions(prev => [newSession, ...prev]);
    setChats(prev => ({
      ...prev,
      [newId]: [
        {
          id: `msg_user_${Date.now()}`,
          sender: 'user',
          text: initialQuery,
          timestamp: new Date().toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' }),
        }
      ]
    }));

    // Pre-populate some data sources for new sessions so they aren't empty
    setDataSources(prev => ({
      ...prev,
      [newId]: [
        { id: `src_pg_${Date.now()}`, name: 'Sales Database', type: 'PostgreSQL' },
        { id: `src_csv_${Date.now()}`, name: 'Customer_Insights.csv', type: 'Spreadsheet' }
      ]
    }));

    setActiveSessionId(newId);
    simulateAiResponse(newId, initialQuery);
    return newId;
  };

  const simulateAiResponse = (sessionId, query) => {
    setIsStreaming(true);
    setCurrentStreamingText('');
    setCurrentStreamingEvents([
      { type: 'pipeline_start', message: 'Starting analysis pipeline...' }
    ]);

    setTimeout(() => {
      setCurrentStreamingEvents(prev => [
        ...prev,
        { type: 'orchestration_start', message: 'Analyzing query and routing to tools...' }
      ]);
    }, 1000);

    setTimeout(() => {
      setCurrentStreamingEvents(prev => [
        ...prev,
        { type: 'chart_agent_start', message: 'Generating visual chart configurations...' }
      ]);
    }, 2000);

    setTimeout(() => {
      setCurrentStreamingEvents(prev => [
        ...prev,
        { type: 'synthesis_start', message: 'Synthesizing final insights...' }
      ]);
    }, 3200);

    // Simulated Response Stream
    const answer = `Based on the active data sources, here is the simulated analytical breakdown for your query: "${query}". We detected steady growth trends and can verify these via automated charts below. Let me know if you would like me to compile this into a formal report.`;
    let index = 0;

    setTimeout(() => {
      const interval = setInterval(() => {
        if (index < answer.length) {
          setCurrentStreamingText(prev => prev + answer.charAt(index));
          index++;
        } else {
          clearInterval(interval);
          setIsStreaming(false);

          // Add final message
          setChats(prev => {
            const currentChats = prev[sessionId] || [];
            return {
              ...prev,
              [sessionId]: [
                ...currentChats,
                {
                  id: `msg_ai_${Date.now()}`,
                  sender: 'ai',
                  text: answer,
                  timestamp: new Date().toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' }),
                  chart: query.toLowerCase().includes('chart') || query.toLowerCase().includes('graph') || query.toLowerCase().includes('trend') ? {
                    type: 'line',
                    title: 'Calculated Analytics Trend',
                    data: [
                      { name: 'Q1', value: 400000 },
                      { name: 'Q2', value: 800000 },
                      { name: 'Q3', value: 600000 },
                      { name: 'Q4', value: 1200000 }
                    ]
                  } : null
                }
              ]
            };
          });
          setCurrentStreamingText('');
          setCurrentStreamingEvents([]);
        }
      }, 15);
    }, 4000);
  };

  const sendMessage = async (text) => {
    if (!text.trim() || !activeSessionId) return;

    const userMsg = {
      id: `msg_user_${Date.now()}`,
      sender: 'user',
      text,
      timestamp: new Date().toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' }),
    };

    setChats(prev => ({
      ...prev,
      [activeSessionId]: [...(prev[activeSessionId] || []), userMsg]
    }));

    if (apiOnline) {
      // Connect with actual streaming FastAPI backend
      setIsStreaming(true);
      setCurrentStreamingText('');
      setCurrentStreamingEvents([]);

      try {
        const response = await fetch('http://localhost:8000/stream/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ session_id: activeSessionId, query: text })
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const parts = buffer.split('\n\n');
          buffer = parts.pop(); // keep last incomplete chunk

          for (const part of parts) {
            if (part.startsWith('event: ')) {
              const lines = part.split('\n');
              const eventType = lines[0].replace('event: ', '').trim();
              const dataStr = lines[1]?.replace('data: ', '').trim();
              
              if (dataStr) {
                try {
                  const data = JSON.parse(dataStr);
                  
                  if (eventType === 'token') {
                    setCurrentStreamingText(prev => prev + data.token);
                  } else if (eventType === 'response_complete') {
                    setChats(prev => ({
                      ...prev,
                      [activeSessionId]: [
                        ...(prev[activeSessionId] || []),
                        {
                          id: `msg_ai_${Date.now()}`,
                          sender: 'ai',
                          text: data.answer,
                          timestamp: new Date().toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' }),
                        }
                      ]
                    }));
                    fetchSessionChartsData(activeSessionId);
                  } else {
                    // Pipeline stages
                    setCurrentStreamingEvents(prev => [...prev, { type: eventType, message: data.message || JSON.stringify(data) }]);
                  }
                } catch (e) {
                  console.error('Error parsing SSE data:', e);
                }
              }
            }
          }
        }
        setIsStreaming(false);
        setCurrentStreamingText('');
        setCurrentStreamingEvents([]);
      } catch (err) {
        console.error('API Stream failed, falling back to simulation', err);
        simulateAiResponse(activeSessionId, text);
      }
    } else {
      simulateAiResponse(activeSessionId, text);
    }
  };

  const addDataSource = (source) => {
    if (!activeSessionId) return;
    const newSource = {
      id: `src_${Date.now()}`,
      ...source
    };
    setDataSources(prev => ({
      ...prev,
      [activeSessionId]: [...(prev[activeSessionId] || []), newSource]
    }));
  };

  const removeDataSource = async (sourceId) => {
    if (!activeSessionId) return;

    const currentSources = dataSources[activeSessionId] || [];
    const sourceToDelete = currentSources.find(s => s.id === sourceId);

    if (apiOnline && sourceToDelete) {
      try {
        const isDbConnection = (sourceToDelete.type === 'PostgreSQL' || sourceToDelete.type === 'MySQL') && !sourceToDelete.name.endsWith('(Table)');
        
        if (isDbConnection) {
          await fetch(`http://localhost:8000/ingest/sessions/${activeSessionId}/connections/${sourceId}`, {
            method: 'DELETE'
          });
        } else {
          await fetch(`http://localhost:8000/ingest/sessions/${activeSessionId}/files/${encodeURIComponent(sourceId)}`, {
            method: 'DELETE'
          });
        }
      } catch (err) {
        console.error('Failed to delete source from backend:', err);
      }
    }

    setDataSources(prev => ({
      ...prev,
      [activeSessionId]: (prev[activeSessionId] || []).filter(s => s.id !== sourceId)
    }));
  };

  const selectSession = (id) => {
    setActiveSessionId(id);
  };

  const deleteSession = (id) => {
    setSessions(prev => prev.filter(s => s.id !== id));
    setChats(prev => {
      const copy = { ...prev };
      delete copy[id];
      return copy;
    });
    if (activeSessionId === id) {
      setActiveSessionId(null);
    }
  };

  const handleNewQueryClick = () => {
    setActiveSessionId(null);
  };

  return (
    <AppContext.Provider value={{
      theme,
      toggleTheme,
      sessions,
      chats,
      dataSources: dataSources[activeSessionId] || [],
      activeSessionId,
      isStreaming,
      currentStreamingText,
      currentStreamingEvents,
      sidebarTab,
      setSidebarTab,
      apiOnline,
      createSession,
      sendMessage,
      addDataSource,
      removeDataSource,
      selectSession,
      deleteSession,
      handleNewQueryClick,
      sessionCharts: sessionCharts[activeSessionId] || [],
      fetchSessionChartsData,
      fetchSessions,
      fetchSessionChats,
      fetchSessionConnections,
    }}>
      {children}
    </AppContext.Provider>
  );
};
