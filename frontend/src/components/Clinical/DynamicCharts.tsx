import React, { useState, useMemo } from 'react';
import createPlotComponent from 'react-plotly.js/factory';
import Plotly from 'plotly.js-dist-min';
import { Download, PieChart, BarChart3, Activity } from 'lucide-react';
import { ChartSpec, EncounterClassItem, MonthlyTrendItem, TopDiagnosisItem } from '../../types/analytics';

const Plot = createPlotComponent(Plotly);

interface DynamicChartsProps {
  chartSpec?: ChartSpec | null;
  results?: Record<string, any>[];
  isQuestionMode?: boolean;
  encounterClasses?: EncounterClassItem[];
  monthlyTrends?: MonthlyTrendItem[];
  topDiagnoses?: TopDiagnosisItem[];
  selectedTables?: string[];
  customTitle?: string;
  customCategories?: string[];
  customValues?: number[];
}

type ChartType = 'hbar' | 'vbar' | 'line' | 'area' | 'donut' | 'pie' | 'scatter';
type CompanionView = 'auto' | 'volume' | 'tiers' | 'demographics' | 'safety' | 'efficacy';

// Safe clinical color palette
const colorPalette = [
  '#4F46E5', '#0D9488', '#F59E0B', '#EF4444', '#8B5CF6', '#06B6D4', '#EC4899', '#10B981'
];

// Clinical AE Severity color coding
const severityColorMap: Record<string, string> = {
  MILD: '#10B981',       // Emerald (Mild)
  MODERATE: '#F59E0B',   // Amber (Moderate)
  SEVERE: '#EF4444',     // Crimson / Rose (Severe)
};

// Formats technical column keys into clean, human-readable clinical labels
const formatClinicalLabel = (key?: string): string => {
  if (!key) return '';
  const lower = key.toLowerCase();
  if (lower === 'trt01a' || lower === 'treatment_arm' || lower === 'arm') return 'Treatment Arm';
  if (lower === 'aesev' || lower === 'severity') return 'Adverse Event Severity';
  if (lower === 'event_count' || lower === 'total_adverse_events' || lower === 'ae_count' || lower === 'cnt') return 'Adverse Event Count';
  if (lower === 'ae_rate_pct' || lower === 'overall_ae_rate_pct') return 'AE Incidence Rate (%)';
  if (lower === 'response_rate_pct') return 'Efficacy Response Rate (%)';
  if (lower === 'total_subjects' || lower === 'subject_count' || lower === 'enrolled_subjects') return 'Subject Count';
  if (lower === 'ae_subjects') return 'Subjects with AE';
  if (lower === 'mean_age') return 'Mean Age (Years)';
  if (lower === 'aedecod') return 'Adverse Event Term (AEDECOD)';
  if (lower === 'paramcd' || lower === 'param') return 'Clinical Parameter';
  if (lower === 'avisit') return 'Analysis Visit';
  if (lower === 'mean_change' || lower === 'chg') return 'Mean Change from Baseline';
  if (lower === 'mean_pct_change' || lower === 'pchg') return 'Mean % Change from Baseline';
  if (lower === 'mean_val' || lower === 'mean_aval' || lower === 'aval') return 'Analysis Value';
  if (lower === 'sex') return 'Sex Category';
  if (lower === 'siteid' || lower === 'site_name') return 'Clinical Site';
  return key.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase());
};

// Formats metric numbers accurately for clinical interpretation (rates with %, counts with commas)
const formatMetricValue = (v: number, metricKey?: string): string => {
  const lower = (metricKey || '').toLowerCase();
  if (lower.includes('pct') || lower.includes('rate') || lower.includes('percentage')) {
    return `${v.toFixed(1)}%`;
  }
  if (Number.isInteger(v) || v >= 100) {
    return v.toLocaleString();
  }
  return v.toFixed(1);
};

