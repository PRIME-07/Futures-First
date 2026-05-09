import React from 'react';
import { useApp } from '../../context/AppContext';
import { HelpCircle, Database, MessageSquare, LineChart, FileText, ArrowRight } from 'lucide-react';

export default function HowToUseView() {
  const { theme } = useApp();
  const isDark = theme === 'dark';

  const steps = [
    {
      icon: <Database className="text-blue-500" size={18} />,
      title: '1. Connect Your SQL Databases',
      desc: 'Use the "Add Data Source" form in the sidebar to connect PostgreSQL (Movies DB, Automotive DB) or MySQL (Ecommerce DB). The orchestrator automatically introspects table schemas.'
    },
    {
      icon: <FileText className="text-purple-500" size={18} />,
      title: '2. Ingest Spreadsheets & PDFs',
      desc: 'Upload CSV spreadsheets (like marketing_spend.csv) or unstructured PDF documents (like quarterly_report.pdf) directly into your active session.'
    },
    {
      icon: <MessageSquare className="text-orange-500" size={18} />,
      title: '3. Ask Context-Rich Questions',
      desc: 'Ask questions in plain English, e.g., "Which titles performed best according to quarterly_report?" (FAISS PDF RAG) or "Plot a rolling average of marketing spend" (Pandas Tools).'
    },
    {
      icon: <LineChart className="text-green-500" size={18} />,
      title: '4. Visual Analysis & Recharts',
      desc: 'The pipeline runs parallel tools, auto-detects chart types (composed, bar, line), resolves correlations or outlier bounds, and renders interactive graphs instantly.'
    }
  ];

  return (
    <div className="flex-grow h-screen overflow-y-auto p-6 md:p-12 bg-transparent flex flex-col gap-6 font-sans relative">
      {/* Background Grid Pattern */}
      <div className="absolute inset-0 bg-grid-pattern pointer-events-none -z-10" />

      {/* Header */}
      <div className="flex justify-between items-center border-b border-gray-100 dark:border-[#1e2026] pb-4 shrink-0">
        <div className="flex flex-col gap-1">
          <h2 className="text-xl font-bold font-geist text-gray-900 dark:text-white leading-tight">How To Use Insight Monkey?</h2>
          <p className="text-xs text-gray-500">Master the business intelligence platform with this streamlined step-by-step onboarding guide.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-4xl mt-2">
        {steps.map((step, idx) => (
          <div
            key={idx}
            className={`p-5 rounded-xl border flex gap-4 ${
              isDark ? 'bg-[#0d0e12] border-[#1e2026]' : 'bg-white border-gray-100'
            }`}
          >
            <div className="w-10 h-10 rounded-lg bg-orange-500/5 flex items-center justify-center shrink-0 border border-orange-500/10">
              {step.icon}
            </div>
            <div className="flex flex-col gap-1.5">
              <span className="text-sm font-semibold text-gray-800 dark:text-gray-200">{step.title}</span>
              <p className="text-xs leading-relaxed text-gray-500 dark:text-gray-400 font-light">{step.desc}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Try It Call To Action */}
      <div className={`p-6 rounded-xl border flex flex-col md:flex-row items-center justify-between gap-4 max-w-4xl mt-4 ${
        isDark ? 'bg-gradient-to-r from-orange-500/5 to-transparent border-orange-500/10' : 'bg-orange-500/2 border-orange-500/5'
      }`}>
        <div className="flex flex-col gap-1 text-center md:text-left">
          <span className="text-sm font-bold text-gray-800 dark:text-white">Ready to explore your business data?</span>
          <span className="text-xs text-gray-500 font-light">Launch a new query or click one of our pre-populated previous sessions!</span>
        </div>
        <button
          onClick={() => window.location.reload()}
          className="py-2.5 px-4 rounded-lg bg-[#f97316] hover:bg-[#ea580c] text-white text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors cursor-pointer shrink-0"
        >
          <span>Get Started Now</span>
          <ArrowRight size={14} />
        </button>
      </div>
    </div>
  );
}
