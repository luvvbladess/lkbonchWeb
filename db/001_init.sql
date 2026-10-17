-- Личный кабинет университета 2.0 beta
-- Один экземпляр базы = один вуз. Общего tenant_id нет.
-- Повторный прогон этого файла не предполагается: его применяет app.migrate один раз.
--
-- Инварианты:
-- - роль одна: student, employee или admin; студенту права не выдаются;
-- - оценки и групповой чат принадлежат преподавателю из учебного плана;
-- - отметку на конкретной паре правит преподаватель этой пары;
-- - явку преподавателя меняет только администратор с отдельным правом;
-- - в блоке выборных у студента одна активная заявка;
-- - демо-оплата не создаёт проводку и не меняет долг;
-- - ошибочная проводка гасится записью с тем же знаком и суммой, баланс её не считает;
-- - факультет студента берётся из группы, отдельным полем не хранится;
-- - семестры не пересекаются по датам, активный семестр один.

CREATE EXTENSION IF NOT EXISTS citext;

-- ---------------------------------------------------------------------------
-- Types
-- ---------------------------------------------------------------------------

CREATE TYPE user_role AS ENUM ('student', 'employee', 'admin');
CREATE TYPE account_status AS ENUM ('pending', 'active', 'blocked');
CREATE TYPE funding_type AS ENUM ('budget', 'paid', 'targeted');
CREATE TYPE org_unit_kind AS ENUM ('institute', 'faculty', 'department', 'other');
CREATE TYPE semester_status AS ENUM ('planned', 'active', 'closed');
CREATE TYPE discipline_kind AS ENUM ('required', 'elective');
CREATE TYPE application_status AS ENUM ('pending', 'approved', 'rejected', 'withdrawn');
CREATE TYPE publication_status AS ENUM ('draft', 'published');
CREATE TYPE attendance_mark AS ENUM ('present', 'absent');
CREATE TYPE attendance_origin AS ENUM ('student', 'system', 'teacher', 'admin');
CREATE TYPE grade_kind AS ENUM ('current', 'passfail', 'graded_credit', 'exam');
CREATE TYPE conversation_kind AS ENUM ('group', 'direct');
CREATE TYPE certificate_delivery AS ENUM ('electronic', 'paper', 'appointment');
CREATE TYPE request_status AS ENUM ('pending', 'in_progress', 'ready', 'rejected', 'issued');
CREATE TYPE dorm_status AS ENUM ('pending', 'in_progress', 'settled', 'rejected');
CREATE TYPE contract_kind AS ENUM ('tuition', 'housing', 'other');
CREATE TYPE ledger_direction AS ENUM ('charge', 'payment');
CREATE TYPE payment_method AS ENUM ('card', 'sbp');
CREATE TYPE portfolio_kind AS ENUM ('portfolio', 'resume');
CREATE TYPE correction_field AS ENUM (
    'group',
    'course',
    'record_book_number',
    'student_card_number',
    'funding',
    'lives_in_dorm'
);
CREATE TYPE notification_type AS ENUM (
    'schedule_changed',
    'grade_posted',
    'message',
    'certificate_updated',
    'dorm_updated',
    'elective_updated',
    'correction_updated',
    'demo_payment_recorded'
);
CREATE TYPE correction_status AS ENUM ('pending', 'applied', 'rejected');
CREATE TYPE import_domain AS ENUM (
    'students',
    'employees',
    'groups',
    'disciplines',
    'elective_blocks',
    'curriculum',
    'lessons',
    'scholarships',
    'contracts',
    'ledger'
);
CREATE TYPE import_mode AS ENUM ('insert_only', 'upsert');
CREATE TYPE import_status AS ENUM ('preview', 'applied', 'failed');
CREATE TYPE device_platform AS ENUM ('web', 'android', 'ios');

CREATE FUNCTION touch_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;

CREATE FUNCTION person_name_key(last_name text, first_name text, middle_name text) RETURNS text
LANGUAGE sql
STABLE AS $$
    SELECT translate(
        lower(concat_ws(' ', last_name, first_name, NULLIF(middle_name, ''))),
        'ёЁ',
        'ее'
    );
$$;

CREATE FUNCTION users_before_write() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    NEW.name_key := person_name_key(NEW.last_name, NEW.first_name, NEW.middle_name);
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;

CREATE FUNCTION forbid_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'table % is append-only', TG_TABLE_NAME;
END;
$$;

-- ---------------------------------------------------------------------------
-- University. Ровно одна строка.
-- ---------------------------------------------------------------------------

