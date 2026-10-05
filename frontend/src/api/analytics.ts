import apiClient from './client';
import { 
  AnalyticsRequest, 
  AnalyticsResponse, 
  OverviewResponse, 
  DashboardCustomizationResponse,
  FollowUpRequest,
  FollowUpResponse,
} from '../types/analytics';

export const analyticsApi = {
  getOverview: async (): Promise<OverviewResponse> => {
    const res = await apiClient.get<OverviewResponse>('/analytics/overview');
    return res.data;
  },

  customizeDashboard: async (tables: string[]): Promise<DashboardCustomizationResponse> => {
    const res = await apiClient.post<DashboardCustomizationResponse>('/analytics/dashboard', { tables });
    return res.data;
  },

  runAnalytics: async (payload: AnalyticsRequest): Promise<AnalyticsResponse> => {
    const res = await apiClient.post<AnalyticsResponse>('/analytics/run', payload);
    return res.data;
  },

  runFollowUp: async (payload: FollowUpRequest): Promise<FollowUpResponse> => {
    const res = await apiClient.post<FollowUpResponse>('/analytics/followup', payload);
    return res.data;
  },
};

export default analyticsApi;
