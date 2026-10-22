from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

Role = Literal["student", "employee", "admin"]
AccountStatus = Literal["pending", "active", "blocked"]
Funding = Literal["budget", "paid", "targeted"]
OrgKind = Literal["institute", "faculty", "department", "other"]
SemesterStatus = Literal["planned", "active", "closed"]
DisciplineKind = Literal["required", "elective"]
ApplicationStatus = Literal["pending", "approved", "rejected", "withdrawn"]
Publication = Literal["draft", "published"]
AttendanceMarkName = Literal["present", "absent"]
AttendanceOrigin = Literal["student", "system", "teacher", "admin"]
GradeKind = Literal["current", "passfail", "graded_credit", "exam"]
ConversationKind = Literal["group", "direct"]
DeliveryMode = Literal["electronic", "paper", "appointment"]
RequestStatus = Literal["pending", "in_progress", "ready", "rejected", "issued"]
DormStatus = Literal["pending", "in_progress", "settled", "rejected"]
ContractKind = Literal["tuition", "housing", "other"]
LedgerDirection = Literal["charge", "payment"]
PayMethod = Literal["card", "sbp"]
PortfolioKind = Literal["portfolio", "resume"]
CorrectionField = Literal[
    "group",
    "course",
    "record_book_number",
    "student_card_number",
    "funding",
    "lives_in_dorm",
]
CorrectionStatus = Literal["pending", "applied", "rejected"]
NotificationType = Literal[
    "schedule_changed",
    "grade_posted",
    "message",
    "certificate_updated",
    "dorm_updated",
    "elective_updated",
    "correction_updated",
    "demo_payment_recorded",
]
Section = Literal[
    "schedule",
    "diary",
    "chats",
    "electives",
    "certificates",
    "dormitory",
    "contracts",
    "portfolio",
    "scholarships",
]
StaffRole = Literal["employee", "admin"]
ImportMode = Literal["insert_only", "upsert"]
DevicePlatform = Literal["web", "android", "ios"]

DEMO_MESSAGE = "Демо-оплата выполнена, средства не списаны"
ACTIVATION_MESSAGE = "Если запись найдена, код отправлен на зарегистрированный контакт."


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        ser_json_timedelta="iso8601",
    )


class FieldError(ApiModel):
    field: str
    message: str


class ErrorInfo(ApiModel):
    code: str
    message: str
    details: list[FieldError] | None = None


class ErrorResponse(ApiModel):
    error: ErrorInfo


class Health(ApiModel):
    status: Literal["ok", "degraded"]
    database: Literal["ok", "down"]


class Ack(ApiModel):
    message: str


class TokenPair(ApiModel):
    access_token: str
    refresh_token: str
    expires_in: int


class RefreshBody(ApiModel):
    refresh_token: str


class PasswordChange(ApiModel):
    current_password: str
    new_password: str


class ActivationRequest(ApiModel):
    last_name: str
    first_name: str
    middle_name: str = ""
    identifier: str


class ActivationConfirm(ActivationRequest):
    code: str
    login: str
    password: str


class LoginRequest(ApiModel):
    login: str
    password: str


class UniversityPublic(ApiModel):
    name: str
    short_name: str
    brand_seed: str
    brand_accent: str
    enabled_sections: list[Section]
    logo_url: str | None = None


class UniversitySettings(UniversityPublic):
    timezone: str
    student_match_field: Literal["student_card_number", "record_book_number"]
    pass_score: str
    failing_labels: list[str]


class UniversitySettingsUpdate(ApiModel):
    name: str | None = None
    short_name: str | None = None
    brand_seed: str | None = None
    brand_accent: str | None = None
    enabled_sections: list[Section] | None = None
    timezone: str | None = None
    student_match_field: Literal["student_card_number", "record_book_number"] | None = None
    pass_score: str | None = None
    failing_labels: list[str] | None = None
    logo_file_id: UUID | None = None


class StudentProfile(ApiModel):
    group_id: UUID | None = None
    group_name: str | None = None
    org_unit_name: str | None = None
    course: int | None = None
    funding: Funding
    record_book_number: str | None = None
    student_card_number: str | None = None
    lives_in_dorm: bool


class EmployeeProfile(ApiModel):
    org_unit_name: str | None = None
    position: str