CREATE TABLE university (
    id smallint PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    name text NOT NULL,
    short_name text NOT NULL DEFAULT '',
    logo_file_id uuid,
    brand_seed text NOT NULL DEFAULT '#F7941D',
    brand_accent text NOT NULL DEFAULT '#9A4A00',
    timezone text NOT NULL DEFAULT 'Europe/Moscow',
    student_match_field text NOT NULL DEFAULT 'student_card_number'
        CHECK (student_match_field IN ('student_card_number', 'record_book_number')),
    teacher_attendance_rule text NOT NULL DEFAULT 'present_at_start'
        CHECK (teacher_attendance_rule IN ('present_at_start')),
    pass_score numeric(6, 2) NOT NULL DEFAULT 3,
    failing_labels text[] NOT NULL DEFAULT ARRAY['2', 'незачет', 'неявка', 'н/я'],
    enabled_sections text[] NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT university_sections_known CHECK (
        enabled_sections <@ ARRAY[
            'schedule', 'diary', 'chats', 'electives',
            'certificates', 'dormitory', 'contracts',
            'portfolio', 'scholarships'
        ]::text[]
    )
);

CREATE TRIGGER university_touch
    BEFORE UPDATE ON university
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

INSERT INTO university (name, short_name, enabled_sections)
VALUES (
    'Университет',
    '',
    ARRAY[
        'schedule', 'diary', 'chats', 'electives',
        'certificates', 'dormitory', 'contracts',
        'portfolio', 'scholarships'
    ]
);

-- ---------------------------------------------------------------------------
-- Structure and calendar
-- ---------------------------------------------------------------------------

CREATE TABLE org_units (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_id uuid REFERENCES org_units (id) ON DELETE RESTRICT,
    kind org_unit_kind NOT NULL,
    name text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TRIGGER org_units_touch
    BEFORE UPDATE ON org_units
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

CREATE TABLE semesters (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    title text NOT NULL,
    starts_on date NOT NULL,
    ends_on date NOT NULL,
    status semester_status NOT NULL DEFAULT 'planned',
    elective_open_on date,
    elective_close_on date,
    elective_change_until date,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (ends_on >= starts_on),
    CHECK (elective_close_on IS NULL OR elective_open_on IS NULL OR elective_close_on >= elective_open_on),
    EXCLUDE USING gist (daterange(starts_on, ends_on, '[]') WITH &&)
);

CREATE TRIGGER semesters_touch
    BEFORE UPDATE ON semesters
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

CREATE UNIQUE INDEX semesters_one_active
    ON semesters (status)
    WHERE status = 'active';

CREATE TABLE groups (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_unit_id uuid NOT NULL REFERENCES org_units (id) ON DELETE RESTRICT,
    name text NOT NULL,
    course smallint NOT NULL CHECK (course BETWEEN 1 AND 6),
    entry_year smallint NOT NULL CHECK (entry_year BETWEEN 1990 AND 2100),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (org_unit_id, name, entry_year)
);

CREATE TRIGGER groups_touch
    BEFORE UPDATE ON groups
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- ---------------------------------------------------------------------------
-- Accounts
-- ---------------------------------------------------------------------------

CREATE TABLE users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    role user_role NOT NULL,
    status account_status NOT NULL DEFAULT 'pending',
    last_name text NOT NULL,
    first_name text NOT NULL,
    middle_name text NOT NULL DEFAULT '',
    name_key text NOT NULL DEFAULT '',
    login citext,
    email citext,
    phone text,
    password_hash text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (status <> 'active' OR password_hash IS NOT NULL),
    CHECK (login IS NULL OR length(login) > 0),
    CHECK (phone IS NULL OR phone <> '')
);

CREATE TRIGGER users_before_write_trg
    BEFORE INSERT OR UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION users_before_write();

CREATE UNIQUE INDEX users_login_unique ON users (login) WHERE login IS NOT NULL;
CREATE UNIQUE INDEX users_email_unique ON users (email) WHERE email IS NOT NULL;
CREATE UNIQUE INDEX users_phone_unique ON users (phone) WHERE phone IS NOT NULL;
CREATE INDEX users_name_key_idx ON users (name_key);

CREATE TABLE permissions (
    code text PRIMARY KEY,
    description text NOT NULL
);

INSERT INTO permissions (code, description) VALUES
    ('attendance.correct_teacher', 'Менять автоматическую явку преподавателя'),
    ('electives.review', 'Обрабатывать заявки на выборные дисциплины'),
    ('certificates.review', 'Обрабатывать заказы справок'),
    ('dorm.review', 'Обрабатывать заявления на общежитие'),
    ('contracts.manage', 'Вести договоры, начисления и платежи'),
    ('scholarships.manage', 'Вести стипендии'),
    ('users.manage', 'Создавать пользователей, роли и права'),
    ('import.run', 'Импортировать файлы'),
    ('settings.manage', 'Настраивать вуз, календарь и справочники'),
    ('schedule.manage', 'Вести и публиковать расписание'),
    ('audit.read', 'Читать журнал действий'),
    ('data.correct', 'Применять запросы на исправление сведений студента');

