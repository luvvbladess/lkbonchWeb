from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
from fastapi.responses import FileResponse

from app.db import get_conn
from app.deps import require_user
from app.schemas import (
    Ack,
    ActivationConfirm,
    ActivationRequest,
    ContactsUpdate,
    Conversation,
    Attendance,
    CertificateCreate,
    CertificateRequest,
    CertificateReview,
    CertificateType,
    Contract,
    DemoPayment,
    DemoPaymentCreate,
    DeviceRegistration,
    Diary,
    DirectChatCreate,
    DormApplication,
    DormCreate,
    DormReview,
    ElectiveApplication,
    ElectiveOffer,
    Grade,
    GradeWrite,
    GrantReplace,
    Health,
    JournalStudent,
    Lesson,
    LessonDetail,
    LoginRequest,
    MarkBody,
    Me,
    Message,
    MessageCreate,
    MessagePage,
    MessageUpdate,
    NotificationPage,
    PasswordChange,
    PortfolioDocument,
    PortfolioWrite,
    ProfileCorrection,
    ProfileCorrectionCreate,
    Rating,
    RefreshBody,
    ReviewDecision,
    ScholarshipView,
    StoredFile,
    StudentCard,
    TeachingAssignment,
    TokenPair,
    UniversityPublic,
    ApiModel,
)
from app.services import auth as auth_service
from app.services import chats, desk, profile, schedule, study
from app.services.common import public_university, load_university

router = APIRouter()


class ReadBody(ApiModel):
    message_id: UUID


class ElectiveApply(ApiModel):
    group_discipline_id: UUID


@router.get("/api/v1/university", operation_id="getUniversity", response_model=UniversityPublic)
def get_university(conn=Depends(get_conn)) -> UniversityPublic:
    return public_university(load_university(conn))


@router.get("/api/v1/university/logo", operation_id="getUniversityLogo", response_class=FileResponse)
def get_university_logo(conn=Depends(get_conn)) -> FileResponse:
    return desk.open_logo(conn)


@router.post("/api/v1/auth/activation/request", operation_id="requestActivation", status_code=202, response_model=Ack)
def request_activation(body: ActivationRequest, conn=Depends(get_conn)) -> Ack:
    return auth_service.request_activation(conn, body)


@router.post("/api/v1/auth/activation/confirm", operation_id="confirmActivation", response_model=TokenPair)
def confirm_activation(body: ActivationConfirm, conn=Depends(get_conn)) -> TokenPair:
    return auth_service.confirm_activation(conn, body)


@router.post("/api/v1/auth/login", operation_id="login", response_model=TokenPair)
def login(body: LoginRequest, conn=Depends(get_conn)) -> TokenPair:
    return auth_service.login(conn, body)


@router.post("/api/v1/auth/refresh", operation_id="refreshSession", response_model=TokenPair)
def refresh_session(body: RefreshBody, conn=Depends(get_conn)) -> TokenPair:
    return auth_service.refresh_session(conn, body.refresh_token)


@router.post("/api/v1/auth/logout", operation_id="logout", status_code=204)
def logout(body: RefreshBody, user=Depends(require_user), conn=Depends(get_conn)) -> Response:
    auth_service.logout(conn, user.id, body.refresh_token)
    return Response(status_code=204)


@router.post("/api/v1/auth/password", operation_id="changePassword", status_code=204)
def change_password(body: PasswordChange, user=Depends(require_user), conn=Depends(get_conn)) -> Response:
    auth_service.change_password(conn, user, body.current_password, body.new_password)
    return Response(status_code=204)


@router.get("/api/v1/me", operation_id="getMe", response_model=Me)
def get_me(user=Depends(require_user), conn=Depends(get_conn)) -> Me:
    return profile.build_me(conn, user)


@router.patch("/api/v1/me/contacts", operation_id="updateMyContacts", response_model=Me)
def update_contacts(body: ContactsUpdate, user=Depends(require_user), conn=Depends(get_conn)) -> Me:
    return profile.update_contacts(conn, user, body)


@router.get("/api/v1/me/student-card", operation_id="getStudentCard", response_model=StudentCard)
def student_card(user=Depends(require_user), conn=Depends(get_conn)) -> StudentCard:
    return profile.student_card(conn, user)


@router.get("/api/v1/me/scholarship", operation_id="getMyScholarship", response_model=ScholarshipView)
def scholarship(user=Depends(require_user), conn=Depends(get_conn)) -> ScholarshipView:
    return profile.my_scholarship(conn, user)


