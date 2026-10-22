import { Component, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { BreakpointObserver } from '@angular/cdk/layout';
import { MatIconButton } from '@angular/material/button';
import { MatIcon } from '@angular/material/icon';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { map } from 'rxjs';

import { CabinetApi } from '../core/api';
import { personName } from '../core/format';
import { Section } from '../core/models';
import { Session } from '../core/session';

interface NavItem {
  path: string;
  label: string;
  icon: string;
  sections: Section[] | null;
}

const NAV: NavItem[] = [
  { path: '/schedule', label: 'Расписание', icon: 'calendar_today', sections: ['schedule'] },
  { path: '/diary', label: 'Дневник', icon: 'menu_book', sections: ['diary'] },
  { path: '/chats', label: 'Чаты', icon: 'forum', sections: ['chats'] },
  { path: '/services', label: 'Услуги', icon: 'description', sections: ['certificates', 'dormitory', 'contracts'] },
  { path: '/profile', label: 'Профиль', icon: 'person', sections: null },
];

@Component({
  selector: 'app-shell',
  imports: [RouterOutlet, RouterLink, RouterLinkActive, MatIcon, MatIconButton],
  templateUrl: './shell.html',
})
export class Shell {
  private readonly api = inject(CabinetApi);
  private readonly router = inject(Router);
  readonly session = inject(Session);
  readonly offline = signal(!navigator.onLine);
  readonly unread = signal(0);

  readonly layout = toSignal(
    inject(BreakpointObserver)
      .observe(['(max-width: 599.98px)', '(min-width: 600px) and (max-width: 839.98px)', '(min-width: 840px)'])
      .pipe(
        map((state) => {
          if (state.breakpoints['(min-width: 840px)']) return 'expanded';
          if (state.breakpoints['(min-width: 600px) and (max-width: 839.98px)']) return 'medium';
          return 'compact';
        }),
      ),
    { initialValue: 'expanded' as 'compact' | 'medium' | 'expanded' },
  );

  readonly items = computed(() => {
    const enabled = new Set(this.session.me()?.enabledSections ?? []);
    return NAV.filter((item) => !item.sections || item.sections.some((section) => enabled.has(section)));
  });

  readonly name = computed(() => {
    const me = this.session.me();
    return me ? personName(me) : '';
  });

  constructor() {
    window.addEventListener('online', () => this.offline.set(false));
    window.addEventListener('offline', () => this.offline.set(true));
    this.api.university().subscribe((university) => this.session.applyUniversity(university));
    this.api.notifications().subscribe((page) => this.unread.set(page.items.filter((item) => !item.readAt).length));
  }

  logout(): void {
    const refresh = this.session.refresh();
    const done = () => {
      this.session.clear();
      void this.router.navigateByUrl('/login');
    };
    if (!refresh) {
      done();
      return;
    }
    this.api.logout(refresh).subscribe({ next: done, error: done });
  }
}