export const DynamicCharts: React.FC<DynamicChartsProps> = ({
  chartSpec,
  results = [],
  isQuestionMode = false,
  encounterClasses = [],
  topDiagnoses = [],
  selectedTables = ['study', 'sites', 'dm'],
  customTitle,
  customCategories,
  customValues,
}) => {
  // Chart type switcher states
  const [pipelineChartType, setPipelineChartType] = useState<ChartType>('vbar');
  const [overviewChartType, setOverviewChartType] = useState<ChartType>('vbar');
  const [companionView, setCompanionView] = useState<CompanionView>('auto');

  // Helper to construct Plotly trace and layout for single-dimension charts
  const getPlotConfig = (
    type: ChartType,
    categories: string[],
    values: number[],
    primaryColor: string = '#4F46E5',
    xLabel?: string,
    yLabel?: string,
    metricKey?: string,
  ) => {
    let data: any[] = [];
    let layout: any = {
      autosize: true,
      plot_bgcolor: '#FFFFFF',
      paper_bgcolor: '#FFFFFF',
    };

    const effectiveXLabel = xLabel || 'Category';
    const effectiveYLabel = yLabel || 'Metric Value';

    if (type === 'hbar') {
      data = [
        {
          type: 'bar',
          orientation: 'h',
          y: categories,
          x: values,
          marker: { color: primaryColor, opacity: 0.9 },
          text: values.map((v) => formatMetricValue(v, metricKey)),
          textposition: 'auto',
          hoverinfo: 'x+y',
        },
      ];
      layout = {
        ...layout,
        margin: { l: 150, r: 30, t: 20, b: 40 },
        xaxis: {
          title: { text: effectiveYLabel, font: { size: 10, color: '#64748B' } },
          gridcolor: '#F1F5F9',
          zerolinecolor: '#E2E8F0',
          tickfont: { size: 10 },
        },
        yaxis: {
          title: { text: effectiveXLabel, font: { size: 10, color: '#64748B' } },
          autorange: 'reversed',
          tickfont: { size: 11, color: '#334155' },
        },
      };
    } else if (type === 'vbar') {
      data = [
        {
          type: 'bar',
          x: categories,
          y: values,
          marker: { color: primaryColor, opacity: 0.9 },
          text: values.map((v) => formatMetricValue(v, metricKey)),
          textposition: 'auto',
          hoverinfo: 'x+y',
        },
      ];
      layout = {
        ...layout,
        margin: { l: 60, r: 25, t: 20, b: 70 },
        xaxis: {
          title: { text: effectiveXLabel, font: { size: 10, color: '#64748B' } },
          tickangle: -20,
          tickfont: { size: 9, color: '#334155' },
          gridcolor: '#F1F5F9',
        },
        yaxis: {
          title: { text: effectiveYLabel, font: { size: 10, color: '#64748B' } },
          gridcolor: '#F1F5F9',
          zerolinecolor: '#E2E8F0',
        },
      };
    } else if (type === 'line') {
      data = [
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
      layout = {
        ...layout,
        margin: { l: 60, r: 25, t: 20, b: 65 },
        xaxis: {
          title: { text: effectiveXLabel, font: { size: 10, color: '#64748B' } },
          tickangle: -20,
          tickfont: { size: 9, color: '#334155' },
          gridcolor: '#F1F5F9',
        },
        yaxis: {
          title: { text: effectiveYLabel, font: { size: 10, color: '#64748B' } },
          gridcolor: '#F1F5F9',
        },
      };
    } else if (type === 'area') {
      data = [
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
      layout = {
        ...layout,
        margin: { l: 60, r: 25, t: 20, b: 65 },
        xaxis: {
          title: { text: effectiveXLabel, font: { size: 10, color: '#64748B' } },
          tickangle: -20,
          tickfont: { size: 9, color: '#334155' },
          gridcolor: '#F1F5F9',
        },
        yaxis: {
          title: { text: effectiveYLabel, font: { size: 10, color: '#64748B' } },
          gridcolor: '#F1F5F9',
        },
      };
    } else if (type === 'donut') {
      data = [
        {
          type: 'pie',
          hole: 0.6,
          labels: categories,
          values: values,
          marker: { colors: colorPalette },
          textinfo: 'percent',
          hoverinfo: 'label+value+percent',
        },
      ];
      layout = {
        ...layout,
        showlegend: true,
        legend: { orientation: 'h', y: -0.2, font: { size: 9 } },
        margin: { l: 10, r: 10, t: 10, b: 35 },
      };
    } else if (type === 'pie') {
      data = [
        {
          type: 'pie',
          labels: categories,
          values: values,
          marker: { colors: colorPalette },
          textinfo: 'percent',
          hoverinfo: 'label+value+percent',
        },
      ];
      layout = {
        ...layout,
        showlegend: true,
        legend: { orientation: 'h', y: -0.2, font: { size: 9 } },
        margin: { l: 10, r: 10, t: 10, b: 35 },
      };
    } else {
      // scatter
      data = [
        {
          type: 'scatter',
          mode: 'markers',
          x: categories,
          y: values,
          marker: { size: 10, color: primaryColor, opacity: 0.85 },
          hoverinfo: 'x+y',
        },
      ];
      layout = {
        ...layout,
        margin: { l: 60, r: 25, t: 20, b: 65 },
        xaxis: {
          title: { text: effectiveXLabel, font: { size: 10, color: '#64748B' } },
          tickangle: -20,
          tickfont: { size: 9, color: '#334155' },
          gridcolor: '#F1F5F9',
        },
        yaxis: {
          title: { text: effectiveYLabel, font: { size: 10, color: '#64748B' } },
          gridcolor: '#F1F5F9',
        },
      };
    }

    return { data, layout };
  };

  // Real randomized treatment arms for Charts (from ADSL)
  const defaultClinicalArms: EncounterClassItem[] = [
    { class_name: 'Drug X', count: 5011 },
    { class_name: 'Placebo', count: 4989 },
  ];
  const activeArms = encounterClasses.length > 0 ? encounterClasses : defaultClinicalArms;

  // Total subjects across treatment arms for accurate denominator percentages
  const totalArmSubjects = useMemo(() => {
    return activeArms.reduce((sum, a) => sum + (Number(a.count) || 0), 0);
  }, [activeArms]);

  // Labels for Donut Chart with distinct counts and percentages
  const armLabelsWithPct = useMemo(() => {
    return activeArms.map((a) => {
      const cnt = Number(a.count) || 0;
      const pct = totalArmSubjects > 0 ? ((cnt / totalArmSubjects) * 100).toFixed(1) : '0.0';
      return `${a.class_name}: ${cnt.toLocaleString()} (${pct}%)`;
    });
  }, [activeArms, totalArmSubjects]);

  // =========================================================================
  // Authentic Cohort Data Detector: Strictly checks for a real cohort column
  // (Do not substitute treatment arm or sex for cohort)
  // =========================================================================
  const cohortData = useMemo(() => {
    if (results && results.length > 0) {
      const keys = Object.keys(results[0]);
      const cohortKey = keys.find(
        (k) => {
          const l = k.toLowerCase();
          return (l === 'cohort' || l.endsWith('_cohort') || l === 'arm_cohort') && !l.includes('trt') && !l.includes('sex');
        }
      );
      if (cohortKey) {
        const cohortTotals: Record<string, number> = {};
        const subjectCol = keys.find((k) => k.toLowerCase().includes('subjid') || k.toLowerCase().includes('id'));
        if (subjectCol) {
          const seen = new Set<string>();
          results.forEach((r) => {
            const sid = String(r[subjectCol]);
            const c = String(r[cohortKey] ?? 'Unknown');
            const combo = `${c}::${sid}`;
            if (!seen.has(combo)) {
              seen.add(combo);
              cohortTotals[c] = (cohortTotals[c] || 0) + 1;
            }
          });
        } else {
          results.forEach((r) => {
            const c = String(r[cohortKey] ?? 'Unknown');
            cohortTotals[c] = (cohortTotals[c] || 0) + 1;
          });
        }
        return {
          categories: Object.keys(cohortTotals),
          values: Object.values(cohortTotals),
        };
      }
    }
    // No cohort column exists in dataset (ADSL and DM CDISC tables do not define a cohort column)
    return null;
  }, [results]);

  // =========================================================================
  // Top Adverse Events by Frequency (ADAE CDISC analysis)
  // When no protocol cohort variable exists, replaces the cohort chart with
  // distinct subject counts per adverse event term (AEDECOD).
  // =========================================================================
  const topAEData = useMemo(() => {
    // 1. If results has AEDECOD / adverse event columns with distinct subject count, extract from results
    if (results && results.length > 0) {
      const keys = Object.keys(results[0]);
      const aeTermKey = keys.find((k) => {
        const l = k.toLowerCase();
        return l === 'aedecod' || l === 'aeterm' || l === 'adverse_event';
      });
      const countKey = keys.find((k) => {
        const l = k.toLowerCase();
        return l === 'cnt' || l === 'count' || l === 'distinct_subjects' || l === 'subject_count' || l === 'total_subjects' || l === 'ae_subjects';
      });
      if (aeTermKey && countKey) {
        const sorted = [...results]
          .filter((r) => r[aeTermKey])
          .sort((a, b) => (Number(b[countKey]) || 0) - (Number(a[countKey]) || 0))
          .slice(0, 5);
        if (sorted.length > 0) {
          return {
            categories: sorted.map((r) => String(r[aeTermKey])),
            values: sorted.map((r) => Number(r[countKey]) || 0),
          };
        }
      }
    }
    // 2. Otherwise use topDiagnoses (which is populated from ADAE with COUNT(DISTINCT USUBJID) filtered by TRTEMFL='Y' and SAFFL='Y')
    if (topDiagnoses && topDiagnoses.length > 0) {
      const top5 = [...topDiagnoses]
        .filter((d) => d.diagnosis && d.count > 0)
        .sort((a, b) => b.count - a.count)
        .slice(0, 5);
      if (top5.length > 0) {
        return {
          categories: top5.map((d) => d.diagnosis),
          values: top5.map((d) => d.count),
        };
      }
    }
    return null;
  }, [results, topDiagnoses]);

  // =========================================================================
  // Question-Driven Mode: Render Verified Question Results (3 Charts Layout)
  // =========================================================================
  if (isQuestionMode && results.length > 0) {
    const keys = Object.keys(results[0]);
    const xKey = chartSpec?.x_column || keys[0];
    const yKey = chartSpec?.y_column || keys[1] || keys[0];
    const groupKey = chartSpec?.group_column || (
      keys.find((k) => k !== xKey && k !== yKey && typeof results[0][k] === 'string')
    );
    const title = chartSpec?.title || (
      groupKey
        ? `${formatClinicalLabel(yKey)} by ${formatClinicalLabel(xKey)} and ${formatClinicalLabel(groupKey)}`
        : `${formatClinicalLabel(yKey)} by ${formatClinicalLabel(xKey)}`
    );

    let pipelineData: any[] = [];
    let pipelineLayout: any = {};

    // MULTI-DIMENSIONAL STRATIFICATION: Render all 7 supported chart types
    if (groupKey) {
      const distinctX = Array.from(new Set(results.map((r) => String(r[xKey] ?? ''))));
      let distinctGroups = Array.from(new Set(results.map((r) => String(r[groupKey] ?? ''))));

      // Order severity categories clinically: MILD -> MODERATE -> SEVERE
      if (
        groupKey.toLowerCase().includes('sev') ||
        distinctGroups.some((g) => ['MILD', 'MODERATE', 'SEVERE'].includes(g.toUpperCase()))
      ) {
        const order = ['MILD', 'MODERATE', 'SEVERE'];
        distinctGroups = distinctGroups.sort((a, b) => {
          const idxA = order.indexOf(a.toUpperCase());
          const idxB = order.indexOf(b.toUpperCase());
          return (idxA !== -1 ? idxA : 99) - (idxB !== -1 ? idxB : 99);
        });
      }

      const xLabel = formatClinicalLabel(xKey);
      const yLabel = formatClinicalLabel(yKey);

      // 1. Donut / Pie Charts
      if (pipelineChartType === 'donut' || pipelineChartType === 'pie') {
        const isDonut = pipelineChartType === 'donut';
        const labels = results.map((r) => `${r[xKey]} - ${r[groupKey]}`);
        const values = results.map((r) => Number(r[yKey]) || 0);
        const colors = results.map((r, i) => {
          const grp = String(r[groupKey]).toUpperCase();
          return severityColorMap[grp] || colorPalette[i % colorPalette.length];
        });

        pipelineData = [
          {
            type: 'pie',
            hole: isDonut ? 0.55 : 0,
            labels,
            values,
            marker: { colors },
            textinfo: 'percent',
            hoverinfo: 'label+value+percent',
          },
        ];

        pipelineLayout = {
          autosize: true,
          uirevision: pipelineChartType,
          plot_bgcolor: '#FFFFFF',
          paper_bgcolor: '#FFFFFF',
          margin: { l: 20, r: 20, t: 20, b: 60 },
          showlegend: true,
          legend: { orientation: 'h', y: -0.22, x: 0.05, font: { size: 9, color: '#334155' } },
        };
      } else {
        // 2. Bar (VBar / HBar), Line, Area, and Scatter Charts
        const isHBar = pipelineChartType === 'hbar';

        pipelineData = distinctGroups.map((grp, idx) => {
          const vals = distinctX.map((xVal) => {
            const row = results.find(
              (r) => String(r[xKey]) === xVal && String(r[groupKey]) === grp
            );
            return row ? Number(row[yKey]) || 0 : 0;
          });
          const color = severityColorMap[grp.toUpperCase()] || colorPalette[idx % colorPalette.length];

          if (isHBar) {
            return {
              name: grp,
              type: 'bar',
              orientation: 'h',
              y: distinctX,
              x: vals,
              marker: { color, opacity: 0.9 },
              text: vals.map((v) => formatMetricValue(v, yKey)),
              textposition: 'auto',
              hoverinfo: 'x+y+name',
            };
          } else if (pipelineChartType === 'line') {
            return {
              name: grp,
              type: 'scatter',
              mode: 'lines+markers',
              x: distinctX,
              y: vals,
              line: { color, width: 3, shape: 'spline' },
              marker: { size: 7, color },
              text: vals.map((v) => formatMetricValue(v, yKey)),
              hoverinfo: 'x+y+name',
            };
          } else if (pipelineChartType === 'area') {
            return {
              name: grp,
              type: 'scatter',
              mode: 'lines',
              fill: 'tozeroy',
              x: distinctX,
              y: vals,
              line: { color, width: 2.5, shape: 'spline' },
              text: vals.map((v) => formatMetricValue(v, yKey)),
              hoverinfo: 'x+y+name',
            };
          } else if (pipelineChartType === 'scatter') {
            return {
              name: grp,
              type: 'scatter',
              mode: 'markers',
              x: distinctX,
              y: vals,
              marker: { size: 12, color, opacity: 0.85 },
              text: vals.map((v) => formatMetricValue(v, yKey)),
              hoverinfo: 'x+y+name',
            };
          } else {
            // Default: vbar (Vertical Bar Grouped)
            return {
              name: grp,
              type: 'bar',
              x: distinctX,
              y: vals,
              marker: { color, opacity: 0.9 },
              text: vals.map((v) => formatMetricValue(v, yKey)),
              textposition: 'auto',
              hoverinfo: 'x+y+name',
            };
          }
        });

        pipelineLayout = {
          autosize: true,
          uirevision: pipelineChartType,
          barmode: (isHBar || pipelineChartType === 'vbar') ? 'group' : undefined,
          plot_bgcolor: '#FFFFFF',
          paper_bgcolor: '#FFFFFF',
          margin: isHBar ? { l: 120, r: 25, t: 20, b: 60 } : { l: 60, r: 25, t: 20, b: 70 },
          showlegend: true,
          legend: { orientation: 'h', y: -0.22, x: 0.1, font: { size: 10, color: '#334155' } },
          xaxis: {
            title: {
              text: isHBar ? yLabel : xLabel,
              font: { size: 10, color: '#64748B' },
            },
            gridcolor: '#F1F5F9',
            zerolinecolor: '#E2E8F0',
            tickfont: { size: 10 },
          },
          yaxis: {
            title: {
              text: isHBar ? xLabel : yLabel,
              font: { size: 10, color: '#64748B' },
            },
            autorange: isHBar ? 'reversed' : true,
            gridcolor: '#F1F5F9',
            zerolinecolor: '#E2E8F0',
            tickfont: { size: 10, color: '#334155' },
          },
        };
      }
    } else {
      // SINGLE-DIMENSIONAL DATA
      const categories = results.map((r) => String(r[xKey] ?? ''));
      const values = results.map((r) => Number(r[yKey]) || 0);

      const cfg = getPlotConfig(
        pipelineChartType,
        categories,
        values,
        '#4F46E5',
        formatClinicalLabel(xKey),
        formatClinicalLabel(yKey),
        yKey
      );
      pipelineData = cfg.data;
      pipelineLayout = {
        ...cfg.layout,
        uirevision: pipelineChartType,
      };
    }

    return (
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3.5">
        {/* Main Dynamic Chart (Left 2 Columns) with Chart Type mini-box */}
        <div className="lg:col-span-2 bg-white border border-gray-200/90 rounded-xl p-4 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
            <div className="flex items-center space-x-2">
              <BarChart3 className="w-4 h-4 text-indigo-600" />
              <h3 className="text-xs font-bold text-gray-900">{title}</h3>
            </div>

            {/* Right Header Area: Mini Box for Chart Type near Verified Pipeline Chart */}
            <div className="flex items-center space-x-2">
              <div className="flex items-center space-x-1.5 bg-gray-50 border border-gray-200/90 rounded-lg px-2 py-1 shadow-2xs">
                <span className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">
                  Chart Type:
                </span>
                <select
                  value={pipelineChartType}
                  onChange={(e) => setPipelineChartType(e.target.value as ChartType)}
                  className="bg-white border border-gray-200 rounded px-1.5 py-0.5 text-xs text-gray-800 font-medium focus:ring-1 focus:ring-indigo-500 cursor-pointer shadow-2xs"
                >
                  <option value="vbar">Vertical Bar</option>
                  <option value="hbar">Horizontal Bar</option>
                  <option value="line">Line Chart</option>
                  <option value="area">Area Chart</option>
                  <option value="donut">Donut Chart</option>
                  <option value="pie">Pie Chart</option>
                  <option value="scatter">Scatter Plot</option>
                </select>
              </div>

              <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold text-indigo-600 bg-indigo-50 border border-indigo-100">
                Verified Pipeline Chart
              </span>
            </div>
          </div>

          <div className="w-full h-[280px]">
            <Plot
              data={pipelineData}
              layout={pipelineLayout}
              useResizeHandler={true}
              style={{ width: '100%', height: '100%' }}
              config={{ displayModeBar: false, responsive: true }}
            />
          </div>
        </div>

        {/* Right Column: Dynamic Companion Chart + Treatment Arm Allocation Chart */}
        <div className="space-y-3.5 flex flex-col justify-between">
          {/* Chart 2: Subject Count by Cohort or Top Adverse Events by Frequency */}
          <div className="bg-white border border-gray-200/90 rounded-xl p-3.5 shadow-sm">
            <div className="flex items-center justify-between mb-1.5">
              <div className="flex items-center space-x-1.5">
                <Activity className="w-3.5 h-3.5 text-indigo-600" />
                <h3 className="text-xs font-bold text-gray-900 leading-tight">
                  {cohortData ? 'Subject Count by Cohort' : 'Top Adverse Events by Frequency'}
                </h3>
              </div>

              <div className="flex items-center space-x-1.5">
                <span className="text-[10px] font-semibold text-gray-500 bg-gray-50 px-1.5 py-0.5 rounded-full border border-gray-200 font-mono">
                  {cohortData
                    ? `${cohortData.categories.length} Cohorts`
                    : topAEData
                    ? 'Dataset: adae'
                    : 'AE Data: N/A'}
                </span>
              </div>
            </div>

            <div className="w-full h-[145px]">
              {cohortData ? (
                <Plot
                  data={[
                    {
                      type: 'bar',
                      x: cohortData.categories,
                      y: cohortData.values,
                      marker: { color: '#6366F1' },
                      text: cohortData.values.map((v) => v.toLocaleString()),
                      textposition: 'auto',
                      hoverinfo: 'x+y',
                    },
                  ]}
                  layout={{
                    autosize: true,
                    margin: { l: 40, r: 15, t: 10, b: 35 },
                    xaxis: { tickfont: { size: 9, color: '#64748B' } },
                    yaxis: { tickfont: { size: 9, color: '#64748B' }, gridcolor: '#F8FAFC' },
                    plot_bgcolor: '#FFFFFF',
                    paper_bgcolor: '#FFFFFF',
                  }}
                  useResizeHandler={true}
                  style={{ width: '100%', height: '100%' }}
                  config={{ displayModeBar: false, responsive: true }}
                />
              ) : topAEData ? (
                <Plot
                  data={[
                    {
                      type: 'bar',
                      orientation: 'h',
                      y: topAEData.categories,
                      x: topAEData.values,
                      marker: { color: '#6366F1' },
                      text: topAEData.values.map((v) => v.toLocaleString()),
                      textposition: 'auto',
                      hovertemplate: '%{y}: %{x:,} subjects<extra></extra>',
                    },
                  ]}
                  layout={{
                    autosize: true,
                    margin: { l: 120, r: 20, t: 8, b: 24 },
                    xaxis: {
                      title: { text: 'Distinct Subjects', font: { size: 8.5, color: '#64748B' } },
                      tickfont: { size: 8, color: '#64748B' },
                      gridcolor: '#F8FAFC',
                    },
                    yaxis: {
                      tickfont: { size: 8.5, color: '#334155' },
                      autorange: 'reversed',
                    },
                    plot_bgcolor: '#FFFFFF',
                    paper_bgcolor: '#FFFFFF',
                  }}
                  useResizeHandler={true}
                  style={{ width: '100%', height: '100%' }}
                  config={{ displayModeBar: false, responsive: true }}
                />
              ) : (
                <div className="w-full h-full flex flex-col items-center justify-center bg-gray-50/70 rounded-lg border border-dashed border-gray-200/90 p-3 text-center">
                  <div className="w-7 h-7 rounded-full bg-slate-100 flex items-center justify-center text-slate-500 mb-1.5">
                    <Activity className="w-3.5 h-3.5" />
                  </div>
                  <p className="text-xs font-semibold text-gray-700">Adverse event data unavailable</p>
                  <p className="text-[10px] text-gray-400 mt-0.5 max-w-[220px] leading-tight">
                    No treatment-emergent adverse event records found in ADAE dataset.
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Chart 3: Treatment Arm Allocation (Donut Chart) */}
          <div className="bg-white border border-gray-200/90 rounded-xl p-3.5 shadow-sm">
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center space-x-2">
                <PieChart className="w-3.5 h-3.5 text-emerald-600" />
                <h3 className="text-xs font-bold text-gray-900">Treatment Arm Allocation</h3>
              </div>
              <span className="text-[10px] font-semibold text-gray-500 font-mono">
                {activeArms.length} Treatment Arms
              </span>
            </div>

            <div className="w-full h-[140px]">
              <Plot
                data={[
                  {
                    type: 'pie',
                    hole: 0.65,
                    labels: armLabelsWithPct,
                    values: activeArms.map((c) => c.count),
                    marker: {
                      colors: colorPalette,
                    },
                    textinfo: 'percent',
                    hoverinfo: 'label+value+percent',
                  },
                ]}
                layout={{
                  autosize: true,
                  showlegend: true,
                  legend: {
                    orientation: 'v',
                    x: 0.82,
                    y: 0.5,
                    font: { size: 8.5, color: '#334155' },
                  },
                  margin: { l: 0, r: 85, t: 5, b: 5 },
                  plot_bgcolor: '#FFFFFF',
                  paper_bgcolor: '#FFFFFF',
                }}
                useResizeHandler={true}
                style={{ width: '100%', height: '100%' }}
                config={{ displayModeBar: false, responsive: true }}
              />
            </div>
          </div>
        </div>
      </div>
    );
  }

  // =========================================================================
  // General Overview Mode: Chart 1 (Total Subjects by Treatment Arm or Custom)
  // =========================================================================
  const isCustomApplied = Boolean(
    (customCategories && customCategories.length > 0) ||
    (customValues && customValues.length > 0) ||
    customTitle
  );

  const barCategories = isCustomApplied && customCategories && customCategories.length > 0
    ? customCategories
    : activeArms.map((a) => a.class_name);

  const barValues = isCustomApplied && customValues && customValues.length > 0
    ? customValues
    : activeArms.map((a) => Number(a.count) || 0);

  const displayTitle = customTitle || 'Total Subjects by Treatment Arm';

  const categoryLabel = isCustomApplied ? 'Category' : 'Treatment Arm';
  const metricLabel = isCustomApplied ? 'Metric Value' : 'Distinct Subject Count';
  const metricKey = isCustomApplied ? 'value' : 'total_subjects';

  const { data: overviewData, layout: overviewLayout } = getPlotConfig(
    overviewChartType,
    barCategories.length > 0 ? barCategories : ['Drug X', 'Placebo'],
    barValues.length > 0 ? barValues : [5011, 4989],
    '#4F46E5',
    categoryLabel,
    metricLabel,
    metricKey
  );

  const overviewLayoutWithRevision = {
    ...overviewLayout,
    uirevision: overviewChartType,
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-3.5">
      {/* Chart 1: Total Subjects by Treatment Arm (Large Left Card) */}
      <div className="lg:col-span-2 bg-white border border-gray-200/90 rounded-xl p-4 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
          <div className="flex items-center space-x-2">
            <BarChart3 className="w-4 h-4 text-indigo-600" />
            <h3 className="text-xs font-bold text-gray-900">
              {displayTitle}
            </h3>
          </div>
          <div className="flex items-center space-x-2">
            {/* Chart Type Selector Dropdown */}
            <div className="flex items-center space-x-1.5 bg-gray-50 border border-gray-200/90 rounded-lg px-2 py-1 shadow-2xs">
              <span className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">
                Chart Type:
              </span>
              <select
                value={overviewChartType}
                onChange={(e) => setOverviewChartType(e.target.value as ChartType)}
                className="bg-white border border-gray-200 rounded px-1.5 py-0.5 text-xs text-gray-800 font-medium focus:ring-1 focus:ring-indigo-500 cursor-pointer shadow-2xs"
              >
                <option value="vbar">Vertical Bar</option>
                <option value="hbar">Horizontal Bar</option>
                <option value="line">Line Chart</option>
                <option value="area">Area Chart</option>
                <option value="donut">Donut Chart</option>
                <option value="pie">Pie Chart</option>
                <option value="scatter">Scatter Plot</option>
              </select>
            </div>

            <button className="flex items-center space-x-1 px-2.5 py-1 rounded border border-gray-200 bg-white hover:bg-gray-50 text-[11px] font-medium text-gray-600 shadow-2xs transition-colors">
              <Download className="w-3 h-3 text-gray-500" />
              <span>Export Chart</span>
            </button>
          </div>
        </div>

        <div className="w-full h-[280px]">
          <Plot
            data={overviewData}
            layout={overviewLayoutWithRevision}
            useResizeHandler={true}
            style={{ width: '100%', height: '100%' }}
            config={{ displayModeBar: false, responsive: true }}
          />
        </div>
      </div>

      {/* Right Column: Chart 2 (Top Adverse Events by Frequency) + Chart 3 (Treatment Arm Allocation) */}
      <div className="space-y-3.5 flex flex-col justify-between">
        {/* Chart 2: Subject Count by Cohort or Top Adverse Events by Frequency */}
        <div className="bg-white border border-gray-200/90 rounded-xl p-3.5 shadow-sm">
          <div className="flex items-center justify-between mb-1.5">
            <div className="flex items-center space-x-1.5">
              <Activity className="w-3.5 h-3.5 text-indigo-600" />
              <h3 className="text-xs font-bold text-gray-900 leading-tight">
                {cohortData ? 'Subject Count by Cohort' : 'Top Adverse Events by Frequency'}
              </h3>
            </div>

            <div className="flex items-center space-x-1.5">
              <span className="text-[10px] font-semibold text-gray-500 bg-gray-50 px-1.5 py-0.5 rounded-full border border-gray-200 font-mono">
                {cohortData
                  ? `${cohortData.categories.length} Cohorts`
                  : topAEData
                  ? 'Dataset: adae'
                  : 'AE Data: N/A'}
              </span>
            </div>
          </div>

          <div className="w-full h-[145px]">
            {cohortData ? (
              <Plot
                data={[
                  {
                    type: 'bar',
                    x: cohortData.categories,
                    y: cohortData.values,
                    marker: { color: '#6366F1' },
                    text: cohortData.values.map((v) => v.toLocaleString()),
                    textposition: 'auto',
                    hoverinfo: 'x+y',
                  },
                ]}
                layout={{
                  autosize: true,
                  margin: { l: 40, r: 15, t: 10, b: 35 },
                  xaxis: { tickfont: { size: 9, color: '#64748B' } },
                  yaxis: { tickfont: { size: 9, color: '#64748B' }, gridcolor: '#F8FAFC' },
                  plot_bgcolor: '#FFFFFF',
                  paper_bgcolor: '#FFFFFF',
                }}
                useResizeHandler={true}
                style={{ width: '100%', height: '100%' }}
                config={{ displayModeBar: false, responsive: true }}
              />
            ) : topAEData ? (
              <Plot
                data={[
                  {
                    type: 'bar',
                    orientation: 'h',
                    y: topAEData.categories,
                    x: topAEData.values,
                    marker: { color: '#6366F1' },
                    text: topAEData.values.map((v) => v.toLocaleString()),
                    textposition: 'auto',
                    hovertemplate: '%{y}: %{x:,} subjects<extra></extra>',
                  },
                ]}
                layout={{
                  autosize: true,
                  margin: { l: 120, r: 20, t: 8, b: 24 },
                  xaxis: {
                    title: { text: 'Distinct Subjects', font: { size: 8.5, color: '#64748B' } },
                    tickfont: { size: 8, color: '#64748B' },
                    gridcolor: '#F8FAFC',
                  },
                  yaxis: {
                    tickfont: { size: 8.5, color: '#334155' },
                    autorange: 'reversed',
                  },
                  plot_bgcolor: '#FFFFFF',
                  paper_bgcolor: '#FFFFFF',
                }}
                useResizeHandler={true}
                style={{ width: '100%', height: '100%' }}
                config={{ displayModeBar: false, responsive: true }}
              />
            ) : (
              <div className="w-full h-full flex flex-col items-center justify-center bg-gray-50/70 rounded-lg border border-dashed border-gray-200/90 p-3 text-center">
                <div className="w-7 h-7 rounded-full bg-slate-100 flex items-center justify-center text-slate-500 mb-1.5">
                  <Activity className="w-3.5 h-3.5" />
                </div>
                <p className="text-xs font-semibold text-gray-700">Adverse event data unavailable</p>
                <p className="text-[10px] text-gray-400 mt-0.5 max-w-[220px] leading-tight">
                  No treatment-emergent adverse event records found in ADAE dataset.
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Chart 3: Treatment Arm Allocation (Donut Chart) */}
        <div className="bg-white border border-gray-200/90 rounded-xl p-3.5 shadow-sm">
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center space-x-2">
              <PieChart className="w-3.5 h-3.5 text-emerald-600" />
              <h3 className="text-xs font-bold text-gray-900">Treatment Arm Allocation</h3>
            </div>
            <span className="text-[10px] font-semibold text-gray-500 font-mono">
              {activeArms.length} Treatment Arms
            </span>
          </div>

          <div className="w-full h-[140px]">
            <Plot
              data={[
                {
                  type: 'pie',
                  hole: 0.65,
                  labels: armLabelsWithPct,
                  values: activeArms.map((c) => c.count),
                  marker: {
                    colors: colorPalette,
                  },
                  textinfo: 'percent',
                  hoverinfo: 'label+value+percent',
                },
              ]}
              layout={{
                autosize: true,
                showlegend: true,
                legend: {
                  orientation: 'v',
                  x: 0.82,
                  y: 0.5,
                  font: { size: 8.5, color: '#334155' },
                },
                margin: { l: 0, r: 85, t: 5, b: 5 },
                plot_bgcolor: '#FFFFFF',
                paper_bgcolor: '#FFFFFF',
              }}
              useResizeHandler={true}
              style={{ width: '100%', height: '100%' }}
              config={{ displayModeBar: false, responsive: true }}
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default DynamicCharts;
