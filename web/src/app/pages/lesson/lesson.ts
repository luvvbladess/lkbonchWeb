import { Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { MatButton } from '@angular/material/button';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { CabinetApi } from '../../core/api';
import { formatDay, formatTime, messageOf, online } from '../../core/format';
import { LessonDetail } from '../../core/models';
import { Session } from '../../core/session';
import { StatusChip } from '../../ui/status';

@Component({
  selector: 'app-lesson',
  imports: [MatButton, RouterLink, StatusChip],
  templateUrl: './lesson.html',
})
export class LessonPage {
  private readonly api = inject(CabinetApi);
  private readonly destroyRef = inject(DestroyRef);
  readonly session = inject(Session);
  readonly lesson = signal<LessonDetail | null>(null);
  readonly loading = signal(true);
  readonly error = signal('');
  readonly actionError = signal('');

  constructor() {
    inject(ActivatedRoute)
      .paramMap.pipe(takeUntilDestroyed())
      .subscribe((params) => {
        const id = params.get('lessonId');
        if (id) this.load(id);
      });
  }

  time(iso: string): string {
    return formatTime(iso);
  }

  day(iso: string): string {
    return formatDay(iso);
  }

  markFor(userId: string) {
    return this.lesson()?.attendance.find((item) => item.userId === userId);
  }

  markSelf(): void {
    const lesson = this.lesson();
    if (!lesson) return;
    if (!online()) {
      this.actionError.set('Не удалось отметиться. Нет сети — обратитесь к преподавателю.');
      return;
    }
    this.actionError.set('');
    this.api.markOwn(lesson.id).subscribe({
      next: () => this.load(lesson.id),
      error: (error) => this.actionError.set(messageOf(error)),
    });
  }

  correct(userId: string, mark: 'present' | 'absent'): void {
    const lesson = this.lesson();
    if (!lesson) return;
    if (!online()) {
      this.actionError.set('Нет сети. Отметку сохранить нельзя.');
      return;
    }
    this.api.correctStudent(lesson.id, userId, mark).subscribe({
      next: () => this.load(lesson.id),
      error: (error) => this.actionError.set(messageOf(error)),
    });
  }

  private load(id: string): void {
    this.loading.set(true);
    this.api
      .lesson(id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (lesson) => {
          this.lesson.set(lesson);
          this.loading.set(false);
        },
        error: (error) => {
          this.error.set(messageOf(error));
          this.loading.set(false);
        },
      });
  }
}
