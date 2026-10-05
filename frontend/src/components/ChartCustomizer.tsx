import React, { useState, useEffect, useMemo } from 'react';
import createPlotComponent from 'react-plotly.js/factory';
import Plotly from 'plotly.js-dist-min';
import { Sliders, RotateCcw } from 'lucide-react';
import { ChartSpec } from '../types/analytics';

const Plot = createPlotComponent(Plotly);

interface ChartCustomizerProps {
  results: Record<string, any>[];
  defaultSpec?: ChartSpec | null;
  onExport?: () => void;
}

type ChartType = 'hbar' | 'vbar' | 'line' | 'area' | 'donut' | 'pie' | 'scatter';
type AggregationType = 'none' | 'avg' | 'sum' | 'count' | 'min' | 'max';
type AxisScale = 'linear' | 'log';
type SortOrder = 'none' | 'desc' | 'asc';

export const ChartCustomizer: React.FC<ChartCustomizerProps> = ({
  results = [],
  defaultSpec,
}) => {
  // Extract all available columns from actual verified results
  const availableColumns = useMemo(() => {
    if (!results || results.length === 0) return [];
    return Object.keys(results[0]);
  }, [results]);

  // Extract only numeric columns for Y-axis / Value
  const numericColumns = useMemo(() => {
    if (!results || results.length === 0) return [];
    return Object.keys(results[0]).filter((col) => {
      const val = results[0][col];
      return typeof val === 'number' || (!isNaN(Number(val)) && val !== null && val !== '');
    });
  }, [results]);

  // Initial defaults based on backend spec or first columns
  const initialX = defaultSpec?.x_column || availableColumns[0] || 'diagnosis';
  const initialY = defaultSpec?.y_column || numericColumns[0] || availableColumns[1] || 'average_length_of_stay';
  const initialTitle = defaultSpec?.title || 'Average Length of Stay by Diagnosis';

  const [chartType, setChartType] = useState<ChartType>('hbar');
  const [xColumn, setXColumn] = useState<string>(initialX);
  const [yColumn, setYColumn] = useState<string>(initialY);
  const [title, setTitle] = useState<string>(initialTitle);
  const [aggregation, setAggregation] = useState<AggregationType>('none');
  const [axisScale, setAxisScale] = useState<AxisScale>('linear');
  const [sortOrder, setSortOrder] = useState<SortOrder>('none');

  useEffect(() => {
    if (defaultSpec?.x_column && availableColumns.includes(defaultSpec.x_column)) {
      setXColumn(defaultSpec.x_column);
    } else if (availableColumns.length > 0) {
      setXColumn(availableColumns[0]);
    }

    if (defaultSpec?.y_column && numericColumns.includes(defaultSpec.y_column)) {
      setYColumn(defaultSpec.y_column);
    } else if (numericColumns.length > 0) {
      setYColumn(numericColumns[0]);
    }

    if (defaultSpec?.title) {
      setTitle(defaultSpec.title);
    }
  }, [defaultSpec, availableColumns, numericColumns]);

  const handleReset = () => {
    setChartType('hbar');
    setXColumn(initialX);
    setYColumn(initialY);
    setTitle(initialTitle);
    setAggregation('none');
    setAxisScale('linear');
    setSortOrder('none');
  };

  // Process data with aggregation & sorting
  const { categories, values } = useMemo(() => {
    if (!results || results.length === 0 || !xColumn) {
      return { categories: [], values: [] };
    }

    let processedItems: Array<{ cat: string; val: number }> = [];

    if (aggregation === 'none') {
      processedItems = results.map((r) => ({
        cat: String(r[xColumn] ?? ''),
        val: Number(r[yColumn]) || 0,
      }));
    } else {
      // Group by X Column
      const grouped: Record<string, number[]> = {};
      results.forEach((r) => {
        const cat = String(r[xColumn] ?? '');
        const val = Number(r[yColumn]) || 0;
        if (!grouped[cat]) grouped[cat] = [];
        grouped[cat].push(val);
      });

      const cats = Object.keys(grouped);
      processedItems = cats.map((cat) => {
        const list = grouped[cat];
        let val = 0;
        if (aggregation === 'sum') val = list.reduce((a, b) => a + b, 0);
        else if (aggregation === 'count') val = list.length;
        else if (aggregation === 'min') val = Math.min(...list);
        else if (aggregation === 'max') val = Math.max(...list);
        else val = list.reduce((a, b) => a + b, 0) / (list.length || 1); // avg
        return { cat, val };
      });
    }

    // Apply Sorting
    if (sortOrder === 'desc') {
      processedItems.sort((a, b) => b.val - a.val);
    } else if (sortOrder === 'asc') {
      processedItems.sort((a, b) => a.val - b.val);
    }

    const cats = processedItems.map((item) => item.cat);
    const vals = processedItems.map((item) => {
      if (axisScale === 'log' && item.val <= 0) {
        return 0.01;
      }
      return item.val;
    });

    return { categories: cats, values: vals };
  }, [results, xColumn, yColumn, aggregation, sortOrder, axisScale]);

  // Construct Plotly trace based on chartType
  const plotlyData = useMemo(() => {
    const primaryColor = '#4F46E5';
    const pieColorPalette = [
      '#4F46E5', '#38BDF8', '#10B981', '#F59E0B', '#EC4899', '#8B5CF6', '#14B8A6'
    ];

    if (chartType === 'hbar') {
      return [
        {
          type: 'bar',
          orientation: 'h',
          y: categories,
          x: values,
          marker: { color: primaryColor, opacity: 0.9 },
          text: values.map((v) => `${typeof v === 'number' ? (v >= 10 ? v.toFixed(0) : v.toFixed(1)) : v}`),
          textposition: 'auto',
          hoverinfo: 'x+y',
        },
      ];
    }

    if (chartType === 'vbar') {
      return [
        {
          type: 'bar',
          x: categories,
          y: values,
          marker: { color: primaryColor, opacity: 0.9 },
          text: values.map((v) => `${typeof v === 'number' ? (v >= 10 ? v.toFixed(0) : v.toFixed(1)) : v}`),
          textposition: 'auto',
          hoverinfo: 'x+y',
        },
      ];
    }

    if (chartType === 'line') {
      return [
        {
          type: 'scatter',
          mode: 'lines+markers',
          x: categories,
          y: values,
          line: { color: primaryColor, width: 3, shape: 'spline' },
          marker: { size: 6, color: '#312E81' },
          hoverinfo: 'x+y',
        },
      ];
    }

    if (chartType === 'area') {
      return [
        {
          type: 'scatter',
          mode: 'lines',
          fill: 'tozeroy',
          fillcolor: 'rgba(79, 70, 229, 0.18)',
          x: categories,
          y: values,
          line: { color: primaryColor, width: 2.5, shape: 'spline' },
          hoverinfo: 'x+y',
        },
      ];
    }

    if (chartType === 'donut') {
      return [
        {
          type: 'pie',
          hole: 0.6,
          labels: categories,
          values: values,
          marker: { colors: pieColorPalette },
          textinfo: 'percent',
          hoverinfo: 'label+value+percent',
        },
      ];
    }

    if (chartType === 'pie') {
      return [
        {
          type: 'pie',
          labels: categories,
          values: values,
          marker: { colors: pieColorPalette },
          textinfo: 'percent',
          hoverinfo: 'label+value+percent',
        },
      ];
    }

    // scatter
    return [
      {
        type: 'scatter',
        mode: 'markers',
        x: categories,
        y: values,
        marker: { size: 10, color: primaryColor, opacity: 0.8 },
        hoverinfo: 'x+y',
      },
    ];
  }, [chartType, categories, values]);

  return (
    <div className="bg-white border border-gray-200/90 rounded-xl p-5 shadow-sm space-y-4">
      {/* Header and Controls Toggle */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-gray-100">
        <div className="flex items-center space-x-2">
          <div className="w-8 h-8 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600">
            <Sliders className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-gray-900 leading-tight">
              Verified Chart Customizer
            </h3>
            <p className="text-[11px] text-gray-500">
              Interactive visualization powered strictly by verified query outcomes
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <button
            type="button"
            onClick={handleReset}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg border border-gray-200 bg-white hover:bg-gray-50 text-xs font-semibold text-gray-700 shadow-2xs transition-colors cursor-pointer"
          >
            <RotateCcw className="w-3.5 h-3.5 text-gray-400" />
            <span>Reset Default</span>
          </button>
        </div>
      </div>

      {/* Top Mini-Bars Strip: Chart Type, Axis, Sort, Aggregation, and Title */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2.5 bg-gray-50/80 p-3 rounded-xl border border-gray-100 text-xs">
        {/* Mini-Bar 1: Chart Type */}
        <div>
          <label className="block text-[10px] font-bold text-gray-500 uppercase tracking-wider mb-1">
            Chart Type
          </label>
          <select
            value={chartType}
            onChange={(e) => setChartType(e.target.value as ChartType)}
            className="w-full bg-white border border-gray-200 rounded-lg px-2.5 py-1.5 text-xs text-gray-800 font-medium focus:ring-1 focus:ring-indigo-500 cursor-pointer"
          >
            <option value="hbar">Horizontal Bar</option>
            <option value="vbar">Vertical Bar</option>
            <option value="line">Line Chart</option>
            <option value="area">Area Chart</option>
            <option value="donut">Donut Chart</option>
            <option value="pie">Pie Chart</option>
            <option value="scatter">Scatter Plot</option>
          </select>
        </div>

        {/* Mini-Bar 2: X Axis / Category */}
        <div>
          <label className="block text-[10px] font-bold text-gray-500 uppercase tracking-wider mb-1">
            X Axis / Category
          </label>
          <select
            value={xColumn}
            onChange={(e) => setXColumn(e.target.value)}
            className="w-full bg-white border border-gray-200 rounded-lg px-2.5 py-1.5 text-xs text-gray-800 font-mono focus:ring-1 focus:ring-indigo-500 cursor-pointer"
          >
            {availableColumns.map((col) => (
              <option key={col} value={col}>
                {col}
              </option>
            ))}
          </select>
        </div>

        {/* Mini-Bar 3: Y Axis / Value */}
        <div>
          <label className="block text-[10px] font-bold text-gray-500 uppercase tracking-wider mb-1">
            Y Axis / Value
          </label>
          <select
            value={yColumn}
            onChange={(e) => setYColumn(e.target.value)}
            className="w-full bg-white border border-gray-200 rounded-lg px-2.5 py-1.5 text-xs text-gray-800 font-mono focus:ring-1 focus:ring-indigo-500 cursor-pointer"
          >
            {(numericColumns.length > 0 ? numericColumns : availableColumns).map((col) => (
              <option key={col} value={col}>
                {col}
              </option>
            ))}
          </select>
        </div>

        {/* Mini-Bar 4: Axis Scale */}
        <div>
          <label className="block text-[10px] font-bold text-gray-500 uppercase tracking-wider mb-1">
            Axis Scale
          </label>
          <select
            value={axisScale}
            onChange={(e) => setAxisScale(e.target.value as AxisScale)}
            className="w-full bg-white border border-gray-200 rounded-lg px-2.5 py-1.5 text-xs text-gray-800 font-medium focus:ring-1 focus:ring-indigo-500 cursor-pointer"
          >
            <option value="linear">Linear Scale</option>
            <option value="log">Logarithmic (Log₁₀)</option>
          </select>
        </div>

        {/* Mini-Bar 5: Sort Order */}
        <div>
          <label className="block text-[10px] font-bold text-gray-500 uppercase tracking-wider mb-1">
            Sort Order
          </label>
          <select
            value={sortOrder}
            onChange={(e) => setSortOrder(e.target.value as SortOrder)}
            className="w-full bg-white border border-gray-200 rounded-lg px-2.5 py-1.5 text-xs text-gray-800 font-medium focus:ring-1 focus:ring-indigo-500 cursor-pointer"
          >
            <option value="none">Default Order</option>
            <option value="desc">Highest to Lowest (Desc)</option>
            <option value="asc">Lowest to Highest (Asc)</option>
          </select>
        </div>

        {/* Mini-Bar 6: Aggregation */}
        <div>
          <label className="block text-[10px] font-bold text-gray-500 uppercase tracking-wider mb-1">
            Aggregation
          </label>
          <select
            value={aggregation}
            onChange={(e) => setAggregation(e.target.value as AggregationType)}
            className="w-full bg-white border border-gray-200 rounded-lg px-2.5 py-1.5 text-xs text-gray-800 font-medium focus:ring-1 focus:ring-indigo-500 cursor-pointer"
          >
            <option value="none">Raw Values</option>
            <option value="avg">Average (AVG)</option>
            <option value="sum">Sum (SUM)</option>
            <option value="count">Count</option>
            <option value="min">Min</option>
            <option value="max">Max</option>
          </select>
        </div>

        {/* Mini-Bar 7: Chart Title */}
        <div className="col-span-2 sm:col-span-4 lg:col-span-1">
          <label className="block text-[10px] font-bold text-gray-500 uppercase tracking-wider mb-1">
            Chart Title
          </label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="w-full bg-white border border-gray-200 rounded-lg px-2.5 py-1.5 text-xs text-gray-800 font-medium focus:ring-1 focus:ring-indigo-500"
          />
        </div>
      </div>

      {/* Dynamic Plotly Render */}
      <div className="w-full h-[360px] bg-white rounded-xl pt-2">
        <Plot
          data={plotlyData as any}
          layout={{
            autosize: true,
            title: { text: title, font: { size: 13, color: '#1E293B' } },
            margin: {
              l: chartType === 'hbar' ? 160 : 50,
              r: 30,
              t: 40,
              b: chartType === 'vbar' ? 80 : 40,
            },
            xaxis: {
              gridcolor: '#F1F5F9',
              zerolinecolor: '#E2E8F0',
              tickfont: { size: 10, color: '#475569' },
              type: (chartType === 'hbar' && axisScale === 'log') ? 'log' : 'linear',
            },
            yaxis: {
              autorange: chartType === 'hbar' ? 'reversed' : true,
              tickfont: { size: 10, color: '#475569' },
              gridcolor: '#F1F5F9',
              type: (chartType !== 'hbar' && chartType !== 'donut' && chartType !== 'pie' && axisScale === 'log') ? 'log' : 'linear',
            },
            plot_bgcolor: '#FFFFFF',
            paper_bgcolor: '#FFFFFF',
          }}
          useResizeHandler={true}
          style={{ width: '100%', height: '100%' }}
          config={{ displayModeBar: false, responsive: true }}
        />
      </div>
    </div>
  );
};

export default ChartCustomizer;
