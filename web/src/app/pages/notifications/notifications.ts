import { Component, inject, signal } from '@angular/core';
import { MatButton } from '@angular/material/button';

import { CabinetApi } from '../../core/api';
import { formatDay, formatTime, messageOf } from '../../core/format';
import { NotificationItem } from '../../core/models';

@Component({
  selector: 'app-notifications',
  imports: [MatButton],
  templateUrl: './notifications.html',
})
export class NotificationsPage {
  private readonly api = inject(CabinetApi);
  readonly items = signal<NotificationItem[]>([]);
  readonly error = signal('');
  readonly loading = signal(true);

  constructor() {
    this.load();
  }

  when(iso: string): string {
    return `${formatDay(iso)}, ${formatTime(iso)}`;
  }

  read(item: NotificationItem): void {
    if (item.readAt) return;
    this.api.readNotification(item.id).subscribe({ next: () => this.load(), error: (error) => this.error.set(messageOf(error)) });
  }

  readAll(): void {
    this.api.readAllNotifications().subscribe({ next: () => this.load(), error: (error) => this.error.set(messageOf(error)) });
  }

  private load(): void {
    this.api.notifications().subscribe({
      next: (page) => {
        this.items.set(page.items);
        this.loading.set(false);
      },
      error: (error) => {
        this.error.set(messageOf(error));
        this.loading.set(false);
      },
    });
  }
}
