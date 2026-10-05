import React, { useState } from 'react';
import WorkspaceSelection from './pages/WorkspaceSelection';
import ClinicalDashboard from './pages/ClinicalDashboard';
import TechnicalDashboard from './pages/TechnicalDashboard';

export type WorkspaceView = 'selection' | 'clinical' | 'technical';

export const App: React.FC = () => {
  const [currentWorkspace, setCurrentWorkspace] = useState<WorkspaceView>('selection');

  return (
    <div className="min-h-screen flex flex-col bg-[#F8FAFC]">
      {/* Main Workspace Router / View */}
      <div className="flex-1 flex flex-col">
        {currentWorkspace === 'selection' && (
          <WorkspaceSelection
            onSelect={(ws) => setCurrentWorkspace(ws)}
          />
        )}

        {currentWorkspace === 'clinical' && (
          <ClinicalDashboard
            onSwitchRole={() => setCurrentWorkspace('selection')}
          />
        )}

        {currentWorkspace === 'technical' && (
          <TechnicalDashboard
            onSwitchRole={() => setCurrentWorkspace('selection')}
          />
        )}
      </div>
    </div>
  );
};

export default App;
