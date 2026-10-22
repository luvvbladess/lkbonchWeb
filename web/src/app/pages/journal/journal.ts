import { Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButton } from '@angular/material/button';
import { MatCheckbox } from '@angular/material/checkbox';
import { MatFormField, MatLabel } from '@angular/material/form-field';
import { MatInput } from '@angular/material/input';
import { MatOption, MatSelect } from '@angular/material/select';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { CabinetApi } from '../../core/api';
import { gradeKind, messageOf } from '../../core/format';
import { JournalStudent, TeachingAssignment } from '../../core/models';

@Component({
  selector: 'app-journal',
  imports: [ReactiveFormsModule, MatButton, MatCheckbox, MatFormField, MatLabel, MatInput, MatSelect, MatOption, RouterLink],
  templateUrl: './journal.html',
})
export class JournalPage {
  private readonly api = inject(CabinetApi);
  private readonly destroyRef = inject(DestroyRef);
  readonly students = signal<JournalStudent[]>([]);
  readonly assignment = signal<TeachingAssignment | null>(null);
  readonly loading = signal(true);
  readonly error = signal('');
  readonly form = inject(FormBuilder).nonNullable.group({
    studentId: ['', Validators.required],
    kind: ['current', Validators.required],
    title: ['', Validators.required],
    score: [''],
    label: [''],
    isFinal: [false],
  });

  constructor() {
    inject(ActivatedRoute)
      .paramMap.pipe(takeUntilDestroyed())
      .subscribe((params) => {
        const id = params.get('groupDisciplineId');
        if (!id) return;
        this.api.teaching().subscribe((items) => this.assignment.set(items.find((item) => item.groupDisciplineId === id) ?? null));
        this.load(id);
      });
  }

  kind(value: string): string {
    return gradeKind(value);
  }

  save(): void {
    const assignment = this.assignment();
    if (!assignment || this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    const value = this.form.getRawValue();
    this.api
      .createGrade({
        studentId: value.studentId,
        disciplineId: assignment.disciplineId,
        semesterId: assignment.semesterId,
        kind: value.kind,
        title: value.title.trim(),
        score: value.score.trim() || null,
        label: value.label.trim(),
        isFinal: value.isFinal,
      })
      .subscribe({
        next: () => this.load(assignment.groupDisciplineId),
        error: (error) => this.error.set(messageOf(error)),
      });
  }

  private load(id: string): void {
    this.api
      .journal(id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (students) => {
          this.students.set(students);
          this.loading.set(false);
        },
        error: (error) => {
          this.error.set(messageOf(error));
          this.loading.set(false);
        },
      });
  }
}
