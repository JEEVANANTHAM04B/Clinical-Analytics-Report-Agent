import apiClient from './client';
import { ClinicalTable, ListTablesResponse } from '../types/analytics';

export interface RelationshipItem {
  id: number;
  parent_table: string;
  parent_column: string;
  child_table: string;
  child_column: string;
  status: string;
  analyst_note?: string | null;
  created_at?: string;
}

export interface AuditLogItem {
  id: number;
  timestamp: string;
  action: string;
  details?: string;
  user?: string;
  user_agent?: string;
  message?: string;
  created_at?: string;
  status?: string;
  entity_type?: string;
  entity_name?: string;
}

export const databaseApi = {
  getTables: async (): Promise<ClinicalTable[]> => {
    const res = await apiClient.get<any>('/database/tables');
    if (Array.isArray(res.data)) return res.data;
    if (res.data && Array.isArray(res.data.tables)) return res.data.tables;
    return [];
  },

  getRelationships: async (): Promise<RelationshipItem[]> => {
    const res = await apiClient.get<any>('/database/relationships');
    return Array.isArray(res.data) ? res.data : (res.data?.relationships || []);
  },

  getAuditLogs: async (): Promise<{ status: string; audit_logs: AuditLogItem[] }> => {
    const res = await apiClient.get<any>('/database/audit-logs');
    const logs = res.data?.audit_logs || res.data?.logs || res.data?.items || (Array.isArray(res.data) ? res.data : []);
    return {
      status: res.data?.status || 'success',
      audit_logs: logs,
    };
  },

  getHealth: async () => {
    const res = await apiClient.get('/health');
    return res.data;
  },

  getDbHealth: async () => {
    const res = await apiClient.get('/health/db');
    return res.data;
  },

  getRegistry: async (includeAll: boolean = true) => {
    const res = await apiClient.get<any>('/database/registry', { params: { include_all: includeAll } });
    return res.data;
  },

  updateRegistryStatus: async (
    datasetName: string,
    statusData: { classification?: string; approval_status?: string; category?: string; description?: string }
  ) => {
    const res = await apiClient.put<any>(`/database/registry/${datasetName}/status`, statusData);
    return res.data;
  },

  approveDataset: async (datasetName: string) => {
    const res = await apiClient.post<any>(`/database/registry/${datasetName}/approve`);
    return res.data;
  },
};

export default databaseApi;
