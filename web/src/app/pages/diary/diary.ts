import { Component, inject, signal } from '@angular/core';
import { MatButton } from '@angular/material/button';
import { MatIcon } from '@angular/material/icon';
import { RouterLink } from '@angular/router';

import { CabinetApi } from '../../core/api';
import { decimal, gradeKind, messageOf, requestStatus } from '../../core/format';
import { Diary, ElectiveOffer, Grade, Rating, TeachingAssignment } from '../../core/models';
import { Session } from '../../core/session';
import { StatusChip } from '../../ui/status';

@Component({
  selector: 'app-diary',
  imports: [MatButton, MatIcon, RouterLink, StatusChip],
  templateUrl: './diary.html',
})
export class DiaryPage {
  private readonly api = inject(CabinetApi);
  readonly session = inject(Session);
  readonly diary = signal<Diary | null>(null);
  readonly debts = signal<Grade[]>([]);
  readonly rating = signal<Rating | null>(null);
  readonly electives = signal<ElectiveOffer[]>([]);
  readonly teaching = signal<TeachingAssignment[]>([]);
  readonly loading = signal(true);
  readonly error = signal('');
  readonly semester = signal(0);

  constructor() {
    if (this.session.me()?.role === 'employee') {
      this.api.teaching().subscribe({
        next: (items) => {
          this.teaching.set(items);
          this.loading.set(false);
        },
        error: (error) => {
          this.error.set(messageOf(error));
          this.loading.set(false);
        },
      });
      return;
    }
    this.api.diary().subscribe({
      next: (diary) => {
        this.diary.set(diary);
        this.loading.set(false);
      },
      error: (error) => {
        this.error.set(messageOf(error));
        this.loading.set(false);
      },
    });
    this.api.debts().subscribe((items) => this.debts.set(items));
    this.api.rating().subscribe((rating) => this.rating.set(rating));
    if (this.session.me()?.enabledSections.includes('electives')) {
      this.api.electives().subscribe((items) => this.electives.set(items));
    }
  }

  kind(value: string): string {
    return gradeKind(value);
  }

  score(value: string | null): string {
    return decimal(value, 0);
  }

  ratingText(value: string | null): string {
    return decimal(value, 3);
  }

  credits(value: string): string {
    return decimal(value, 1);
  }

  status(value: string) {
    return requestStatus(value);
  }

  choose(id: string): void {
    this.api.applyElective(id).subscribe({
      next: () => this.api.electives().subscribe((items) => this.electives.set(items)),
      error: (error) => this.error.set(messageOf(error)),
    });
  }

  withdraw(id: string): void {
    this.api.withdrawElective(id).subscribe({
      next: () => this.api.electives().subscribe((items) => this.electives.set(items)),
      error: (error) => this.error.set(messageOf(error)),
    });
  }
}
