import { Component, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButton } from '@angular/material/button';
import { MatButtonToggle, MatButtonToggleGroup } from '@angular/material/button-toggle';
import { MatFormField, MatLabel } from '@angular/material/form-field';
import { MatInput } from '@angular/material/input';
import { MatOption, MatSelect } from '@angular/material/select';
import { RouterLink } from '@angular/router';

import { CabinetApi } from '../../core/api';
import { contractKind, deliveryLabel, formatDate, messageOf, money, requestStatus } from '../../core/format';
import { CertificateRequest, CertificateType, Contract, DormApplication, Section } from '../../core/models';
import { Session } from '../../core/session';
import { StatusChip } from '../../ui/status';

@Component({
  selector: 'app-services',
  imports: [
    ReactiveFormsModule,
    MatButton,
    MatButtonToggleGroup,
    MatButtonToggle,
    MatFormField,
    MatLabel,
    MatInput,
    MatSelect,
    MatOption,
    RouterLink,
    StatusChip,
  ],
  templateUrl: './services.html',
})
export class ServicesPage {
  private readonly api = inject(CabinetApi);
  readonly session = inject(Session);
  readonly tab = signal<'certificates' | 'dorm' | 'contracts'>('certificates');
  readonly types = signal<CertificateType[]>([]);
  readonly certificates = signal<CertificateRequest[]>([]);
  readonly dorms = signal<DormApplication[]>([]);
  readonly contracts = signal<Contract[]>([]);
  readonly error = signal('');
  readonly loading = signal(true);
  readonly certificateForm = inject(FormBuilder).nonNullable.group({
    typeId: ['', Validators.required],
    deliveryMode: ['electronic', Validators.required],
    comment: [''],
  });
  readonly dormComment = inject(FormBuilder).nonNullable.control('');

  readonly tabs = computed(() => {
    const enabled = new Set(this.session.me()?.enabledSections ?? []);
    const items: { id: 'certificates' | 'dorm' | 'contracts'; label: string; section: Section }[] = [
      { id: 'certificates', label: 'Справки', section: 'certificates' },
      { id: 'dorm', label: 'Общежитие', section: 'dormitory' },
      { id: 'contracts', label: 'Договоры', section: 'contracts' },
    ];
    return items.filter((item) => enabled.has(item.section));
  });

  constructor() {
    const first = this.tabs()[0];
    if (first) this.tab.set(first.id);
    this.reload();
  }

  status(value: string) {
    return requestStatus(value);
  }

  delivery(value: string): string {
    return deliveryLabel(value);
  }

  when(iso: string): string {
    return formatDate(iso);
  }

  kind(value: string): string {
    return contractKind(value);
  }

  sum(value: string): string {
    return money(value);
  }

  orderCertificate(): void {
    if (this.certificateForm.invalid) {
      this.certificateForm.markAllAsTouched();
      return;
    }
    const value = this.certificateForm.getRawValue();
    this.api.createCertificate(value.typeId, value.deliveryMode, value.comment).subscribe({
      next: () => this.reload(),
      error: (error) => this.error.set(messageOf(error)),
    });
  }

  orderDorm(): void {
    this.api.createDorm(this.dormComment.value).subscribe({
      next: () => this.reload(),
      error: (error) => this.error.set(messageOf(error)),
    });
  }

  private reload(): void {
    this.loading.set(true);
    this.api.certificateTypes().subscribe((items) => this.types.set(items.filter((item) => item.enabled)));
    this.api.certificateRequests().subscribe({
      next: (items) => {
        this.certificates.set(items);
        this.loading.set(false);
      },
      error: (error) => {
        this.error.set(messageOf(error));
        this.loading.set(false);
      },
    });
    this.api.dorms().subscribe((items) => this.dorms.set(items));
    this.api.contracts().subscribe((items) => this.contracts.set(items));
  }
}
