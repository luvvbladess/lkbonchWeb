import { HttpErrorResponse, HttpRequest } from '@angular/common/http';

const STUDENT = '11111111-1111-4111-8111-111111111111';
const TEACHER = '22222222-2222-4222-8222-222222222222';
const SEM = '33333333-3333-4333-8333-333333333333';
const DISC = '44444444-4444-4444-8444-444444444441';
const GD = '55555555-5555-4555-8555-555555555551';
const NOW = '66666666-6666-4666-8666-666666666661';
const LATER = '66666666-6666-4666-8666-666666666662';
const CANCELLED = '66666666-6666-4666-8666-666666666663';
const CHAT = '77777777-7777-4777-8777-777777777771';
const CLOSED = '77777777-7777-4777-8777-777777777772';
const CERT_TYPE = '88888888-8888-4888-8888-888888888881';
const CONTRACT = '99999999-9999-4999-8999-999999999991';

const sections = [
  'schedule',
  'diary',
  'chats',
  'electives',
  'certificates',
  'dormitory',
  'contracts',
  'portfolio',
  'scholarships',
];

function at(day: number, hour: number, minute = 0): string {
  const date = new Date();
  date.setDate(date.getDate() + day);
  date.setHours(hour, minute, 0, 0);
  return date.toISOString();
}

function shift(minutes: number): string {
  return new Date(Date.now() + minutes * 60_000).toISOString();
}

const university = {
  name: 'Санкт-Петербургский государственный университет телекоммуникаций им. проф. М. А. Бонч-Бруевича',
  shortName: 'СПбГУТ',
  brandSeed: '#F7941D',
  brandAccent: '#9A4A00',
  enabledSections: sections,
  logoUrl: null,
};

const studentMe = {
  id: STUDENT,
  role: 'student',
  status: 'active',
  lastName: 'Соколова',
  firstName: 'Мария',
  middleName: 'Игоревна',
  login: 'student',
  email: 'm.sokolova@example.edu',
  phone: '+7 921 000-11-22',
  permissions: [],
  enabledSections: sections,
  student: {
    groupId: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1',
    groupName: 'ИКПИ-41',
    orgUnitName: 'Факультет ИКСС',
    course: 4,
    funding: 'budget',
    recordBookNumber: '210441',
    studentCardNumber: '20210441',
    livesInDorm: false,
  },
  employee: null,
};

const teacherMe = {
  id: TEACHER,
  role: 'employee',
  status: 'active',
  lastName: 'Петров',
  firstName: 'Алексей',
  middleName: 'Сергеевич',
  login: 'teacher',
  email: 'a.petrov@example.edu',
  phone: '+7 921 000-33-44',
  permissions: [],
  enabledSections: sections,
  student: null,
  employee: { orgUnitName: 'Кафедра программной инженерии', position: 'Доцент' },
};

const lessons = [
  {
    id: NOW,
    disciplineName: 'Проектирование программных систем',
    startsAt: shift(-25),
    endsAt: shift(65),
    room: '414/1',
    publicationStatus: 'published',
    cancelled: false,
    groups: ['ИКПИ-41'],
    teacherName: 'Петров Алексей Сергеевич',
    note: '',
  },
  {
    id: LATER,
    disciplineName: 'Сети связи',
    startsAt: at(0, 16, 20),
    endsAt: at(0, 17, 50),
    room: '208/2',
    publicationStatus: 'published',
    cancelled: false,
    groups: ['ИКПИ-41'],
    teacherName: 'Орлова Нина Павловна',
    note: '',
  },
  {
    id: CANCELLED,
    disciplineName: 'Базы данных',
    startsAt: at(0, 18, 0),
    endsAt: at(0, 19, 30),
    room: '101/1',
    publicationStatus: 'published',
    cancelled: true,
    groups: ['ИКПИ-41'],
    teacherName: 'Петров Алексей Сергеевич',
    note: 'Преподаватель на конференции',
  },
  {
    id: '66666666-6666-4666-8666-666666666664',
    disciplineName: 'Проектирование программных систем',
    startsAt: at(1, 9, 0),
    endsAt: at(1, 10, 30),
    room: '414/1',
    publicationStatus: 'published',
    cancelled: false,
    groups: ['ИКПИ-41'],
    teacherName: 'Петров Алексей Сергеевич',
    note: '',
  },
];

