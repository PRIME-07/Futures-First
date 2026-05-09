import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { useApp } from '../../context/AppContext';

export default function LineChartComponent({ data, title }) {
  const { theme } = useApp();
  const isDark = theme === 'dark';

  // Format currency value to M / K representation
  const formatYAxisValue = (val) => {
    if (val >= 1000000) return `$${(val / 1000000).toFixed(1)}M`;
    if (val >= 1000) return `$${(val / 1000).toFixed(0)}K`;
    return `$${val}`;
  };

  // Custom formatted tooltip
  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div className={`p-2 rounded-lg border shadow-xl text-xs ${
          isDark 
            ? 'bg-[#0d0e12] border-[#1e2026] text-white' 
            : 'bg-white border-gray-200 text-gray-900'
        }`}>
          <p className="font-semibold">{label}</p>
          <p className="text-[#f97316]">
            Revenue: <span className="font-bold">${payload[0].value.toLocaleString()}</span>
          </p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className={`p-4 rounded-xl border flex flex-col gap-3 h-72 ${
      isDark 
        ? 'bg-[#090a0d] border-[#1e2026] text-white' 
        : 'bg-white border-gray-100 text-gray-800'
    }`}>
      {title && (
        <span className="text-xs font-semibold tracking-wide text-gray-400 uppercase">
          {title}
        </span>
      )}
      <div className="w-full h-full flex-grow text-[10px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={data}
            margin={{ top: 10, right: 10, left: -20, bottom: 5 }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              stroke={isDark ? 'rgba(255, 255, 255, 0.03)' : 'rgba(0, 0, 0, 0.04)'}
              vertical={false}
            />
            <XAxis
              dataKey="name"
              stroke={isDark ? '#52525b' : '#a1a1aa'}
              tickLine={false}
              axisLine={false}
              dy={10}
            />
            <YAxis
              stroke={isDark ? '#52525b' : '#a1a1aa'}
              tickLine={false}
              axisLine={false}
              tickFormatter={formatYAxisValue}
              dx={-5}
            />
            <Tooltip content={<CustomTooltip />} />
            <Line
              type="monotone"
              dataKey="value"
              stroke="#f97316"
              strokeWidth={2}
              dot={{ r: 3, fill: '#f97316', stroke: '#f97316', strokeWidth: 1 }}
              activeDot={{ r: 5, fill: '#ffffff', stroke: '#f97316', strokeWidth: 2 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
