import React from 'react';
import { 
  LineChart, Line, BarChart, Bar, ComposedChart, 
  PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer 
} from 'recharts';
import { useApp } from '../../context/AppContext';

export default function DynamicChartComponent({ chart }) {
  const { theme } = useApp();
  const isDark = theme === 'dark';

  if (!chart || !chart.data || !chart.config) return null;

  const { title, chart_type, config, data } = chart;
  const { x_key, series } = config;

  const CHART_ICONS = { pie: '🥧', line: '📈', bar: '📊', composed: '📉' };
  const chartIcon = CHART_ICONS[chart_type] || '📊';

  const PIE_COLORS = [
    '#f97316', '#3B82F6', '#10B981', '#8B5CF6',
    '#F59E0B', '#EF4444', '#06B6D4', '#84CC16'
  ];

  // Format metric values nicely
  const formatYAxisValue = (val) => {
    if (val === undefined || val === null) return '';
    if (typeof val !== 'number') return val;
    if (val >= 1000000) return `${(val / 1000000).toFixed(1)}M`;
    if (val >= 1000) return `${(val / 1000).toFixed(0)}K`;
    if (val % 1 !== 0) return val.toFixed(2);
    return val;
  };

  // Custom tooltip for cartesian charts
  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div className={`p-3 rounded-xl border shadow-2xl text-xs flex flex-col gap-1.5 ${
          isDark 
            ? 'bg-[#0c0d12]/90 border-orange-500/20 text-white backdrop-blur-md' 
            : 'bg-white/90 border-orange-500/10 text-gray-900 backdrop-blur-md'
        }`}>
          <p className="font-semibold text-gray-500 dark:text-gray-400 mb-0.5">{x_key.replace('_', ' ').toUpperCase()}: {label}</p>
          <div className="flex flex-col gap-1">
            {payload.map((p, idx) => (
              <p key={idx} className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full" style={{ backgroundColor: p.color || '#f97316' }} />
                <span className="font-medium text-gray-600 dark:text-gray-300">{p.name}:</span>
                <span className="font-bold text-gray-900 dark:text-white">{formatYAxisValue(p.value)}</span>
              </p>
            ))}
          </div>
        </div>
      );
    }
    return null;
  };

  // Select the appropriate Chart container and series components
  const renderChart = () => {

    // ── Pie Chart ─────────────────────────────────────────────────────────────
    if (chart_type === 'pie') {
      const total = data.reduce((sum, d) => sum + (d.value || 0), 0);
      const RADIAN = Math.PI / 180;

      const PieLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, value, name }) => {
        const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
        const x = cx + radius * Math.cos(-midAngle * RADIAN);
        const y = cy + radius * Math.sin(-midAngle * RADIAN);
        const pct = total > 0 ? ((value / total) * 100).toFixed(1) : 0;
        // Only render label if slice is big enough
        if (pct < 5) return null;
        return (
          <text x={x} y={y} fill="white" textAnchor="middle" dominantBaseline="central"
            style={{ fontSize: '10px', fontWeight: 700 }}>
            {pct}%
          </text>
        );
      };

      const PieTooltip = ({ active, payload }) => {
        if (active && payload && payload.length) {
          const { name, value } = payload[0];
          const pct = total > 0 ? ((value / total) * 100).toFixed(1) : 0;
          return (
            <div className={`p-3 rounded-xl border shadow-2xl text-xs flex flex-col gap-1 ${
              isDark
                ? 'bg-[#0c0d12]/90 border-orange-500/20 text-white backdrop-blur-md'
                : 'bg-white/90 border-orange-500/10 text-gray-900 backdrop-blur-md'
            }`}>
              <p className="font-semibold text-orange-400">{name}</p>
              <p className="text-gray-300">{formatYAxisValue(value)} <span className="text-orange-400">({pct}%)</span></p>
            </div>
          );
        }
        return null;
      };

      return (
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            outerRadius="75%"
            innerRadius="35%"
            dataKey="value"
            nameKey="name"
            labelLine={false}
            label={<PieLabel />}
            strokeWidth={2}
            stroke={isDark ? '#0c0d12' : '#ffffff'}
          >
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={PIE_COLORS[index % PIE_COLORS.length]} />
            ))}
          </Pie>
          <Tooltip content={<PieTooltip />} />
          <Legend
            verticalAlign="bottom"
            height={36}
            iconType="circle"
            iconSize={8}
            formatter={(value) => <span style={{ fontSize: '10px', color: isDark ? '#a1a1aa' : '#52525b' }}>{value}</span>}
          />
        </PieChart>
      );
    }

    // ── Bar / Line / Composed ─────────────────────────────────────────────────
    const isComposed = chart_type === 'composed' || chart_type === 'composed_outlier';
    if (chart_type === 'bar') {
      return (
        <BarChart data={data} margin={{ top: 10, right: 10, left: -10, bottom: 5 }}>
          <CartesianGrid
            strokeDasharray="3 3"
            stroke={isDark ? 'rgba(255, 255, 255, 0.04)' : 'rgba(0, 0, 0, 0.04)'}
            vertical={false}
          />
          <XAxis
            dataKey={x_key}
            stroke={isDark ? '#52525b' : '#a1a1aa'}
            tickLine={false}
            axisLine={false}
            dy={8}
          />
          <YAxis
            stroke={isDark ? '#52525b' : '#a1a1aa'}
            tickLine={false}
            axisLine={false}
            tickFormatter={formatYAxisValue}
            dx={-5}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend 
            verticalAlign="bottom" 
            height={36} 
            iconType="circle"
            iconSize={8}
            wrapperStyle={{ paddingTop: '10px', fontSize: '10px' }}
          />
          {series.map((s, idx) => (
            <Bar
              key={idx}
              dataKey={s.y_key}
              name={s.label}
              fill={s.color || '#f97316'}
              radius={[4, 4, 0, 0]}
            />
          ))}
        </BarChart>
      );
    }

    if (chart_type === 'line') {
      return (
        <LineChart data={data} margin={{ top: 10, right: 10, left: -10, bottom: 5 }}>
          <CartesianGrid
            strokeDasharray="3 3"
            stroke={isDark ? 'rgba(255, 255, 255, 0.04)' : 'rgba(0, 0, 0, 0.04)'}
            vertical={false}
          />
          <XAxis
            dataKey={x_key}
            stroke={isDark ? '#52525b' : '#a1a1aa'}
            tickLine={false}
            axisLine={false}
            dy={8}
          />
          <YAxis
            stroke={isDark ? '#52525b' : '#a1a1aa'}
            tickLine={false}
            axisLine={false}
            tickFormatter={formatYAxisValue}
            dx={-5}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend 
            verticalAlign="bottom" 
            height={36} 
            iconType="circle"
            iconSize={8}
            wrapperStyle={{ paddingTop: '10px', fontSize: '10px' }}
          />
          {series.map((s, idx) => (
            <Line
              key={idx}
              type="monotone"
              dataKey={s.y_key}
              name={s.label}
              stroke={s.color || '#f97316'}
              strokeWidth={2}
              dot={{ r: 3, fill: s.color || '#f97316', stroke: s.color || '#f97316' }}
              activeDot={{ r: 5, fill: '#ffffff', stroke: s.color || '#f97316', strokeWidth: 2 }}
            />
          ))}
        </LineChart>
      );
    }

    // Default to ComposedChart which handles both mixed graphs and IQRs beautifully
    const hasDualAxes = series.some(s => s.yAxisId === 'right');
    return (
      <ComposedChart data={data} margin={{ top: 10, right: hasDualAxes ? 25 : 10, left: -10, bottom: 5 }}>
        <CartesianGrid
          strokeDasharray="3 3"
          stroke={isDark ? 'rgba(255, 255, 255, 0.04)' : 'rgba(0, 0, 0, 0.04)'}
          vertical={false}
        />
        <XAxis
          dataKey={x_key}
          stroke={isDark ? '#52525b' : '#a1a1aa'}
          tickLine={false}
          axisLine={false}
          dy={8}
        />
        <YAxis
          yAxisId="left"
          stroke={isDark ? '#52525b' : '#a1a1aa'}
          tickLine={false}
          axisLine={false}
          tickFormatter={formatYAxisValue}
          dx={-5}
        />
        {hasDualAxes && (
          <YAxis
            yAxisId="right"
            orientation="right"
            stroke={isDark ? '#52525b' : '#a1a1aa'}
            tickLine={false}
            axisLine={false}
            tickFormatter={formatYAxisValue}
            dx={5}
          />
        )}
        <Tooltip content={<CustomTooltip />} />
        <Legend 
          verticalAlign="bottom" 
          height={36} 
          iconType="circle"
          iconSize={8}
          wrapperStyle={{ paddingTop: '10px', fontSize: '10px' }}
        />
        {series.map((s, idx) => {
          if (s.type === 'bar') {
            return (
              <Bar
                key={idx}
                yAxisId={s.yAxisId || "left"}
                dataKey={s.y_key}
                name={s.label}
                fill={s.color || '#3B82F6'}
                radius={[4, 4, 0, 0]}
              />
            );
          }
          return (
            <Line
              key={idx}
              yAxisId={s.yAxisId || "left"}
              type="monotone"
              dataKey={s.y_key}
              name={s.label}
              stroke={s.color || '#EF4444'}
              strokeWidth={2}
              strokeDasharray={s.strokeDasharray}
              dot={s.strokeDasharray ? false : { r: 3, fill: s.color || '#EF4444' }}
              activeDot={s.strokeDasharray ? false : { r: 5, fill: '#ffffff', stroke: s.color || '#EF4444', strokeWidth: 2 }}
            />
          );
        })}
      </ComposedChart>
    );
  };

  return (
    <div className={`p-4 rounded-xl border border-orange-500/15 flex flex-col gap-3 h-72 ${
      isDark 
        ? 'bg-[#090a0d] text-white shadow-lg' 
        : 'bg-white text-gray-800 shadow-md'
    }`}>
      {title && (
        <span className="text-xs font-semibold tracking-wide text-orange-500 uppercase font-geist">
          {chartIcon} {title}
        </span>
      )}
      <div className="w-full h-full flex-grow text-[10px] font-sans">
        <ResponsiveContainer width="100%" height="100%">
          {renderChart()}
        </ResponsiveContainer>
      </div>
    </div>
  );
}