@router.get("/api/v1/me/rating", operation_id="getMyRating", response_model=Rating)
def rating(user=Depends(require_user), conn=Depends(get_conn)) -> Rating:
    return profile.my_rating(conn, user)


@router.get("/api/v1/me/corrections", operation_id="listMyCorrections", response_model=list[ProfileCorrection])
def my_corrections(user=Depends(require_user), conn=Depends(get_conn)):
    return study.list_corrections(conn, user)


@router.post("/api/v1/me/corrections", operation_id="createCorrection", status_code=201, response_model=ProfileCorrection)
def create_correction(body: ProfileCorrectionCreate, user=Depends(require_user), conn=Depends(get_conn)):
    return study.create_correction(conn, user, body)


@router.get("/api/v1/schedule", operation_id="listSchedule", response_model=list[Lesson])
def list_schedule(
    interval_from: datetime = Query(alias="from"),
    interval_to: datetime = Query(alias="to"),
    user=Depends(require_user),
    conn=Depends(get_conn),
):
    return schedule.list_schedule(conn, user, interval_from, interval_to)


@router.get("/api/v1/lessons/{lesson_id}", operation_id="getLesson", response_model=LessonDetail)
def get_lesson(lesson_id: UUID, user=Depends(require_user), conn=Depends(get_conn)):
    return schedule.get_lesson(conn, user, lesson_id)


@router.post("/api/v1/lessons/{lesson_id}/attendance", operation_id="markOwnAttendance", response_model=Attendance)
def mark_attendance(lesson_id: UUID, user=Depends(require_user), conn=Depends(get_conn)):
    return schedule.mark_own(conn, user, lesson_id)


@router.patch(
    "/api/v1/lessons/{lesson_id}/attendance/{user_id}",
    operation_id="correctStudentAttendance",
    response_model=Attendance,
)
def correct_attendance(
    lesson_id: UUID,
    user_id: UUID,
    body: MarkBody,
    user=Depends(require_user),
    conn=Depends(get_conn),
):
    return schedule.correct_student(conn, user, lesson_id, user_id, body.mark)


@router.get("/api/v1/diary", operation_id="getDiary", response_model=Diary)
def get_diary(
    semester_id: UUID | None = Query(default=None, alias="semesterId"),
    user=Depends(require_user),
    conn=Depends(get_conn),
):
    return study.diary(conn, user, semester_id)


@router.get("/api/v1/debts", operation_id="listDebts", response_model=list[Grade])
def list_debts(user=Depends(require_user), conn=Depends(get_conn)):
    return study.debts(conn, user)


@router.get("/api/v1/teaching", operation_id="listMyTeaching", response_model=list[TeachingAssignment])
def teaching(user=Depends(require_user), conn=Depends(get_conn)):
    return study.teaching(conn, user)


@router.get(
    "/api/v1/teaching/{group_discipline_id}/grades",
    operation_id="listTeachingGrades",
    response_model=list[JournalStudent],
)
def teaching_grades(group_discipline_id: UUID, user=Depends(require_user), conn=Depends(get_conn)):
    return study.teaching_grades(conn, user, group_discipline_id)


@router.post("/api/v1/grades", operation_id="createGrade", status_code=201, response_model=Grade)
def create_grade(body: GradeWrite, user=Depends(require_user), conn=Depends(get_conn)):
    return study.create_grade(conn, user, body)


@router.patch("/api/v1/grades/{grade_id}", operation_id="updateGrade", response_model=Grade)
def update_grade(grade_id: UUID, body: GradeWrite, user=Depends(require_user), conn=Depends(get_conn)):
    return study.update_grade(conn, user, grade_id, body)


@router.get("/api/v1/electives", operation_id="listElectives", response_model=list[ElectiveOffer])
def electives(user=Depends(require_user), conn=Depends(get_conn)):
    return study.list_electives(conn, user)


@router.post(
    "/api/v1/elective-applications",
    operation_id="applyForElective",
    status_code=201,
    response_model=ElectiveApplication,
)
def apply_elective(body: ElectiveApply, user=Depends(require_user), conn=Depends(get_conn)):
    return study.apply_elective(conn, user, body.group_discipline_id)


@router.patch(
    "/api/v1/elective-applications/{application_id}",
    operation_id="withdrawElectiveApplication",
    response_model=ElectiveApplication,
)
def withdraw_elective(application_id: UUID, user=Depends(require_user), conn=Depends(get_conn)):
    return study.withdraw_elective(conn, user, application_id)