const attendance: Record<string, { userId: string; fullName: string; mark: 'present' | 'absent'; origin: string; updatedAt: string }[]> = {
  [NOW]: [],
};

const messages: Record<string, {
  id: string;
  authorUserId: string;
  authorName: string;
  body: string;
  createdAt: string;
  editedAt: string | null;
  deleted: boolean;
  attachmentIds: string[];
}[]> = {
  [CHAT]: [
    {
      id: 'abababab-abab-4aba-8aba-abababababa1',
      authorUserId: TEACHER,
      authorName: 'Петров Алексей Сергеевич',
      body: 'К следующей паре прочитайте раздел про контракт API.',
      createdAt: shift(-180),
      editedAt: null,
      deleted: false,
      attachmentIds: [],
    },
  ],
  [CLOSED]: [
    {
      id: 'abababab-abab-4aba-8aba-abababababa2',
      authorUserId: STUDENT,
      authorName: 'Соколова Мария Игоревна',
      body: 'Спасибо за семестр.',
      createdAt: at(-40, 12),
      editedAt: null,
      deleted: false,
      attachmentIds: [],
    },
  ],
};

const read: Record<string, boolean> = { [CHAT]: false, [CLOSED]: true };

const state = {
  role: 'student' as 'student' | 'employee',
  certificates: [
    {
      id: 'cccccccc-cccc-4ccc-8ccc-ccccccccccc1',
      typeTitle: 'Справка об обучении',
      deliveryMode: 'electronic',
      status: 'pending',
      comment: 'Для банка',
      appointmentAt: null,
      createdAt: shift(-2 * 24 * 60),
      studentId: STUDENT,
      studentName: 'Соколова Мария Игоревна',
    },
  ] as Record<string, unknown>[],
  dorms: [] as Record<string, unknown>[],
  electives: [
    {
      groupDisciplineId: '55555555-5555-4555-8555-555555555552',
      disciplineName: 'Мобильная разработка',
      credits: '3.0',
      blockTitle: 'Профиль, 7 семестр',
      application: {
        id: 'edededed-eded-4ede-8ede-ededededede1',
        status: 'pending',
        disciplineName: 'Мобильная разработка',
        studentName: 'Соколова Мария Игоревна',
        submittedAt: shift(-60),
      },
    },
    {
      groupDisciplineId: '55555555-5555-4555-8555-555555555553',
      disciplineName: 'Инфокоммуникационные системы',
      credits: '3.0',
      blockTitle: 'Профиль, 7 семестр',
      application: null,
    },
  ],
  corrections: [] as Record<string, unknown>[],
  portfolio: [
    {
      id: 'ffffffff-ffff-4fff-8fff-fffffffffff1',
      kind: 'portfolio',
      title: 'Учебный проект кабинета',
      body: 'Командная работа, роль — клиентская часть.',
      fileId: null,
    },
  ],
  notifications: [
    {
      id: '12121212-1212-4121-8121-121212121212',
      type: 'grade_posted',
      title: 'Новая оценка',
      body: 'Сети связи: зачёт',
      readAt: null,
      createdAt: shift(-90),
    },
    {
      id: '12121212-1212-4121-8121-121212121213',
      type: 'schedule_changed',
      title: 'Занятие отменено',
      body: 'Базы данных сегодня не состоятся',
      readAt: shift(-30),
      createdAt: shift(-200),
    },
  ],
  demoPayments: [] as { id: string; method: string; amount: string; message: string; educational: true }[],
  journal: [
    { studentId: STUDENT, studentName: 'Соколова Мария Игоревна', grades: [] as Record<string, unknown>[] },
    { studentId: '11111111-1111-4111-8111-111111111112', studentName: 'Иванов Пётр Олегович', grades: [] as Record<string, unknown>[] },
  ],
};

function fail(status: number, code: string, message: string): HttpErrorResponse {
  return new HttpErrorResponse({ status, error: { error: { code, message } } });
}

