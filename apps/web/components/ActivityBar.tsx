'use client';

import React from 'react';
import {
  FolderKanban,
  GitBranch,
  Video,
  Palette,
  Brain,
  Mic,
  Settings,
  Users,
  MessageSquare
} from 'lucide-react';

interface ActivityBarProps {
  activeTab: string;
  onSelectTab: (tab: string) => void;
  onOpenSettings: () => void;
  onOpenPersonas: () => void;
  onOpenAgentChat: () => void;
}

export const ActivityBar: React.FC<ActivityBarProps> = ({
  activeTab,
  onSelectTab,
  onOpenSettings,
  onOpenPersonas,
  onOpenAgentChat,
}) => {
  return (
    <nav className="vscode-activity-bar" aria-label="Activity Rail">
      <div className="activity-top-group">
        <button className={`activity-icon-btn ${activeTab === 'explorer' ? 'active' : ''}`} onClick={() => onSelectTab('explorer')} title="Asset Explorer & Playbooks">
          <FolderKanban size={20} />
        </button>
        <button className={`activity-icon-btn ${activeTab === 'pipeline' ? 'active' : ''}`} onClick={() => onSelectTab('pipeline')} title="Custom Pipeline Builder">
          <GitBranch size={20} />
        </button>
        <button className={`activity-icon-btn ${activeTab === 'motion' ? 'active' : ''}`} onClick={() => onSelectTab('motion')} title="Higgsfield Camera Motion Studio">
          <Video size={20} />
        </button>
        <button className={`activity-icon-btn ${activeTab === 'grading' ? 'active' : ''}`} onClick={() => onSelectTab('grading')} title="Hollywood Color Grading & LUT Deck">
          <Palette size={20} />
        </button>
        <button className={`activity-icon-btn ${activeTab === 'cognition' || activeTab === 'thinking' ? 'active' : ''}`} onClick={() => onSelectTab('thinking')} title="Cursor AI Thinking & Cognitive Anatomy">
          <Brain size={20} />
        </button>
        <button className={`activity-icon-btn ${activeTab === 'audio' ? 'active' : ''}`} onClick={onOpenPersonas} title="Character Personas & ElevenLabs Voices">
          <Users size={20} />
        </button>
        <button className={`activity-icon-btn ${activeTab === 'audio-stage' ? 'active' : ''}`} onClick={() => onSelectTab('audio')} title="ElevenLabs Speech Studio & Sound Stage">
          <Mic size={20} />
        </button>
        <button className={`activity-icon-btn ${activeTab === 'chat' ? 'active' : ''}`} onClick={onOpenAgentChat} title="Direct LLM Agent Chat">
          <MessageSquare size={20} />
        </button>
      </div>
      <div className="activity-bottom-group">
        <button className="activity-icon-btn" onClick={onOpenSettings} title="Studio Settings & Invariants">
          <Settings size={20} />
        </button>
      </div>
    </nav>
  );
};
