export interface AnalyticsRequest {
  question: string;
  approval_status: 'pending' | 'approved' | 'rejected';
  human_feedback?: string;
  selected_tables?: string[];
  current_plan?: string;
  sql_query?: string;
  resume_from?: string;
  feedback_history?: string[];
  plan_version?: number;
}

export interface TableColumn {
  name: string;
  type: string;
  nullable?: boolean;
}

export interface ClinicalTable {
  name: string;
  display_name: string;
  row_count: number;
  columns: TableColumn[];
}

export interface ListTablesResponse {
  status: string;
  count: number;
  tables: ClinicalTable[];
}

export interface KpiCard {
  label: string;
  value: string;
  highlight?: boolean;
}

export interface DashboardCustomizationResponse {
  status: string;
  valid_combination: boolean;
  message?: string | null;
  selected_tables: string[];
  total_patients?: number | null;
  total_encounters?: number | null;
  primary_metric_label: string;
  primary_metric_value: string;
  kpi_cards: KpiCard[];
  chart_spec?: ChartSpec | null;
  chart_categories: string[];
  chart_values: number[];
  chart_title: string;
  secondary_chart_title?: string | null;
  encounter_classes: EncounterClassItem[];
  monthly_trends: MonthlyTrendItem[];
  verified_results: Record<string, any>[];
  insight?: string | null;
  key_finding: string;
  key_finding_value: string;
  suggested_questions: string[];
}

export interface ChartSpec {
  chart_type?: string;
  title?: string;
  x_column?: string;
  y_column?: string;
  [key: string]: any;
}

export interface AnalyticsResponse {
  status: string;
  question: string;
  analysis_plan?: string | null;
  approval_status?: string | null;
  feedback_history?: string[] | null;
  plan_version?: number | null;
  sql_query?: string | null;
  results: Record<string, any>[];
  insight?: string | null;
  chart_spec?: ChartSpec | null;
  visualization_error?: string | null;
  rag_context?: string | null;
  result_validation?: Record<string, any> | null;
  insight_evidence?: Record<string, any> | null;
  error?: string | null;
}

export interface EncounterClassItem {
  class_name: string;
  count: number;
}

export interface TopDiagnosisItem {
  diagnosis: string;
  count: number;
  avg_los: number;
}

export interface MonthlyTrendItem {
  month: string;
  count: number;
}

export interface OverviewResponse {
  status: string;
  total_patients: number;
  total_encounters: number;
  avg_length_of_stay: number;
  readmission_rate: number;
  data_quality_status: string;
  organization_dataset: string;
  dataset_name: string;
  encounter_classes: EncounterClassItem[];
  top_diagnoses: TopDiagnosisItem[];
  monthly_trends: MonthlyTrendItem[];
}

export type PipelineNodeStatus = 'pending' | 'running' | 'completed' | 'waiting_approval' | 'failed';

export interface PipelineNode {
  id: number;
  name: string;
  status: PipelineNodeStatus;
  detail?: string;
  timestamp?: string;
}

export interface ConversationTurn {
  role: 'user' | 'assistant';
  content: string;
}

export interface FollowUpRequest {
  question: string;
  current_question?: string | null;
  current_results?: Record<string, any>[];
  current_sql?: string | null;
  current_plan?: string | null;
  current_rag_context?: string | null;
  current_insight?: string | null;
  conversation_history?: ConversationTurn[];
  selected_tables?: string[];
}

export interface FollowUpResponse {
  status: string;
  question: string;
  answer: string;
  source: 'verified_results' | 'follow_up_sql' | 'new_analysis' | string;
  is_new_analysis: boolean;
  sql_query?: string | null;
  verified: boolean;
  confidence: number;
  follow_up_results?: Record<string, any>[];
}
