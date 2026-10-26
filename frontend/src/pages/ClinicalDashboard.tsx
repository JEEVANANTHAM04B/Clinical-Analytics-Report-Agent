import { WorkflowNotice } from '../components/Clinical/WorkflowNotice';
import React, { useEffect, useRef, useState } from 'react';
import ClinicalSidebar from '../components/Clinical/ClinicalSidebar';
import ClinicalTopbar from '../components/Clinical/ClinicalTopbar';
import ClinicalMetricsRow from '../components/Clinical/ClinicalMetricsRow';
import ActiveDatasetCard from '../components/Clinical/ActiveDatasetCard';
import AskQuestionSection from '../components/Clinical/AskQuestionSection';
import ClinicalApprovalCard from '../components/Clinical/ClinicalApprovalCard';
import DynamicCharts from '../components/Clinical/DynamicCharts';
import ClinicalInsightsCard from '../components/Clinical/ClinicalInsightsCard';
import VerifiedResultsTable from '../components/Clinical/VerifiedResultsTable';
import FollowUpSection from '../components/Clinical/FollowUpSection';
import FollowUpAnswerCard, { FollowUpHistoryItem } from '../components/Clinical/FollowUpAnswerCard';
import ReportTriggerBanner from '../components/ReportTriggerBanner';
import ReportModal from '../components/ReportModal';
import ReportHistory from '../components/ReportHistory';
import DatasetUploadModal from '../components/DatasetUploadModal';
import { getAvailableClinicalTableNames } from '../components/SidebarTableSelector';
import apiService from '../services/api';
import {
  AnalyticsResponse,
  OverviewResponse,
  ClinicalTable,
  DashboardCustomizationResponse,
  FollowUpResponse
} from '../types/analytics';
import {
  Activity,
  MessageSquare,
  TrendingUp,
  History,
  Settings,
  Sparkles,
  CheckCircle2,
  Clock,
  ArrowRight,
  UploadCloud,
  ShieldAlert,
  Sliders
} from 'lucide-react';

interface ClinicalDashboardProps {
  onSwitchRole: () => void;
}

