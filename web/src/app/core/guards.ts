import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { catchError, map, of, tap } from 'rxjs';

import { CabinetApi } from './api';
import { Session } from './session';

export const authGuard: CanActivateFn = () => {
  const session = inject(Session);
  const api = inject(CabinetApi);
  const router = inject(Router);
  if (!session.access()) return router.createUrlTree(['/login']);
  if (session.me()) return true;
  return api.me().pipe(
    tap((me) => session.me.set(me)),
    map(() => true),
    catchError(() => {
      session.clear();
      return of(router.createUrlTree(['/login']));
    }),
  );
};

export const guestGuard: CanActivateFn = () => {
  const session = inject(Session);
  const router = inject(Router);
  return session.access() ? router.createUrlTree(['/schedule']) : true;
};
