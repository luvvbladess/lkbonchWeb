import { Component, ElementRef, effect, inject, signal, viewChild } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { toCanvas } from 'qrcode';
import { MatButton } from '@angular/material/button';
import { MatFormField, MatLabel } from '@angular/material/form-field';
import { MatInput } from '@angular/material/input';
import { MatOption, MatSelect } from '@angular/material/select';

import { CabinetApi } from '../../core/api';
import { correctionField, decimal, formatDate, fundingLabel, messageOf, money, personName, requestStatus } from '../../core/format';
import { PortfolioDocument, ProfileCorrection, ScholarshipView, StudentCard } from '../../core/models';
import { Session } from '../../core/session';
import { StatusChip } from '../../ui/status';

@Component({
  selector: 'app-profile',
  imports: [ReactiveFormsModule, MatButton, MatFormField, MatLabel, MatInput, MatSelect, MatOption, StatusChip],
  templateUrl: './profile.html',
})
export class ProfilePage {
  private readonly api = inject(CabinetApi);
  readonly session = inject(Session);
  readonly card = signal<StudentCard | null>(null);
  readonly scholarship = signal<ScholarshipView | null>(null);
  readonly corrections = signal<ProfileCorrection[]>([]);
  readonly portfolio = signal<PortfolioDocument[]>([]);
  readonly bright = signal(false);
  readonly error = signal('');
  private readonly qr = viewChild<ElementRef<HTMLCanvasElement>>('qr');
  private readonly qrBright = viewChild<ElementRef<HTMLCanvasElement>>('qrBright');

  readonly contacts = inject(FormBuilder).nonNullable.group({
    email: [''],
    phone: [''],
  });
  readonly password = inject(FormBuilder).nonNullable.group({
    currentPassword: ['', Validators.required],
    newPassword: ['', [Validators.required, Validators.minLength(8)]],
  });
  readonly correction = inject(FormBuilder).nonNullable.group({
    fieldName: ['group', Validators.required],
    requestedValue: ['', Validators.required],
    comment: [''],
  });
  readonly document = inject(FormBuilder).nonNullable.group({
    title: ['', Validators.required],
    body: [''],
  });

  constructor() {
    const me = this.session.me();
    if (me) {
      this.contacts.setValue({ email: me.email ?? '', phone: me.phone ?? '' });
    }
    if (me?.role === 'student') {
      this.api.studentCard().subscribe((card) => this.card.set(card));
      this.api.corrections().subscribe((items) => this.corrections.set(items));
    }
    if (me?.enabledSections.includes('scholarships') && me.role === 'student') {
      this.api.scholarship().subscribe((view) => this.scholarship.set(view));
    }
    if (me?.enabledSections.includes('portfolio')) {
      this.api.portfolio().subscribe((items) => this.portfolio.set(items));
    }
    effect(() => {
      const payload = this.card()?.qrPayload;
      if (!payload) return;
      for (const ref of [this.qr(), this.qrBright()]) {
        const canvas = ref?.nativeElement;
        if (!canvas) continue;
        void toCanvas(canvas, payload, {
          width: canvas.width || 196,
          margin: 1,
          color: { dark: '#1d1b19', light: '#ffffff' },
        });
      }
    });
  }

  name(): string {
    const me = this.session.me();
    return me ? personName(me) : '';
  }

  funding(value: string): string {
    return fundingLabel(value);
  }

  field(value: string): string {
    return correctionField(value);
  }

  status(value: string) {
    return requestStatus(value);
  }

  sum(value: string): string {
    return money(value);
  }

  when(iso: string): string {
    return formatDate(iso);
  }

  ratingText(value: string | null): string {
    return decimal(value, 3);
  }

  saveContacts(): void {
    const value = this.contacts.getRawValue();
    this.api.updateContacts(value.email.trim(), value.phone.trim()).subscribe({
      next: (me) => {
        this.session.me.set(me);
        this.session.showNotice('Контакты сохранены');
      },
      error: (error) => this.error.set(messageOf(error)),
    });
  }

  savePassword(): void {
    if (this.password.invalid) {
      this.password.markAllAsTouched();
      return;
    }
    const value = this.password.getRawValue();
    this.api.changePassword(value.currentPassword, value.newPassword).subscribe({
      next: () => {
        this.password.reset();
        this.session.showNotice('Пароль изменён, другие сеансы закрыты');
      },
      error: (error) => this.error.set(messageOf(error)),
    });
  }

  sendCorrection(): void {
    if (this.correction.invalid) return;
    const value = this.correction.getRawValue();
    this.api.createCorrection(value.fieldName, value.requestedValue.trim(), value.comment.trim()).subscribe({
      next: () => this.api.corrections().subscribe((items) => this.corrections.set(items)),
      error: (error) => this.error.set(messageOf(error)),
    });
  }

  addDocument(): void {
    if (this.document.invalid) return;
    const value = this.document.getRawValue();
    this.api.createPortfolio(value.title.trim(), value.body.trim()).subscribe({
      next: () => {
        this.document.reset();
        this.api.portfolio().subscribe((items) => this.portfolio.set(items));
      },
      error: (error) => this.error.set(messageOf(error)),
    });
  }

  removeDocument(id: string): void {
    this.api.deletePortfolio(id).subscribe({
      next: () => this.portfolio.update((items) => items.filter((item) => item.id !== id)),
      error: (error) => this.error.set(messageOf(error)),
    });
  }
}
