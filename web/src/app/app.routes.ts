import { Routes } from '@angular/router';

import { authGuard, guestGuard } from './core/guards';

export const routes: Routes = [
  {
    path: 'login',
    canActivate: [guestGuard],
    loadComponent: () => import('./pages/login/login').then((m) => m.LoginPage),
    title: 'Вход',
  },
  {
    path: '',
    canActivate: [authGuard],
    loadComponent: () => import('./shell/shell').then((m) => m.Shell),
    children: [
      { path: '', pathMatch: 'full', redirectTo: 'schedule' },
      {
        path: 'schedule',
        loadComponent: () => import('./pages/schedule/schedule').then((m) => m.SchedulePage),
        title: 'Расписание',
      },
      {
        path: 'schedule/:lessonId',
        loadComponent: () => import('./pages/lesson/lesson').then((m) => m.LessonPage),
        title: 'Занятие',
      },
      {
        path: 'diary',
        loadComponent: () => import('./pages/diary/diary').then((m) => m.DiaryPage),
        title: 'Дневник',
      },
      {
        path: 'diary/:groupDisciplineId',
        loadComponent: () => import('./pages/journal/journal').then((m) => m.JournalPage),
        title: 'Журнал',
      },
      {
        path: 'chats',
        loadComponent: () => import('./pages/chats/chats').then((m) => m.ChatsPage),
        title: 'Чаты',
      },
      {
        path: 'services',
        loadComponent: () => import('./pages/services/services').then((m) => m.ServicesPage),
        title: 'Услуги',
      },
      {
        path: 'services/contracts/:contractId',
        loadComponent: () => import('./pages/contract/contract').then((m) => m.ContractPage),
        title: 'Договор',
      },
      {
        path: 'profile',
        loadComponent: () => import('./pages/profile/profile').then((m) => m.ProfilePage),
        title: 'Профиль',
      },
      {
        path: 'notifications',
        loadComponent: () => import('./pages/notifications/notifications').then((m) => m.NotificationsPage),
        title: 'Уведомления',
      },
    ],
  },
  { path: '**', redirectTo: 'schedule' },
];
