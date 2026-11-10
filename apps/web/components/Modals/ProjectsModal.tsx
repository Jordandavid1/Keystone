'use client';

import React, { useEffect, useState } from 'react';
import { FolderKanban, X } from 'lucide-react';
import { createProject, deleteProject, fetchProjects } from '../../lib/api';

interface ProjectsModalProps {
  open: boolean;
  onClose: () => void;
  onSelectProject?: (project: any) => void;
}

export const ProjectsModal: React.FC<ProjectsModalProps> = ({ open, onClose, onSelectProject }) => {
  const [projects, setProjects] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');

  const reload = async () => {
    setError(null);
    try {
      setProjects(await fetchProjects());
    } catch (err: any) {
      setProjects([]);
      setError(err?.message || 'Could not load projects.');
    }
  };

  useEffect(() => {
    if (open) reload();
  }, [open]);

  const handleCreate = async () => {
    if (!name.trim()) {
      setError('A project name is required.');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const created = await createProject(name.trim(), description.trim());
      setName('');
      setDescription('');
      await reload();
      if (created) onSelectProject?.(created);
    } catch (err: any) {
      setError(err?.message || 'Could not create project.');
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async (id: string) => {
    setBusy(true);
    setError(null);
    try {
      await deleteProject(id);
      await reload();
    } catch (err: any) {
      setError(err?.message || 'Could not delete project.');
    } finally {
      setBusy(false);
    }
  };

  if (!open) return null;

  return (
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-modal="true" aria-label="Projects Manager">
      <div className="command-modal" style={{ width: 'min(640px, 94vw)', maxHeight: '85vh', display: 'flex', flexDirection: 'column' }} onClick={(e) => e.stopPropagation()}>
        <div className="chat-top-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <FolderKanban size={16} color="#6366f1" />
            <strong>Creative Projects Manager</strong>
          </div>
          <button className="icon-btn" onClick={onClose} title="Close"><X size={14} /></button>
        </div>
        <div style={{ padding: '18px 22px', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div style={{ fontSize: 11.5, color: 'var(--text-secondary)' }}>
            Projects isolate assets, personas, sessions, and render histories into tenant-scoped creative units.
          </div>
          {error && <div style={{ padding: 10, borderRadius: 8, border: '1px solid rgba(244,63,94,0.4)', color: '#fda4af', fontSize: 12 }}>{error}</div>}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 220, overflowY: 'auto' }}>
            {projects.length === 0 ? (
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>No projects loaded.</div>
            ) : (
              projects.map((project) => (
                <div key={project.id} style={{ display: 'flex', justifyContent: 'space-between', gap: 10, padding: 10, border: '1px solid var(--border-subtle)', borderRadius: 8, background: 'rgba(255,255,255,0.02)' }}>
                  <button onClick={() => onSelectProject?.(project)} style={{ background: 'transparent', border: 'none', textAlign: 'left', color: 'inherit', cursor: 'pointer', flex: 1 }}>
                    <div style={{ fontSize: 13, fontWeight: 700 }}>{project.name}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{project.description || 'No description'}</div>
                    <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', marginTop: 4 }}>{project.id}</div>
                  </button>
                  <button className="icon-btn" onClick={() => handleDelete(project.id)} disabled={busy}>Delete</button>
                </div>
              ))
            )}
          </div>
          <div style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border-subtle)', borderRadius: 8, padding: 14, display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div style={{ fontSize: 12, fontWeight: 700 }}>Create New Project</div>
            <input className="command-input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Project name" style={{ border: '1px solid var(--border-subtle)', borderRadius: 6, padding: '6px 10px', width: '100%' }} />
            <input className="command-input" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Brief project summary" style={{ border: '1px solid var(--border-subtle)', borderRadius: 6, padding: '6px 10px', width: '100%' }} />
            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button className="composer-submit-btn" onClick={handleCreate} disabled={busy}>{busy ? 'Saving...' : '+ Create Project'}</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
