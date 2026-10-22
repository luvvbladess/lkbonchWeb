import { HttpBackend, HttpClient, HttpErrorResponse, HttpInterceptorFn, HttpResponse } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, delay, of, switchMap, throwError } from 'rxjs';

import { environment } from '../../environments/environment';
import { mockAnswer } from './mock';
import { TokenPair } from './models';
import { Session } from './session';

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const session = inject(Session);
  const router = inject(Router);
  const backend = inject(HttpBackend);
  const token = session.access();
  const isAuth = req.url.includes('/api/v1/auth/');
  const authed =
    token && !isAuth ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } }) : req;

  return next(authed).pipe(
    catchError((error: HttpErrorResponse) => {
      const refresh = session.refresh();
      if (
        environment.useMocks ||
        error.status !== 401 ||
        !refresh ||
        req.headers.has('X-Retry') ||
        req.url.includes('/auth/refresh')
      ) {
        if (error.status === 401 && !req.url.includes('/auth/login') && !req.url.includes('/auth/activation')) {
          session.clear();
          void router.navigateByUrl('/login');
        }
        return throwError(() => error);
      }
      const raw = new HttpClient(backend);
      return raw.post<TokenPair>('/api/v1/auth/refresh', { refreshToken: refresh }).pipe(
        switchMap((pair) => {
          session.setTokens(pair);
          const retry = authed.clone({
            setHeaders: { Authorization: `Bearer ${pair.accessToken}`, 'X-Retry': '1' },
          });
          return next(retry);
        }),
        catchError(() => {
          session.clear();
          void router.navigateByUrl('/login');
          return throwError(() => error);
        }),
      );
    }),
  );
};

export const mockInterceptor: HttpInterceptorFn = (req, next) => {
  if (!environment.useMocks || !req.url.startsWith('/api/')) return next(req);
  const result = mockAnswer(req);
  if (result instanceof HttpErrorResponse) return throwError(() => result);
  return of(new HttpResponse({ status: result.status, body: result.body })).pipe(delay(140));
};
