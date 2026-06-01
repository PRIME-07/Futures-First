import React, { useState } from 'react';
import { useApp } from '../../context/AppContext';
import { Database, FileSpreadsheet, FileText, Plus, Trash2, X, Link, Server, Loader2 } from 'lucide-react';

export default function RightSidebar() {
  const { dataSources, removeDataSource, activeSessionId, apiOnline, fetchSessionConnections, getOrCreateSession } = useApp();
  const [showManageModal, setShowManageModal] = useState(false);
  const [newType, setNewType] = useState('PostgreSQL');

  // File Upload State
  const [selectedFiles, setSelectedFiles] = useState([]);

  // Database Connection State
  const [dbHost, setDbHost] = useState('localhost');
  const [dbPort, setDbPort] = useState('5432');
  const [dbName, setDbName] = useState('');
  const [dbUser, setDbUser] = useState('');
  const [dbPassword, setDbPassword] = useState('');

  // General States
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const isDatabase = newType === 'PostgreSQL' || newType === 'MySQL';

  // Handle Type Change to set default ports automatically
  const handleTypeChange = (type) => {
    setNewType(type);
    setError('');
    if (type === 'PostgreSQL') {
      setDbPort('5432');
    } else if (type === 'MySQL') {
      setDbPort('3306');
    }
  };

  const handleFileChange = (e) => {
    const files = Array.from(e.target.files);
    const validExtensions = ['.csv', '.pdf', '.xlsx', '.xls'];
    const currentFiles = [...selectedFiles];
    let newError = '';

    for (let file of files) {
      const ext = '.' + file.name.split('.').pop().toLowerCase();
      if (!validExtensions.includes(ext)) {
        newError = `Incompatible file format: ${file.name}. Only CSV, PDF, and Excel files are allowed.`;
        continue;
      }
      
      if (currentFiles.some(f => f.name === file.name)) {
        newError = `Duplicate file skipped: ${file.name} is already in the upload list.`;
        continue;
      }

      if (dataSources.some(ds => ds.name === file.name)) {
        newError = `File already connected: ${file.name} is already uploaded to this session.`;
        continue;
      }

      currentFiles.push(file);
    }

    if (newError) {
      setError(newError);
    } else {
      setError('');
    }
    setSelectedFiles(currentFiles);
  };

  const handleAddSource = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    let sessionId = activeSessionId;
    if (!sessionId) {
      const defaultTitle = isDatabase ? `${dbName} Database` : (selectedFiles[0] ? selectedFiles[0].name : 'New Session');
      sessionId = getOrCreateSession(defaultTitle);
    }

    try {
      if (isDatabase) {
        if (!dbHost || !dbPort || !dbName || !dbUser) {
          setError('Please fill in all database connection parameters.');
          setLoading(false);
          return;
        }

        const payload = {
          session_id: sessionId,
          db_type: newType.toLowerCase(),
          host: dbHost,
          port: parseInt(dbPort, 10),
          username: dbUser,
          password: dbPassword,
          database_name: dbName
        };

        const response = await fetch('http://localhost:8000/ingest/connect_db', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        const res = await response.json();
        if (!response.ok || res.status !== 'success') {
          throw new Error(res.detail || res.message || 'Database connection failed.');
        }

      } else {
        if (selectedFiles.length === 0) {
          setError('Please select at least one file to upload.');
          setLoading(false);
          return;
        }

        for (let file of selectedFiles) {
          const formData = new FormData();
          formData.append('file', file);
          formData.append('session_id', sessionId);

          const response = await fetch('http://localhost:8000/ingest/', {
            method: 'POST',
            body: formData
          });

          const res = await response.json();
          if (!response.ok || res.status !== 'success') {
            throw new Error(res.detail || res.message || `Upload failed for ${file.name}`);
          }
        }
      }

      // Success - Refresh Sources List & Reset Fields
      if (fetchSessionConnections) {
        await fetchSessionConnections(sessionId);
      }
      setSelectedFiles([]);
      setDbName('');
      setDbUser('');
      setDbPassword('');
      setShowManageModal(false);
    } catch (err) {
      setError(err.message || 'Action failed.');
    } finally {
      setLoading(false);
    }
  };

  const getSourceIcon = (type) => {
    switch (type) {
      case 'PostgreSQL':
        return <Database size={16} className="text-blue-500" />;
      case 'MySQL':
        return <Database size={16} className="text-sky-500" />;
      case 'Spreadsheet':
      case 'CSV':
      case 'Excel':
        return <FileSpreadsheet size={16} className="text-emerald-500" />;
      case 'PDF':
        return <FileText size={16} className="text-rose-500" />;
      default:
        return <FileText size={16} className="text-orange-500" />;
    }
  };

  return (
    <div className="w-72 min-w-72 h-screen bg-white dark:bg-[#08080a] border-l border-gray-100 dark:border-[#1e2026] text-gray-700 dark:text-gray-300 flex flex-col p-4 shrink-0 font-sans select-none overflow-y-auto transition-all duration-200">
      {/* Container Card */}
      <div className="bg-gray-50 dark:bg-[#0d0e12] border border-gray-100 dark:border-[#1e2026] rounded-xl p-4 flex flex-col gap-4 shadow-lg transition-all duration-200">
        <div className="flex items-center justify-between">
          <span className="font-geist text-sm font-semibold text-gray-900 dark:text-white tracking-wide">Data Sources</span>
          <span className="text-[10px] bg-orange-500/10 text-orange-600 dark:bg-orange-500/15 dark:text-orange-400 px-2 py-0.5 rounded-full font-medium border border-orange-500/10">
            {dataSources.length} Connected
          </span>
        </div>

        {/* Source List */}
        <div className="flex flex-col gap-3 min-h-[250px] overflow-y-auto max-h-[calc(100vh-200px)] scrollbar-none pr-1">
          {dataSources.length === 0 ? (
            <div className="text-xs text-gray-400 dark:text-gray-500 text-center py-10 flex flex-col items-center gap-2">
              <Link size={18} className="text-gray-300 dark:text-gray-600" />
              <span>No data sources connected</span>
            </div>
          ) : (
            dataSources.map((source) => (
              <div
                key={source.id}
                className="group flex items-center justify-between p-2 rounded-lg bg-white dark:bg-[#14151b] border border-gray-100 dark:border-[#1e2026]/50 hover:border-orange-500/20 transition-all"
              >
                <div className="flex items-center gap-3 w-[85%]">
                  <div className="w-8 h-8 rounded-lg bg-gray-50 dark:bg-[#1e2026]/50 flex items-center justify-center shrink-0 border border-gray-100 dark:border-transparent">
                    {getSourceIcon(source.type)}
                  </div>
                  <div className="flex flex-col truncate w-full">
                    <span className="text-xs font-medium text-gray-800 dark:text-gray-200 truncate" title={source.name}>
                      {source.name}
                    </span>
                    <span className="text-[10px] text-gray-400 dark:text-gray-500">
                      {source.type}
                    </span>
                  </div>
                </div>
                <button
                  onClick={() => removeDataSource(source.id)}
                  className="opacity-0 group-hover:opacity-100 p-1 text-gray-400 hover:text-red-500 rounded transition-all cursor-pointer"
                >
                  <Trash2 size={13} />
                </button>
              </div>
            ))
          )}
        </div>

        {/* Manage Sources Button */}
        <button
          onClick={() => setShowManageModal(true)}
          className="w-full py-2 px-4 rounded-lg bg-transparent border border-orange-500/30 text-orange-600 dark:text-orange-400 hover:text-white hover:bg-[#f97316] text-xs font-semibold tracking-wide transition-all cursor-pointer text-center mt-2"
        >
          Manage Sources
        </button>
      </div>

      {/* Modal for Managing Sources */}
      {showManageModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 dark:bg-black/60 backdrop-blur-sm animate-fade-in p-4 overflow-y-auto">
          <div className="bg-white dark:bg-[#0d0e12] border border-gray-100 dark:border-[#1e2026] rounded-xl p-5 w-full max-w-sm flex flex-col gap-4 shadow-2xl my-8">
            <div className="flex items-center justify-between border-b border-gray-100 dark:border-[#1e2026] pb-2.5">
              <span className="font-geist text-sm font-semibold text-gray-900 dark:text-white">Add Data Source</span>
              <button
                onClick={() => {
                  setShowManageModal(false);
                  setError('');
                }}
                className="p-1 hover:bg-gray-100 dark:hover:bg-[#1e2026] rounded text-gray-400 hover:text-gray-900 dark:hover:text-white cursor-pointer"
              >
                <X size={15} />
              </button>
            </div>

            {/* Error Message */}
            {error && (
              <div className="bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-900/30 text-red-600 dark:text-red-400 text-[11px] px-3 py-2 rounded-lg leading-relaxed">
                {error}
              </div>
            )}

            {/* Existing Sources with Quick Delete */}
            <div className="flex flex-col gap-1.5 max-h-24 overflow-y-auto scrollbar-none text-xs">
              <span className="text-[10px] text-gray-400 dark:text-gray-500 uppercase tracking-wide font-medium">Connected</span>
              {dataSources.length === 0 ? (
                <span className="text-[11px] text-gray-400 italic">No sources connected yet.</span>
              ) : (
                dataSources.map((source) => (
                  <div key={source.id} className="flex justify-between items-center p-1.5 bg-gray-50 dark:bg-[#14151b] rounded-md">
                    <span className="truncate max-w-[220px] text-gray-700 dark:text-gray-300" title={source.name}>{source.name}</span>
                    <button onClick={() => removeDataSource(source.id)} className="text-gray-400 dark:text-gray-500 hover:text-red-500 cursor-pointer">
                      <Trash2 size={12} />
                    </button>
                  </div>
                ))
              )}
            </div>

            <form onSubmit={handleAddSource} className="flex flex-col gap-3.5 pt-2 border-t border-gray-100 dark:border-[#1e2026]/40">
              <div className="flex flex-col gap-1">
                <label className="text-[10px] text-gray-400 dark:text-gray-500 uppercase font-medium">Source Type</label>
                <select
                  value={newType}
                  onChange={(e) => handleTypeChange(e.target.value)}
                  className="bg-gray-50 dark:bg-[#14151b] border border-gray-100 dark:border-[#1e2026] rounded-lg px-2.5 py-2 text-xs text-gray-900 dark:text-white focus:outline-none focus:border-orange-500 transition-colors cursor-pointer font-medium"
                >
                  <option value="PostgreSQL">PostgreSQL Database</option>
                  <option value="MySQL">MySQL Database</option>
                  <option value="File">File Upload (CSV, PDF, Excel)</option>
                </select>
              </div>

              {/* Conditional Rendering: DB Connection Credentials vs File Upload */}
              {isDatabase ? (
                <div className="flex flex-col gap-2.5">
                  <div className="grid grid-cols-3 gap-2">
                    <div className="col-span-2 flex flex-col gap-1">
                      <label className="text-[9px] text-gray-400 uppercase font-medium">Host</label>
                      <input
                        type="text"
                        value={dbHost}
                        onChange={(e) => setDbHost(e.target.value)}
                        placeholder="localhost"
                        className="bg-gray-50 dark:bg-[#14151b] border border-gray-100 dark:border-[#1e2026] rounded-lg px-2.5 py-1.5 text-xs text-gray-900 dark:text-white focus:outline-none focus:border-orange-500 transition-colors"
                      />
                    </div>
                    <div className="flex flex-col gap-1">
                      <label className="text-[9px] text-gray-400 uppercase font-medium">Port</label>
                      <input
                        type="number"
                        value={dbPort}
                        onChange={(e) => setDbPort(e.target.value)}
                        placeholder={newType === 'PostgreSQL' ? '5432' : '3306'}
                        className="bg-gray-50 dark:bg-[#14151b] border border-gray-100 dark:border-[#1e2026] rounded-lg px-2 py-1.5 text-xs text-gray-900 dark:text-white focus:outline-none focus:border-orange-500 transition-colors"
                      />
                    </div>
                  </div>

                  <div className="flex flex-col gap-1">
                    <label className="text-[9px] text-gray-400 uppercase font-medium">Database Name</label>
                    <input
                      type="text"
                      value={dbName}
                      onChange={(e) => setDbName(e.target.value)}
                      placeholder="e.g. movies_db"
                      className="bg-gray-50 dark:bg-[#14151b] border border-gray-100 dark:border-[#1e2026] rounded-lg px-2.5 py-1.5 text-xs text-gray-900 dark:text-white focus:outline-none focus:border-orange-500 transition-colors"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <div className="flex flex-col gap-1">
                      <label className="text-[9px] text-gray-400 uppercase font-medium">Username</label>
                      <input
                        type="text"
                        value={dbUser}
                        onChange={(e) => setDbUser(e.target.value)}
                        placeholder="user"
                        className="bg-gray-50 dark:bg-[#14151b] border border-gray-100 dark:border-[#1e2026] rounded-lg px-2.5 py-1.5 text-xs text-gray-900 dark:text-white focus:outline-none focus:border-orange-500 transition-colors"
                      />
                    </div>
                    <div className="flex flex-col gap-1">
                      <label className="text-[9px] text-gray-400 uppercase font-medium">Password</label>
                      <input
                        type="password"
                        value={dbPassword}
                        onChange={(e) => setDbPassword(e.target.value)}
                        placeholder="••••••••"
                        className="bg-gray-50 dark:bg-[#14151b] border border-gray-100 dark:border-[#1e2026] rounded-lg px-2.5 py-1.5 text-xs text-gray-900 dark:text-white focus:outline-none focus:border-orange-500 transition-colors"
                      />
                    </div>
                  </div>
                </div>
              ) : (
                <div className="flex flex-col gap-1">
                  <label className="text-[10px] text-gray-400 dark:text-gray-500 uppercase font-medium">Upload Files</label>
                  <div className="relative border-2 border-dashed border-gray-200 dark:border-[#1e2026] rounded-lg p-4 text-center hover:border-orange-500/50 transition-colors bg-gray-50/50 dark:bg-[#14151b]/50">
                    <input
                      type="file"
                      accept=".csv,.pdf,.xlsx,.xls"
                      multiple
                      onChange={handleFileChange}
                      className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                    />
                    <div className="flex flex-col items-center gap-1">
                      <Plus size={16} className="text-gray-400" />
                      <span className="text-[11px] text-gray-500 dark:text-gray-400 font-medium">
                        Select files (CSV, PDF, Excel)
                      </span>
                      <span className="text-[9px] text-gray-400">
                        Supports multiple uploads at a time
                      </span>
                    </div>
                  </div>
                  {selectedFiles.length > 0 && (
                    <div className="flex flex-col gap-1.5 mt-2 max-h-28 overflow-y-auto scrollbar-none">
                      <span className="text-[9px] text-gray-400 dark:text-gray-500 uppercase tracking-wide font-medium">To Upload</span>
                      {selectedFiles.map((file, idx) => (
                        <div key={idx} className="flex justify-between items-center p-1.5 bg-gray-50 dark:bg-[#14151b] rounded-md text-xs">
                          <span className="truncate max-w-[220px] text-gray-700 dark:text-gray-300" title={file.name}>{file.name}</span>
                          <button
                            type="button"
                            onClick={() => {
                              setSelectedFiles(selectedFiles.filter((_, i) => i !== idx));
                              setError('');
                            }}
                            className="text-gray-400 dark:text-gray-500 hover:text-red-500 cursor-pointer"
                          >
                            <X size={12} />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full py-2 bg-[#f97316] hover:bg-[#ea580c] disabled:bg-gray-400 text-white rounded-lg text-xs font-semibold transition-colors flex items-center justify-center gap-1.5 cursor-pointer mt-1"
              >
                {loading ? (
                  <>
                    <Loader2 size={14} className="animate-spin" />
                    <span>Connecting...</span>
                  </>
                ) : (
                  <>
                    <Plus size={14} />
                    <span>Connect Source</span>
                  </>
                )}
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