class Me(ApiModel):
    id: UUID
    role: Role
    status: AccountStatus
    last_name: str
    first_name: str
    middle_name: str = ""
    login: str | None = None
    email: str | None = None
    phone: str | None = None
    permissions: list[str]
    enabled_sections: list[str]
    student: StudentProfile | None = None
    employee: EmployeeProfile | None = None


class ContactsUpdate(ApiModel):
    email: str | None = None
    phone: str | None = None


class StudentCard(ApiModel):
    full_name: str
    student_card_number: str | None = None
    record_book_number: str | None = None
    group_name: str | None = None
    photo_url: str | None = None
    qr_payload: str


class Lesson(ApiModel):
    id: UUID
    discipline_name: str
    starts_at: datetime
    ends_at: datetime
    room: str
    publication_status: Publication
    cancelled: bool
    groups: list[str]
    teacher_name: str | None = None
    note: str = ""


class Attendance(ApiModel):
    user_id: UUID
    full_name: str
    mark: AttendanceMarkName
    origin: AttendanceOrigin
    updated_at: datetime


class LessonPerson(ApiModel):
    user_id: UUID
    full_name: str
    role: Literal["student", "teacher"]


class LessonDetail(Lesson):
    attendance: list[Attendance]
    participants: list[LessonPerson]
    can_mark_self: bool


class MarkBody(ApiModel):
    mark: AttendanceMarkName


class TeacherAttendanceBody(ApiModel):
    user_id: UUID
    mark: AttendanceMarkName


class Grade(ApiModel):
    id: UUID
    discipline_name: str
    semester_id: UUID
    semester_title: str = ""
    student_id: UUID | None = None
    student_name: str | None = None
    kind: GradeKind
    title: str = ""
    score: str | None = None
    label: str = ""
    is_final: bool
    is_debt: bool
    credits: str


class GradeWrite(ApiModel):
    student_id: UUID
    discipline_id: UUID
    semester_id: UUID
    kind: GradeKind
    title: str = ""
    score: str | None = None
    label: str = ""
    is_final: bool


class DiarySemester(ApiModel):
    semester_id: UUID
    title: str
    grades: list[Grade]


class Diary(ApiModel):
    semesters: list[DiarySemester]


class TeachingAssignment(ApiModel):
    group_discipline_id: UUID
    discipline_id: UUID
    semester_id: UUID
    discipline_name: str
    group_name: str
    semester_title: str
    kind: DisciplineKind


class JournalStudent(ApiModel):
    student_id: UUID
    student_name: str
    grades: list[Grade]


class Rating(ApiModel):
    score: str | None = None
    computed_at: datetime | None = None


class ElectiveApplication(ApiModel):
    id: UUID
    status: ApplicationStatus
    discipline_name: str = ""
    student_name: str = ""
    submitted_at: datetime | None = None


class ElectiveOffer(ApiModel):
    group_discipline_id: UUID
    discipline_name: str
    credits: str
    block_title: str = ""
    application: ElectiveApplication | None = None


class ReviewDecision(ApiModel):
    decision: Literal["approved", "rejected"]


class CorrectionDecision(ApiModel):
    decision: Literal["apply", "reject"]


class Message(ApiModel):
    id: UUID
    author_user_id: UUID
    author_name: str = ""
    body: str
    created_at: datetime
    edited_at: datetime | None = None
    deleted: bool
    attachment_ids: list[UUID] = Field(default_factory=list)


class Conversation(ApiModel):
    id: UUID
    kind: ConversationKind
    title: str
    closed: bool
    unread_count: int = 0
    last_message: Message | None = None


class MessageCreate(ApiModel):
    client_message_id: UUID
    body: str = ""
    attachment_ids: list[UUID] = Field(default_factory=list)


class MessageUpdate(ApiModel):
    body: str


class MessagePage(ApiModel):
    items: list[Message]
    next_cursor: str | None = None


class DirectChatCreate(ApiModel):
    discipline_id: UUID
    semester_id: UUID
    peer_user_id: UUID


class Notification(ApiModel):
    id: UUID
    type: NotificationType
    title: str
    body: str = ""
    read_at: datetime | None = None
    created_at: datetime
    payload: dict[str, Any] = Field(default_factory=dict)


