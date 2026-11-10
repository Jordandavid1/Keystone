'use client';

import React, { useEffect, useState } from 'react';
import { X, Zap } from 'lucide-react';
import { fetchCreditLedger } from '../../lib/api';

interface CreditsModalProps {
  open: boolean;
  onClose: () => void;
}

export const CreditsModal: React.FC<CreditsModalProps> = ({ open, onClose }) => {
  const [ledger, setLedger] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setError(null);
    fetchCreditLedger()
      .then(setLedger)
      .catch((err: any) => {
        setLedger(null);
        setError(err?.message || 'Could not load credit ledger.');
      });
  }, [open]);

  if (!open) return null;

  const isLocal = ledger?.balance == null || ledger?.status === 'local_engine';
  const events = Array.isArray(ledger?.events) ? ledger.events : [];

  return (
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-modal="true" aria-label="Credits and Ledger">
      <div className="command-modal" style={{ width: 'min(680px, 94vw)', maxHeight: '85vh', display: 'flex', flexDirection: 'column' }} onClick={(e) => e.stopPropagation()}>
        <div className="chat-top-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Zap size={16} color="#38bdf8" />
            <strong>Studio Credit Ledger</strong>
          </div>
          <button className="icon-btn" onClick={onClose} title="Close"><X size={14} /></button>
        </div>
        <div style={{ padding: '18px 22px', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: 16 }}>
          {error && <div style={{ padding: 10, borderRadius: 8, border: '1px solid rgba(244,63,94,0.4)', color: '#fda4af', fontSize: 12 }}>{error}</div>}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
            <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border-subtle)', borderRadius: 8, padding: 12, textAlign: 'center' }}>
              <div style={{ fontSize: 10, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Available Balance</div>
              <div style={{ fontSize: 20, fontWeight: 800, color: '#38bdf8', fontFamily: 'var(--font-mono)', marginTop: 4 }}>
                {isLocal ? 'LOCAL ENGINE' : Number(ledger.balance).toLocaleString()}
              </div>
            </div>
            <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border-subtle)', borderRadius: 8, padding: 12, textAlign: 'center' }}>
              <div style={{ fontSize: 10, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>In-Flight Hold</div>
              <div style={{ fontSize: 20, fontWeight: 800, color: '#f59e0b', fontFamily: 'var(--font-mono)', marginTop: 4 }}>
                {ledger?.hold == null ? '—' : Number(ledger.hold).toLocaleString()}
              </div>
            </div>
            <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border-subtle)', borderRadius: 8, padding: 12, textAlign: 'center' }}>
              <div style={{ fontSize: 10, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Ledger Status</div>
              <div style={{ fontSize: 16, fontWeight: 800, color: '#34d399', fontFamily: 'var(--font-mono)', marginTop: 4 }}>
                {(ledger?.status || 'unknown').toUpperCase()}
              </div>
            </div>
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            {ledger?.note || 'If the studio API reports no paid balance, generation uses the Colab engine and is not charged per tool. No sample credit totals are shown.'}
          </div>
          <div>
            <div style={{ fontSize: 12, fontWeight: 700, marginBottom: 6 }}>Recent Ledger Events</div>
            <div style={{ maxHeight: 180, overflowY: 'auto', border: '1px solid var(--border-subtle)', borderRadius: 6 }}>
              <table className="studio-table">
                <thead>
                  <tr>
                    <th>Timestamp</th>
                    <th>Action</th>
                    <th>Amount</th>
                    <th>Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {events.length === 0 ? (
                    <tr>
                      <td colSpan={4}>No ledger events. Paid ZenCreator billing is disabled.</td>
                    </tr>
                  ) : (
                    events.map((event: any, idx: number) => (
                      <tr key={`${event.timestamp || 'evt'}-${idx}`}>
                        <td>{event.timestamp || '—'}</td>
                        <td>{event.action || '—'}</td>
                        <td>{event.amount ?? '—'}</td>
                        <td>{event.reason || '—'}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