@router.get(
    "/api/v1/staff/elective-applications",
    operation_id="listElectiveQueue",
    response_model=list[ElectiveApplication],
)
def elective_queue(
    status: str | None = None,
    user=Depends(require_user),
    conn=Depends(get_conn),
):
    return study.elective_queue(conn, user, status)


@router.post(
    "/api/v1/staff/elective-applications/{application_id}/decision",
    operation_id="decideElectiveApplication",
    response_model=ElectiveApplication,
)
def decide_elective(
    application_id: UUID,
    body: ReviewDecision,
    user=Depends(require_user),
    conn=Depends(get_conn),
):
    return study.decide_elective(conn, user, application_id, body.decision)


@router.get("/api/v1/conversations", operation_id="listConversations", response_model=list[Conversation])
def conversations(q: str | None = None, user=Depends(require_user), conn=Depends(get_conn)):
    return chats.list_conversations(conn, user, q)


@router.post("/api/v1/conversations/direct", operation_id="createDirectConversation", response_model=Conversation)
def direct_chat(body: DirectChatCreate, user=Depends(require_user), conn=Depends(get_conn)):
    return chats.create_direct(conn, user, body)


@router.get("/api/v1/conversations/{conversation_id}/messages", operation_id="listMessages", response_model=MessagePage)
def messages(
    conversation_id: UUID,
    cursor: str | None = None,
    limit: int | None = Query(default=None, ge=1, le=100),
    user=Depends(require_user),
    conn=Depends(get_conn),
):
    return chats.list_messages(conn, user, conversation_id, cursor, limit)


@router.post(
    "/api/v1/conversations/{conversation_id}/messages",
    operation_id="createMessage",
    status_code=201,
    response_model=Message,
)
def create_message(conversation_id: UUID, body: MessageCreate, user=Depends(require_user), conn=Depends(get_conn)):
    return chats.create_message(conn, user, conversation_id, body)


@router.patch("/api/v1/messages/{message_id}", operation_id="updateMessage", response_model=Message)
def update_message(message_id: UUID, body: MessageUpdate, user=Depends(require_user), conn=Depends(get_conn)):
    return chats.update_message(conn, user, message_id, body.body)


@router.delete("/api/v1/messages/{message_id}", operation_id="deleteMessage", status_code=204)
def delete_message(message_id: UUID, user=Depends(require_user), conn=Depends(get_conn)) -> Response:
    chats.delete_message(conn, user, message_id)
    return Response(status_code=204)


@router.post("/api/v1/conversations/{conversation_id}/read", operation_id="markConversationRead", status_code=204)
def mark_read(conversation_id: UUID, body: ReadBody, user=Depends(require_user), conn=Depends(get_conn)) -> Response:
    chats.mark_read(conn, user, conversation_id, body.message_id)
    return Response(status_code=204)


@router.get("/api/v1/notifications", operation_id="listNotifications", response_model=NotificationPage)
def notifications(
    cursor: str | None = None,
    limit: int | None = Query(default=None, ge=1, le=100),
    user=Depends(require_user),
    conn=Depends(get_conn),
):
    return desk.list_notifications(conn, user, cursor, limit)


@router.post("/api/v1/notifications/read-all", operation_id="markAllNotificationsRead", status_code=204)
def read_all(user=Depends(require_user), conn=Depends(get_conn)) -> Response:
    desk.mark_all_notifications(conn, user)
    return Response(status_code=204)


@router.post("/api/v1/notifications/{notification_id}/read", operation_id="markNotificationRead", status_code=204)
def read_one(notification_id: UUID, user=Depends(require_user), conn=Depends(get_conn)) -> Response:
    desk.mark_notification(conn, user, notification_id)
    return Response(status_code=204)


@router.post("/api/v1/devices", operation_id="registerDevice", status_code=204)
def register_device(body: DeviceRegistration, user=Depends(require_user), conn=Depends(get_conn)) -> Response:
    desk.register_device(conn, user, body.platform, body.token)
    return Response(status_code=204)


@router.get("/api/v1/certificate-types", operation_id="listCertificateTypes", response_model=list[CertificateType])
def certificate_types(user=Depends(require_user), conn=Depends(get_conn)):
    return desk.certificate_types(conn, user)


