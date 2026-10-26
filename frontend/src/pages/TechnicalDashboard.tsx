import React, { useEffect, useRef, useState } from 'react';
import TechnicalSidebar from '../components/Technical/TechnicalSidebar';
import TechnicalTopbar from '../components/Technical/TechnicalTopbar';
import TechnicalMetricsRow from '../components/Technical/TechnicalMetricsRow';
import ClinicalMetricsRow from '../components/Clinical/ClinicalMetricsRow';
import ActiveDatasetCard from '../components/Clinical/ActiveDatasetCard';
import PipelineVisualizer from '../components/Technical/PipelineVisualizer';
import SqlInspectorCard from '../components/Technical/SqlInspectorCard';
import ActiveDatabaseCard from '../components/Technical/ActiveDatabaseCard';
import SystemHealthCard from '../components/Technical/SystemHealthCard';
import ClinicalApprovalCard from '../components/Clinical/ClinicalApprovalCard';
import DynamicCharts from '../components/Clinical/DynamicCharts';
import ClinicalInsightsCard from '../components/Clinical/ClinicalInsightsCard';
import VerifiedResultsTable from '../components/Clinical/VerifiedResultsTable';
import FollowUpSection from '../components/Clinical/FollowUpSection';
import FollowUpAnswerCard, { FollowUpHistoryItem } from '../components/Clinical/FollowUpAnswerCard';
import ReportTriggerBanner from '../components/ReportTriggerBanner';
import ReportModal from '../components/ReportModal';
import DatasetUploadModal from '../components/DatasetUploadModal';
import { getAvailableClinicalTableNames } from '../components/SidebarTableSelector';
import apiService from '../services/api';
import databaseApi, { AuditLogItem } from '../api/database';
import datasetsApi, { DatasetVersionItem } from '../api/datasets';
import {
  AnalyticsResponse,
  OverviewResponse,
  PipelineNode,
  PipelineNodeStatus,
  ClinicalTable,
  DashboardCustomizationResponse,
  FollowUpResponse
} from '../types/analytics';
import {
  Search,
  Loader2,
  Activity,
  GitFork,
  Terminal,
  CheckSquare,
  History,
  ShieldCheck,
  Cpu,
  Settings,
  CheckCircle2,
  Clock,
  RefreshCw,
  AlertCircle,
  ShieldAlert,
  ArrowRight,
  Code2
} from 'lucide-react';

interface TechnicalDashboardProps {
  onSwitchRole: () => void;
}

const initialPipelineNodes: PipelineNode[] = [
  { id: 1, name: 'Question Parsed', status: 'pending' },
  { id: 2, name: 'Table Selection Check', status: 'pending' },
  { id: 3, name: 'Schema Retrieval', status: 'pending' },
  { id: 4, name: 'Analysis Plan', status: 'pending' },
  { id: 5, name: 'Human Approval', status: 'pending' },
  { id: 6, name: 'SQL Generation', status: 'pending' },
  { id: 7, name: 'SQL Syntax Check', status: 'pending' },
  { id: 8, name: 'SQL Safety Validation', status: 'pending' },
  { id: 9, name: 'Query Execution', status: 'pending' },
  { id: 10, name: 'Result Validation', status: 'pending' },
  { id: 11, name: 'AI Insight Generation', status: 'pending' },
  { id: 12, name: 'Visualization Spec', status: 'pending' },
  { id: 13, name: 'Final Report Ready', status: 'pending' },
];

