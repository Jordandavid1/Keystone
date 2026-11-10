'use client';

import React from 'react';
import {
  FolderKanban,
  GitBranch,
  Video,
  Palette,
  Brain,
  Mic,
  Settings
} from 'lucide-react';

interface ActivityBarProps {
  activeTab: string;
  onSelectTab: (tab: string) => void;
  onOpenSettings: () => void;
}

export const ActivityBar: React.FC<ActivityBarProps> = ({
  activeTab,
  onSelectTab,
  onOpenSettings,
}) => {
  return (
    <nav className="vscode-activity-bar" aria-label="Activity Rail">
      <div className="activity-top-group">
        <button
          className={`activity-icon-btn ${activeTab === 'explorer' ? 'active' : ''}`}
          onClick={() => onSelectTab('explorer')}
          title="Explorer & Generative Suite"
        >
          <FolderKanban size={20} />
        </button>

        <button
          className={`activity-icon-btn ${activeTab === 'pipeline' ? 'active' : ''}`}
          onClick={() => onSelectTab('pipeline')}
          title="Custom Pipeline Builder (Chained Freedom Mode)"
        >
          <GitBranch size={20} />
        </button>

        <button
          className={`activity-icon-btn ${activeTab === 'motion' ? 'active' : ''}`}
          onClick={() => onSelectTab('motion')}
          title="Higgsfield Camera Motion Studio"
        >
          <Video size={20} />
        </button>

        <button
          className={`activity-icon-btn ${activeTab === 'grading' ? 'active' : ''}`}
          onClick={() => onSelectTab('grading')}
          title="Hollywood Color Grading & LUT Deck"
        >
          <Palette size={20} />
        </button>

        <button
          className={`activity-icon-btn ${activeTab === 'cognition' ? 'active' : ''}`}
          onClick={() => onSelectTab('cognition')}
          title="Uncensored LLM Cognition & Brainstorming"
        >
          <Brain size={20} />
        </button>

        <button
          className={`activity-icon-btn ${activeTab === 'audio' ? 'active' : ''}`}
          onClick={() => onSelectTab('audio')}
          title="Voice & Sound Stage"
        >
          <Mic size={20} />
        </button>
      </div>

      <div className="activity-bottom-group">
        <button
          className="activity-icon-btn"
          onClick={onOpenSettings}
          title="Studio Settings & Invariants"
        >
          <Settings size={20} />
        </button>
      </div>
    </nav>
  );
};
