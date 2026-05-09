import React from 'react';
import { useApp } from '../../context/AppContext';
import { FileSpreadsheet, FileText, Database, ShieldCheck, Calendar, Info } from 'lucide-react';

export default function ReportsView() {
  const { theme } = useApp();
  const isDark = theme === 'dark';

  const uploadedReports = [
    { id: 'u_1', name: 'Q2_Sales_Data.xlsx', type: 'Excel Spreadsheet', date: 'May 12, 2024', size: '2.4 MB' },
    { id: 'u_2', name: 'Customer_Insights.csv', type: 'CSV Dataset', date: 'May 11, 2024', size: '1.8 MB' },
    { id: 'u_3', name: 'Product_Manual.pdf', type: 'PDF Document', date: 'May 10, 2024', size: '4.2 MB' },
    { id: 'u_4', name: 'Market_Research.pdf', type: 'PDF Document', date: 'May 08, 2024', size: '3.1 MB' },
    { id: 'u_5', name: 'Sales_Database.sql', type: 'PostgreSQL Database Schema', date: 'May 05, 2024', size: '450 KB' },
    { id: 'u_6', name: 'Marketing_DB.sql', type: 'MySQL Database Schema', date: 'May 03, 2024', size: '280 KB' }
  ];

  const getSourceIcon = (type) => {
    if (type.includes('Excel') || type.includes('CSV')) {
      return <FileSpreadsheet size={18} className="text-emerald-500" />;
    } else if (type.includes('PDF')) {
      return <FileText size={18} className="text-rose-500" />;
    } else {
      return <Database size={18} className="text-blue-500" />;
    }
  };

  return (
    <div className="flex-grow h-screen overflow-y-auto p-6 md:p-12 bg-transparent flex flex-col gap-6 font-sans relative">
      {/* Background Grid Pattern */}
      <div className="absolute inset-0 bg-grid-pattern pointer-events-none -z-10" />

      {/* Header */}
      <div className="flex justify-between items-center border-b border-gray-100 dark:border-[#1e2026] pb-4 shrink-0">
        <div className="flex flex-col gap-1">
          <h2 className="text-xl font-bold font-geist text-gray-900 dark:text-white leading-tight">Uploaded Universal Reports</h2>
          <p className="text-xs text-gray-500">Access the universal data sources and reports uploaded to the Insight Monkey platform.</p>
        </div>
      </div>

      {/* Info Warning */}
      <div className="p-4 rounded-xl border border-blue-500/10 bg-blue-500/2 flex items-start gap-3 max-w-3xl">
        <Info size={16} className="text-blue-500 shrink-0 mt-0.5" />
        <div className="flex flex-col gap-0.5">
          <span className="text-xs font-semibold text-gray-800 dark:text-gray-200">Universal Availability</span>
          <span className="text-[11px] text-gray-500 dark:text-gray-400">These data files are globally mounted across all dynamic workspaces and pipeline queries automatically.</span>
        </div>
      </div>

      {/* Universal Uploads List */}
      <div className="flex flex-col gap-3 max-w-3xl">
        {uploadedReports.map((report) => (
          <div
            key={report.id}
            className={`flex items-center justify-between p-4 rounded-xl border hover:border-orange-500/20 transition-all ${
              isDark ? 'bg-[#0d0e12] border-[#1e2026]' : 'bg-white border-gray-100'
            }`}
          >
            <div className="flex items-center gap-4">
              <div className="w-10 h-10 rounded-lg bg-gray-100 dark:bg-[#14151b] flex items-center justify-center shrink-0 border border-gray-200 dark:border-[#1e2026]/40">
                {getSourceIcon(report.type)}
              </div>
              <div className="flex flex-col gap-0.5">
                <span className="text-sm font-semibold text-gray-800 dark:text-gray-200">{report.name}</span>
                <div className="flex items-center gap-2 text-[10px] text-gray-400">
                  <span className="font-medium text-orange-500/80">{report.type}</span>
                  <span>•</span>
                  <div className="flex items-center gap-1">
                    <Calendar size={10} />
                    <span>{report.date}</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-4">
              <span className="text-xs font-semibold text-gray-400 dark:text-gray-500">{report.size}</span>
              <span className="text-[10px] font-semibold px-2.5 py-0.5 rounded-full bg-green-500/10 text-green-500 flex items-center gap-1 border border-green-500/10">
                <ShieldCheck size={10} />
                <span>Uploaded</span>
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
