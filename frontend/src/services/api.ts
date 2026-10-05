import analyticsApi from '../api/analytics';
import datasetsApi from '../api/datasets';
import databaseApi from '../api/database';

export const apiService = {
  ...analyticsApi,
  ...datasetsApi,
  ...databaseApi,
};

export default apiService;
