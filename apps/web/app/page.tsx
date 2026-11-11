'use client';

import { StudioProvider } from '../lib/studio/store';
import { StudioShell } from '../components/StudioShell';

export default function StudioPage() {
  return (
    <StudioProvider>
      <StudioShell />
    </StudioProvider>
  );
}
