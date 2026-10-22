import { Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButton } from '@angular/material/button';
import { MatFormField, MatLabel } from '@angular/material/form-field';
import { MatInput } from '@angular/material/input';
import { MatRadioButton, MatRadioGroup } from '@angular/material/radio';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { CabinetApi } from '../../core/api';
import { contractKind, formatDate, messageOf, money, online } from '../../core/format';
import { Contract } from '../../core/models';
import { Session } from '../../core/session';

@Component({
  selector: 'app-contract',
  imports: [ReactiveFormsModule, MatButton, MatFormField, MatLabel, MatInput, MatRadioGroup, MatRadioButton, RouterLink],
  templateUrl: './contract.html',
})
export class ContractPage {
  private readonly api = inject(CabinetApi);
  private readonly destroyRef = inject(DestroyRef);
  readonly session = inject(Session);
  readonly contract = signal<Contract | null>(null);
  readonly error = signal('');
  readonly loading = signal(true);
  readonly form = inject(FormBuilder).nonNullable.group({
    amount: ['', Validators.required],
    method: ['card' as 'card' | 'sbp', Validators.required],
  });

  constructor() {
    inject(ActivatedRoute)
      .paramMap.pipe(takeUntilDestroyed())
      .subscribe((params) => {
        const id = params.get('contractId');
        if (id) this.load(id);
      });
  }

  sum(value: string): string {
    return money(value);
  }

  kind(value: string): string {
    return contractKind(value);
  }

  when(iso: string): string {
    return formatDate(iso);
  }

  pay(): void {
    const contract = this.contract();
    if (!contract || this.form.invalid) return;
    if (!online()) {
      this.error.set('Нет сети. Учебную оплату провести нельзя.');
      return;
    }
    const value = this.form.getRawValue();
    this.api.demoPayment(contract.id, value.amount.replace(',', '.'), value.method).subscribe({
      next: (result) => {
        this.session.showNotice(result.message);
        this.load(contract.id);
      },
      error: (error) => this.error.set(messageOf(error)),
    });
  }

  private load(id: string): void {
    this.api
      .contract(id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (contract) => {
          this.contract.set(contract);
          if (!this.form.controls.amount.value) this.form.controls.amount.setValue(contract.debt);
          this.loading.set(false);
        },
        error: (error) => {
          this.error.set(messageOf(error));
          this.loading.set(false);
        },
      });
  }
}
