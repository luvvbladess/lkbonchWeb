import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import {
  CertificateRequest,
  CertificateType,
  Contract,
  Conversation,
  Diary,
  DormApplication,
  ElectiveOffer,
  Grade,
  JournalStudent,
  Lesson,
  LessonDetail,
  Me,
  Message,
  MessagePage,
  NotificationItem,
  PortfolioDocument,
  ProfileCorrection,
  Rating,
  ScholarshipView,
  StudentCard,
  TeachingAssignment,
  TokenPair,
  UniversityPublic,
} from './models';

@Injectable({ providedIn: 'root' })
export class CabinetApi {
  private readonly http = inject(HttpClient);

  university(): Observable<UniversityPublic> {
    return this.http.get<UniversityPublic>('/api/v1/university');
  }

  requestActivation(body: {
    lastName: string;
    firstName: string;
    middleName: string;
    identifier: string;
  }): Observable<{ message: string }> {
    return this.http.post<{ message: string }>('/api/v1/auth/activation/request', body);
  }

  confirmActivation(body: {
    lastName: string;
    firstName: string;
    middleName: string;
    identifier: string;
    code: string;
    login: string;
    password: string;
  }): Observable<TokenPair> {
    return this.http.post<TokenPair>('/api/v1/auth/activation/confirm', body);
  }

  login(login: string, password: string): Observable<TokenPair> {
    return this.http.post<TokenPair>('/api/v1/auth/login', { login, password });
  }

  logout(refreshToken: string): Observable<void> {
    return this.http.post<void>('/api/v1/auth/logout', { refreshToken });
  }

  changePassword(currentPassword: string, newPassword: string): Observable<void> {
    return this.http.post<void>('/api/v1/auth/password', { currentPassword, newPassword });
  }

  me(): Observable<Me> {
    return this.http.get<Me>('/api/v1/me');
  }

  updateContacts(email: string, phone: string): Observable<Me> {
    return this.http.patch<Me>('/api/v1/me/contacts', { email, phone });
  }

  studentCard(): Observable<StudentCard> {
    return this.http.get<StudentCard>('/api/v1/me/student-card');
  }

  scholarship(): Observable<ScholarshipView> {
    return this.http.get<ScholarshipView>('/api/v1/me/scholarship');
  }

  rating(): Observable<Rating> {
    return this.http.get<Rating>('/api/v1/me/rating');
  }

  corrections(): Observable<ProfileCorrection[]> {
    return this.http.get<ProfileCorrection[]>('/api/v1/me/corrections');
  }

  createCorrection(fieldName: string, requestedValue: string, comment: string): Observable<ProfileCorrection> {
    return this.http.post<ProfileCorrection>('/api/v1/me/corrections', { fieldName, requestedValue, comment });
  }

  schedule(from: Date, to: Date): Observable<Lesson[]> {
    const params = new HttpParams().set('from', from.toISOString()).set('to', to.toISOString());
    return this.http.get<Lesson[]>('/api/v1/schedule', { params });
  }

  lesson(id: string): Observable<LessonDetail> {
    return this.http.get<LessonDetail>(`/api/v1/lessons/${id}`);
  }

  markOwn(id: string): Observable<unknown> {
    return this.http.post(`/api/v1/lessons/${id}/attendance`, {});
  }

  correctStudent(lessonId: string, userId: string, mark: 'present' | 'absent'): Observable<unknown> {
    return this.http.patch(`/api/v1/lessons/${lessonId}/attendance/${userId}`, { mark });
  }

  diary(): Observable<Diary> {
    return this.http.get<Diary>('/api/v1/diary');
  }

  debts(): Observable<Grade[]> {
    return this.http.get<Grade[]>('/api/v1/debts');
  }

  teaching(): Observable<TeachingAssignment[]> {
    return this.http.get<TeachingAssignment[]>('/api/v1/teaching');
  }

  journal(groupDisciplineId: string): Observable<JournalStudent[]> {
    return this.http.get<JournalStudent[]>(`/api/v1/teaching/${groupDisciplineId}/grades`);
  }

