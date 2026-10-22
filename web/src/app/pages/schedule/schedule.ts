import { Component, computed, effect, inject, signal, untracked } from '@angular/core';
import { MatButtonToggle, MatButtonToggleGroup } from '@angular/material/button-toggle';
import { MatIconButton } from '@angular/material/button';
import { MatIcon } from '@angular/material/icon';
import { RouterLink } from '@angular/router';

import { CabinetApi } from '../../core/api';
import { addDays, dayKey, formatDay, formatTime, messageOf, startOfDay, startOfWeek } from '../../core/format';
import { Lesson } from '../../core/models';
import { StatusChip } from '../../ui/status';

@Component({
  selector: 'app-schedule',
  imports: [MatButtonToggleGroup, MatButtonToggle, MatIconButton, MatIcon, RouterLink, StatusChip],
  templateUrl: './schedule.html',
})
export class SchedulePage {
  private readonly api = inject(CabinetApi);
  readonly span = signal<'day' | 'week'>('day');
  readonly anchor = signal(new Date());
  readonly lessons = signal<Lesson[]>([]);
  readonly loading = signal(true);
  readonly error = signal('');

  readonly range = computed(() => {
    const anchor = this.anchor();
    if (this.span() === 'week') {
      const from = startOfWeek(anchor);
      return { from, to: addDays(from, 7), label: `${formatDay(from.toISOString())} — ${formatDay(addDays(from, 6).toISOString())}` };
    }
    const from = startOfDay(anchor);
    return { from, to: addDays(from, 1), label: formatDay(from.toISOString()) };
  });

  readonly groups = computed(() => {
    const buckets = new Map<string, Lesson[]>();
    for (const lesson of this.lessons()) {
      const key = dayKey(lesson.startsAt);
      buckets.set(key, [...(buckets.get(key) ?? []), lesson]);
    }
    return [...buckets.entries()].map(([key, items]) => ({
      key,
      title: formatDay(items[0].startsAt),
      items,
    }));
  });

  constructor() {
    effect(() => {
      const range = this.range();
      untracked(() => this.load(range.from, range.to));
    });
  }

  shift(direction: number): void {
    const step = this.span() === 'week' ? 7 : 1;
    this.anchor.set(addDays(this.anchor(), direction * step));
  }

  today(): void {
    this.anchor.set(new Date());
  }

  time(iso: string): string {
    return formatTime(iso);
  }

  private load(from: Date, to: Date): void {
    this.loading.set(true);
    this.error.set('');
    this.api.schedule(from, to).subscribe({
      next: (lessons) => {
        this.lessons.set(lessons);
        this.loading.set(false);
      },
      error: (error) => {
        this.error.set(messageOf(error));
        this.loading.set(false);
      },
    });
  }
}