function roleOf(req: HttpRequest<unknown>): 'student' | 'employee' | null {
  const header = req.headers.get('Authorization') ?? '';
  if (header.endsWith('teacher')) return 'employee';
  if (header.endsWith('student')) return 'student';
  return null;
}

function me(req: HttpRequest<unknown>) {
  return roleOf(req) === 'employee' ? teacherMe : studentMe;
}

function lessonDetail(id: string, role: 'student' | 'employee') {
  const lesson = lessons.find((item) => item.id === id);
  if (!lesson) return fail(404, 'not_found', 'Занятие не найдено');
  const marks = attendance[id] ?? [];
  const students = [
    { userId: STUDENT, fullName: 'Соколова Мария Игоревна', role: 'student' },
    { userId: '11111111-1111-4111-8111-111111111112', fullName: 'Иванов Пётр Олегович', role: 'student' },
  ];
  const teacher = { userId: TEACHER, fullName: 'Петров Алексей Сергеевич', role: 'teacher' };
  const open = !lesson.cancelled && Date.now() >= new Date(lesson.startsAt).getTime() && Date.now() <= new Date(lesson.endsAt).getTime();
  const already = marks.some((mark) => mark.userId === STUDENT);
  return {
    ...lesson,
    attendance: role === 'student' ? marks.filter((mark) => mark.userId === STUDENT) : marks,
    participants: role === 'student' ? [students[0], teacher] : students,
    canMarkSelf: role === 'student' && open && !already,
  };
}

