import { HttpErrorResponse } from '@angular/common/http';

const ZONE = 'Europe/Moscow';

export function messageOf(error: unknown): string {
  if (error instanceof HttpErrorResponse) {
    const message = error.error?.error?.message;
    if (typeof message === 'string' && message) return message;
    if (error.status === 0) return 'Нет сети. Данные могут быть устаревшими.';
  }
  return 'Не удалось выполнить запрос';
}

export function personName(person: { lastName: string; firstName: string; middleName?: string }): string {
  return [person.lastName, person.firstName, person.middleName].filter(Boolean).join(' ');
}

export function formatTime(iso: string): string {
  return new Intl.DateTimeFormat('ru-RU', {
    hour: '2-digit',
    minute: '2-digit',
    timeZone: ZONE,
  }).format(new Date(iso));
}

export function formatDay(iso: string): string {
  const text = new Intl.DateTimeFormat('ru-RU', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    timeZone: ZONE,
  }).format(new Date(iso));
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function formatDate(iso: string): string {
  return new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    timeZone: ZONE,
  }).format(new Date(iso));
}

export function dayKey(iso: string): string {
  return new Intl.DateTimeFormat('en-CA', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    timeZone: ZONE,
  }).format(new Date(iso));
}

export function money(value: string): string {
  return `${new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(value))} ₽`;
}

export function decimal(value: string | null, digits = 3): string {
  if (!value) return '—';
  const number = Number(value);
  if (Number.isNaN(number)) return value;
  return new Intl.NumberFormat('ru-RU', { maximumFractionDigits: digits }).format(number);
}

export function startOfDay(date: Date): Date {
  const copy = new Date(date);
  copy.setHours(0, 0, 0, 0);
  return copy;
}

export function addDays(date: Date, days: number): Date {
  const copy = new Date(date);
  copy.setDate(copy.getDate() + days);
  return copy;
}

export function startOfWeek(date: Date): Date {
  const copy = startOfDay(date);
  const mondayOffset = (copy.getDay() + 6) % 7;
  return addDays(copy, -mondayOffset);
}

const GRADE_KIND: Record<string, string> = {
  current: 'Текущая',
  passfail: 'Зачёт',
  graded_credit: 'Диф. зачёт',
  exam: 'Экзамен',
};

const REQUEST: Record<string, { label: string; icon: string; tone: string }> = {
  pending: { label: 'На рассмотрении', icon: 'schedule', tone: 'warning' },
  in_progress: { label: 'В работе', icon: 'pending', tone: 'info' },
  ready: { label: 'Готово', icon: 'done_all', tone: 'success' },
  issued: { label: 'Выдано', icon: 'task_alt', tone: 'success' },
  rejected: { label: 'Отклонено', icon: 'block', tone: 'error' },
  settled: { label: 'Заселён', icon: 'done_all', tone: 'success' },
  approved: { label: 'Одобрено', icon: 'done_all', tone: 'success' },
  withdrawn: { label: 'Отозвано', icon: 'undo', tone: 'neutral' },
  applied: { label: 'Внесено', icon: 'task_alt', tone: 'success' },
};

export function gradeKind(kind: string): string {
  return GRADE_KIND[kind] ?? kind;
}

export function requestStatus(status: string): { label: string; icon: string; tone: string } {
  return REQUEST[status] ?? { label: status, icon: 'info', tone: 'neutral' };
}

export function fundingLabel(value: string): string {
  if (value === 'budget') return 'Бюджет';
  if (value === 'paid') return 'Договор';
  if (value === 'targeted') return 'Целевое';
  return value;
}

export function deliveryLabel(value: string): string {
  if (value === 'electronic') return 'Электронная';
  if (value === 'paper') return 'Бумажная';
  if (value === 'appointment') return 'Очно';
  return value;
}

export function contractKind(value: string): string {
  if (value === 'tuition') return 'Обучение';
  if (value === 'housing') return 'Общежитие';
  return 'Прочее';
}

export function correctionField(value: string): string {
  const labels: Record<string, string> = {
    group: 'Группа',
    course: 'Курс',
    record_book_number: 'Номер зачётки',
    student_card_number: 'Номер студенческого',
    funding: 'Основа обучения',
    lives_in_dorm: 'Проживание в общежитии',
  };
  return labels[value] ?? value;
}

export function online(): boolean {
  return navigator.onLine;
}