  createGrade(body: {
    studentId: string;
    disciplineId: string;
    semesterId: string;
    kind: string;
    title: string;
    score: string | null;
    label: string;
    isFinal: boolean;
  }): Observable<Grade> {
    return this.http.post<Grade>('/api/v1/grades', body);
  }

  electives(): Observable<ElectiveOffer[]> {
    return this.http.get<ElectiveOffer[]>('/api/v1/electives');
  }

  applyElective(groupDisciplineId: string): Observable<unknown> {
    return this.http.post('/api/v1/elective-applications', { groupDisciplineId });
  }

  withdrawElective(id: string): Observable<unknown> {
    return this.http.patch(`/api/v1/elective-applications/${id}`, {});
  }

  conversations(query = ''): Observable<Conversation[]> {
    const params = query ? new HttpParams().set('q', query) : undefined;
    return this.http.get<Conversation[]>('/api/v1/conversations', { params });
  }

  messages(id: string): Observable<MessagePage> {
    return this.http.get<MessagePage>(`/api/v1/conversations/${id}/messages`);
  }

  sendMessage(id: string, clientMessageId: string, body: string): Observable<Message> {
    return this.http.post<Message>(`/api/v1/conversations/${id}/messages`, { clientMessageId, body });
  }

  editMessage(id: string, body: string): Observable<Message> {
    return this.http.patch<Message>(`/api/v1/messages/${id}`, { body });
  }

  deleteMessage(id: string): Observable<void> {
    return this.http.delete<void>(`/api/v1/messages/${id}`);
  }

  markRead(conversationId: string, messageId: string): Observable<void> {
    return this.http.post<void>(`/api/v1/conversations/${conversationId}/read`, { messageId });
  }

  notifications(): Observable<{ items: NotificationItem[]; nextCursor: string | null }> {
    return this.http.get<{ items: NotificationItem[]; nextCursor: string | null }>('/api/v1/notifications');
  }

  readNotification(id: string): Observable<void> {
    return this.http.post<void>(`/api/v1/notifications/${id}/read`, {});
  }

  readAllNotifications(): Observable<void> {
    return this.http.post<void>('/api/v1/notifications/read-all', {});
  }

  certificateTypes(): Observable<CertificateType[]> {
    return this.http.get<CertificateType[]>('/api/v1/certificate-types');
  }

  certificateRequests(): Observable<CertificateRequest[]> {
    return this.http.get<CertificateRequest[]>('/api/v1/certificate-requests');
  }

  createCertificate(typeId: string, deliveryMode: string, comment: string): Observable<CertificateRequest> {
    return this.http.post<CertificateRequest>('/api/v1/certificate-requests', { typeId, deliveryMode, comment });
  }

  dorms(): Observable<DormApplication[]> {
    return this.http.get<DormApplication[]>('/api/v1/dorm-applications');
  }

  createDorm(comment: string): Observable<DormApplication> {
    return this.http.post<DormApplication>('/api/v1/dorm-applications', { comment });
  }

  contracts(): Observable<Contract[]> {
    return this.http.get<Contract[]>('/api/v1/contracts');
  }

  contract(id: string): Observable<Contract> {
    return this.http.get<Contract>(`/api/v1/contracts/${id}`);
  }

  demoPayment(id: string, amount: string, method: 'card' | 'sbp'): Observable<{ message: string; educational: true }> {
    return this.http.post<{ message: string; educational: true }>(`/api/v1/contracts/${id}/demo-payments`, {
      amount,
      method,
    });
  }

  portfolio(): Observable<PortfolioDocument[]> {
    return this.http.get<PortfolioDocument[]>('/api/v1/portfolio');
  }

  createPortfolio(title: string, body: string): Observable<PortfolioDocument> {
    return this.http.post<PortfolioDocument>('/api/v1/portfolio', { kind: 'portfolio', title, body });
  }

  deletePortfolio(id: string): Observable<void> {
    return this.http.delete<void>(`/api/v1/portfolio/${id}`);
  }
}
