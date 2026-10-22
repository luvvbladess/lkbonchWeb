import { Injectable, signal } from '@angular/core';

import { Me, TokenPair, UniversityPublic } from './models';

const ACCESS = 'lk.access';
const REFRESH = 'lk.refresh';

@Injectable({ providedIn: 'root' })
export class Session {
  readonly access = signal<string | null>(sessionStorage.getItem(ACCESS));
  readonly refresh = signal<string | null>(sessionStorage.getItem(REFRESH));
  readonly me = signal<Me | null>(null);
  readonly university = signal<UniversityPublic | null>(null);
  readonly dark = signal(localStorage.getItem('lk.theme') === 'dark');
  readonly notice = signal('');

  constructor() {
    this.paint();
  }

  setTokens(pair: TokenPair): void {
    this.access.set(pair.accessToken);
    this.refresh.set(pair.refreshToken);
    sessionStorage.setItem(ACCESS, pair.accessToken);
    sessionStorage.setItem(REFRESH, pair.refreshToken);
  }

  clear(): void {
    this.access.set(null);
    this.refresh.set(null);
    this.me.set(null);
    sessionStorage.removeItem(ACCESS);
    sessionStorage.removeItem(REFRESH);
  }

  toggleTheme(): void {
    const next = !this.dark();
    this.dark.set(next);
    localStorage.setItem('lk.theme', next ? 'dark' : 'light');
    this.paint();
  }

  applyUniversity(university: UniversityPublic): void {
    this.university.set(university);
    this.paint();
  }

  private paint(): void {
    const root = document.documentElement;
    root.classList.toggle('dark', this.dark());
    const university = this.university();
    if (university) {
      root.style.setProperty('--lk-brand', university.brandSeed);
    }
    if (!this.dark() && university?.brandAccent) {
      root.style.setProperty('--mat-sys-primary', university.brandAccent);
    } else {
      root.style.removeProperty('--mat-sys-primary');
    }
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', this.dark() ? '#1d1b19' : '#fffbf8');
  }

  showNotice(text: string): void {
    this.notice.set(text);
    const current = text;
    setTimeout(() => {
      if (this.notice() === current) this.notice.set('');
    }, 4200);
  }
}
