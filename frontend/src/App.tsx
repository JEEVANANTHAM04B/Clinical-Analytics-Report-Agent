import React, { useState } from 'react';
import { ErrorBoundary } from './components/ErrorBoundary';
import './studio.css';
const ClinicalDashboard = React.lazy(() => import('./pages/ClinicalDashboard'));
const TechnicalDashboard = React.lazy(() => import('./pages/TechnicalDashboard'));

export type WorkspaceView = 'clinical' | 'technical';

export const App: React.FC = () => {
  const [currentWorkspace, setCurrentWorkspace] = useState<WorkspaceView>('clinical');

  return (
    <div className="studio-shell min-h-screen flex flex-col">
      <ErrorBoundary fallbackTitle="Clinical Analytics Workspace Error">
        <React.Suspense fallback={<p role="status">Loading workspace…</p>}>
          <div className="flex-1 flex flex-col">
            {currentWorkspace === 'clinical' && (
              <ClinicalDashboard
                onSwitchRole={() => setCurrentWorkspace('technical')}
              />
            )}

            {currentWorkspace === 'technical' && (
              <TechnicalDashboard
                onSwitchRole={() => setCurrentWorkspace('clinical')}
              />
            )}
          </div>
        </React.Suspense>
      </ErrorBoundary>
    </div>
  );
};

export default App;