class NotificationPage(ApiModel):
    items: list[Notification]
    next_cursor: str | None = None


class DeviceRegistration(ApiModel):
    platform: DevicePlatform
    token: str


class CertificateType(ApiModel):
    id: UUID
    code: str
    title: str
    enabled: bool
    delivery_modes: list[DeliveryMode]


class CertificateTypeWrite(ApiModel):
    code: str
    title: str
    enabled: bool = True
    delivery_modes: list[DeliveryMode]


class CertificateRequest(ApiModel):
    id: UUID
    type_title: str
    delivery_mode: DeliveryMode
    status: RequestStatus
    comment: str = ""
    appointment_at: datetime | None = None
    result_file_id: UUID | None = None
    created_at: datetime
    student_id: UUID | None = None
    student_name: str | None = None


class CertificateCreate(ApiModel):
    type_id: UUID
    delivery_mode: DeliveryMode
    comment: str = ""


class CertificateReview(ApiModel):
    status: Literal["in_progress", "ready", "rejected", "issued"] | None = None
    appointment_at: datetime | None = None
    comment: str | None = None
    result_file_id: UUID | None = None


class DormApplication(ApiModel):
    id: UUID
    status: DormStatus
    building: str = ""
    room: str = ""
    comment: str = ""
    contract_id: UUID | None = None
    created_at: datetime
    student_id: UUID | None = None
    student_name: str | None = None


class DormCreate(ApiModel):
    comment: str = ""


class DormReview(ApiModel):
    status: Literal["in_progress", "settled", "rejected"] | None = None
    building: str | None = None
    room: str | None = None
    contract_id: UUID | None = None
    comment: str | None = None


class LedgerEntry(ApiModel):
    id: UUID
    direction: LedgerDirection
    amount: str
    occurred_on: date
    description: str = ""
    reversed: bool
    reverses_entry_id: UUID | None = None


class DemoPayment(ApiModel):
    id: UUID
    educational: Literal[True] = True
    result: Literal["demo_completed"] = "demo_completed"
    method: PayMethod
    amount: str
    message: str


class Contract(ApiModel):
    id: UUID
    kind: ContractKind
    number: str
    title: str = ""
    charged: str
    paid: str
    debt: str
    student_id: UUID | None = None
    entries: list[LedgerEntry] | None = None
    demo_payments: list[DemoPayment] | None = None


class DemoPaymentCreate(ApiModel):
    amount: str
    method: PayMethod


class ContractWrite(ApiModel):
    student_id: UUID
    kind: ContractKind
    number: str
    title: str = ""
    opened_on: date | None = None


class LedgerWrite(ApiModel):
    direction: LedgerDirection
    amount: str
    occurred_on: date
    description: str = ""
    reverses_entry_id: UUID | None = None


class ScholarshipGrant(ApiModel):
    id: UUID
    title: str
    amount: str
    next_payout_on: date | None = None
    active: bool
    student_id: UUID | None = None


class ScholarshipPayout(ApiModel):
    id: UUID
    amount: str
    paid_on: date
    grant_id: UUID | None = None


class ScholarshipView(ApiModel):
    grants: list[ScholarshipGrant]
    payouts: list[ScholarshipPayout]


class ScholarshipWrite(ApiModel):
    student_id: UUID
    title: str
    amount: str
    next_payout_on: date | None = None


class ScholarshipPayoutWrite(ApiModel):
    amount: str
    paid_on: date


class PortfolioDocument(ApiModel):
    id: UUID
    kind: PortfolioKind
    title: str
    body: str = ""
    file_id: UUID | None = None
    grantee_user_ids: list[UUID] = Field(default_factory=list)


class PortfolioWrite(ApiModel):
    kind: PortfolioKind
    title: str
    body: str = ""
    file_id: UUID | None = None


class GrantReplace(ApiModel):
    user_ids: list[UUID]


class StoredFile(ApiModel):
    id: UUID
    original_name: str
    content_type: str
    size_bytes: int


class OrgUnit(ApiModel):
    id: UUID
    parent_id: UUID | None = None
    kind: OrgKind
    name: str


class OrgUnitWrite(ApiModel):
    parent_id: UUID | None = None
    kind: OrgKind
    name: str