export const ClinicalDashboard: React.FC<ClinicalDashboardProps> = ({ onSwitchRole }) => {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [overview, setOverview] = useState<OverviewResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isApproving, setIsApproving] = useState(false);
  const [approveElapsedSecs, setApproveElapsedSecs] = useState(0);
  const [currentQuestion, setCurrentQuestion] = useState('What is the adverse event rate by treatment arm?');
  const [draftQuestion, setDraftQuestion] = useState(currentQuestion);

  // Analytics state
  const [isQuestionMode, setIsQuestionMode] = useState(false);
  const [approvalPending, setApprovalPending] = useState(false);
  const [analysisPlan, setAnalysisPlan] = useState<string | null>(null);
  const [planVersion, setPlanVersion] = useState(1);
  const [feedbackHistory, setFeedbackHistory] = useState<string[]>([]);
  const [isRegenerating, setIsRegenerating] = useState(false);
  const [analyticsResult, setAnalyticsResult] = useState<AnalyticsResponse | null>(null);
  const [recovery, setRecovery] = useState<Partial<AnalyticsResponse> | null>(null);
  const [analysisIdentity, setAnalysisIdentity] = useState<{analysis_id?: string; state_version?: number}>({});
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Dynamic Table Selection & Custom Dashboard state
  const [availableTables, setAvailableTables] = useState<ClinicalTable[]>([]);
  const [selectedTables, setSelectedTables] = useState<string[]>([]);
  const hasManualTableSelection = useRef(false);
  const [isApplyingTables, setIsApplyingTables] = useState(false);
  const [tableCombinationError, setTableCombinationError] = useState<string | null>(null);
  const [customDashboardData, setCustomDashboardData] = useState<DashboardCustomizationResponse | null>(null);
  const [blockedInfo, setBlockedInfo] = useState<{
    status: string;
    reason?: string;
    question: string;
    required_tables: string[];
    selected_tables: string[];
    missing_tables: string[];
    message: string;
    next_action?: string;
  } | null>(null);

  // Modals state
  const [isReportModalOpen, setIsReportModalOpen] = useState(false);
  const [reportHistoryRefreshKey, setReportHistoryRefreshKey] = useState(0);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);

  // Lightweight Follow-up session state (does NOT restart main workflow)
  const [followUpAnswer, setFollowUpAnswer] = useState<FollowUpResponse | null>(null);
  const [followUpHistory, setFollowUpHistory] = useState<FollowUpHistoryItem[]>([]);
  const [isFollowUpLoading, setIsFollowUpLoading] = useState(false);

  // Query & Follow-Up history tracker for the side History page
  const [historyFilter, setHistoryFilter] = useState<'all' | 'analysis' | 'followup'>('all');
  const [expandedAnswerIdx, setExpandedAnswerIdx] = useState<number | null>(null);
  const [queryHistory, setQueryHistory] = useState<Array<{
    type?: 'analysis' | 'followup';
    question: string;
    answer?: string;
    timestamp: string;
    rows: number;
    status: string;
    source?: string;
    sql_query?: string | null;
  }>>([]);

  // Load general clinical metrics and dynamic tables from real database on mount
  const fetchData = async () => {
    try {
      const [overviewData, tablesData] = await Promise.all([
        apiService.getOverview().catch((err) => {
          console.error('Failed to load clinical overview:', err);
          return null;
        }),
        apiService.getTables().catch((err) => {
          console.error('Failed to load clinical tables:', err);
          return null;
        }),
      ]);

      if (overviewData) setOverview(overviewData);
      const tablesList = Array.isArray(tablesData)
        ? tablesData
        : (tablesData as any)?.tables || [];
      if (tablesList.length > 0) {
        setAvailableTables(tablesList);
        if (!hasManualTableSelection.current) {
          setSelectedTables(getAvailableClinicalTableNames(tablesList));
        }
      }
    } catch (err: any) {
      console.error('Failed to load initial data:', err);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  // Handle user applying custom table selection
  const handleApplyTableSelection = async (tablesToApply: string[]) => {
    const sanitized = (tablesToApply || []).filter(
      (t) => !['patients', 'encounters', 'conditions', 'medications', 'observations', 'procedures'].includes(t.toLowerCase().trim())
    );

    if (!sanitized || sanitized.length === 0) {
      setTableCombinationError('Please select at least one clinical table.');
      return;
    }

    setIsApplyingTables(true);
    setTableCombinationError(null);

    try {
      const response = await apiService.customizeDashboard(sanitized);
      if (!response.valid_combination) {
        setTableCombinationError(
          response.message ||
          'These tables cannot currently be combined because no approved relationship exists.'
        );
        return;
      }

      setSelectedTables(sanitized);
      hasManualTableSelection.current = true;
      setCustomDashboardData(response);
      setTableCombinationError(null);
      setIsQuestionMode(false);
      setBlockedInfo(null);
      setActiveTab('dashboard');
      await handleRunAnalysisWithTables(draftQuestion || blockedInfo?.question || currentQuestion, sanitized);
    } catch (err: any) {
      console.error('Error applying table selection:', err);
      setTableCombinationError(
        err.response?.data?.detail ||
        'These tables cannot currently be combined because no approved relationship exists.'
      );
    } finally {
      setIsApplyingTables(false);
    }
  };

  // Run question against an explicit table selection
  const handleRunAnalysisWithTables = async (question: string, tablesToUse?: string[]) => {
    if (!question.trim() || isLoading) {
      if (!question.trim()) setErrorMessage('Enter a clinical question before starting analysis.');
      return;
    }
    const tables = tablesToUse || selectedTables;
    if (tables.length === 0) {
      setErrorMessage('Dataset tables are still loading. Please try again once they are available.');
      return;
    }
    setIsLoading(true);
    setErrorMessage(null);
    setCurrentQuestion(question);
    setDraftQuestion(question);
    setAnalysisIdentity({});
    setRecovery(null);
    setPlanVersion(1);
    setFeedbackHistory([]);

    try {
      const res = await apiService.runAnalytics({
        question,
        approval_status: 'pending',
        selected_tables: tables,
        plan_version: 1,
      });
      setAnalysisIdentity({analysis_id: res.analysis_id, state_version: res.state_version});
      setRecovery(null);

      if (res.status === 'blocked') {
        setBlockedInfo({
          status: 'blocked',
          reason: res.reason || 'required_tables_not_selected',
          question: res.question || question,
          required_tables: res.required_tables || [],
          selected_tables: res.selected_tables || tables,
          missing_tables: res.missing_tables || [],
          message: res.message || 'This analysis requires tables that have not been selected.',
          next_action: res.next_action || 'select_missing_tables',
        });
        setApprovalPending(false);
        setAnalysisPlan(null);
        setAnalyticsResult(null);
        setIsQuestionMode(false);
        return;
      }

      setBlockedInfo(null);

      if (res.analysis_plan) {
        setAnalysisPlan(res.analysis_plan);
        setApprovalPending(true);
      } else {
        setErrorMessage('Failed to generate analysis plan.');
      }
    } catch (err: any) {
      console.error('Error starting analysis:', err);
      const detail = err.response?.data?.detail;
      if (detail?.stage_status) { setRecovery(detail); setAnalysisIdentity({analysis_id: detail.analysis_id, state_version: detail.state_version}); }
      setErrorMessage(typeof detail === 'string' ? detail : detail?.message || 'An error occurred while connecting to the analytics engine.');
    } finally {
      setIsLoading(false);
    }
  };

  // Step 1: User runs question -> calls backend with approval_status = 'pending' + selected_tables
  const handleRunAnalysis = (question: string) => {
    return handleRunAnalysisWithTables(question, selectedTables);
  };

  // User clicks to select missing tables and resume analysis
  const handleSelectMissingTablesAndResume = async (missing: string[]) => {
    const sanitizedMissing = missing.map((t) => t.toLowerCase().trim());
    const newTables = Array.from(new Set([...selectedTables.map((t) => t.toLowerCase().trim()), ...sanitizedMissing]));
    setSelectedTables(newTables);
    hasManualTableSelection.current = true;
    setBlockedInfo(null);

    try {
      const response = await apiService.customizeDashboard(newTables);
      if (response.valid_combination) {
        setCustomDashboardData(response);
      }
    } catch (e) {
      console.error('Failed to update dashboard metadata for selected tables:', e);
    }

    await handleRunAnalysisWithTables(currentQuestion, newTables);
  };

  // Step 2: User approves analysis plan -> calls backend with approval_status = 'approved' + selected_tables
  const handleApprovePlan = async () => {
    setIsApproving(true);
    setErrorMessage(null);
    setApproveElapsedSecs(0);

    // Tick up a seconds counter so the user can see the pipeline is alive
    const timer = setInterval(() => {
      setApproveElapsedSecs((s) => s + 1);
    }, 1000);

    try {
      console.log('APPROVAL REQUEST START');
      console.log('[Clinical Approve] Sending approval request:', {
        question: currentQuestion,
        approval_status: 'approved',
        ...analysisIdentity,
        current_plan: analysisPlan,
        feedback_history: feedbackHistory,
        plan_version: planVersion,
        selected_tables: selectedTables,
      });

      const res = await apiService.runAnalytics({
        question: currentQuestion,
        approval_status: 'approved',
        ...analysisIdentity,
        current_plan: analysisPlan || undefined,
        feedback_history: feedbackHistory,
        plan_version: planVersion,
        selected_tables: selectedTables,
      });
      setAnalysisIdentity({analysis_id: res.analysis_id, state_version: res.state_version});
      setRecovery(null);

      console.log('APPROVAL RESPONSE RECEIVED');
      console.log('[Clinical Approve] Response received:', {
        http_status: 200,
        response_status: res.status,
        approval_status: res.approval_status,
        analysis_plan: res.analysis_plan ? 'Present' : 'None',
        sql_query: res.sql_query,
        results_row_count: res.results?.length ?? 0,
        insight: res.insight ? res.insight.slice(0, 80) + '...' : 'None',
        chart_spec: res.chart_spec,
        visualization_error: res.visualization_error,
        error: res.error,
      });

      if (res.status === 'blocked') {
        setBlockedInfo({
          status: 'blocked',
          reason: res.reason || 'required_tables_not_selected',
          question: res.question || currentQuestion,
          required_tables: res.required_tables || [],
          selected_tables: res.selected_tables || selectedTables,
          missing_tables: res.missing_tables || [],
          message: res.message || 'This analysis requires tables that have not been selected.',
          next_action: res.next_action || 'select_missing_tables',
        });
        setApprovalPending(false);
        setAnalysisPlan(null);
        setAnalyticsResult(null);
        setIsQuestionMode(false);
        return;
      }

      if (res.status === 'awaiting_approval' || res.approval_status === 'pending') {
        setApprovalPending(false);
        setAnalysisPlan(null);
        setAnalyticsResult(null);
        setErrorMessage('Approval did not start execution. The analysis context changed; run the question again to review a fresh plan.');
        return;
      }
      if (res.status !== 'success' && res.status !== 'partial_success') {
        setApprovalPending(false);
        setErrorMessage(res.message || 'The analysis did not complete. Review the response before trying again.');
        return;
      }

      setBlockedInfo(null);
      setAnalyticsResult(res);
      setApprovalPending(false);
      setIsQuestionMode(true);

      // Add to query history
      setQueryHistory((prev) => [
        {
          type: 'analysis',
          question: currentQuestion,
          answer: res.insight || 'Analysis executed and verified successfully.',
          timestamp: 'Just now',
          rows: res.results?.length || 0,
          status: 'Verified & Approved',
          sql_query: res.sql_query,
        },
        ...prev,
      ]);
    } catch (err: any) {
      console.error('[Approve] CAUGHT ERROR:', err);
      console.error('[Approve] Error type:', err?.constructor?.name);
      console.error('[Approve] Error message:', err?.message);
      console.error('[Approve] Error code:', err?.code);
      console.error('[Approve] Error response:', err?.response?.status, err?.response?.data);
      const isTimeout = err.code === 'ECONNABORTED' || err.message?.includes('timeout');
      const detail = err.response?.data?.detail;
      if (detail?.stage_status) { setRecovery(detail); setAnalysisIdentity({analysis_id: detail.analysis_id, state_version: detail.state_version}); }
      const msg = isTimeout
        ? 'The analytics pipeline is taking longer than expected. Please try again — the database query and AI insight generation can take up to 2 minutes.'
        : typeof detail === 'string' ? detail : detail?.message || 'Failed to complete verified SQL execution.';
      setErrorMessage(msg);
    } finally {
      clearInterval(timer);
      setIsApproving(false);
      setApproveElapsedSecs(0);
    }
  };

  const recoverAnalysis = async (action: 'retry' | 'stop' | 'approve_quality' | 'reject_quality') => {
    if (!analysisIdentity?.analysis_id) {
      if (action === 'stop' || action === 'reject_quality') {
        setRecovery(null);
        setErrorMessage('Analysis cancelled. No further stages will run.');
        setApprovalPending(false);
        setIsApproving(false);
        return;
      }
      if (action === 'retry') {
        setRecovery(null);
        setErrorMessage(null);
        setIsApproving(false);
        await handleRunAnalysis(currentQuestion);
        return;
      }
    }
    setIsApproving(true);
    try {
      const res = await apiService.runAnalytics({question: currentQuestion, approval_status: 'approved',
        selected_tables: selectedTables, ...analysisIdentity, action});
      setAnalysisIdentity({analysis_id: res.analysis_id, state_version: res.state_version});
      setRecovery(null);
      setErrorMessage((action === 'stop' || action === 'reject_quality') ? 'Analysis cancelled. No further stages will run.' : null);
      setApprovalPending(false);
      if (action === 'retry' || action === 'approve_quality') {setAnalyticsResult(res); setIsQuestionMode(true);}
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      if (detail?.stage_status) {setRecovery(detail); setAnalysisIdentity({analysis_id: detail.analysis_id, state_version: detail.state_version});}
      setErrorMessage(typeof detail === 'string' ? detail : detail?.message || 'Recovery could not complete.');
    } finally {setIsApproving(false);}
  };

  // Step 3: User rejects plan -> calls backend with approval_status = 'rejected' and optional feedback + selected_tables
  const handleRejectPlan = async (feedback: string) => {
    setIsRegenerating(true);
    setErrorMessage(null);

    const trimmed = feedback.trim();
    const updatedHistory = trimmed && !feedbackHistory.includes(trimmed)
      ? [...feedbackHistory, trimmed]
      : feedbackHistory;

    try {
      const res = await apiService.runAnalytics({
        question: currentQuestion,
        approval_status: 'rejected',
        ...analysisIdentity,
        human_feedback: trimmed,
        current_plan: analysisPlan || undefined,
        feedback_history: updatedHistory,
        plan_version: planVersion,
        selected_tables: selectedTables,
      });
      setAnalysisIdentity({analysis_id: res.analysis_id, state_version: res.state_version});
      setRecovery(null);

      // Show regenerated plan and ask for approval again
      if (res.analysis_plan) {
        setAnalysisPlan(res.analysis_plan);
        setPlanVersion((v) => v + 1);
        setFeedbackHistory(res.feedback_history || updatedHistory);
        setApprovalPending(true); // Remain stopped at human approval gate
      }
    } catch (err: any) {
      console.error('Error regenerating plan:', err);
      setErrorMessage(err.response?.data?.detail || 'Failed to regenerate analysis plan.');
    } finally {
      setIsRegenerating(false);
    }
  };

  // Follow-up question flow (Lightweight session analysis, does NOT restart workflow)
  const handleFollowUp = async (followUpQuestion: string) => {
    setIsFollowUpLoading(true);
    setErrorMessage(null);

    try {
      const originalResults = analyticsResult?.results || (overview?.top_diagnoses as any[]) || [];
      const latestFollowUpResults = [...followUpHistory]
        .reverse()
        .find((item) => item.follow_up_results?.length)?.follow_up_results;
      const res = await apiService.runFollowUp({
        question: followUpQuestion,
        current_question: currentQuestion,
        current_results: latestFollowUpResults || originalResults,
        original_results: originalResults,
        current_sql: analyticsResult?.sql_query,
        current_plan: analyticsResult?.analysis_plan || analysisPlan,
        current_insight: analyticsResult?.insight,
        conversation_history: followUpHistory.flatMap((h) => [
          { role: 'user' as const, content: h.question },
          { role: 'assistant' as const, content: h.answer },
        ]),
        selected_tables: selectedTables,
      });

      setFollowUpAnswer(res);
      setFollowUpHistory((prev) => [
        ...prev,
        {
          question: followUpQuestion,
          answer: res.answer,
          source: res.source,
          sql_query: res.sql_query,
          verified: res.verified,
          follow_up_results: res.follow_up_results,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ]);

      // Record follow-up answer in side history page
      setQueryHistory((prev) => [
        {
          type: 'followup',
          question: followUpQuestion,
          answer: res.answer,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          rows: res.source === 'follow_up_sql' ? 1 : (analyticsResult?.results?.length || 0),
          status: res.verified ? 'Follow-Up Verified' : 'Follow-Up Completed',
          source: res.source,
          sql_query: res.sql_query,
        },
        ...prev,
      ]);
    } catch (err: any) {
      console.error('Follow-up error:', err);
      setErrorMessage(err.response?.data?.detail || 'Failed to process follow-up query.');
    } finally {
      setIsFollowUpLoading(false);
    }
  };

  // Calculate dynamic findings if results exist
  const verifiedRows = analyticsResult?.results || [];
  let peakFindingText = "Peak LOS Variance";
  let peakFindingValue = "4.0d (Anemia)";
  if (verifiedRows.length > 0) {
    const highestRow = [...verifiedRows].sort((a, b) => {
      const valA = Number(a.avg_length_of_stay || a[Object.keys(a)[1]] || 0);
      const valB = Number(b.avg_length_of_stay || b[Object.keys(b)[1]] || 0);
      return valB - valA;
    })[0];
    if (highestRow) {
      const diagName = highestRow.diagnosis || highestRow[Object.keys(highestRow)[0]] || 'Top Diagnosis';
      const diagVal = Number(highestRow.avg_length_of_stay || highestRow[Object.keys(highestRow)[1]] || 0).toFixed(1);
      peakFindingValue = `${diagVal}d (${diagName.length > 18 ? diagName.substring(0, 18) + '...' : diagName})`;
    }
  }

  // Pre-built questions for the queries library
  const prebuiltQueries = [
    {
      title: 'Average Length of Stay by Diagnosis',
      category: 'Inpatient LOS',
      question: 'What is the average length of stay by diagnosis?',
      desc: 'Calculates DATEDIFF(STOP, START) for completed inpatient encounters grouped by SNOMED condition description.',
    },
    {
      title: 'Compare Inpatient vs Emergency Encounters',
      category: 'Volume & Capacity',
      question: 'Compare inpatient and emergency encounters',
      desc: 'Aggregates admission volumes, average duration, and distinct patient counts across acute care classes.',
    },
    {
      title: 'Readmission Risk by Condition',
      category: 'Quality & Readmissions',
      question: 'Which conditions have the highest 30-day readmission rate?',
      desc: 'Evaluates 30-day return encounters following discharge across primary clinical diagnoses.',
    },
    {
      title: 'Encounter Duration Distribution by Class',
      category: 'Operational Throughput',
      question: 'Show length of stay distribution across encounter classes',
      desc: 'Breaks down outpatient, ambulatory, urgent care, wellness, and inpatient duration benchmarks.',
    },
  ];

  return (
    <div className="studio-workspace flex min-h-screen">
      {/* Sidebar */}
      {/* Sidebar with Table Selector inside Red-Box area */}
      <ClinicalSidebar
        activeTab={activeTab}
        onTabChange={setActiveTab}
        availableTables={availableTables}
        selectedTables={selectedTables}
        onApplySelection={handleApplyTableSelection}
        isApplying={isApplyingTables || isLoading}
        combinationError={tableCombinationError}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0">
        <ClinicalTopbar
          title={
            activeTab === 'dashboard'
              ? (isQuestionMode ? "Clinical Visual Dashboard" : "Clinical Dashboard")
              : activeTab === 'analytics'
              ? "In-Depth Clinical Analytics"
              : activeTab === 'queries'
              ? "Clinical Questions & Queries Library"
              : activeTab === 'trends'
              ? "Patient & Encounter Trends"
              : activeTab === 'history'
              ? "Verified Analysis History"
              : activeTab === 'reports'
              ? "Clinical Reports Center"
              : "Clinical Organization Settings"
          }
          datasetName={overview?.dataset_name || "Organization Dataset"}
          onOpenTechnical={onSwitchRole}
        />

        {/* FULL WIDTH CONTAINER: compact scale matching Screenshot density */}
        <main className="studio-main p-4 md:p-5 space-y-3.5 flex-1 w-full">
          {/* Error Banner if any */}
          {errorMessage && <WorkflowNotice message={errorMessage} recovery={recovery} busy={isApproving}
            onAction={recoverAnalysis} onDismiss={() => setErrorMessage(null)} />}

          {Array.isArray(analyticsResult?.eda_findings?.findings) && analyticsResult.eda_findings.findings.length > 0 && (
            <section
              aria-label="Data quality"
              className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-xs"
            >
              <h3 className="font-semibold">Data-quality assessment</h3>
              {analyticsResult.eda_findings.scope && <p>{analyticsResult.eda_findings.scope}</p>}

              {analyticsResult.eda_findings.findings.map((f, i) => (
                <p key={i}>
                  <strong>{f.severity}: </strong>
                  {f.message}
                </p>
              ))}
            </section>
          )}
          {/* TAB 1: MAIN DASHBOARD */}
          {activeTab === 'dashboard' && (
            <>
              {/* Metric Cards Row (Real counts from MySQL, dynamically customizable by table selection) */}
              <ClinicalMetricsRow
                totalPatients={overview?.total_patients ?? 0}
                totalEncounters={overview?.total_encounters ?? 0}
                avgLos={overview?.avg_length_of_stay ?? 0}
                readmissionRate={overview?.readmission_rate ?? 0}
                dataQualityStatus={overview?.data_quality_status ?? "Not assessed"}
                datasetStatus={overview?.organization_dataset ?? "Unavailable"}
                selectedTables={customDashboardData?.selected_tables || selectedTables}
                kpiCards={customDashboardData?.kpi_cards}
              />

              {/* Active Dataset Card with Upload Trigger */}
              <ActiveDatasetCard
                datasetName={overview?.dataset_name || "Clinical Trial CDISC Dataset"}
                onUploadClick={() => setIsUploadModalOpen(true)}
              />

              {/* Ask Question Bar */}
              <AskQuestionSection
                onRunAnalysis={handleRunAnalysis}
                isLoading={isLoading}
                defaultQuestion={draftQuestion}
                onQuestionChange={setDraftQuestion}
                suggestedQuestions={customDashboardData?.suggested_questions}
              />

              {/* ANALYSIS BLOCKED CARD */}
              {blockedInfo && (
                <div className="bg-white border-2 border-rose-300 rounded-xl p-5 shadow-sm space-y-4">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center space-x-3">
                      <div className="w-10 h-10 rounded-lg bg-rose-50 border border-rose-200 flex items-center justify-center text-rose-600">
                        <ShieldAlert className="w-5 h-5" />
                      </div>
                      <div>
                        <div className="flex items-center space-x-2">
                          <span className="text-[11px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-rose-100 text-rose-800 border border-rose-200">
                            ANALYSIS BLOCKED
                          </span>
                          <span className="text-xs text-rose-600 font-semibold">Strict Table Boundary Enforced</span>
                        </div>
                        <h3 className="text-sm font-bold text-gray-900 mt-1">
                          Your question requires additional dataset tables.
                        </h3>
                      </div>
                    </div>
                    <button
                      onClick={() => setBlockedInfo(null)}
                      className="text-gray-400 hover:text-gray-600 text-sm font-bold p-1 cursor-pointer"
                    >
                      ×
                    </button>
                  </div>

                  <div className="bg-gray-50 rounded-lg p-3 border border-gray-200 text-xs text-gray-700">
                    <span className="font-semibold text-gray-900">Question: </span>
                    <span className="italic">"{blockedInfo.question}"</span>
                  </div>

                  <div>
                    <h4 className="text-xs font-bold text-gray-700 uppercase tracking-wider mb-2">
                      Required Dataset Tables:
                    </h4>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      {blockedInfo.required_tables.map((table) => {
                        const isSelected = blockedInfo.selected_tables.map(s => s.toLowerCase()).includes(table.toLowerCase());
                        return (
                          <div
                            key={table}
                            className={`flex items-center justify-between p-2.5 rounded-lg border text-xs ${
                              isSelected
                                ? 'bg-emerald-50/70 border-emerald-200 text-emerald-900'
                                : 'bg-rose-50/80 border-rose-200 text-rose-900 font-medium'
                            }`}
                          >
                            <span className="font-mono font-bold uppercase">{table}</span>
                            <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
                              isSelected
                                ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                                : 'bg-rose-100 text-rose-800 border border-rose-300'
                            }`}>
                              {isSelected ? '✓ Selected' : '✕ Not selected'}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  <div className="text-xs text-gray-700 bg-amber-50/60 border border-amber-200/80 rounded-lg p-3">
                    <p className="font-medium text-amber-900">{blockedInfo.message}</p>
                  </div>

                  {blockedInfo.missing_tables.length > 0 && (
                    <div className="flex items-center justify-end space-x-3 pt-1">
                      <button
                        onClick={() => handleSelectMissingTablesAndResume(blockedInfo.missing_tables)}
                        className="flex items-center space-x-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold shadow-xs transition-colors cursor-pointer"
                      >
                        <span>Select {blockedInfo.missing_tables.map(t => t.toUpperCase()).join(' & ')} & Resume Analysis</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  )}
                </div>
              )}

              {/* Human Approval Required Gate (When approval_status === pending) */}
              {approvalPending && analysisPlan && (
                <ClinicalApprovalCard
                  analysisPlan={analysisPlan}
                  question={currentQuestion}
                  onApprove={handleApprovePlan}
                  onReject={handleRejectPlan}
                  isLoading={isApproving}
                  isRegenerating={isRegenerating}
                  planVersion={planVersion}
                  feedbackHistory={feedbackHistory}
                  elapsedSecs={approveElapsedSecs}
                  errorMessage={errorMessage}
                />
              )}

              {/* Dynamic Plotly Charts Section */}
              <DynamicCharts
                chartSpec={analyticsResult?.chart_spec}
                results={analyticsResult?.results}
                isQuestionMode={isQuestionMode}
                encounterClasses={overview?.encounter_classes}
                monthlyTrends={overview?.monthly_trends}
                topDiagnoses={overview?.top_diagnoses}
                selectedTables={customDashboardData?.selected_tables || selectedTables}
                customTitle={customDashboardData?.chart_title}
                customCategories={customDashboardData?.chart_categories}
                customValues={customDashboardData?.chart_values}
              />

              {/* Clinical Insights and Verified Results */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
                <ClinicalInsightsCard
                  insight={analyticsResult?.insight || customDashboardData?.insight}
                  keyFinding={customDashboardData?.key_finding || peakFindingText}
                  keyFindingValue={customDashboardData?.key_finding_value || peakFindingValue}
                />

                <VerifiedResultsTable
                  results={analyticsResult?.results || (customDashboardData?.verified_results as any) || (overview?.top_diagnoses as any)}
                  title={analyticsResult?.results?.length ? 'Verified Results' : 'Dataset Overview'}
                  badgeText={
                    isQuestionMode
                      ? `${analyticsResult?.results.length ?? 0} Rows Verified`
                      : customDashboardData
                      ? `${customDashboardData.verified_results.length} Rows (${customDashboardData.selected_tables.join('+')})`
                      : `${overview?.top_diagnoses?.length ?? 0} Overview Rows`
                  }
                />
              </div>

              {/* Follow-up Section */}
              <FollowUpSection
                onAskFollowUp={handleFollowUp}
                isLoading={isFollowUpLoading}
              />

              {/* FOLLOW-UP ANSWER CARD (Directly below Follow-Up Section) */}
              <FollowUpAnswerCard
                currentAnswer={followUpAnswer}
                history={followUpHistory}
                workspaceType="clinical"
                isLoading={isFollowUpLoading}
                onClear={() => setFollowUpAnswer(null)}
                onRunNewAnalysis={(q) => handleRunAnalysis(q)}
              />

              {/* Report Generation Section */}
              <ReportTriggerBanner
                onOpenReportReview={() => setIsReportModalOpen(true)}
                title="Generate Clinical PDF Report"
                description="Export a publication-ready PDF report containing clinical diagnosis metrics, visual charts, and verified outcomes for clinical audit."
              />
            </>
          )}

          {/* TAB 2: CLINICAL ANALYTICS (IN-DEPTH) */}
          {activeTab === 'analytics' && (
            <div className="space-y-6">
              <div className="bg-white border border-gray-200/90 rounded-xl p-5 shadow-sm">
                <div className="flex items-center space-x-3 mb-4">
                  <div className="w-9 h-9 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600">
                    <Activity className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-gray-900">Dedicated Clinical Analytics Engine</h3>
                    <p className="text-xs text-gray-500">Formulate inquiries and customize visualization parameters directly from verified datasets</p>
                  </div>
                </div>

                <AskQuestionSection
                  onRunAnalysis={handleRunAnalysis}
                  isLoading={isLoading}
                  defaultQuestion={draftQuestion}
                  onQuestionChange={setDraftQuestion}
                />
              </div>

              {/* ANALYSIS BLOCKED CARD */}
              {blockedInfo && (
                <div className="bg-white border-2 border-rose-300 rounded-xl p-5 shadow-sm space-y-4">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center space-x-3">
                      <div className="w-10 h-10 rounded-lg bg-rose-50 border border-rose-200 flex items-center justify-center text-rose-600">
                        <ShieldAlert className="w-5 h-5" />
                      </div>
                      <div>
                        <div className="flex items-center space-x-2">
                          <span className="text-[11px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-rose-100 text-rose-800 border border-rose-200">
                            ANALYSIS BLOCKED
                          </span>
                          <span className="text-xs text-rose-600 font-semibold">Strict Table Boundary Enforced</span>
                        </div>
                        <h3 className="text-sm font-bold text-gray-900 mt-1">
                          Your question requires additional dataset tables.
                        </h3>
                      </div>
                    </div>
                    <button
                      onClick={() => setBlockedInfo(null)}
                      className="text-gray-400 hover:text-gray-600 text-sm font-bold p-1 cursor-pointer"
                    >
                      ×
                    </button>
                  </div>

                  <div className="bg-gray-50 rounded-lg p-3 border border-gray-200 text-xs text-gray-700">
                    <span className="font-semibold text-gray-900">Question: </span>
                    <span className="italic">"{blockedInfo.question}"</span>
                  </div>

                  <div>
                    <h4 className="text-xs font-bold text-gray-700 uppercase tracking-wider mb-2">
                      Required Dataset Tables:
                    </h4>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      {blockedInfo.required_tables.map((table) => {
                        const isSelected = blockedInfo.selected_tables.map(s => s.toLowerCase()).includes(table.toLowerCase());
                        return (
                          <div
                            key={table}
                            className={`flex items-center justify-between p-2.5 rounded-lg border text-xs ${
                              isSelected
                                ? 'bg-emerald-50/70 border-emerald-200 text-emerald-900'
                                : 'bg-rose-50/80 border-rose-200 text-rose-900 font-medium'
                            }`}
                          >
                            <span className="font-mono font-bold uppercase">{table}</span>
                            <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
                              isSelected
                                ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                                : 'bg-rose-100 text-rose-800 border border-rose-300'
                            }`}>
                              {isSelected ? '✓ Selected' : '✕ Not selected'}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  <div className="text-xs text-gray-700 bg-amber-50/60 border border-amber-200/80 rounded-lg p-3">
                    <p className="font-medium text-amber-900">{blockedInfo.message}</p>
                  </div>

                  {blockedInfo.missing_tables.length > 0 && (
                    <div className="flex items-center justify-end space-x-3 pt-1">
                      <button
                        onClick={() => handleSelectMissingTablesAndResume(blockedInfo.missing_tables)}
                        className="flex items-center space-x-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold shadow-xs transition-colors cursor-pointer"
                      >
                        <span>Select {blockedInfo.missing_tables.map(t => t.toUpperCase()).join(' & ')} & Resume Analysis</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  )}
                </div>
              )}

              {approvalPending && analysisPlan && (
                <ClinicalApprovalCard
                  analysisPlan={analysisPlan}
                  question={currentQuestion}
                  onApprove={handleApprovePlan}
                  onReject={handleRejectPlan}
                  isLoading={isApproving}
                  isRegenerating={isRegenerating}
                  planVersion={planVersion}
                  feedbackHistory={feedbackHistory}
                  elapsedSecs={approveElapsedSecs}
                  errorMessage={errorMessage}
                />
              )}

              {/* Dynamic Analytics Charts */}
              <DynamicCharts
                chartSpec={analyticsResult?.chart_spec}
                results={analyticsResult?.results}
                isQuestionMode={isQuestionMode}
                encounterClasses={overview?.encounter_classes}
                monthlyTrends={overview?.monthly_trends}
                topDiagnoses={overview?.top_diagnoses}
                selectedTables={selectedTables}
                customTitle={customDashboardData?.chart_title}
                customCategories={customDashboardData?.chart_categories}
                customValues={customDashboardData?.chart_values}
              />

              {/* Verified Results Table */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2">
                  <VerifiedResultsTable
                    results={analyticsResult?.results || (overview?.top_diagnoses as any)}
                    title={analyticsResult?.results?.length ? 'Verified Results' : 'Dataset Overview'}
                    badgeText={analyticsResult?.results?.length ? 'Verified Outcomes' : 'Overview Snapshot'}
                  />
                </div>
                <div>
                  <ClinicalInsightsCard
                    insight={analyticsResult?.insight}
                    keyFinding={peakFindingText}
                    keyFindingValue={peakFindingValue}
                  />
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: QUESTIONS & QUERIES LIBRARY */}
          {activeTab === 'queries' && (
            <div className="space-y-6">
              <div className="bg-white border border-gray-200/90 rounded-xl p-5 shadow-sm">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center space-x-3">
                    <div className="w-9 h-9 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600">
                      <MessageSquare className="w-5 h-5" />
                    </div>
                    <div>
                      <h3 className="text-sm font-bold text-gray-900">Standard Clinical Question Library</h3>
                      <p className="text-xs text-gray-500">Pre-approved clinical inquiries tested for AST safety and statistical significance</p>
                    </div>
                  </div>
                  <span className="text-xs px-2.5 py-1 rounded-full bg-indigo-50 text-indigo-700 font-semibold border border-indigo-100">
                    {prebuiltQueries.length} Standard Questions
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {prebuiltQueries.map((pq, idx) => (
                    <div key={idx} className="border border-gray-200 rounded-xl p-4 bg-gray-50/50 hover:bg-white hover:border-indigo-200 transition-all flex flex-col justify-between space-y-3">
                      <div>
                        <div className="flex items-center justify-between">
                          <span className="text-[10px] font-bold text-indigo-600 uppercase tracking-wider bg-indigo-50 px-2 py-0.5 rounded">
                            {pq.category}
                          </span>
                        </div>
                        <h4 className="text-sm font-bold text-gray-900 mt-2">{pq.title}</h4>
                        <p className="text-xs text-gray-600 mt-1 font-mono bg-white p-2 rounded border border-gray-100">
                          "{pq.question}"
                        </p>
                        <p className="text-[11px] text-gray-500 mt-2">{pq.desc}</p>
                      </div>

                      <button
                        onClick={() => {
                          setActiveTab('dashboard');
                          handleRunAnalysis(pq.question);
                        }}
                        className="w-full flex items-center justify-center space-x-1.5 py-2 px-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold shadow-xs transition-colors cursor-pointer"
                      >
                        <span>Execute Question</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* TAB 4: PATIENT TRENDS */}
          {activeTab === 'trends' && (
            <div className="space-y-6">
              <ClinicalMetricsRow
                totalPatients={overview?.total_patients ?? 0}
                totalEncounters={overview?.total_encounters ?? 0}
                avgLos={overview?.avg_length_of_stay ?? '—'}
                readmissionRate={overview?.readmission_rate ?? 0}
                dataQualityStatus={overview?.data_quality_status ?? 'Not assessed'}
                datasetStatus={overview?.organization_dataset ?? 'Unavailable'}
              />

              <DynamicCharts
                isQuestionMode={false}
                encounterClasses={overview?.encounter_classes}
                monthlyTrends={overview?.monthly_trends}
              />

              <div className="bg-white border border-gray-200/90 rounded-xl p-5 shadow-sm">
                <h3 className="text-sm font-bold text-gray-900 mb-3">Encounter Volume Breakdown by Clinical Department</h3>
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3">
                  {overview?.encounter_classes && Object.entries(overview.encounter_classes).map(([cls, count]) => (
                    <div key={cls} className="bg-gray-50 p-3 rounded-lg border border-gray-100 text-center">
                      <span className="text-[10px] uppercase font-bold text-gray-500 block truncate">{cls}</span>
                      <span className="text-lg font-bold text-gray-900 mt-1 block">{count.toLocaleString()}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* TAB 6: ANALYSIS HISTORY */}
          {activeTab === 'history' && (
            <div className="bg-white border border-gray-200/90 rounded-xl p-5 shadow-sm space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-2 border-b border-gray-100">
                <div className="flex items-center space-x-3">
                  <div className="w-9 h-9 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 shadow-2xs">
                    <History className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-gray-900">Analysis & Follow-Up Inquiry Log</h3>
                    <p className="text-xs text-gray-500">Historical record of human approvals, primary analyses, and verified follow-up answers</p>
                  </div>
                </div>

                {/* Filter Pills */}
                <div className="flex items-center space-x-1 bg-gray-100/80 p-1 rounded-lg border border-gray-200/60 text-xs">
                  <button
                    type="button"
                    onClick={() => setHistoryFilter('all')}
                    className={`px-2.5 py-1 rounded-md font-semibold transition-colors cursor-pointer ${
                      historyFilter === 'all'
                        ? 'bg-white text-indigo-700 shadow-2xs'
                        : 'text-gray-600 hover:text-gray-900'
                    }`}
                  >
                    All ({queryHistory.length})
                  </button>
                  <button
                    type="button"
                    onClick={() => setHistoryFilter('analysis')}
                    className={`px-2.5 py-1 rounded-md font-semibold transition-colors cursor-pointer ${
                      historyFilter === 'analysis'
                        ? 'bg-white text-indigo-700 shadow-2xs'
                        : 'text-gray-600 hover:text-gray-900'
                    }`}
                  >
                    Primary ({queryHistory.filter((q) => q.type === 'analysis').length})
                  </button>
                  <button
                    type="button"
                    onClick={() => setHistoryFilter('followup')}
                    className={`px-2.5 py-1 rounded-md font-semibold transition-colors cursor-pointer ${
                      historyFilter === 'followup'
                        ? 'bg-white text-[#4F46E5] shadow-2xs'
                        : 'text-gray-600 hover:text-gray-900'
                    }`}
                  >
                    Follow-Ups ({queryHistory.filter((q) => q.type === 'followup').length})
                  </button>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-gray-50 text-gray-500 uppercase text-[10px] font-bold border-y border-gray-200">
                    <tr>
                      <th className="py-2.5 px-4">Timestamp</th>
                      <th className="py-2.5 px-4">Type</th>
                      <th className="py-2.5 px-4">Clinical Question</th>
                      <th className="py-2.5 px-4">Generated Answer / Outcome</th>
                      <th className="py-2.5 px-4">Validation Status</th>
                      <th className="py-2.5 px-4 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {queryHistory
                      .filter((item) => historyFilter === 'all' || item.type === historyFilter)
                      .map((item, idx) => {
                        const isExpanded = expandedAnswerIdx === idx;
                        const isFollowUp = item.type === 'followup';
                        return (
                          <tr key={idx} className="hover:bg-gray-50/60 transition-colors">
                            <td className="py-3 px-4 font-mono text-gray-500 whitespace-nowrap align-top">
                              {item.timestamp}
                            </td>
                            <td className="py-3 px-4 whitespace-nowrap align-top">
                              {isFollowUp ? (
                                <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-[#EEF2FF] text-[#4F46E5] border border-[#C7D2FE]">
                                  <Sparkles className="w-3 h-3 text-[#4F46E5]" />
                                  <span>Follow-Up</span>
                                </span>
                              ) : (
                                <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-indigo-50 text-indigo-700 border border-indigo-200">
                                  <Activity className="w-3 h-3 text-indigo-600" />
                                  <span>Primary</span>
                                </span>
                              )}
                            </td>
                            <td className="py-3 px-4 font-semibold text-gray-900 max-w-[200px] align-top">
                              "{item.question}"
                            </td>
                            <td className="py-3 px-4 text-gray-700 max-w-[340px] align-top">
                              {item.answer ? (
                                <div className="space-y-1">
                                  <div className={`bg-gray-50 p-2 rounded-lg border border-gray-200/70 text-xs text-gray-800 ${
                                    isExpanded ? 'whitespace-pre-wrap' : 'line-clamp-2'
                                  }`}>
                                    {item.answer}
                                  </div>
                                  <button
                                    type="button"
                                    onClick={() => setExpandedAnswerIdx(isExpanded ? null : idx)}
                                    className="text-[10px] font-bold text-indigo-600 hover:text-indigo-800 transition-colors cursor-pointer"
                                  >
                                    {isExpanded ? 'Collapse Answer ▲' : 'View Full Generated Answer ▼'}
                                  </button>
                                </div>
                              ) : (
                                <span className="text-gray-400 font-mono text-[11px]">{item.rows} rows returned</span>
                              )}
                            </td>
                            <td className="py-3 px-4 whitespace-nowrap align-top">
                              <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                                <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                                <span>{item.status}</span>
                              </span>
                            </td>
                            <td className="py-3 px-4 text-right whitespace-nowrap align-top">
                              <button
                                type="button"
                                onClick={() => {
                                  setActiveTab('dashboard');
                                  if (isFollowUp) {
                                    handleFollowUp(item.question);
                                  } else {
                                    handleRunAnalysis(item.question);
                                  }
                                }}
                                className="text-xs text-indigo-600 hover:text-indigo-800 font-semibold cursor-pointer"
                              >
                                {isFollowUp ? 'Ask Again' : 'Re-run'}
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* TAB 7: CLINICAL REPORTS */}
          {activeTab === 'reports' && (
            <ReportHistory onGenerate={() => setIsReportModalOpen(true)} refreshKey={reportHistoryRefreshKey} />
          )}

          {/* TAB 8: SETTINGS */}
          {activeTab === 'settings' && (
            <div className="bg-white border border-gray-200/90 rounded-xl p-6 shadow-sm space-y-6">
              <div>
                <h3 className="text-base font-bold text-gray-900">Clinical Organization Settings</h3>
                <p className="text-xs text-gray-500">Dataset connections, audit configuration, and ingestion controls</p>
              </div>

              <div className="space-y-4 text-xs">
                <div className="border border-gray-200 rounded-xl p-4 flex items-center justify-between">
                  <div>
                    <h4 className="font-bold text-gray-800">Organization EHR Dataset</h4>
                    <p className="text-gray-500 mt-0.5">Active repository: {overview?.dataset_name || "Organization EHR Dataset"}</p>
                  </div>
                  <button
                    onClick={() => setIsUploadModalOpen(true)}
                    className="flex items-center space-x-1.5 px-3 py-1.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 rounded-lg font-semibold cursor-pointer"
                  >
                    <UploadCloud className="w-4 h-4" />
                    <span>Upload New Dataset</span>
                  </button>
                </div>

                <div className="border border-gray-200 rounded-xl p-4 space-y-2">
                  <h4 className="font-bold text-gray-800">Clinical Analysis Guardrails</h4>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-gray-600 pt-1">
                    <div className="p-2.5 bg-gray-50 rounded-lg border border-gray-100">
                      <span className="font-semibold block text-gray-800">Inpatient LOS Filter:</span>
                      <span>DATEDIFF(STOP, START) strictly between 0 and 30 days</span>
                    </div>
                    <div className="p-2.5 bg-gray-50 rounded-lg border border-gray-100">
                      <span className="font-semibold block text-gray-800">Readmission Horizon:</span>
                      <span>30-Day return encounter window</span>
                    </div>
                    <div className="p-2.5 bg-gray-50 rounded-lg border border-gray-100">
                      <span className="font-semibold block text-gray-800">AST SQL Policy:</span>
                      <span>SELECT only, no modifications or drops permitted</span>
                    </div>
                    <div className="p-2.5 bg-gray-50 rounded-lg border border-gray-100">
                      <span className="font-semibold block text-gray-800">Human Approval Gate:</span>
                      <span>Enforced on Node 5 before any database execution</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </main>
      </div>

      {/* Report review modal */}
      <ReportModal
        isOpen={isReportModalOpen}
        onAcknowledged={() => setReportHistoryRefreshKey((value) => value + 1)}
        onClose={() => setIsReportModalOpen(false)}
        question={currentQuestion}
        analysisPlan={analyticsResult?.analysis_plan || analysisPlan}
        insight={analyticsResult?.insight}
        results={analyticsResult?.results || []}
        sqlQuery={analyticsResult?.sql_query}
        workspaceType="clinical"
        selectedTables={selectedTables}
        followUpAnswers={followUpHistory}
        datasetName={overview?.dataset_name}
        analysisRunId={analysisIdentity.analysis_id}
      />

      {/* Dataset Upload Modal */}
      <DatasetUploadModal
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        onUploadSuccess={() => {
          fetchData();
        }}
      />
    </div>
  );
};

export default ClinicalDashboard;
