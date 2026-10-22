export type Role = 'student' | 'employee' | 'admin';
export type Section =
  | 'schedule'
  | 'diary'
  | 'chats'
  | 'electives'
  | 'certificates'
  | 'dormitory'
  | 'contracts'
  | 'portfolio'
  | 'scholarships';

export interface TokenPair {
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
}

export interface UniversityPublic {
  name: string;
  shortName: string;
  brandSeed: string;
  brandAccent: string;
  enabledSections: Section[];
  logoUrl: string | null;
}

export interface Me {
  id: string;
  role: Role;
  status: string;
  lastName: string;
  firstName: string;
  middleName: string;
  login: string | null;
  email: string | null;
  phone: string | null;
  permissions: string[];
  enabledSections: Section[];
  student: {
    groupId: string | null;
    groupName: string | null;
    orgUnitName: string | null;
    course: number | null;
    funding: 'budget' | 'paid' | 'targeted';
    recordBookNumber: string | null;
    studentCardNumber: string | null;
    livesInDorm: boolean;
  } | null;
  employee: { orgUnitName: string | null; position: string } | null;
}

export interface StudentCard {
  fullName: string;
  studentCardNumber: string | null;
  recordBookNumber: string | null;
  groupName: string | null;
  photoUrl: string | null;
  qrPayload: string;
}

export interface Lesson {
  id: string;
  disciplineName: string;
  startsAt: string;
  endsAt: string;
  room: string;
  publicationStatus: string;
  cancelled: boolean;
  groups: string[];
  teacherName: string | null;
  note: string;
}

export interface Attendance {
  userId: string;
  fullName: string;
  mark: 'present' | 'absent';
  origin: 'student' | 'system' | 'teacher' | 'admin';
  updatedAt: string;
}

export interface LessonDetail extends Lesson {
  attendance: Attendance[];
  participants: { userId: string; fullName: string; role: 'student' | 'teacher' }[];
  canMarkSelf: boolean;
}

export interface Grade {
  id: string;
  disciplineName: string;
  semesterId: string;
  semesterTitle: string;
  studentId: string | null;
  studentName: string | null;
  kind: 'current' | 'passfail' | 'graded_credit' | 'exam';
  title: string;
  score: string | null;
  label: string;
  isFinal: boolean;
  isDebt: boolean;
  credits: string;
}

export interface Diary {
  semesters: { semesterId: string; title: string; grades: Grade[] }[];
}

export interface TeachingAssignment {
  groupDisciplineId: string;
  disciplineId: string;
  semesterId: string;
  disciplineName: string;
  groupName: string;
  semesterTitle: string;
  kind: 'required' | 'elective';
}

export interface JournalStudent {
  studentId: string;
  studentName: string;
  grades: Grade[];
}

export interface Rating {
  score: string | null;
  computedAt: string | null;
}

export interface ElectiveOffer {
  groupDisciplineId: string;
  disciplineName: string;
  credits: string;
  blockTitle: string;
  application: {
    id: string;
    status: string;
    disciplineName: string;
    studentName: string;
    submittedAt: string | null;
  } | null;
}

export interface Conversation {
  id: string;
  kind: 'group' | 'direct';
  title: string;
  closed: boolean;
  unreadCount: number;
  lastMessage: Message | null;
}

export interface Message {
  id: string;
  authorUserId: string;
  authorName: string;
  body: string;
  createdAt: string;
  editedAt: string | null;
  deleted: boolean;
  attachmentIds: string[];
}

export interface MessagePage {
  items: Message[];
  nextCursor: string | null;
}

export interface NotificationItem {
  id: string;
  type: string;
  title: string;
  body: string;
  readAt: string | null;
  createdAt: string;
}

export interface CertificateType {
  id: string;
  code: string;
  title: string;
  enabled: boolean;
  deliveryModes: ('electronic' | 'paper' | 'appointment')[];
}

export interface CertificateRequest {
  id: string;
  typeTitle: string;
  deliveryMode: 'electronic' | 'paper' | 'appointment';
  status: 'pending' | 'in_progress' | 'ready' | 'rejected' | 'issued';
  comment: string;
  appointmentAt: string | null;
  createdAt: string;
  studentId: string | null;
  studentName: string | null;
}

export interface DormApplication {
  id: string;
  status: 'pending' | 'in_progress' | 'settled' | 'rejected';
  building: string;
  room: string;
  comment: string;
  createdAt: string;
  studentId: string | null;
  studentName: string | null;
}

export interface Contract {
  id: string;
  kind: 'tuition' | 'housing' | 'other';
  number: string;
  title: string;
  charged: string;
  paid: string;
  debt: string;
  studentId: string | null;
  entries?: {
    id: string;
    direction: 'charge' | 'payment';
    amount: string;
    occurredOn: string;
    description: string;
    reversed: boolean;
  }[];
  demoPayments?: { id: string; method: 'card' | 'sbp'; amount: string; message: string; educational: true }[];
}

export interface PortfolioDocument {
  id: string;
  kind: 'portfolio' | 'resume';
  title: string;
  body: string;
  fileId: string | null;
}

export interface ProfileCorrection {
  id: string;
  fieldName: string;
  requestedValue: string;
  comment: string;
  status: 'pending' | 'applied' | 'rejected';
  createdAt: string;
}

export interface ScholarshipView {
  grants: { id: string; title: string; amount: string; nextPayoutOn: string | null; active: boolean }[];
  payouts: { id: string; amount: string; paidOn: string }[];
}

export interface ApiFailure {
  error: { code: string; message: string };
}