class Semester(ApiModel):
    id: UUID
    title: str
    starts_on: date
    ends_on: date
    status: SemesterStatus
    elective_open_on: date | None = None
    elective_close_on: date | None = None
    elective_change_until: date | None = None


class SemesterWrite(ApiModel):
    title: str
    starts_on: date
    ends_on: date
    status: SemesterStatus = "planned"
    elective_open_on: date | None = None
    elective_close_on: date | None = None
    elective_change_until: date | None = None


class ChatSyncResult(ApiModel):
    conversations_created: int
    members_added: int


class StudyGroup(ApiModel):
    id: UUID
    org_unit_id: UUID
    name: str
    course: int
    entry_year: int


class StudyGroupWrite(ApiModel):
    org_unit_id: UUID
    name: str
    course: int
    entry_year: int


class Discipline(ApiModel):
    id: UUID
    code: str
    name: str
    org_unit_id: UUID | None = None


class DisciplineWrite(ApiModel):
    code: str
    name: str
    org_unit_id: UUID | None = None


class ElectiveBlock(ApiModel):
    id: UUID
    group_id: UUID
    semester_id: UUID
    title: str


class ElectiveBlockWrite(ApiModel):
    group_id: UUID
    semester_id: UUID
    title: str


class CurriculumItem(ApiModel):
    id: UUID
    group_id: UUID
    discipline_id: UUID
    semester_id: UUID
    kind: DisciplineKind
    credits: str
    teacher_user_id: UUID | None = None
    elective_block_id: UUID | None = None


class CurriculumItemWrite(ApiModel):
    group_id: UUID
    discipline_id: UUID
    semester_id: UUID
    kind: DisciplineKind
    credits: str = "0"
    teacher_user_id: UUID | None = None
    elective_block_id: UUID | None = None


class LessonWrite(ApiModel):
    semester_id: UUID
    discipline_id: UUID
    teacher_user_id: UUID | None = None
    starts_at: datetime
    ends_at: datetime
    room: str = ""
    note: str = ""
    group_ids: list[UUID]
    cancelled: bool | None = None


class AdminUser(ApiModel):
    id: UUID
    role: Role
    status: AccountStatus
    last_name: str
    first_name: str
    middle_name: str = ""
    login: str | None = None
    email: str | None = None
    phone: str | None = None
    permissions: list[str]


class StaffUserWrite(ApiModel):
    role: StaffRole
    last_name: str
    first_name: str
    middle_name: str = ""
    login: str
    email: str | None = None
    phone: str | None = None
    password: str
    position: str = ""
    org_unit_id: UUID | None = None
    permissions: list[str] = Field(default_factory=list)


class StaffUserUpdate(ApiModel):
    last_name: str
    first_name: str
    middle_name: str = ""
    login: str
    email: str | None = None
    phone: str | None = None
    password: str | None = None
    position: str | None = None
    org_unit_id: UUID | None = None
    permissions: list[str] | None = None


class UserPage(ApiModel):
    items: list[AdminUser]
    next_cursor: str | None = None


class PermissionInfo(ApiModel):
    code: str
    description: str


class PermissionReplace(ApiModel):
    permissions: list[str]


class RatingFormula(ApiModel):
    id: UUID
    name: str
    definition: dict[str, Any]


class RatingFormulaWrite(ApiModel):
    name: str
    definition: dict[str, Any]


class ProfileCorrection(ApiModel):
    id: UUID
    field_name: CorrectionField
    requested_value: str
    comment: str = ""
    status: CorrectionStatus
    created_at: datetime
    student_id: UUID | None = None
    student_name: str | None = None


class ProfileCorrectionCreate(ApiModel):
    field_name: CorrectionField
    requested_value: str
    comment: str = ""


class ImportIssue(ApiModel):
    row_number: int
    field_name: str = ""
    message: str


class ImportBatch(ApiModel):
    id: UUID
    domain: str
    mode: ImportMode
    status: Literal["preview", "applied", "failed"]
    accepted_count: int
    rejected_count: int
    issues: list[ImportIssue]


class AuditEvent(ApiModel):
    id: int
    actor_user_id: UUID | None = None
    action: str
    entity_type: str
    entity_id: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class AuditPage(ApiModel):
    items: list[AuditEvent]
    next_cursor: str | None = None