@router.get("/api/v1/certificate-requests", operation_id="listCertificateRequests", response_model=list[CertificateRequest])
def certificate_requests(status: str | None = None, user=Depends(require_user), conn=Depends(get_conn)):
    return desk.list_certificate_requests(conn, user, status)


@router.post(
    "/api/v1/certificate-requests",
    operation_id="createCertificateRequest",
    status_code=201,
    response_model=CertificateRequest,
)
def create_certificate(body: CertificateCreate, user=Depends(require_user), conn=Depends(get_conn)):
    return desk.create_certificate(conn, user, body)


@router.patch(
    "/api/v1/certificate-requests/{request_id}",
    operation_id="updateCertificateRequest",
    response_model=CertificateRequest,
)
def update_certificate(request_id: UUID, body: CertificateReview, user=Depends(require_user), conn=Depends(get_conn)):
    return desk.update_certificate(conn, user, request_id, body)


@router.get("/api/v1/dorm-applications", operation_id="listDormApplications", response_model=list[DormApplication])
def dorms(user=Depends(require_user), conn=Depends(get_conn)):
    return desk.list_dorms(conn, user)


@router.post("/api/v1/dorm-applications", operation_id="createDormApplication", status_code=201, response_model=DormApplication)
def create_dorm(body: DormCreate, user=Depends(require_user), conn=Depends(get_conn)):
    return desk.create_dorm(conn, user, body.comment)


@router.patch(
    "/api/v1/dorm-applications/{application_id}",
    operation_id="updateDormApplication",
    response_model=DormApplication,
)
def update_dorm(application_id: UUID, body: DormReview, user=Depends(require_user), conn=Depends(get_conn)):
    return desk.update_dorm(conn, user, application_id, body)


@router.get("/api/v1/contracts", operation_id="listContracts", response_model=list[Contract])
def contracts(user=Depends(require_user), conn=Depends(get_conn)):
    return desk.list_contracts(conn, user)


@router.get("/api/v1/contracts/{contract_id}", operation_id="getContract", response_model=Contract)
def contract(contract_id: UUID, user=Depends(require_user), conn=Depends(get_conn)):
    return desk.get_contract(conn, user, contract_id)


@router.post(
    "/api/v1/contracts/{contract_id}/demo-payments",
    operation_id="createDemoPayment",
    status_code=201,
    response_model=DemoPayment,
)
def demo_payment(contract_id: UUID, body: DemoPaymentCreate, user=Depends(require_user), conn=Depends(get_conn)):
    return desk.create_demo_payment(conn, user, contract_id, body)


@router.get("/api/v1/portfolio", operation_id="listPortfolio", response_model=list[PortfolioDocument])
def portfolio(user=Depends(require_user), conn=Depends(get_conn)):
    return desk.list_portfolio(conn, user)


@router.post("/api/v1/portfolio", operation_id="createPortfolioDocument", status_code=201)
def create_portfolio(body: PortfolioWrite, user=Depends(require_user), conn=Depends(get_conn)):
    return desk.create_portfolio(conn, user, body)


@router.patch("/api/v1/portfolio/{document_id}", operation_id="updatePortfolioDocument", response_model=PortfolioDocument)
def update_portfolio(document_id: UUID, body: PortfolioWrite, user=Depends(require_user), conn=Depends(get_conn)):
    return desk.update_portfolio(conn, user, document_id, body)


@router.delete("/api/v1/portfolio/{document_id}", operation_id="deletePortfolioDocument", status_code=204)
def delete_portfolio(document_id: UUID, user=Depends(require_user), conn=Depends(get_conn)) -> Response:
    desk.delete_portfolio(conn, user, document_id)
    return Response(status_code=204)


@router.put(
    "/api/v1/portfolio/{document_id}/grants",
    operation_id="replacePortfolioGrants",
    response_model=PortfolioDocument,
)
def portfolio_grants(document_id: UUID, body: GrantReplace, user=Depends(require_user), conn=Depends(get_conn)):
    return desk.replace_grants(conn, user, document_id, body.user_ids)


@router.post("/api/v1/files", operation_id="uploadFile", status_code=201, response_model=StoredFile)
def upload_file(file: UploadFile = File(...), user=Depends(require_user), conn=Depends(get_conn)):
    return desk.store_upload(conn, user.id, file)


@router.get("/api/v1/files/{file_id}", operation_id="getFile", response_class=FileResponse)
def get_file(file_id: UUID, user=Depends(require_user), conn=Depends(get_conn)):
    return desk.open_file(conn, user, file_id)
