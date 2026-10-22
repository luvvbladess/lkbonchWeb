import { Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatFormField, MatLabel } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { ActivatedRoute, Router } from '@angular/router';
import { debounceTime } from 'rxjs';

import { CabinetApi } from '../../core/api';
import { formatTime, messageOf, online } from '../../core/format';
import { Conversation, Message } from '../../core/models';
import { Session } from '../../core/session';
import { StatusChip } from '../../ui/status';

@Component({
  selector: 'app-chats',
  imports: [ReactiveFormsModule, MatButton, MatIconButton, MatFormField, MatLabel, MatInput, MatIcon, StatusChip],
  templateUrl: './chats.html',
})
export class ChatsPage {
  private readonly api = inject(CabinetApi);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);
  readonly session = inject(Session);
  readonly conversations = signal<Conversation[]>([]);
  readonly messages = signal<Message[]>([]);
  readonly current = signal<Conversation | null>(null);
  readonly loading = signal(true);
  readonly error = signal('');
  readonly draft = new FormControl('', { nonNullable: true });
  readonly search = new FormControl('', { nonNullable: true });
  readonly editing = signal<string | null>(null);
  private selectedId: string | null = null;

  constructor() {
    this.search.valueChanges.pipe(debounceTime(250), takeUntilDestroyed()).subscribe((query) => this.loadList(query));
    inject(ActivatedRoute)
      .queryParamMap.pipe(takeUntilDestroyed())
      .subscribe((params) => this.open(params.get('c')));
    this.loadList('');
  }

  time(iso: string): string {
    return formatTime(iso);
  }

  select(id: string): void {
    void this.router.navigate(['/chats'], { queryParams: { c: id } });
  }

  back(): void {
    void this.router.navigate(['/chats']);
  }

  onEnter(event: Event): void {
    const keyboard = event as KeyboardEvent;
    if (keyboard.shiftKey) return;
    keyboard.preventDefault();
    this.send();
  }

  send(): void {
    const conversation = this.current();
    const body = this.draft.value.trim();
    if (!conversation || !body) return;
    if (!online()) {
      this.error.set('Сообщение не доставлено. Нет сети.');
      return;
    }
    if (conversation.closed) return;
    const editing = this.editing();
    const request = editing
      ? this.api.editMessage(editing, body)
      : this.api.sendMessage(conversation.id, crypto.randomUUID(), body);
    request.subscribe({
      next: () => {
        this.draft.setValue('');
        this.editing.set(null);
        this.open(conversation.id);
        this.loadList(this.search.value);
      },
      error: (error) => this.error.set(messageOf(error)),
    });
  }

  edit(message: Message): void {
    this.editing.set(message.id);
    this.draft.setValue(message.body);
  }

  remove(message: Message): void {
    this.api.deleteMessage(message.id).subscribe({
      next: () => this.open(this.current()?.id ?? null),
      error: (error) => this.error.set(messageOf(error)),
    });
  }

  private loadList(query: string): void {
    this.api.conversations(query).subscribe({
      next: (items) => {
        this.conversations.set(items);
        this.loading.set(false);
        if (this.selectedId) {
          this.current.set(items.find((item) => item.id === this.selectedId) ?? null);
        }
      },
      error: (error) => {
        this.error.set(messageOf(error));
        this.loading.set(false);
      },
    });
  }

  private open(id: string | null): void {
    this.selectedId = id;
    if (!id) {
      this.current.set(null);
      this.messages.set([]);
      return;
    }
    this.current.set(this.conversations().find((item) => item.id === id) ?? null);
    this.api
      .messages(id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (page) => {
          this.messages.set(page.items);
          const last = page.items.at(-1);
          if (last) this.api.markRead(id, last.id).subscribe();
        },
        error: (error) => this.error.set(messageOf(error)),
      });
  }
}
