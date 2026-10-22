import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatButtonToggle, MatButtonToggleGroup } from '@angular/material/button-toggle';
import { MatFormField, MatLabel, MatSuffix } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { Router } from '@angular/router';

import { environment } from '../../../environments/environment';
import { CabinetApi } from '../../core/api';
import { messageOf } from '../../core/format';
import { Session } from '../../core/session';

@Component({
  selector: 'app-login',
  imports: [
    ReactiveFormsModule,
    MatButton,
    MatIconButton,
    MatButtonToggleGroup,
    MatButtonToggle,
    MatFormField,
    MatLabel,
    MatSuffix,
    MatInput,
    MatIcon,
  ],
  templateUrl: './login.html',
})
export class LoginPage {
  private readonly api = inject(CabinetApi);
  private readonly session = inject(Session);
  private readonly router = inject(Router);
  private readonly forms = inject(FormBuilder);

  readonly mode = signal<'student' | 'staff'>('student');
  readonly step = signal<'request' | 'confirm' | 'login'>('request');
  readonly error = signal('');
  readonly hint = signal('');
  readonly busy = signal(false);
  readonly showPassword = signal(false);
  readonly mocks = environment.useMocks;
  readonly university = this.session.university;

  readonly activation = this.forms.nonNullable.group({
    lastName: ['', Validators.required],
    firstName: ['', Validators.required],
    middleName: [''],
    identifier: ['', Validators.required],
    code: [''],
    login: [''],
    password: [''],
  });

  readonly staff = this.forms.nonNullable.group({
    login: ['', Validators.required],
    password: ['', [Validators.required, Validators.minLength(8)]],
  });

  constructor() {
    this.api.university().subscribe({
      next: (university) => this.session.applyUniversity(university),
      error: () => this.error.set('Не удалось получить название университета'),
    });
  }

  requestCode(): void {
    if (this.activation.controls.lastName.invalid || this.activation.controls.firstName.invalid || this.activation.controls.identifier.invalid) {
      this.activation.markAllAsTouched();
      return;
    }
    this.busy.set(true);
    this.error.set('');
    const value = this.activation.getRawValue();
    this.api.requestActivation(value).subscribe({
      next: (ack) => {
        this.hint.set(ack.message);
        this.step.set('confirm');
        this.busy.set(false);
      },
      error: (error) => {
        this.error.set(messageOf(error));
        this.busy.set(false);
      },
    });
  }

  confirm(): void {
    const value = this.activation.getRawValue();
    if (value.password.length < 8 || value.login.trim().length < 3 || value.code.trim().length < 4) {
      this.error.set('Нужны код, логин и пароль не короче 8 символов');
      return;
    }
    this.busy.set(true);
    this.error.set('');
    this.api.confirmActivation(value).subscribe({
      next: (pair) => this.enter(pair),
      error: (error) => {
        this.error.set(messageOf(error));
        this.busy.set(false);
      },
    });
  }

  login(): void {
    if (this.staff.invalid) {
      this.staff.markAllAsTouched();
      return;
    }
    this.busy.set(true);
    this.error.set('');
    const value = this.staff.getRawValue();
    this.api.login(value.login.trim(), value.password).subscribe({
      next: (pair) => this.enter(pair),
      error: (error) => {
        this.error.set(messageOf(error));
        this.busy.set(false);
      },
    });
  }

  private enter(pair: { accessToken: string; refreshToken: string; expiresIn: number }): void {
    this.session.setTokens(pair);
    this.api.me().subscribe({
      next: (me) => {
        this.session.me.set(me);
        void this.router.navigateByUrl('/schedule');
      },
      error: (error) => {
        this.session.clear();
        this.error.set(messageOf(error));
        this.busy.set(false);
      },
    });
  }
}