export function mockAnswer(req: HttpRequest<unknown>): { status: number; body: unknown } | HttpErrorResponse {
  const url = new URL(req.url, 'http://cabinet.local');
  const path = url.pathname;
  const query = (name: string) => req.params.get(name) ?? url.searchParams.get(name);
  const method = req.method.toUpperCase();
  const role = roleOf(req);

  if (path === '/api/v1/university' && method === 'GET') return { status: 200, body: university };
  if (path === '/api/v1/auth/activation/request' && method === 'POST') {
    return { status: 202, body: { message: 'Если запись найдена, код отправлен на зарегистрированный контакт.' } };
  }
  if (path === '/api/v1/auth/activation/confirm' && method === 'POST') {
    const body = req.body as { code?: string; password?: string };
    if (body.code !== '000000') return fail(400, 'bad_code', 'Код не подошёл');
    if (!body.password || body.password.length < 8) return fail(422, 'weak_password', 'Пароль должен быть не короче 8 символов');
    state.role = 'student';
    return { status: 200, body: { accessToken: 'mock.student', refreshToken: 'refresh.student', expiresIn: 900 } };
  }
  if (path === '/api/v1/auth/login' && method === 'POST') {
    const body = req.body as { login?: string; password?: string };
    const known = body.login === 'student' || body.login === 'teacher';
    if (!known || !body.password || body.password.length < 8) {
      return fail(401, 'invalid_login', 'Неверный логин или пароль');
    }
    state.role = body.login === 'teacher' ? 'employee' : 'student';
    const who = state.role === 'employee' ? 'teacher' : 'student';
    return { status: 200, body: { accessToken: `mock.${who}`, refreshToken: `refresh.${who}`, expiresIn: 900 } };
  }
  if (path === '/api/v1/auth/refresh' && method === 'POST') {
    const body = req.body as { refreshToken?: string };
    const who = body.refreshToken?.endsWith('teacher') ? 'teacher' : 'student';
    state.role = who === 'teacher' ? 'employee' : 'student';
    return { status: 200, body: { accessToken: `mock.${who}`, refreshToken: `refresh.${who}`, expiresIn: 900 } };
  }
  if (path === '/api/v1/auth/logout' && method === 'POST') return { status: 204, body: null };
  if (!role) return fail(401, 'unauthorized', 'Нужно войти');

  if (path === '/api/v1/me' && method === 'GET') return { status: 200, body: me(req) };
  if (path === '/api/v1/me/contacts' && method === 'PATCH') {
    const body = req.body as { email?: string; phone?: string };
    const current = me(req);
    current.email = body.email ?? current.email;
    current.phone = body.phone ?? current.phone;
    return { status: 200, body: current };
  }
  if (path === '/api/v1/auth/password' && method === 'POST') {
    const body = req.body as { newPassword?: string };
    if (!body.newPassword || body.newPassword.length < 8) {
      return fail(422, 'weak_password', 'Пароль должен быть не короче 8 символов');
    }
    return { status: 204, body: null };
  }
  if (path === '/api/v1/me/student-card') {
    if (role !== 'student') return fail(404, 'not_found', 'Студенческий есть только у студента');
    return {
      status: 200,
      body: {
        fullName: 'Соколова Мария Игоревна',
        studentCardNumber: '20210441',
        recordBookNumber: '210441',
        groupName: 'ИКПИ-41',
        photoUrl: null,
        qrPayload: 'lkbonch:СПбГУТ:20210441',
      },
    };
  }
  if (path === '/api/v1/me/scholarship') {
    return {
      status: 200,
      body: {
        grants: [{ id: 'b1b1b1b1-b1b1-41b1-81b1-b1b1b1b1b1b1', title: 'Государственная академическая', amount: '4200.00', nextPayoutOn: at(12, 0).slice(0, 10), active: true }],
        payouts: [{ id: 'b2b2b2b2-b2b2-42b2-82b2-b2b2b2b2b2b2', amount: '4200.00', paidOn: at(-20, 0).slice(0, 10) }],
      },
    };
  }
  if (path === '/api/v1/me/rating') return { status: 200, body: { score: '4.350', computedAt: shift(-10) } };
  if (path === '/api/v1/me/corrections' && method === 'GET') return { status: 200, body: state.corrections };
  if (path === '/api/v1/me/corrections' && method === 'POST') {
    const body = req.body as { fieldName: string; requestedValue: string; comment: string };
    const created = { id: crypto.randomUUID(), ...body, status: 'pending', createdAt: new Date().toISOString() };
    state.corrections = [created, ...state.corrections];
    return { status: 201, body: created };
  }
  if (path === '/api/v1/schedule') {
    const from = new Date(query('from') ?? 0).getTime();
    const to = new Date(query('to') ?? '2100-01-01').getTime();
    const visible = lessons.filter((lesson) => new Date(lesson.startsAt).getTime() < to && new Date(lesson.endsAt).getTime() > from);
    const mine = role === 'employee' ? visible.filter((lesson) => lesson.teacherName?.startsWith('Петров')) : visible;
    return { status: 200, body: mine };
  }
  const lessonMatch = path.match(/^\/api\/v1\/lessons\/([^/]+)$/);
  if (lessonMatch && method === 'GET') {
    const detail = lessonDetail(lessonMatch[1], role);
    if (detail instanceof HttpErrorResponse) return detail;
    return { status: 200, body: detail };
  }
  const markMatch = path.match(/^\/api\/v1\/lessons\/([^/]+)\/attendance$/);
  if (markMatch && method === 'POST') {
    const detail = lessonDetail(markMatch[1], 'student');
    if (detail instanceof HttpErrorResponse) return detail;
    if (!detail.canMarkSelf) return fail(409, 'attendance_closed', 'Отметиться можно только во время занятия');
    attendance[markMatch[1]] = [
      ...(attendance[markMatch[1]] ?? []),
      { userId: STUDENT, fullName: 'Соколова Мария Игоревна', mark: 'present', origin: 'student', updatedAt: new Date().toISOString() },
    ];
    return { status: 200, body: attendance[markMatch[1]][0] };
  }
  const correctMatch = path.match(/^\/api\/v1\/lessons\/([^/]+)\/attendance\/([^/]+)$/);
  if (correctMatch && method === 'PATCH') {
    if (role !== 'employee') return fail(403, 'forbidden', 'Исправлять отметку может преподаватель занятия');
    const body = req.body as { mark: 'present' | 'absent' };
    const list = attendance[correctMatch[1]] ?? [];
    const existing = list.find((item) => item.userId === correctMatch[2]);
    const name = correctMatch[2] === STUDENT ? 'Соколова Мария Игоревна' : 'Иванов Пётр Олегович';
    const row = { userId: correctMatch[2], fullName: name, mark: body.mark, origin: 'teacher', updatedAt: new Date().toISOString() };
    attendance[correctMatch[1]] = existing ? list.map((item) => (item.userId === row.userId ? row : item)) : [...list, row];
    return { status: 200, body: row };
  }
  if (path === '/api/v1/diary') {
    if (role !== 'student') return fail(403, 'forbidden', 'Дневник студента доступен студенту');
    return {
      status: 200,
      body: {
        semesters: [
          {
            semesterId: SEM,
            title: 'Осень 2026',
            grades: [
              { id: 'd1d1d1d1-d1d1-41d1-81d1-d1d1d1d1d1d1', disciplineName: 'Сети связи', semesterId: SEM, semesterTitle: 'Осень 2026', studentId: STUDENT, studentName: null, kind: 'passfail', title: 'Зачёт', score: null, label: 'зачтено', isFinal: true, isDebt: false, credits: '4.0' },
              { id: 'd2d2d2d2-d2d2-42d2-82d2-d2d2d2d2d2d2', disciplineName: 'Базы данных', semesterId: SEM, semesterTitle: 'Осень 2026', studentId: STUDENT, studentName: null, kind: 'exam', title: 'Экзамен', score: '2', label: 'неуд', isFinal: true, isDebt: true, credits: '5.0' },
              { id: 'd3d3d3d3-d3d3-43d3-83d3-d3d3d3d3d3d3', disciplineName: 'Проектирование программных систем', semesterId: SEM, semesterTitle: 'Осень 2026', studentId: STUDENT, studentName: null, kind: 'current', title: 'Лабораторная 2', score: '5', label: 'отл', isFinal: false, isDebt: false, credits: '4.0' },
            ],
          },
        ],
      },
    };
  }
  if (path === '/api/v1/debts') {
    return {
      status: 200,
      body: [
        { id: 'd2d2d2d2-d2d2-42d2-82d2-d2d2d2d2d2d2', disciplineName: 'Базы данных', semesterId: SEM, semesterTitle: 'Осень 2026', kind: 'exam', title: 'Экзамен', score: '2', label: 'неуд', isFinal: true, isDebt: true, credits: '5.0' },
      ],
    };
  }
  if (path === '/api/v1/teaching' && method === 'GET') {
    if (role !== 'employee') return fail(403, 'forbidden', 'Журнал ведёт преподаватель дисциплины');
    return {
      status: 200,
      body: [
        { groupDisciplineId: GD, disciplineId: DISC, semesterId: SEM, disciplineName: 'Проектирование программных систем', groupName: 'ИКПИ-41', semesterTitle: 'Осень 2026', kind: 'required' },
      ],
    };
  }
  const journalMatch = path.match(/^\/api\/v1\/teaching\/([^/]+)\/grades$/);
  if (journalMatch) return { status: 200, body: state.journal };
  if (path === '/api/v1/grades' && method === 'POST') {
    const body = req.body as { studentId: string; kind: string; title: string; score: string | null; label: string; isFinal: boolean };
    const student = state.journal.find((item) => item.studentId === body.studentId);
    const grade = {
      id: crypto.randomUUID(),
      disciplineName: 'Проектирование программных систем',
      semesterId: SEM,
      semesterTitle: 'Осень 2026',
      studentId: body.studentId,
      studentName: student?.studentName ?? '',
      kind: body.kind,
      title: body.title,
      score: body.score,
      label: body.label,
      isFinal: body.isFinal,
      isDebt: body.isFinal && body.score != null && Number(body.score) < 3,
      credits: '4.0',
    };
    if (student) student.grades = [...student.grades, grade];
    return { status: 201, body: grade };
  }
  if (path === '/api/v1/electives') return { status: 200, body: state.electives };
  if (path === '/api/v1/elective-applications' && method === 'POST') {
    const body = req.body as { groupDisciplineId: string };
    const chosen = state.electives.find((item) => item.groupDisciplineId === body.groupDisciplineId);
    if (!chosen) return fail(404, 'not_found', 'Дисциплина не найдена');
    for (const offer of state.electives) {
      if (offer.blockTitle === chosen.blockTitle && offer.application && ['pending', 'approved'].includes(offer.application.status)) {
        offer.application = { ...offer.application, status: 'withdrawn' };
      }
    }
    chosen.application = {
      id: crypto.randomUUID(),
      status: 'pending',
      disciplineName: chosen.disciplineName,
      studentName: 'Соколова Мария Игоревна',
      submittedAt: new Date().toISOString(),
    };
    return { status: 201, body: chosen.application };
  }
  const withdraw = path.match(/^\/api\/v1\/elective-applications\/([^/]+)$/);
  if (withdraw && method === 'PATCH') {
    for (const offer of state.electives) {
      if (offer.application?.id === withdraw[1]) offer.application = { ...offer.application, status: 'withdrawn' };
    }
    return { status: 200, body: { id: withdraw[1], status: 'withdrawn' } };
  }
  if (path === '/api/v1/conversations') {
    const queryText = (query('q') ?? '').toLowerCase();
    const list = [
      {
        id: CHAT,
        kind: 'group',
        title: 'Проектирование программных систем · ИКПИ-41',
        closed: false,
        unreadCount: read[CHAT] ? 0 : 1,
        lastMessage: messages[CHAT].at(-1) ?? null,
      },
      {
        id: CLOSED,
        kind: 'group',
        title: 'Базы данных · ИКПИ-31',
        closed: true,
        unreadCount: 0,
        lastMessage: messages[CLOSED].at(-1) ?? null,
      },
    ].filter((item) => !queryText || item.title.toLowerCase().includes(queryText));
    return { status: 200, body: list };
  }
  const messageList = path.match(/^\/api\/v1\/conversations\/([^/]+)\/messages$/);
  if (messageList && method === 'GET') return { status: 200, body: { items: messages[messageList[1]] ?? [], nextCursor: null } };
  if (messageList && method === 'POST') {
    if (messageList[1] === CLOSED) return fail(409, 'conversation_closed', 'Семестр закрыт, сообщения больше не принимаются');
    const body = req.body as { clientMessageId: string; body: string };
    const existing = (messages[messageList[1]] ?? []).find((item) => item.id === body.clientMessageId);
    if (existing) return { status: 201, body: existing };
    const created = {
      id: body.clientMessageId,
      authorUserId: role === 'employee' ? TEACHER : STUDENT,
      authorName: role === 'employee' ? 'Петров Алексей Сергеевич' : 'Соколова Мария Игоревна',
      body: body.body,
      createdAt: new Date().toISOString(),
      editedAt: null,
      deleted: false,
      attachmentIds: [],
    };
    messages[messageList[1]] = [...(messages[messageList[1]] ?? []), created];
    return { status: 201, body: created };
  }
  const readMatch = path.match(/^\/api\/v1\/conversations\/([^/]+)\/read$/);
  if (readMatch) {
    read[readMatch[1]] = true;
    return { status: 204, body: null };
  }
  const edit = path.match(/^\/api\/v1\/messages\/([^/]+)$/);
  if (edit && method === 'PATCH') {
    const body = req.body as { body: string };
    for (const list of Object.values(messages)) {
      const message = list.find((item) => item.id === edit[1]);
      if (message) {
        message.body = body.body;
        message.editedAt = new Date().toISOString();
        return { status: 200, body: message };
      }
    }
    return fail(404, 'not_found', 'Сообщение не найдено');
  }
  if (edit && method === 'DELETE') {
    for (const list of Object.values(messages)) {
      const message = list.find((item) => item.id === edit[1]);
      if (message) {
        message.deleted = true;
        message.body = '';
        return { status: 204, body: null };
      }
    }
    return fail(404, 'not_found', 'Сообщение не найдено');
  }
  if (path === '/api/v1/notifications' && method === 'GET') return { status: 200, body: { items: state.notifications, nextCursor: null } };
  if (path === '/api/v1/notifications/read-all') {
    state.notifications = state.notifications.map((item) => ({ ...item, readAt: item.readAt ?? new Date().toISOString() }));
    return { status: 204, body: null };
  }
  const note = path.match(/^\/api\/v1\/notifications\/([^/]+)\/read$/);
  if (note) {
    state.notifications = state.notifications.map((item) => (item.id === note[1] ? { ...item, readAt: new Date().toISOString() } : item));
    return { status: 204, body: null };
  }
  if (path === '/api/v1/certificate-types') {
    return { status: 200, body: [{ id: CERT_TYPE, code: 'study', title: 'Справка об обучении', enabled: true, deliveryModes: ['electronic', 'paper', 'appointment'] }] };
  }
  if (path === '/api/v1/certificate-requests' && method === 'GET') return { status: 200, body: state.certificates };
  if (path === '/api/v1/certificate-requests' && method === 'POST') {
    const body = req.body as { typeId: string; deliveryMode: string; comment: string };
    const created = {
      id: crypto.randomUUID(),
      typeTitle: 'Справка об обучении',
      deliveryMode: body.deliveryMode,
      status: 'pending',
      comment: body.comment,
      appointmentAt: null,
      createdAt: new Date().toISOString(),
      studentId: STUDENT,
      studentName: 'Соколова Мария Игоревна',
    };
    state.certificates = [created, ...state.certificates];
    return { status: 201, body: created };
  }
  if (path === '/api/v1/dorm-applications' && method === 'GET') return { status: 200, body: state.dorms };
  if (path === '/api/v1/dorm-applications' && method === 'POST') {
    if (state.dorms.some((item) => item['status'] === 'pending')) {
      return fail(409, 'already_open', 'Заявка на общежитие уже рассматривается');
    }
    const body = req.body as { comment?: string };
    const created = { id: crypto.randomUUID(), status: 'pending', building: '', room: '', comment: body.comment ?? '', createdAt: new Date().toISOString(), studentId: STUDENT, studentName: 'Соколова Мария Игоревна' };
    state.dorms = [created];
    return { status: 201, body: created };
  }
  if (path === '/api/v1/contracts' && method === 'GET') {
    return { status: 200, body: [{ id: CONTRACT, kind: 'tuition', number: 'Д-2024-118', title: 'Обучение, 2026/27', charged: '180000.00', paid: '90000.00', debt: '90000.00', studentId: STUDENT }] };
  }
  if (path === `/api/v1/contracts/${CONTRACT}` && method === 'GET') {
    return {
      status: 200,
      body: {
        id: CONTRACT,
        kind: 'tuition',
        number: 'Д-2024-118',
        title: 'Обучение, 2026/27',
        charged: '180000.00',
        paid: '90000.00',
        debt: '90000.00',
        studentId: STUDENT,
        entries: [
          { id: 'e1', direction: 'charge', amount: '180000.00', occurredOn: '2026-09-01', description: 'Начисление за семестр', reversed: false },
          { id: 'e2', direction: 'payment', amount: '90000.00', occurredOn: '2026-09-10', description: 'Оплата', reversed: false },
        ],
        demoPayments: state.demoPayments,
      },
    };
  }
  if (path === `/api/v1/contracts/${CONTRACT}/demo-payments` && method === 'POST') {
    const body = req.body as { amount: string; method: 'card' | 'sbp' };
    const payment = { id: crypto.randomUUID(), method: body.method, amount: body.amount, message: 'Демо-оплата выполнена, средства не списаны', educational: true as const };
    state.demoPayments = [...state.demoPayments, payment];
    return { status: 201, body: payment };
  }
  if (path === '/api/v1/portfolio' && method === 'GET') return { status: 200, body: state.portfolio };
  if (path === '/api/v1/portfolio' && method === 'POST') {
    const body = req.body as { title: string; body: string; kind: string };
    const created = { id: crypto.randomUUID(), kind: body.kind, title: body.title, body: body.body, fileId: null };
    state.portfolio = [created, ...state.portfolio];
    return { status: 201, body: created };
  }
  const portfolio = path.match(/^\/api\/v1\/portfolio\/([^/]+)$/);
  if (portfolio && method === 'DELETE') {
    state.portfolio = state.portfolio.filter((item) => item.id !== portfolio[1]);
    return { status: 204, body: null };
  }
  return fail(404, 'not_found', 'Запрос не найден');
}