CREATE TABLE user_permissions (
    user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    permission_code text NOT NULL REFERENCES permissions (code),
    PRIMARY KEY (user_id, permission_code)
);

CREATE TABLE refresh_tokens (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    token_hash text NOT NULL UNIQUE,
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz,
    replaced_by uuid REFERENCES refresh_tokens (id),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX refresh_tokens_user_idx ON refresh_tokens (user_id);

CREATE TABLE activation_codes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    code_hash text NOT NULL,
    destination text NOT NULL,
    attempts smallint NOT NULL DEFAULT 0,
    expires_at timestamptz NOT NULL,
    used_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX activation_codes_user_idx ON activation_codes (user_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- Files. Локальный том /data/files, не внешнее хранилище.
-- ---------------------------------------------------------------------------

CREATE TABLE files (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    object_key text NOT NULL UNIQUE,
    original_name text NOT NULL,
    content_type text NOT NULL,
    size_bytes bigint NOT NULL CHECK (size_bytes >= 0),
    uploaded_by uuid NOT NULL REFERENCES users (id),
    created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE university
    ADD CONSTRAINT university_logo_file_fk
    FOREIGN KEY (logo_file_id) REFERENCES files (id);

CREATE TABLE employee_profiles (
    user_id uuid PRIMARY KEY REFERENCES users (id) ON DELETE CASCADE,
    org_unit_id uuid REFERENCES org_units (id),
    position text NOT NULL DEFAULT '',
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TRIGGER employee_profiles_touch
    BEFORE UPDATE ON employee_profiles
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

CREATE TABLE student_profiles (
    user_id uuid PRIMARY KEY REFERENCES users (id) ON DELETE CASCADE,
    group_id uuid REFERENCES groups (id),
    -- Личный курс. Может отличаться от курса группы, если студент остался на курсе.
    course smallint CHECK (course IS NULL OR course BETWEEN 1 AND 6),
    funding funding_type NOT NULL DEFAULT 'budget',
    record_book_number text,
    student_card_number text,
    photo_file_id uuid REFERENCES files (id),
    lives_in_dorm boolean NOT NULL DEFAULT false,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TRIGGER student_profiles_touch
    BEFORE UPDATE ON student_profiles
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

CREATE UNIQUE INDEX student_card_unique
    ON student_profiles (student_card_number)
    WHERE student_card_number IS NOT NULL;

CREATE UNIQUE INDEX record_book_unique
    ON student_profiles (record_book_number)
    WHERE record_book_number IS NOT NULL;

-- ---------------------------------------------------------------------------
-- Study plan
-- ---------------------------------------------------------------------------

CREATE TABLE disciplines (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code text NOT NULL UNIQUE,
    name text NOT NULL,
    org_unit_id uuid REFERENCES org_units (id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TRIGGER disciplines_touch
    BEFORE UPDATE ON disciplines
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

CREATE TABLE elective_blocks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id uuid NOT NULL REFERENCES groups (id) ON DELETE CASCADE,
    semester_id uuid NOT NULL REFERENCES semesters (id) ON DELETE RESTRICT,
    title text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (group_id, semester_id, title)
);

CREATE TABLE group_disciplines (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id uuid NOT NULL REFERENCES groups (id) ON DELETE CASCADE,
    discipline_id uuid NOT NULL REFERENCES disciplines (id) ON DELETE RESTRICT,
    semester_id uuid NOT NULL REFERENCES semesters (id) ON DELETE RESTRICT,
    kind discipline_kind NOT NULL,
    elective_block_id uuid REFERENCES elective_blocks (id) ON DELETE RESTRICT,
    credits numeric(4, 1) NOT NULL DEFAULT 0 CHECK (credits >= 0),
    -- Преподаватель дисциплины: оценки и владелец группового чата.
    teacher_user_id uuid REFERENCES users (id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (group_id, discipline_id, semester_id),
    CONSTRAINT group_disciplines_elective_shape CHECK (
        (kind = 'required' AND elective_block_id IS NULL)
        OR (kind = 'elective' AND elective_block_id IS NOT NULL)
    )
);

CREATE TRIGGER group_disciplines_touch
    BEFORE UPDATE ON group_disciplines
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

CREATE INDEX group_disciplines_teacher_idx ON group_disciplines (teacher_user_id);

CREATE TABLE elective_applications (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    student_user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    group_discipline_id uuid NOT NULL REFERENCES group_disciplines (id) ON DELETE CASCADE,
    elective_block_id uuid NOT NULL REFERENCES elective_blocks (id),
    status application_status NOT NULL DEFAULT 'pending',
    submitted_at timestamptz NOT NULL DEFAULT now(),
    decided_at timestamptz,
    decided_by uuid REFERENCES users (id)
);

-- Одна живая заявка на блок. Отозванные строки остаются историей.
CREATE UNIQUE INDEX elective_applications_one_choice
    ON elective_applications (student_user_id, elective_block_id)
    WHERE status IN ('pending', 'approved');

-- ---------------------------------------------------------------------------
-- Dated lessons. Недельный шаблон не хранится: импорт сразу создаёт даты.
-- Отметка и перенос пары относятся к конкретной встрече.
-- ---------------------------------------------------------------------------

CREATE TABLE lessons (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    semester_id uuid NOT NULL REFERENCES semesters (id) ON DELETE RESTRICT,
    discipline_id uuid NOT NULL REFERENCES disciplines (id) ON DELETE RESTRICT,
    -- Кто ведёт эту встречу. Может отличаться от преподавателя дисциплины: замена правит отметки, но не зачётку.
    teacher_user_id uuid REFERENCES users (id),
    starts_at timestamptz NOT NULL,
    ends_at timestamptz NOT NULL,
    room text NOT NULL DEFAULT '',
    note text NOT NULL DEFAULT '',
    publication_status publication_status NOT NULL DEFAULT 'draft',
    published_at timestamptz,
    cancelled_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (ends_at > starts_at)
);

CREATE TRIGGER lessons_touch
    BEFORE UPDATE ON lessons
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

CREATE INDEX lessons_teacher_starts_idx ON lessons (teacher_user_id, starts_at);
CREATE INDEX lessons_published_starts_idx
    ON lessons (starts_at)
    WHERE publication_status = 'published';

CREATE TABLE lesson_groups (
    lesson_id uuid NOT NULL REFERENCES lessons (id) ON DELETE CASCADE,
    group_id uuid NOT NULL REFERENCES groups (id) ON DELETE RESTRICT,
    PRIMARY KEY (lesson_id, group_id)
);

CREATE INDEX lesson_groups_group_idx ON lesson_groups (group_id, lesson_id);

-- Нет строки — студент ещё не отмечен. Это не то же самое, что явный absent.
-- После начала пары сервер сам ставит преподавателю present с origin system.
CREATE TABLE attendance_marks (
    lesson_id uuid NOT NULL REFERENCES lessons (id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    mark attendance_mark NOT NULL,
    origin attendance_origin NOT NULL,
    updated_by uuid REFERENCES users (id),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (lesson_id, user_id)
);

-- ---------------------------------------------------------------------------
-- Grades, debts, rating
-- Формула — JSON, не текст для eval и не SQL.
-- Допустимый вид: {"type":"weighted_average","of":"final_numeric_grades","weight":"credits"}
-- type: weighted_average | mean | sum. of: final_numeric_grades.
-- ---------------------------------------------------------------------------

CREATE TABLE grades (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    student_user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    discipline_id uuid NOT NULL REFERENCES disciplines (id) ON DELETE RESTRICT,
    semester_id uuid NOT NULL REFERENCES semesters (id) ON DELETE RESTRICT,
    kind grade_kind NOT NULL,
    title text NOT NULL DEFAULT '',
    score numeric(6, 2),
    label text NOT NULL DEFAULT '',
    is_final boolean NOT NULL DEFAULT false,
    is_debt boolean NOT NULL DEFAULT false,
    -- Снимок кредитов на момент оценки. Рейтинг не ходит в план задним числом.
    credits numeric(4, 1) NOT NULL DEFAULT 0 CHECK (credits >= 0),
    recorded_by uuid REFERENCES users (id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TRIGGER grades_touch
    BEFORE UPDATE ON grades
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

CREATE INDEX grades_student_semester_idx ON grades (student_user_id, semester_id);

CREATE TABLE rating_formulas (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    definition jsonb NOT NULL,
    is_active boolean NOT NULL DEFAULT false,
    updated_by uuid REFERENCES users (id),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX rating_formulas_one_active
    ON rating_formulas (is_active)
    WHERE is_active;

CREATE TRIGGER rating_formulas_touch
    BEFORE UPDATE ON rating_formulas
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

CREATE TABLE rating_snapshots (
    student_user_id uuid PRIMARY KEY REFERENCES users (id) ON DELETE CASCADE,
    formula_id uuid REFERENCES rating_formulas (id),
    score numeric(8, 3) NOT NULL,
    computed_at timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Chats. Групповой чат один на дисциплину группы в семестре.
-- После closed_at история читается, новые сообщения запрещает сервер.
-- ---------------------------------------------------------------------------

CREATE TABLE conversations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    kind conversation_kind NOT NULL,
    semester_id uuid NOT NULL REFERENCES semesters (id) ON DELETE RESTRICT,
    discipline_id uuid NOT NULL REFERENCES disciplines (id) ON DELETE RESTRICT,
    group_id uuid REFERENCES groups (id) ON DELETE RESTRICT,
    student_user_id uuid REFERENCES users (id) ON DELETE CASCADE,
    teacher_user_id uuid REFERENCES users (id),
    closed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT conversations_shape CHECK (
        (
            kind = 'group'
            AND group_id IS NOT NULL
            AND student_user_id IS NULL
            AND teacher_user_id IS NULL
        )
        OR (
            kind = 'direct'
            AND group_id IS NULL
            AND student_user_id IS NOT NULL
            AND teacher_user_id IS NOT NULL
        )
    )
);

CREATE UNIQUE INDEX conversations_group_unique
    ON conversations (semester_id, discipline_id, group_id)
    WHERE kind = 'group';

CREATE UNIQUE INDEX conversations_direct_unique
    ON conversations (semester_id, discipline_id, student_user_id, teacher_user_id)
    WHERE kind = 'direct';

CREATE TABLE conversation_members (
    conversation_id uuid NOT NULL REFERENCES conversations (id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    last_read_message_id uuid,
    last_read_at timestamptz,
    PRIMARY KEY (conversation_id, user_id)
);

CREATE INDEX conversation_members_user_idx ON conversation_members (user_id);

CREATE TABLE messages (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id uuid NOT NULL REFERENCES conversations (id) ON DELETE CASCADE,
    author_user_id uuid NOT NULL REFERENCES users (id),
    client_message_id uuid,
    body text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now(),
    edited_at timestamptz,
    deleted_at timestamptz,
    UNIQUE (conversation_id, client_message_id)
);

CREATE INDEX messages_conversation_created_idx ON messages (conversation_id, created_at);
CREATE INDEX messages_search_idx ON messages USING gin (to_tsvector('russian', body));

ALTER TABLE conversation_members
    ADD CONSTRAINT conversation_members_last_read_fk
    FOREIGN KEY (last_read_message_id) REFERENCES messages (id) ON DELETE SET NULL;

CREATE TABLE message_attachments (
    message_id uuid NOT NULL REFERENCES messages (id) ON DELETE CASCADE,
    file_id uuid NOT NULL REFERENCES files (id) ON DELETE RESTRICT,
    PRIMARY KEY (message_id, file_id)
);

-- ---------------------------------------------------------------------------
-- Notifications. Push-токены нужны мобильным клиентам, веб может их не слать.
-- ---------------------------------------------------------------------------

CREATE TABLE notifications (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    type notification_type NOT NULL,
    title text NOT NULL,
    body text NOT NULL DEFAULT '',
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    read_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX notifications_user_created_idx ON notifications (user_id, created_at DESC);
CREATE INDEX notifications_unread_idx ON notifications (user_id, created_at DESC) WHERE read_at IS NULL;

CREATE TABLE device_tokens (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    platform device_platform NOT NULL,
    token text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, token)
);

-- ---------------------------------------------------------------------------
-- Services
-- ---------------------------------------------------------------------------

CREATE TABLE certificate_types (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code text NOT NULL UNIQUE,
    title text NOT NULL,
    enabled boolean NOT NULL DEFAULT true,
    sort_order integer NOT NULL DEFAULT 0,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TRIGGER certificate_types_touch
    BEFORE UPDATE ON certificate_types
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

CREATE TABLE certificate_type_modes (
    type_id uuid NOT NULL REFERENCES certificate_types (id) ON DELETE CASCADE,
    mode certificate_delivery NOT NULL,
    PRIMARY KEY (type_id, mode)
);

CREATE TABLE certificate_requests (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    student_user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    type_id uuid NOT NULL REFERENCES certificate_types (id) ON DELETE RESTRICT,
    delivery_mode certificate_delivery NOT NULL,
    status request_status NOT NULL DEFAULT 'pending',
    comment text NOT NULL DEFAULT '',
    appointment_at timestamptz,
    result_file_id uuid REFERENCES files (id),
    assignee_user_id uuid REFERENCES users (id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TRIGGER certificate_requests_touch
    BEFORE UPDATE ON certificate_requests
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

CREATE INDEX certificate_requests_student_idx ON certificate_requests (student_user_id, created_at DESC);
CREATE INDEX certificate_requests_status_idx ON certificate_requests (status, created_at DESC);

CREATE TABLE contracts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    student_user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    kind contract_kind NOT NULL,
    number text NOT NULL,
    title text NOT NULL DEFAULT '',
    opened_on date,
    closed_on date,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (student_user_id, number)
);

CREATE TRIGGER contracts_touch
    BEFORE UPDATE ON contracts
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

CREATE TABLE demo_payments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_id uuid NOT NULL REFERENCES contracts (id) ON DELETE CASCADE,
    student_user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    amount numeric(12, 2) NOT NULL CHECK (amount > 0),
    method payment_method NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

-- Ошибочную проводку не редактируют: добавляют обратную запись.
CREATE TABLE ledger_entries (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_id uuid NOT NULL REFERENCES contracts (id) ON DELETE CASCADE,
    direction ledger_direction NOT NULL,
    amount numeric(12, 2) NOT NULL CHECK (amount > 0),
    occurred_on date NOT NULL,
    description text NOT NULL DEFAULT '',
    reverses_entry_id uuid UNIQUE,
    created_by uuid REFERENCES users (id),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ledger_entries_contract_idx ON ledger_entries (contract_id, occurred_on);

ALTER TABLE ledger_entries
    ADD CONSTRAINT ledger_entries_reverses_fk
    FOREIGN KEY (reverses_entry_id) REFERENCES ledger_entries (id);

CREATE TRIGGER ledger_entries_no_update
    BEFORE UPDATE OR DELETE ON ledger_entries
    FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

CREATE TABLE dorm_applications (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    student_user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    status dorm_status NOT NULL DEFAULT 'pending',
    building text NOT NULL DEFAULT '',
    room text NOT NULL DEFAULT '',
    comment text NOT NULL DEFAULT '',
    contract_id uuid REFERENCES contracts (id),
    assignee_user_id uuid REFERENCES users (id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TRIGGER dorm_applications_touch
    BEFORE UPDATE ON dorm_applications
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

CREATE INDEX dorm_applications_student_idx ON dorm_applications (student_user_id, created_at DESC);

CREATE TABLE scholarship_grants (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    student_user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    title text NOT NULL,
    amount numeric(12, 2) NOT NULL CHECK (amount >= 0),
    next_payout_on date,
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TRIGGER scholarship_grants_touch
    BEFORE UPDATE ON scholarship_grants
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

CREATE TABLE scholarship_payouts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    grant_id uuid NOT NULL REFERENCES scholarship_grants (id) ON DELETE CASCADE,
    amount numeric(12, 2) NOT NULL CHECK (amount >= 0),
    paid_on date NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Portfolio
-- ---------------------------------------------------------------------------

CREATE TABLE portfolio_documents (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    student_user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    kind portfolio_kind NOT NULL,
    title text NOT NULL,
    body text NOT NULL DEFAULT '',
    file_id uuid REFERENCES files (id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TRIGGER portfolio_documents_touch
    BEFORE UPDATE ON portfolio_documents
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

CREATE TABLE portfolio_grants (
    document_id uuid NOT NULL REFERENCES portfolio_documents (id) ON DELETE CASCADE,
    grantee_user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    PRIMARY KEY (document_id, grantee_user_id)
);

-- ---------------------------------------------------------------------------
-- Corrections of university-owned student fields
-- ---------------------------------------------------------------------------

CREATE TABLE profile_corrections (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    student_user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    field_name correction_field NOT NULL,
    requested_value text NOT NULL,
    comment text NOT NULL DEFAULT '',
    status correction_status NOT NULL DEFAULT 'pending',
    reviewer_user_id uuid REFERENCES users (id),
    created_at timestamptz NOT NULL DEFAULT now(),
    decided_at timestamptz
);

CREATE INDEX profile_corrections_status_idx ON profile_corrections (status, created_at DESC);

-- ---------------------------------------------------------------------------
-- Import. По умолчанию клиент делает preview. insert_only не затирает строки.
-- ---------------------------------------------------------------------------

CREATE TABLE import_batches (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    domain import_domain NOT NULL,
    mode import_mode NOT NULL DEFAULT 'insert_only',
    status import_status NOT NULL DEFAULT 'preview',
    original_name text NOT NULL,
    stored_file_id uuid REFERENCES files (id),
    accepted_count integer NOT NULL DEFAULT 0,
    rejected_count integer NOT NULL DEFAULT 0,
    created_by uuid NOT NULL REFERENCES users (id),
    created_at timestamptz NOT NULL DEFAULT now(),
    applied_at timestamptz
);

CREATE TABLE import_issues (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id uuid NOT NULL REFERENCES import_batches (id) ON DELETE CASCADE,
    row_number integer NOT NULL,
    field_name text NOT NULL DEFAULT '',
    message text NOT NULL,
    raw jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX import_issues_batch_idx ON import_issues (batch_id, row_number);

-- ---------------------------------------------------------------------------
-- Audit. Только добавление.
-- ---------------------------------------------------------------------------

CREATE TABLE audit_events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor_user_id uuid REFERENCES users (id),
    action text NOT NULL,
    entity_type text NOT NULL,
    entity_id text NOT NULL DEFAULT '',
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX audit_events_created_idx ON audit_events (created_at DESC);
CREATE INDEX audit_events_entity_idx ON audit_events (entity_type, entity_id);

CREATE TRIGGER audit_events_no_update
    BEFORE UPDATE OR DELETE ON audit_events
    FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

-- ---------------------------------------------------------------------------
-- Invariants that a column check cannot express
-- ---------------------------------------------------------------------------

CREATE FUNCTION teacher_must_be_employee() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.teacher_user_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM users WHERE id = NEW.teacher_user_id AND role = 'employee'
    ) THEN
        RAISE EXCEPTION 'only an employee can be assigned as a teacher';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER group_disciplines_teacher
    BEFORE INSERT OR UPDATE OF teacher_user_id ON group_disciplines
    FOR EACH ROW EXECUTE FUNCTION teacher_must_be_employee();

CREATE TRIGGER lessons_teacher
    BEFORE INSERT OR UPDATE OF teacher_user_id ON lessons
    FOR EACH ROW EXECUTE FUNCTION teacher_must_be_employee();

CREATE FUNCTION user_permissions_role_check() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    actor_role user_role;
    employee_codes text[] := ARRAY[
        'electives.review', 'certificates.review', 'dorm.review',
        'contracts.manage', 'scholarships.manage', 'data.correct'
    ];
    admin_codes text[] := ARRAY[
        'attendance.correct_teacher', 'users.manage', 'import.run',
        'settings.manage', 'schedule.manage', 'audit.read',
        'electives.review', 'certificates.review', 'dorm.review',
        'contracts.manage', 'scholarships.manage', 'data.correct'
    ];
BEGIN
    SELECT role INTO actor_role FROM users WHERE id = NEW.user_id;
    IF actor_role = 'student' OR actor_role IS NULL THEN
        RAISE EXCEPTION 'students do not receive permission grants';
    ELSIF actor_role = 'employee' AND NOT (NEW.permission_code = ANY (employee_codes)) THEN
        RAISE EXCEPTION 'permission % belongs to the admin panel', NEW.permission_code;
    ELSIF actor_role = 'admin' AND NOT (NEW.permission_code = ANY (admin_codes)) THEN
        RAISE EXCEPTION 'permission % is not assignable', NEW.permission_code;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER user_permissions_role
    BEFORE INSERT OR UPDATE ON user_permissions
    FOR EACH ROW EXECUTE FUNCTION user_permissions_role_check();

CREATE FUNCTION student_profile_is_student() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM users WHERE id = NEW.user_id AND role = 'student') THEN
        RAISE EXCEPTION 'student profile requires the student role';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER student_profiles_role
    BEFORE INSERT OR UPDATE ON student_profiles
    FOR EACH ROW EXECUTE FUNCTION student_profile_is_student();

CREATE FUNCTION employee_profile_is_employee() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM users WHERE id = NEW.user_id AND role = 'employee') THEN
        RAISE EXCEPTION 'employee profile requires the employee role';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER employee_profiles_role
    BEFORE INSERT OR UPDATE ON employee_profiles
    FOR EACH ROW EXECUTE FUNCTION employee_profile_is_employee();

CREATE FUNCTION group_discipline_block_matches() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.elective_block_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM elective_blocks
        WHERE id = NEW.elective_block_id
          AND group_id = NEW.group_id
          AND semester_id = NEW.semester_id
    ) THEN
        RAISE EXCEPTION 'elective block belongs to another group or semester';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER group_disciplines_block
    BEFORE INSERT OR UPDATE ON group_disciplines
    FOR EACH ROW EXECUTE FUNCTION group_discipline_block_matches();

CREATE FUNCTION elective_application_fill_block() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    SELECT elective_block_id INTO NEW.elective_block_id
    FROM group_disciplines
    WHERE id = NEW.group_discipline_id;
    IF NEW.elective_block_id IS NULL THEN
        RAISE EXCEPTION 'applications exist only for electives';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER elective_applications_block
    BEFORE INSERT OR UPDATE OF group_discipline_id ON elective_applications
    FOR EACH ROW EXECUTE FUNCTION elective_application_fill_block();

CREATE FUNCTION conversations_roles() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.kind = 'direct' THEN
        IF NOT EXISTS (
            SELECT 1 FROM users WHERE id = NEW.student_user_id AND role = 'student'
        ) THEN
            RAISE EXCEPTION 'direct chat student must have the student role';
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM users WHERE id = NEW.teacher_user_id AND role = 'employee'
        ) THEN
            RAISE EXCEPTION 'direct chat teacher must be an employee';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER conversations_roles_check
    BEFORE INSERT OR UPDATE ON conversations
    FOR EACH ROW EXECUTE FUNCTION conversations_roles();

CREATE FUNCTION grades_set_debt() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    pass numeric;
    labels text[];
    normalized text;
BEGIN
    IF NOT NEW.is_final THEN
        NEW.is_debt := false;
        RETURN NEW;
    END IF;
    SELECT pass_score, failing_labels INTO pass, labels FROM university WHERE id = 1;
    normalized := translate(lower(btrim(NEW.label)), 'ёЁ', 'ее');
    NEW.is_debt := (NEW.score IS NOT NULL AND NEW.score < pass)
        OR EXISTS (
            SELECT 1 FROM unnest(labels) AS item
            WHERE translate(lower(btrim(item)), 'ёЁ', 'ее') = normalized
              AND normalized <> ''
        );
    RETURN NEW;
END;
$$;

CREATE TRIGGER grades_debt
    BEFORE INSERT OR UPDATE ON grades
    FOR EACH ROW EXECUTE FUNCTION grades_set_debt();

CREATE FUNCTION certificate_request_mode() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM certificate_type_modes
        WHERE type_id = NEW.type_id AND mode = NEW.delivery_mode
    ) THEN
        RAISE EXCEPTION 'this certificate cannot be issued that way';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER certificate_requests_mode
    BEFORE INSERT OR UPDATE OF type_id, delivery_mode ON certificate_requests
    FOR EACH ROW EXECUTE FUNCTION certificate_request_mode();

CREATE FUNCTION ledger_reversal_matches() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    original ledger_entries%ROWTYPE;
BEGIN
    IF NEW.reverses_entry_id IS NULL THEN
        RETURN NEW;
    END IF;
    SELECT * INTO original FROM ledger_entries WHERE id = NEW.reverses_entry_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'reversal target does not exist';
    END IF;
    IF original.reverses_entry_id IS NOT NULL THEN
        RAISE EXCEPTION 'a reversal cannot be reversed';
    END IF;
    IF original.contract_id <> NEW.contract_id
        OR original.direction <> NEW.direction
        OR original.amount <> NEW.amount THEN
        RAISE EXCEPTION 'reversal must repeat the contract, direction and amount';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER ledger_entries_reversal
    BEFORE INSERT ON ledger_entries
    FOR EACH ROW EXECUTE FUNCTION ledger_reversal_matches();

CREATE FUNCTION users_role_keeps_profile() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.role IS DISTINCT FROM OLD.role THEN
        IF NEW.role <> 'student' AND EXISTS (
            SELECT 1 FROM student_profiles WHERE user_id = NEW.id
        ) THEN
            RAISE EXCEPTION 'student profile blocks this role change';
        END IF;
        IF NEW.role <> 'employee' AND EXISTS (
            SELECT 1 FROM employee_profiles WHERE user_id = NEW.id
        ) THEN
            RAISE EXCEPTION 'employee profile blocks this role change';
        END IF;
        IF EXISTS (SELECT 1 FROM user_permissions WHERE user_id = NEW.id) THEN
            RAISE EXCEPTION 'clear permissions before changing the role';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER users_role_profile
    BEFORE UPDATE OF role ON users
    FOR EACH ROW EXECUTE FUNCTION users_role_keeps_profile();

-- ---------------------------------------------------------------------------
-- Views
-- ---------------------------------------------------------------------------

CREATE VIEW academic_debts AS
SELECT
    id,
    student_user_id,
    discipline_id,
    semester_id,
    kind,
    title,
    label,
    score,
    updated_at
FROM grades
WHERE is_debt;

CREATE VIEW contract_balances AS
SELECT
    contract_id,
    COALESCE(SUM(amount) FILTER (WHERE direction = 'charge'), 0) AS charged,
    COALESCE(SUM(amount) FILTER (WHERE direction = 'payment'), 0) AS paid,
    COALESCE(SUM(amount) FILTER (WHERE direction = 'charge'), 0)
        - COALESCE(SUM(amount) FILTER (WHERE direction = 'payment'), 0) AS debt
FROM ledger_entries
WHERE reverses_entry_id IS NULL
  AND NOT EXISTS (
      SELECT 1
      FROM ledger_entries reversal
      WHERE reversal.reverses_entry_id = ledger_entries.id
  )
GROUP BY contract_id;