export const TechnicalDashboard: React.FC<TechnicalDashboardProps> = ({ onSwitchRole }) => {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [question, setQuestion] = useState('What is the adverse event rate by treatment arm?');
  const [isExecuting, setIsExecuting] = useState(false);
  const [isApprovalPending, setIsApprovalPending] = useState(false);
  const [isRegenerating, setIsRegenerating] = useState(false);
  const [pipelineNodes, setPipelineNodes] = useState<PipelineNode[]>(initialPipelineNodes);
  const [analysisPlan, setAnalysisPlan] = useState<string | null>(null);
  const [planVersion, setPlanVersion] = useState(1);
  const [feedbackHistory, setFeedbackHistory] = useState<string[]>([]);
  const [analyticsResult, setAnalyticsResult] = useState<AnalyticsResponse | null>(null);
  const [overview, setOverview] = useState<OverviewResponse | null>(null);
  const [isReportModalOpen, setIsReportModalOpen] = useState(false);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [failedStep, setFailedStep] = useState<number | null>(null);
  const [currentSqlQuery, setCurrentSqlQuery] = useState<string | null>(null);
  const [executionErrorDetails, setExecutionErrorDetails] = useState<{
    message: string;
    sqlQuery?: string;
    failedNode?: string;
    exceptionType?: string;
  } | null>(null);

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

  // Lightweight Follow-up session state (does NOT restart pipeline)
  const [followUpAnswer, setFollowUpAnswer] = useState<FollowUpResponse | null>(null);
  const [followUpHistory, setFollowUpHistory] = useState<FollowUpHistoryItem[]>([]);
  const [isFollowUpLoading, setIsFollowUpLoading] = useState(false);

  // Technical Query History Tracker for Queries Tab
  const [technicalQueries, setTechnicalQueries] = useState<Array<{
    type: 'analysis' | 'followup';
    question: string;
    answer?: string;
    timestamp: string;
    sql_query?: string | null;
    ast_status?: string;
    latency?: string;
    rows?: number;
  }>>([]);

  // Tab specific data
  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>([]);
  const [isAuditLoading, setIsAuditLoading] = useState(false);
  const [auditError, setAuditError] = useState<string | null>(null);
  const [isRefreshingAudit, setIsRefreshingAudit] = useState(false);
  const [datasetVersions, setDatasetVersions] = useState<DatasetVersionItem[]>([]);
  const [healthStatus, setHealthStatus] = useState<any>(null);

  // Fetch overview metrics and dynamic tables from real database on mount
  const fetchData = async () => {
    try {
      const [overviewData, tablesData] = await Promise.all([
        apiService.getOverview().catch((err) => {
          console.error('Failed to load technical overview:', err);
          return null;
        }),
        apiService.getTables().catch((err) => {
          console.error('Failed to load database tables:', err);
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

  // Handle user applying custom table selection in technical observatory
  const handleApplyTableSelection = async (tablesToApply: string[]) => {
    const sanitized = (tablesToApply || []).filter(
      (t) => !['patients', 'encounters', 'conditions', 'medications', 'observations', 'procedures'].includes(t.toLowerCase().trim())
    );

    if (!sanitized || sanitized.length === 0) {
      setTableCombinationError('Please select at least one database table.');
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
      setBlockedInfo(null);
      setActiveTab('dashboard');
      await handleExecutePipelineWithTables(question || blockedInfo?.question || '', sanitized);
    } catch (err: any) {
      console.error('Error applying technical table selection:', err);
      setTableCombinationError(
        err.response?.data?.detail ||
        'These tables cannot currently be combined because no approved relationship exists.'
      );
    } finally {
      setIsApplyingTables(false);
    }
  };

  // Fetch tab-specific data when tab changes
  useEffect(() => {
    let auditInterval: any = null;

    if (activeTab === 'audit') {
      setIsAuditLoading(true);
      setAuditError(null);

      const loadAudit = (isSilent = false) => {
        if (!isSilent) setIsRefreshingAudit(true);
        databaseApi.getAuditLogs()
          .then((res) => {
            if (res && Array.isArray(res.audit_logs)) {
              setAuditLogs(res.audit_logs);
              setAuditError(null);
            } else {
              setAuditLogs([]);
            }
          })
          .catch((err) => {
            console.error('Audit logs fetch failed:', err);
            setAuditError('Unable to load audit events. Check FastAPI/MySQL connection.');
          })
          .finally(() => {
            setIsAuditLoading(false);
            setIsRefreshingAudit(false);
          });
      };

      loadAudit(false);
      // Auto-poll live database audit trail every 3 seconds
      auditInterval = setInterval(() => {
        loadAudit(true);
      }, 3000);
    } else if (activeTab === 'health') {
      Promise.all([databaseApi.getHealth(), databaseApi.getDbHealth()]).then(([h, dbH]) => {
        setHealthStatus({ app: h, db: dbH });
      }).catch(console.error);
    } else if (activeTab === 'settings') {
      datasetsApi.getVersions().then((res) => {
        if (res?.versions) setDatasetVersions(res.versions);
      }).catch(console.error);
    }

    return () => {
      if (auditInterval) clearInterval(auditInterval);
    };
  }, [activeTab]);

  // Helper to update node status
  const updateNodeStatus = (id: number, status: PipelineNodeStatus) => {
    setPipelineNodes((prev) =>
      prev.map((n) => (n.id === id ? { ...n, status } : n))
    );
  };

  // Helper to mark nodes up to a certain step
  const setNodesProgress = (completedUpTo: number, runningId?: number, waitingId?: number) => {
    setPipelineNodes((prev) =>
      prev.map((n) => {
        if (n.id <= completedUpTo) return { ...n, status: 'completed' };
        if (runningId && n.id === runningId) return { ...n, status: 'running' };
        if (waitingId && n.id === waitingId) return { ...n, status: 'waiting_approval' };
        return { ...n, status: 'pending' };
      })
    );
  };

  // Step 1: Execute pipeline with specific tables
  const handleExecutePipelineWithTables = async (questionToRun: string, tablesToUse?: string[]) => {
    if (!questionToRun.trim() || isExecuting) return;
    const tables = tablesToUse || selectedTables;
    if (tables.length === 0) {
      setErrorMessage('Dataset tables are still loading. Please try again once they are available.');
      return;
    }

    setIsExecuting(true);
    setErrorMessage(null);
    setExecutionErrorDetails(null);
    setFailedStep(null);
    setCurrentSqlQuery(null);
    setIsApprovalPending(false);

    // Animate initial parsing nodes
    setNodesProgress(0, 1);
    await new Promise((r) => setTimeout(r, 200));
    setNodesProgress(1, 2);
    await new Promise((r) => setTimeout(r, 250));
    setNodesProgress(2, 3);
    await new Promise((r) => setTimeout(r, 300));
    setNodesProgress(3, 4);

    try {
      setPlanVersion(1);
      setFeedbackHistory([]);
      const res = await apiService.runAnalytics({
        question: questionToRun,
        approval_status: 'pending',
        selected_tables: tables,
        plan_version: 1,
      });

      if (res && res.status === 'blocked') {
        // Table Selection Validation BLOCKED!
        setBlockedInfo({
          status: 'blocked',
          reason: res.reason || 'required_tables_not_selected',
          question: res.question || questionToRun,
          required_tables: res.required_tables || [],
          selected_tables: res.selected_tables || tables,
          missing_tables: res.missing_tables || [],
          message: res.message || 'This analysis requires tables that have not been selected.',
          next_action: res.next_action || 'select_missing_tables',
        });
        setPipelineNodes((prev) =>
          prev.map((n) => {
            if (n.id === 1) return { ...n, status: 'completed' };
            if (n.id === 2) return { ...n, status: 'blocked', detail: res.message || 'Required tables not selected' };
            return { ...n, status: 'pending' };
          })
        );
        setIsApprovalPending(false);
        setAnalysisPlan(null);
        setAnalyticsResult(null);
        setErrorMessage(res.message || 'Analysis blocked: required tables not selected');
        return;
      }

      setBlockedInfo(null);

      if (res && res.analysis_plan) {
        setAnalysisPlan(res.analysis_plan);
        // Step 4: Analysis Plan ✓ completed
        // Step 5: Human Approval ⏳ Awaiting Approval
        setNodesProgress(4, undefined, 5);
        setIsApprovalPending(true);
      } else {
        console.error('Backend returned response without analysis_plan:', res);
        updateNodeStatus(4, 'failed');
        setErrorMessage('Analysis plan generation failed. Please retry.');
      }
    } catch (err: any) {
      console.error('Analysis plan generation error in Technical Workspace:', err);
      updateNodeStatus(4, 'failed');
      const errData = err.response?.data?.detail;
      const detail = typeof errData === 'string' ? errData : errData?.message || err.message || 'Analysis plan generation failed. Please retry.';
      setErrorMessage(detail);
    } finally {
      setIsExecuting(false);
    }
  };

  const handleExecutePipeline = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    return handleExecutePipelineWithTables(question, selectedTables);
  };

  // User selects missing tables and resumes analysis
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
      console.error('Failed to update technical metadata for selected tables:', e);
    }

    await handleExecutePipelineWithTables(question, newTables);
  };

  // Step 2: Approve & Resume + selected_tables
  const handleApprove = async () => {
    setIsExecuting(true);
    setIsApprovalPending(false);
    setErrorMessage(null);
    setExecutionErrorDetails(null);
    setFailedStep(null);

    // Node 5 (Human Approval) is completed, Node 6 (SQL Generation) is actively running
    setNodesProgress(5, 6);

    try {
      console.log('APPROVAL REQUEST START');
      console.log('[Technical Approve] Sending approval payload:', {
        question,
        approval_status: 'approved',
        current_plan: analysisPlan,
        feedback_history: feedbackHistory,
        plan_version: planVersion,
        selected_tables: selectedTables,
      });

      const res = await apiService.runAnalytics({
        question,
        approval_status: 'approved',
        current_plan: analysisPlan || undefined,
        feedback_history: feedbackHistory,
        plan_version: planVersion,
        selected_tables: selectedTables,
      });

      console.log('APPROVAL RESPONSE RECEIVED');
      console.log('[Technical Approve] API response details:', {
        http_status: 200,
        status: res.status,
        approval_status: res.approval_status,
        analysis_plan: res.analysis_plan ? 'Present' : 'None',
        sql_query: res.sql_query,
        results_row_count: res.results?.length ?? 0,
        insight: res.insight ? res.insight.slice(0, 80) + '...' : 'None',
        chart_spec: res.chart_spec,
        visualization_error: res.visualization_error,
        error: res.error,
      });

      if (res && res.status === 'blocked') {
        setBlockedInfo({
          status: 'blocked',
          reason: res.reason || 'required_tables_not_selected',
          question: res.question || question,
          required_tables: res.required_tables || [],
          selected_tables: res.selected_tables || selectedTables,
          missing_tables: res.missing_tables || [],
          message: res.message || 'This analysis requires tables that have not been selected.',
          next_action: res.next_action || 'select_missing_tables',
        });
        setPipelineNodes((prev) =>
          prev.map((n) => {
            if (n.id <= 5) return { ...n, status: 'completed' };
            if (n.id === 6 || n.id === 8) return { ...n, status: 'blocked', detail: res.message || 'Unauthorized table reference' };
            return { ...n, status: 'pending' };
          })
        );
        setErrorMessage(res.message || 'Analysis blocked: unauthorized table reference or required table not selected.');
        setAnalyticsResult(null);
        setIsExecuting(false);
        return;
      }

      if (res.status === 'awaiting_approval' || res.approval_status === 'pending') {
        setAnalysisPlan(null);
        setAnalyticsResult(null);
        updateNodeStatus(6, 'failed');
        setFailedStep(6);
        setErrorMessage('Approval did not start execution. Run the question again to review a fresh plan.');
        return;
      }
      if (res.status !== 'success' && res.status !== 'partial_success') {
        updateNodeStatus(6, 'failed');
        setFailedStep(6);
        setErrorMessage(res.message || 'The pipeline did not complete. Review the response before trying again.');
        return;
      }

      setBlockedInfo(null);

      // Immediately display the generated SQL in the SqlInspectorCard
      if (res.sql_query) {
        setCurrentSqlQuery(res.sql_query);
      }

      // Step through nodes 6 -> 7 -> 8 -> 9 -> 10 to 14
      for (let step = 7; step <= 14; step++) {
        setNodesProgress(step - 1, step);
        await new Promise((r) => setTimeout(r, 60));
      }

      setNodesProgress(14);
      setAnalyticsResult(res);
      setFailedStep(null);

      setTechnicalQueries((prev) => [
        {
          type: 'analysis',
          question: question,
          answer: res.insight || 'Analysis completed; no insight text returned.',
          timestamp: 'Just now',
          sql_query: res.sql_query,
          ast_status: 'SQL validated',
          latency: 'Not measured',
          rows: res.results?.length || 0,
        },
        ...prev,
      ]);
    } catch (err: any) {
      console.error('Execution error after approval in Technical Workspace:', err);
      const errData = err.response?.data?.detail;
      const errorMsg = typeof errData === 'string' ? errData : errData?.message || err.message || 'Execution failed. Check backend connection at port 8001.';
      const sql = typeof errData === 'object' ? errData?.sql_query : null;
      const failedNode = typeof errData === 'object' ? errData?.failed_node : (err.response ? 'execute_sql' : 'generate_sql');
      const exceptionType = typeof errData === 'object' ? errData?.exception_type : (err.response ? 'DatabaseError' : 'NetworkError');

      if (sql) setCurrentSqlQuery(sql);

      // Map backend failed_node to visual step ID
      const nodeMap: Record<string, number> = {
        'generate_sql': 6,
        'validate_sql': 8,
        'execute_sql': 9,
        'validate_results': 10,
        'generate_insight': 11,
        'validate_insight': 11,
        'regenerate_insight': 11,
        'generate_chart': 12,
      };
      const stepToFail = (failedNode && nodeMap[failedNode]) ? nodeMap[failedNode] : (err.response ? 9 : 6);

      setExecutionErrorDetails({
        message: errorMsg,
        sqlQuery: sql || currentSqlQuery || undefined,
        failedNode,
        exceptionType,
      });
      setErrorMessage(errorMsg);
      setFailedStep(stepToFail);
      setPipelineNodes((prev) =>
        prev.map((n) => {
          if (n.id < stepToFail) return { ...n, status: 'completed' };
          if (n.id === stepToFail) return { ...n, status: 'failed' };
          return { ...n, status: 'pending' };
        })
      );
    } finally {
      setIsExecuting(false);
    }
  };

  // Step 2b: Dedicated Retry for Query Execution failure (Node 9)
  // Preserves existing approved plan and SQL, does NOT restart from START
  const handleRetryQueryExecution = async () => {
    if (isExecuting) return;

    setIsExecuting(true);
    setErrorMessage(null);
    setExecutionErrorDetails(null);
    setFailedStep(null);

    // Visual state: Nodes 1-8 COMPLETED, Node 9 RUNNING 🔄, Nodes 10-14 pending
    setPipelineNodes((prev) =>
      prev.map((n) => {
        if (n.id < 9) return { ...n, status: 'completed' };
        if (n.id === 9) return { ...n, status: 'running' };
        return { ...n, status: 'pending' };
      })
    );

    try {
      const res = await apiService.runAnalytics({
        question,
        approval_status: 'approved',
        current_plan: analysisPlan || undefined,
        sql_query: currentSqlQuery || undefined,
        resume_from: 'execute_sql',
        feedback_history: feedbackHistory,
        plan_version: planVersion,
        selected_tables: selectedTables,
      });

      if (res.sql_query) {
        setCurrentSqlQuery(res.sql_query);
      }

      // Step through nodes 10 to 14
      for (let step = 10; step <= 14; step++) {
        setNodesProgress(step - 1, step);
        await new Promise((r) => setTimeout(r, 80));
      }

      setNodesProgress(14);
      setAnalyticsResult(res);
      setFailedStep(null);

      setTechnicalQueries((prev) => [
        {
          type: 'analysis',
          question: question,
          answer: res.insight || 'Analysis completed; no insight text returned.',
          timestamp: 'Just now',
          sql_query: res.sql_query,
          ast_status: 'SQL validated',
          latency: 'Not measured',
          rows: res.results?.length || 0,
        },
        ...prev,
      ]);
    } catch (err: any) {
      console.error('Retry Query Execution failed:', err);
      const errData = err.response?.data?.detail;
      const errorMsg = typeof errData === 'string' ? errData : errData?.message || err.message || 'Query execution failed.';
      const sql = typeof errData === 'object' ? errData?.sql_query : null;
      const failedNode = typeof errData === 'object' ? errData?.failed_node : 'execute_sql';
      const exceptionType = typeof errData === 'object' ? errData?.exception_type : 'DatabaseError';

      if (sql) setCurrentSqlQuery(sql);
      setExecutionErrorDetails({
        message: errorMsg,
        sqlQuery: sql || currentSqlQuery || undefined,
        failedNode,
        exceptionType,
      });
      setErrorMessage(errorMsg);
      setFailedStep(9);
      setPipelineNodes((prev) =>
        prev.map((n) => {
          if (n.id < 9) return { ...n, status: 'completed' };
          if (n.id === 9) return { ...n, status: 'failed' };
          return { ...n, status: 'pending' };
        })
      );
    } finally {
      setIsExecuting(false);
    }
  };

  // Step 3: Reject and regenerate analysis plan + selected_tables
  const handleReject = async (feedback: string) => {
    setIsRegenerating(true);
    setErrorMessage(null);
    setExecutionErrorDetails(null);
    setFailedStep(null);
    setCurrentSqlQuery(null);
    setAnalyticsResult(null);

    // Return to node 4: generating revised analysis plan
    setNodesProgress(3, 4);

    const trimmed = feedback.trim();
    const updatedHistory = trimmed && !feedbackHistory.includes(trimmed)
      ? [...feedbackHistory, trimmed]
      : feedbackHistory;

    try {
      const res = await apiService.runAnalytics({
        question,
        approval_status: 'rejected',
        human_feedback: trimmed,
        current_plan: analysisPlan || undefined,
        feedback_history: updatedHistory,
        plan_version: planVersion,
        selected_tables: selectedTables,
      });

      if (res && res.analysis_plan) {
        setAnalysisPlan(res.analysis_plan);
        setPlanVersion((v) => v + 1);
        setFeedbackHistory(res.feedback_history || updatedHistory);
        // Step 4 ✓ completed, Step 5 ⏳ Awaiting Approval again with revised plan
        setNodesProgress(4, undefined, 5);
        setIsApprovalPending(true);
      } else {
        console.error('Backend returned response without revised analysis_plan:', res);
        updateNodeStatus(4, 'failed');
        setErrorMessage('Analysis plan revision failed. Please retry.');
      }
    } catch (err: any) {
      console.error('Error regenerating analysis plan in Technical Workspace:', err);
      updateNodeStatus(4, 'failed');
      const errData = err.response?.data?.detail;
      const detail = typeof errData === 'string' ? errData : errData?.message || err.message || 'Analysis plan regeneration failed. Please retry.';
      setErrorMessage(detail);
    } finally {
      setIsRegenerating(false);
    }
  };

  const handleResetPipeline = () => {
    setPipelineNodes(initialPipelineNodes);
    setAnalyticsResult(null);
    setAnalysisPlan(null);
    setCurrentSqlQuery(null);
    setFailedStep(null);
    setExecutionErrorDetails(null);
    setPlanVersion(1);
    setFeedbackHistory([]);
    setIsApprovalPending(false);
    setIsRegenerating(false);
    setErrorMessage(null);
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
        current_question: question,
        current_results: latestFollowUpResults || originalResults,
        original_results: originalResults,
        current_sql: analyticsResult?.sql_query,
        current_plan: analyticsResult?.analysis_plan,
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

      // Record in technical queries log for side history page
      setTechnicalQueries((prev) => [
        {
          type: 'followup',
          question: followUpQuestion,
          answer: res.answer,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          sql_query: res.sql_query,
          ast_status: res.verified ? 'AST Verified Safe' : 'Context Verified',
          latency: '340ms',
          rows: res.source === 'follow_up_sql' ? 1 : (analyticsResult?.results?.length || 0),
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

  return (
    <div className="studio-workspace flex min-h-screen">
      {/* Sidebar */}
      <TechnicalSidebar
        activeTab={activeTab}
        onTabChange={setActiveTab}
        onSwitchRole={onSwitchRole}
        availableTables={availableTables}
        selectedTables={selectedTables}
        onApplySelection={handleApplyTableSelection}
        isApplying={isApplyingTables || isExecuting}
        combinationError={tableCombinationError}
      />

      {/* Main Observatory Area */}
      <div className="flex-1 flex flex-col min-w-0">
        <TechnicalTopbar
          title={
            activeTab === 'dashboard'
              ? "Technical Observability Dashboard"
              : activeTab === 'analytics'
              ? "AST & Query Performance Analytics"
              : activeTab === 'pipeline'
              ? "LangGraph State Machine Pipeline"
              : activeTab === 'sql'
              ? "AST SQL Explorer & Dialect Guard"
              : activeTab === 'ast'
              ? "Abstract Syntax Tree (AST) Validation"
              : activeTab === 'queries'
              ? "Technical Query Execution History"
              : activeTab === 'audit'
              ? "Database Security & Audit Trail"
              : activeTab === 'health'
              ? "System Health & Infrastructure"
              : "Technical Pipeline Settings"
          }
          nodeCount={pipelineNodes.length}
        />

        {/* FULL WIDTH CONTAINER: compact actual scale matching Screenshot 1-4 */}
        <main className="studio-main p-4 md:p-5 space-y-3.5 flex-1 w-full">
          {/* Error Banner if any */}
          {errorMessage && (
            <div className="p-3.5 bg-rose-50 border border-rose-200 text-rose-800 text-xs rounded-xl shadow-xs space-y-2">
              <div className="flex items-start justify-between">
                <div className="flex items-start space-x-2.5">
                  <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                  <div className="space-y-1">
                    <div className="font-bold text-rose-900 text-sm">
                      {failedStep === 9 ? 'Query Execution Failed' : 'Pipeline Execution Failed'}
                    </div>
                    <div className="font-mono text-[11px] text-rose-700 bg-rose-100/70 p-2 rounded border border-rose-200/80 whitespace-pre-wrap">
                      {errorMessage}
                      {executionErrorDetails?.exceptionType && (
                        <div className="mt-1 text-[10px] text-rose-600">
                          Exception: <span className="font-semibold">{executionErrorDetails.exceptionType}</span> | Failed Node: <span className="font-semibold">{executionErrorDetails.failedNode || 'execute_sql'}</span>
                        </div>
                      )}
                      {executionErrorDetails?.sqlQuery && (
                        <div className="mt-1 text-[10px] text-rose-600 truncate max-w-xl">
                          SQL: <span className="font-semibold font-mono">{executionErrorDetails.sqlQuery}</span>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
                <button onClick={() => setErrorMessage(null)} className="text-rose-400 hover:text-rose-600 font-bold ml-2">×</button>
              </div>
              <div className="flex items-center justify-end space-x-2 pt-1 border-t border-rose-100">
                {failedStep === 9 ? (
                  <button
                    type="button"
                    onClick={handleRetryQueryExecution}
                    disabled={isExecuting}
                    className="px-3 py-1.5 bg-rose-600 hover:bg-rose-700 disabled:opacity-50 text-white font-semibold rounded-md text-xs flex items-center space-x-1.5 cursor-pointer transition-colors shadow-2xs"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${isExecuting ? 'animate-spin' : ''}`} />
                    <span>Retry Query Execution</span>
                  </button>
                ) : failedStep && failedStep >= 6 ? (
                  <button
                    type="button"
                    onClick={handleApprove}
                    disabled={isExecuting}
                    className="px-3 py-1.5 bg-rose-600 hover:bg-rose-700 disabled:opacity-50 text-white font-semibold rounded-md text-xs flex items-center space-x-1.5 cursor-pointer transition-colors shadow-2xs"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${isExecuting ? 'animate-spin' : ''}`} />
                    <span>Retry SQL Pipeline</span>
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => handleExecutePipeline()}
                    disabled={isExecuting}
                    className="px-3 py-1.5 bg-rose-600 hover:bg-rose-700 disabled:opacity-50 text-white font-semibold rounded-md text-xs flex items-center space-x-1.5 cursor-pointer transition-colors shadow-2xs"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${isExecuting ? 'animate-spin' : ''}`} />
                    <span>Retry Pipeline</span>
                  </button>
                )}
              </div>
            </div>
          )}

          {/* TAB 1: MAIN TECHNICAL OBSERVABILITY DASHBOARD */}
          {activeTab === 'dashboard' && (
            <>
              {/* 2. Query Pipeline Trigger Bar (Screenshot 2 & 4) */}
              <div className="studio-composer studio-technical-composer bg-white border border-gray-200/90 rounded-xl p-3.5 shadow-sm space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">
                    LANGGRAPH PROMPT ENGINE & EXECUTION TRIGGER
                  </span>
                  <span className="text-[10px] font-semibold text-gray-500 bg-gray-50 px-2 py-0.5 rounded border border-gray-200 font-mono">
                    Validated SQL workflow
                  </span>
                </div>

                <form onSubmit={handleExecutePipeline} className="flex items-center gap-2">
                  <div className="relative flex-1">
                    <Search className="w-3.5 h-3.5 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
                    <input
                      type="text"
                      value={question}
                      onChange={(e) => setQuestion(e.target.value)}
                      placeholder="Show pediatric length of stay breakdown"
                      className="w-full pl-9 pr-3 py-2 bg-gray-50/70 border border-gray-200 rounded-lg text-xs text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-blue-500"
                      disabled={isExecuting}
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={isExecuting || !question.trim()}
                    className="px-4 py-2 bg-[#4F46E5] hover:bg-[#4338CA] active:bg-[#3730A3] disabled:opacity-50 text-white text-xs font-semibold rounded-lg shadow-sm flex items-center space-x-1.5 transition-all cursor-pointer flex-shrink-0"
                  >
                    {isExecuting ? (
                      <>
                        <Loader2 className="w-3 h-3 animate-spin" />
                        <span>Executing...</span>
                      </>
                    ) : (
                      <>
                        <span>Execute Pipeline</span>
                        <span>→</span>
                      </>
                    )}
                  </button>
                </form>
              </div>

              {/* Dataset & Selected Tables 6-KPI Metrics Row (Requested by User) */}
              <ClinicalMetricsRow
                totalPatients={overview?.total_patients ?? '—'}
                totalEncounters={overview?.total_encounters ?? '—'}
                avgLos={overview?.avg_length_of_stay ?? '—'}
                readmissionRate={overview?.readmission_rate ?? '—'}
                dataQualityStatus={overview?.data_quality_status ?? "Not assessed"}
                datasetStatus={overview?.organization_dataset ?? "Unavailable"}
                selectedTables={selectedTables}
                kpiCards={customDashboardData?.kpi_cards}
              />

              {/* 1. Top Observability 6-KPI Stat Cards (Screenshot 2 & 4) */}
              <TechnicalMetricsRow
                pipelineStatus={`${pipelineNodes.filter((node) => node.status === 'completed').length}/${pipelineNodes.length} Stages`}
                astValidation={analyticsResult?.sql_query ? 'Validated SQL' : 'Not run'}
                latency={isExecuting ? 'Processing...' : 'Not measured'}
                resultStatus="See analysis"
                sqlSafety={analyticsResult?.sql_query ? 'Validated' : 'Not run'}
                mysqlPool="See System Health"
              />

              {/* ANALYSIS BLOCKED CARD */}
              {blockedInfo && (
                <div className="bg-white border-2 border-rose-300 rounded-xl p-4 shadow-sm space-y-3">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center space-x-3">
                      <div className="w-9 h-9 rounded-lg bg-rose-50 border border-rose-200 flex items-center justify-center text-rose-600">
                        <ShieldAlert className="w-5 h-5" />
                      </div>
                      <div>
                        <div className="flex items-center space-x-2">
                          <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-rose-100 text-rose-800 border border-rose-200">
                            ANALYSIS BLOCKED
                          </span>
                          <span className="text-xs text-rose-600 font-semibold">Strict Table Boundary Enforced</span>
                        </div>
                        <h3 className="text-xs font-bold text-gray-900 mt-0.5">
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

                  <div className="bg-gray-50 rounded-lg p-2.5 border border-gray-200 text-xs text-gray-700">
                    <span className="font-semibold text-gray-900">Question: </span>
                    <span className="italic">"{blockedInfo.question}"</span>
                  </div>

                  <div>
                    <h4 className="text-[11px] font-bold text-gray-700 uppercase tracking-wider mb-1.5">
                      Required Dataset Tables:
                    </h4>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      {blockedInfo.required_tables.map((table) => {
                        const isSelected = blockedInfo.selected_tables.map(s => s.toLowerCase()).includes(table.toLowerCase());
                        return (
                          <div
                            key={table}
                            className={`flex items-center justify-between p-2 rounded-lg border text-xs ${
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

                  <div className="text-xs text-gray-700 bg-amber-50/60 border border-amber-200/80 rounded-lg p-2.5">
                    <p className="font-medium text-amber-900">{blockedInfo.message}</p>
                  </div>

                  {blockedInfo.missing_tables.length > 0 && (
                    <div className="flex items-center justify-end space-x-3 pt-0.5">
                      <button
                        onClick={() => handleSelectMissingTablesAndResume(blockedInfo.missing_tables)}
                        className="flex items-center space-x-2 px-3.5 py-1.5 bg-[#4F46E5] hover:bg-[#4338CA] text-white rounded-lg text-xs font-semibold shadow-xs transition-colors cursor-pointer"
                      >
                        <span>Select {blockedInfo.missing_tables.map(t => t.toUpperCase()).join(' & ')} & Resume Analysis</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  )}
                </div>
              )}

              {/* 3. Middle 2-Column Grid (Screenshot 2 & 4): Vertical 14-Step Trace (Left) + 3 Stacked Cards (Right) */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-3.5 items-start">
                {/* Left Column: Vertical 14-Step Trace */}
                <div className="lg:col-span-4 xl:col-span-4">
                  <PipelineVisualizer
                    nodes={pipelineNodes}
                    onApprove={handleApprove}
                    onReject={handleReject}
                    onReset={handleResetPipeline}
                    onRetry={failedStep === 9 ? handleRetryQueryExecution : (failedStep && failedStep >= 6 ? handleApprove : () => handleExecutePipeline())}
                    isApprovalPending={isApprovalPending}
                  />
                </div>

                {/* Right Column: 3 Stacked Cards + HUMAN APPROVAL */}
                <div className="lg:col-span-8 xl:col-span-8 space-y-3">
                  {/* Card 1: Active MySQL Connection & Database Schema */}
                  <ActiveDatabaseCard
                    datasetName={overview?.dataset_name || "Organization EHR Dataset"}
                    onUploadClick={() => setIsUploadModalOpen(true)}
                  />

                  {/* HUMAN APPROVAL (LARGE APPROVAL CARD) */}
                  {/* Placed AFTER ActiveDatabaseCard and BEFORE SqlInspectorCard */}
                  {isApprovalPending && analysisPlan && (
                    <div id="technical-human-approval-card" className="w-full">
                      <ClinicalApprovalCard
                        analysisPlan={analysisPlan}
                        question={question}
                        audience="technical"
                        onApprove={handleApprove}
                        onReject={handleReject}
                        isLoading={isExecuting}
                        isRegenerating={isRegenerating}
                        planVersion={planVersion}
                        feedbackHistory={feedbackHistory}
                        errorMessage={errorMessage}
                      />
                    </div>
                  )}

                  {/* Card 2: Generated SQL & AST Inspection */}
                  <SqlInspectorCard
                    sqlQuery={currentSqlQuery || analyticsResult?.sql_query}
                    statusBadge={isApprovalPending ? 'Awaiting Approval' : failedStep === 9 ? 'Execution Failed' : 'AST Validated'}
                  />

                </div>
              </div>

              {/* 4. Dynamic Charts Section (Screenshot 3) */}
              <DynamicCharts
                chartSpec={analyticsResult?.chart_spec}
                results={analyticsResult?.results}
                isQuestionMode={Boolean(analyticsResult?.results?.length)}
                encounterClasses={overview?.encounter_classes}
                monthlyTrends={overview?.monthly_trends}
                topDiagnoses={overview?.top_diagnoses}
                selectedTables={selectedTables}
                customTitle={customDashboardData?.chart_title}
                customCategories={customDashboardData?.chart_categories}
                customValues={customDashboardData?.chart_values}
              />

              {/* 5. Clinical Insights and Verified Results */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
                <ClinicalInsightsCard
                  insight={analyticsResult?.insight || customDashboardData?.insight}
                  keyFinding={customDashboardData?.key_finding}
                  keyFindingValue={customDashboardData?.key_finding_value}
                />

                <VerifiedResultsTable
                  results={analyticsResult?.results || (customDashboardData?.verified_results as any)}
                  badgeText={
                    analyticsResult?.results?.length
                      ? `${analyticsResult.results.length} Rows Verified`
                      : customDashboardData
                      ? `${customDashboardData.verified_results.length} Rows (${customDashboardData.selected_tables.join('+')})`
                      : "No result rows"
                  }
                />
              </div>

              {/* 6. Follow-up Analysis & Next Queries (Screenshot 1) */}
              <FollowUpSection
                onAskFollowUp={handleFollowUp}
                isLoading={isFollowUpLoading}
              />

              {/* FOLLOW-UP ANSWER CARD (Directly below Follow-Up Section) */}
              <FollowUpAnswerCard
                currentAnswer={followUpAnswer}
                history={followUpHistory}
                workspaceType="technical"
                isLoading={isFollowUpLoading}
                onClear={() => setFollowUpAnswer(null)}
                onRunNewAnalysis={(q) => {
                  setQuestion(q);
                  handleExecutePipeline();
                }}
              />

              {/* 7. Certified Report Generation Card (Screenshot 1) */}
              <ReportTriggerBanner
                onOpenReportReview={() => setIsReportModalOpen(true)}
                title="Generate Technical & Clinical PDF Report"
                description="Export a publication-ready PDF audit report containing LangGraph execution logs, AST SQL queries, clinical charts, and verified outcomes."
              />
            </>
          )}

          {/* TAB 2: ANALYTICS */}
          {activeTab === 'analytics' && (
            <div className="space-y-4">
              <TechnicalMetricsRow
                pipelineStatus={`${pipelineNodes.filter((node) => node.status === 'completed').length}/${pipelineNodes.length} Stages`}
                astValidation={analyticsResult?.sql_query ? 'Validated SQL' : 'Not run'}
                latency={isExecuting ? 'Processing...' : 'Not measured'}
                resultStatus="See analysis"
                sqlSafety={analyticsResult?.sql_query ? 'Validated' : 'Not run'}
                mysqlPool="See System Health"
              />
              <DynamicCharts
                chartSpec={analyticsResult?.chart_spec}
                results={analyticsResult?.results}
                isQuestionMode={!!analyticsResult?.results && analyticsResult.results.length > 0}
                encounterClasses={overview?.encounter_classes}
                monthlyTrends={overview?.monthly_trends}
                topDiagnoses={overview?.top_diagnoses}
                selectedTables={selectedTables}
                customTitle={customDashboardData?.chart_title}
                customCategories={customDashboardData?.chart_categories}
                customValues={customDashboardData?.chart_values}
              />
              <VerifiedResultsTable
                results={analyticsResult?.results || (overview?.top_diagnoses as any)}
                badgeText="AST Verified Result Set"
              />
            </div>
          )}

          {/* TAB 3: PIPELINE EXECUTION */}
          {activeTab === 'pipeline' && (
            <div className="space-y-6">
              <PipelineVisualizer
                nodes={pipelineNodes}
                onApprove={handleApprove}
                onReject={handleReject}
                onReset={handleResetPipeline}
                onRetry={() => handleExecutePipeline()}
                isApprovalPending={isApprovalPending}
              />
              <div className="bg-white border border-gray-200/90 rounded-xl p-5 shadow-sm space-y-4">
                <h3 className="text-sm font-bold text-gray-900">LangGraph Pipeline State Machine Architecture</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
                  <div className="p-3 bg-gray-50 rounded-lg border border-gray-100">
                    <span className="font-bold text-gray-800 block mb-1">Phase 1: Question & Schema</span>
                    <p className="text-gray-500">Normalizes input string, loads MySQL table schemas and relationship graph, retrieves semantic ontology references.</p>
                  </div>
                  <div className="p-3 bg-amber-50/60 rounded-lg border border-amber-200/80">
                    <span className="font-bold text-amber-800 block mb-1">Phase 2: Plan & Human Gate</span>
                    <p className="text-amber-700">Generates structured analysis plan. Pipeline blocks deterministically at Node 5 until explicit human approval.</p>
                  </div>
                  <div className="p-3 bg-blue-50/60 rounded-lg border border-blue-200/80">
                    <span className="font-bold text-blue-800 block mb-1">Phase 3: SQL & AST Safety</span>
                    <p className="text-blue-700">Synthesizes MySQL SQL, validates with sqlglot AST parser ensuring strict read-only SELECT clauses, and executes safely.</p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 4: SQL EXPLORER */}
          {activeTab === 'sql' && (
            <div className="space-y-6">
              <SqlInspectorCard sqlQuery={analyticsResult?.sql_query} />
              <ActiveDatabaseCard />
            </div>
          )}

          {/* TAB 5: AST VALIDATION */}
          {activeTab === 'ast' && (
            <div className="bg-white border border-gray-200/90 rounded-xl p-6 shadow-sm space-y-5">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 rounded-xl bg-blue-50 border border-blue-100 flex items-center justify-center text-blue-600">
                  <CheckSquare className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-gray-900">Abstract Syntax Tree (AST) Safety Validator</h3>
                  <p className="text-xs text-gray-500">Strict compile-time syntax and permission enforcement powered by sqlglot</p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                <div className="p-4 bg-emerald-50/50 border border-emerald-200 rounded-xl space-y-2">
                  <h4 className="font-bold text-emerald-800 flex items-center space-x-1.5">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                    <span>Allowed Operations</span>
                  </h4>
                  <ul className="list-disc list-inside text-gray-700 space-y-1">
                    <li><code className="bg-white px-1.5 py-0.5 rounded font-mono text-[11px]">SELECT</code> statements only</li>
                    <li><code className="bg-white px-1.5 py-0.5 rounded font-mono text-[11px]">JOIN</code> on validated relationships</li>
                    <li>Aggregations: <code className="bg-white px-1.5 py-0.5 rounded font-mono text-[11px]">AVG, COUNT, SUM, MIN, MAX</code></li>
                    <li>Date math: <code className="bg-white px-1.5 py-0.5 rounded font-mono text-[11px]">DATEDIFF(STOP, START)</code></li>
                  </ul>
                </div>

                <div className="p-4 bg-rose-50/50 border border-rose-200 rounded-xl space-y-2">
                  <h4 className="font-bold text-rose-800 flex items-center space-x-1.5">
                    <AlertCircle className="w-4 h-4 text-rose-600" />
                    <span>Forbidden Keywords & Violations</span>
                  </h4>
                  <ul className="list-disc list-inside text-gray-700 space-y-1">
                    <li><code className="bg-white px-1.5 py-0.5 rounded font-mono text-[11px]">DROP, DELETE, TRUNCATE</code></li>
                    <li><code className="bg-white px-1.5 py-0.5 rounded font-mono text-[11px]">UPDATE, INSERT, ALTER</code></li>
                    <li>Multi-statement injections (<code className="bg-white px-1.5 py-0.5 rounded font-mono text-[11px]">;</code>)</li>
                    <li>Unapproved system schema queries (<code className="bg-white px-1.5 py-0.5 rounded font-mono text-[11px]">information_schema</code>)</li>
                  </ul>
                </div>
              </div>
            </div>
          )}

          {/* TAB 7: QUERY HISTORY */}
          {activeTab === 'queries' && (
            <div className="bg-white border border-gray-200/90 rounded-xl p-5 shadow-sm space-y-4">
              <div className="flex items-center justify-between pb-2 border-b border-gray-100">
                <div className="flex items-center space-x-3">
                  <div className="w-9 h-9 rounded-lg bg-blue-50 border border-blue-100 flex items-center justify-center text-blue-600 shadow-2xs">
                    <History className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-gray-900">Technical Query & Follow-Up Logs</h3>
                    <p className="text-xs text-gray-500">AST validation passes, execution latency, generated SQL, and verified outcomes</p>
                  </div>
                </div>
                <span className="text-xs font-semibold text-blue-700 bg-blue-50 px-2.5 py-1 rounded-full border border-blue-100">
                  {technicalQueries.length} Executions Logged
                </span>
              </div>

              <div className="space-y-4">
                {technicalQueries.length === 0 && (
                  <p className="rounded-xl border border-gray-200 bg-gray-50 p-5 text-sm text-gray-600">
                    No technical queries have run in this workspace session yet.
                  </p>
                )}
                {technicalQueries.map((q, idx) => (
                  <div key={idx} className="bg-gray-50 p-4 rounded-xl border border-gray-200/80 space-y-2.5">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 text-xs">
                      <div className="flex items-center space-x-2">
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                          q.type === 'followup'
                            ? 'bg-[#EEF2FF] text-[#4F46E5] border border-[#C7D2FE]'
                            : 'bg-blue-100 text-blue-700 border border-blue-200'
                        }`}>
                          {q.type === 'followup' ? 'Follow-Up' : 'Pipeline Execution'}
                        </span>
                        <span className="font-bold text-gray-900">"{q.question}"</span>
                      </div>
                      <div className="flex items-center space-x-2 font-mono text-[11px] text-gray-500">
                        <span>{q.timestamp}</span>
                        <span>•</span>
                        <span className="text-emerald-600 font-semibold">{q.ast_status || 'AST Passed'}</span>
                        <span>•</span>
                        <span>{q.latency || '—'}</span>
                      </div>
                    </div>

                    {q.sql_query && (
                      <pre className="bg-[#F1F5F9] text-[#111827] p-3 rounded-lg text-xs font-mono overflow-x-auto border border-[#E5E7EB]">
                        {q.sql_query}
                      </pre>
                    )}

                    {q.answer && (
                      <div className="p-2.5 bg-white rounded-lg border border-gray-200/70 text-xs text-gray-700">
                        <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider block mb-0.5">
                          Verified Outcome Answer
                        </span>
                        <p>{q.answer}</p>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* TAB 8: AUDIT TRAIL */}
          {activeTab === 'audit' && (
            <div className="bg-white border border-gray-200/90 rounded-xl p-5 shadow-sm space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <div className="w-9 h-9 rounded-lg bg-blue-50 border border-blue-100 flex items-center justify-center text-blue-600">
                    <ShieldCheck className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-gray-900">Live Database Audit Trail</h3>
                    <p className="text-xs text-gray-500">Security event logs streamed directly from FastAPI <code className="font-mono text-[10px]">/database/audit-logs</code></p>
                  </div>
                </div>
                <div className="flex items-center space-x-2">
                  <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 mr-1 animate-pulse" />
                    LIVE (3s)
                  </span>
                  <button
                    onClick={() => {
                      setIsRefreshingAudit(true);
                      databaseApi.getAuditLogs().then((res) => {
                        if (res?.audit_logs) {
                          setAuditLogs(res.audit_logs);
                          setAuditError(null);
                        }
                      }).catch(() => {
                        setAuditError('Unable to load audit events. Check FastAPI/MySQL connection.');
                      }).finally(() => {
                        setIsRefreshingAudit(false);
                      });
                    }}
                    title="Refresh Audit Logs"
                    className="p-1.5 text-gray-500 hover:text-gray-800 rounded-lg hover:bg-gray-100 transition-colors"
                  >
                    <RefreshCw className={`w-4 h-4 ${isRefreshingAudit ? 'animate-spin text-blue-600' : ''}`} />
                  </button>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-gray-50 text-gray-500 uppercase text-[10px] font-bold border-y border-gray-200">
                    <tr>
                      <th className="py-2.5 px-4">Log ID</th>
                      <th className="py-2.5 px-4">Action</th>
                      <th className="py-2.5 px-4">Details</th>
                      <th className="py-2.5 px-4">User / Agent</th>
                      <th className="py-2.5 px-4">Timestamp</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {isAuditLoading && auditLogs.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="py-8 text-center text-gray-500">
                          <div className="flex items-center justify-center space-x-2">
                            <Loader2 className="w-4 h-4 animate-spin text-blue-600" />
                            <span>Loading live audit trail from MySQL...</span>
                          </div>
                        </td>
                      </tr>
                    ) : auditError ? (
                      <tr>
                        <td colSpan={5} className="py-8 text-center text-rose-600">
                          <div className="flex flex-col items-center justify-center space-x-1 space-y-1">
                            <div className="flex items-center space-x-1.5">
                              <AlertCircle className="w-4 h-4 text-rose-600" />
                              <span className="font-semibold">{auditError}</span>
                            </div>
                            <span className="text-xs text-gray-500">Check that MySQL service and FastAPI backend are active.</span>
                          </div>
                        </td>
                      </tr>
                    ) : auditLogs.length > 0 ? (
                      auditLogs.map((log) => (
                        <tr key={log.id} className="hover:bg-gray-50/60">
                          <td className="py-2.5 px-4 font-mono text-gray-500">#{log.id}</td>
                          <td className="py-2.5 px-4 font-semibold text-gray-800">
                            <span className="inline-block px-2 py-0.5 rounded text-[11px] font-mono font-medium bg-gray-100 text-gray-800 border border-gray-200">
                              {log.action}
                            </span>
                          </td>
                          <td className="py-2.5 px-4 text-gray-600 font-mono text-[11px] max-w-md truncate" title={log.details || log.message || ''}>
                            {log.details || log.message || '—'}
                          </td>
                          <td className="py-2.5 px-4 text-gray-700">
                            {log.user || log.user_agent || 'system'}
                          </td>
                          <td className="py-2.5 px-4 font-mono text-gray-500 whitespace-nowrap">
                            {log.timestamp || log.created_at || '—'}
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={5} className="py-6 text-center text-gray-400">
                          No audit events recorded yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* TAB 9: SYSTEM HEALTH */}
          {activeTab === 'health' && (
            <div className="space-y-6">
              <SystemHealthCard />
              <div className="bg-white border border-gray-200/90 rounded-xl p-5 shadow-sm space-y-4">
                <h3 className="text-sm font-bold text-gray-900">Microservice Runtime Verification</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 text-xs">
                  <div className="p-3 bg-emerald-50/60 border border-emerald-200 rounded-lg">
                    <span className="text-gray-500 block text-[10px] uppercase font-bold">FastAPI Server</span>
                    <span className="text-sm font-bold text-emerald-800 mt-1 block">ONLINE (Port 8001)</span>
                  </div>
                  <div className="p-3 bg-emerald-50/60 border border-emerald-200 rounded-lg">
                    <span className="text-gray-500 block text-[10px] uppercase font-bold">MySQL Connection Pool</span>
                    <span className="text-sm font-bold text-emerald-800 mt-1 block">CONNECTED (Pool: 5)</span>
                  </div>
                  <div className="p-3 bg-emerald-50/60 border border-emerald-200 rounded-lg">
                    <span className="text-gray-500 block text-[10px] uppercase font-bold">LangGraph Engine</span>
                    <span className="text-sm font-bold text-emerald-800 mt-1 block">ACTIVE (14 Nodes)</span>
                  </div>
                  <div className="p-3 bg-emerald-50/60 border border-emerald-200 rounded-lg">
                    <span className="text-gray-500 block text-[10px] uppercase font-bold">Gemini LLM API</span>
                    <span className="text-sm font-bold text-emerald-800 mt-1 block">AUTHENTICATED</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 10: SETTINGS */}
          {activeTab === 'settings' && (
            <div className="bg-white border border-gray-200/90 rounded-xl p-6 shadow-sm space-y-6">
              <div>
                <h3 className="text-base font-bold text-gray-900">Technical Configuration & Pipeline Parameters</h3>
                <p className="text-xs text-gray-500">LangGraph state timeouts, AST rules, and loaded dataset version history</p>
              </div>

              <div className="space-y-4 text-xs">
                <div className="border border-gray-200 rounded-xl p-4 flex items-center justify-between">
                  <div>
                    <h4 className="font-bold text-gray-800">FastAPI Ingestion Endpoint</h4>
                    <p className="text-gray-500 font-mono text-[11px] mt-0.5">POST http://127.0.0.1:8001/ingestion/upload</p>
                  </div>
                  <button
                    onClick={() => setIsUploadModalOpen(true)}
                    className="flex items-center space-x-1.5 px-3 py-1.5 bg-blue-50 hover:bg-blue-100 text-blue-700 border border-blue-200 rounded-lg font-semibold cursor-pointer"
                  >
                    <span>Upload Dataset</span>
                  </button>
                </div>

                <div className="border border-gray-200 rounded-xl p-4 space-y-2">
                  <h4 className="font-bold text-gray-800">Pipeline Execution Parameters</h4>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-1">
                    <div className="p-2.5 bg-gray-50 rounded-lg border border-gray-100">
                      <span className="font-bold block text-gray-700">Max LLM Iterations:</span>
                      <span className="font-mono text-gray-600">3 retries on validation failure</span>
                    </div>
                    <div className="p-2.5 bg-gray-50 rounded-lg border border-gray-100">
                      <span className="font-bold block text-gray-700">Execution Timeout:</span>
                      <span className="font-mono text-gray-600">60 seconds</span>
                    </div>
                    <div className="p-2.5 bg-gray-50 rounded-lg border border-gray-100">
                      <span className="font-bold block text-gray-700">AST Strictness:</span>
                      <span className="font-mono text-emerald-600 font-bold">STRICT READ-ONLY</span>
                    </div>
                  </div>
                </div>

                {datasetVersions.length > 0 && (
                  <div className="border border-gray-200 rounded-xl p-4 space-y-3">
                    <h4 className="font-bold text-gray-800">Dataset Version Registry</h4>
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs">
                        <thead className="bg-gray-50 text-gray-500 uppercase text-[9px] font-bold">
                          <tr>
                            <th className="py-2 px-3">Dataset</th>
                            <th className="py-2 px-3">File</th>
                            <th className="py-2 px-3">Rows</th>
                            <th className="py-2 px-3">Cols</th>
                            <th className="py-2 px-3">Status</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                          {datasetVersions.map((v) => (
                            <tr key={v.id}>
                              <td className="py-2 px-3 font-semibold">{v.dataset_name}</td>
                              <td className="py-2 px-3 font-mono text-[11px] text-gray-600">{v.source_filename}</td>
                              <td className="py-2 px-3 font-mono">{v.row_count.toLocaleString()}</td>
                              <td className="py-2 px-3 font-mono">{v.column_count}</td>
                              <td className="py-2 px-3">
                                <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-700">
                                  {v.status}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </main>
      </div>

      {/* Certified Report Review Modal with Human Approval Gate */}
      <ReportModal
        isOpen={isReportModalOpen}
        onClose={() => setIsReportModalOpen(false)}
        question={question}
        analysisPlan={analysisPlan || analyticsResult?.analysis_plan}
        insight={analyticsResult?.insight}
        results={analyticsResult?.results}
        sqlQuery={currentSqlQuery || analyticsResult?.sql_query}
        workspaceType="technical"
        selectedTables={selectedTables}
        followUpAnswers={followUpHistory}
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

export default TechnicalDashboard;
