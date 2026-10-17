from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile

from app.db import get_conn
from app.deps import require_user
from app.schemas import (
    AdminUser,
    AuditPage,
    CertificateType,
    CertificateTypeWrite,
    ChatSyncResult,
    Contract,
    ContractWrite,
    CorrectionDecision,
    CurriculumItem,
    CurriculumItemWrite,
    Discipline,
    DisciplineWrite,
    ElectiveBlock,
    ElectiveBlockWrite,
    ImportBatch,
    LedgerEntry,
    LedgerWrite,
    Lesson,
    LessonWrite,
    OrgUnit,
    OrgUnitWrite,
    PermissionInfo,
    PermissionReplace,
    ProfileCorrection,
    RatingFormula,
    RatingFormulaWrite,
    ScholarshipGrant,
    ScholarshipPayout,
    ScholarshipPayoutWrite,
    ScholarshipWrite,
    Semester,
    SemesterWrite,
    StaffUserUpdate,
    StaffUserWrite,
    StudyGroup,
    StudyGroupWrite,
    TeacherAttendanceBody,
    UniversitySettings,
    UniversitySettingsUpdate,
    UserPage,
)
from app.services import admin as catalog
from app.services import desk, imports
from app.services.schedule import correct_teacher

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/university", operation_id="getUniversitySettings", response_model=UniversitySettings)
def get_settings(user=Depends(require_user), conn=Depends(get_conn)):
    return catalog.get_settings(conn, user)


@router.patch("/university", operation_id="updateUniversitySettings", response_model=UniversitySettings)
def update_settings(body: UniversitySettingsUpdate, user=Depends(require_user), conn=Depends(get_conn)):
    return catalog.update_settings(conn, user, body)


@router.get("/org-units", operation_id="listOrgUnits", response_model=list[OrgUnit])
def org_units(user=Depends(require_user), conn=Depends(get_conn)):
    return catalog.list_org_units(conn, user)


@router.post("/org-units", operation_id="createOrgUnit", status_code=201, response_model=OrgUnit)
def create_org_unit(body: OrgUnitWrite, user=Depends(require_user), conn=Depends(get_conn)):
    return catalog.create_org_unit(conn, user, body)


@router.patch("/org-units/{org_unit_id}", operation_id="updateOrgUnit", response_model=OrgUnit)
def update_org_unit(org_unit_id: UUID, body: OrgUnitWrite, user=Depends(require_user), conn=Depends(get_conn)):
    return catalog.update_org_unit(conn, user, org_unit_id, body)


@router.get("/semesters", operation_id="listSemesters", response_model=list[Semester])
def semesters(user=Depends(require_user), conn=Depends(get_conn)):
    return catalog.list_semesters(conn, user)


@router.post("/semesters", operation_id="createSemester", status_code=201, response_model=Semester)
def create_semester(body: SemesterWrite, user=Depends(require_user), conn=Depends(get_conn)):
    return catalog.create_semester(conn, user, body)


@router.patch("/semesters/{semester_id}", operation_id="updateSemester", response_model=Semester)
def update_semester(semester_id: UUID, body: SemesterWrite, user=Depends(require_user), conn=Depends(get_conn)):
    return catalog.update_semester(conn, user, semester_id, body)


@router.post("/semesters/{semester_id}/sync-chats", operation_id="syncSemesterChats", response_model=ChatSyncResult)
def sync_chats(semester_id: UUID, user=Depends(require_user), conn=Depends(get_conn)):
    return catalog.sync_chats(conn, user, semester_id)


@router.post("/semesters/{semester_id}/close", operation_id="closeSemester", response_model=Semester)
def close_semester(semester_id: UUID, user=Depends(require_user), conn=Depends(get_conn)):
    return catalog.close_semester(conn, user, semester_id)


@router.get("/groups", operation_id="listGroups", response_model=list[StudyGroup])
def groups(user=Depends(require_user), conn=Depends(get_conn)):
    return catalog.list_groups(conn, user)


@router.post("/groups", operation_id="createGroup", status_code=201, response_model=StudyGroup)
def create_group(body: StudyGroupWrite, user=Depends(require_user), conn=Depends(get_conn)):
    return catalog.create_group(conn, user, body)


@router.patch("/groups/{group_id}", operation_id="updateGroup", response_model=StudyGroup)
def update_group(group_id: UUID, body: StudyGroupWrite, user=Depends(require_user), conn=Depends(get_conn)):
    return catalog.update_group(conn, user, group_id, body)


@router.get("/disciplines", operation_id="listDisciplines", response_model=list[Discipline])
def disciplines(user=Depends(require_user), conn=Depends(get_conn)):
    return catalog.list_disciplines(conn, user)


@router.post("/disciplines", operation_id="createDiscipline", status_code=201, response_model=Discipline)
def create_discipline(body: DisciplineWrite, user=Depends(require_user), conn=Depends(get_conn)):
    return catalog.create_discipline(conn, user, body)


@router.patch("/disciplines/{discipline_id}", operation_id="updateDiscipline", response_model=Discipline)
def update_discipline(discipline_id: UUID, body: DisciplineWrite, user=Depends(require_user), conn=Depends(get_conn)):
    return catalog.update_discipline(conn, user, discipline_id, body)


@router.get("/elective-blocks", operation_id="listElectiveBlocks", response_model=list[ElectiveBlock])
def blocks(
    semester_id: UUID | None = Query(default=None, alias="semesterId"),
    group_id: UUID | None = Query(default=None, alias="groupId"),
    user=Depends(require_user),
    conn=Depends(get_conn),
):
    return catalog.list_blocks(conn, user, semester_id, group_id)


@router.post("/elective-blocks", operation_id="createElectiveBlock", status_code=201, response_model=ElectiveBlock)
def create_block(body: ElectiveBlockWrite, user=Depends(require_user), conn=Depends(get_conn)):
    return catalog.create_block(conn, user, body)


@router.get("/group-disciplines", operation_id="listCurriculum", response_model=list[CurriculumItem])
def curriculum(
    semester_id: UUID | None = Query(default=None, alias="semesterId"),
    group_id: UUID | None = Query(default=None, alias="groupId"),
    user=Depends(require_user),
    conn=Depends(get_conn),
):
    return catalog.list_curriculum(conn, user, semester_id, group_id)


@router.post("/group-disciplines", operation_id="createCurriculumItem", status_code=201, response_model=CurriculumItem)
def create_curriculum(body: CurriculumItemWrite, user=Depends(require_user), conn=Depends(get_conn)):
    return catalog.create_curriculum(conn, user, body)


@router.get("/lessons", operation_id="listAdminLessons", response_model=list[Lesson])
def lessons(
    semester_id: UUID | None = Query(default=None, alias="semesterId"),
    group_id: UUID | None = Query(default=None, alias="groupId"),
    user=Depends(require_user),
    conn=Depends(get_conn),
):
    return catalog.list_admin_lessons(conn, user, semester_id, group_id)


@router.post("/lessons", operation_id="createLesson", status_code=201, response_model=Lesson)
def create_lesson(body: LessonWrite, user=Depends(require_user), conn=Depends(get_conn)):
    return catalog.create_lesson(conn, user, body)


@router.patch("/lessons/{lesson_id}", operation_id="updateLesson", response_model=Lesson)
def update_lesson(lesson_id: UUID, body: LessonWrite, user=Depends(require_user), conn=Depends(get_conn)):
    return catalog.update_lesson(conn, user, lesson_id, body)


@router.post("/lessons/{lesson_id}/publish", operation_id="publishLesson", response_model=Lesson)
def publish_lesson(lesson_id: UUID, user=Depends(require_user), conn=Depends(get_conn)):
    return catalog.publish_lesson(conn, user, lesson_id)


@router.patch("/lessons/{lesson_id}/teacher-attendance", operation_id="correctTeacherAttendance")
def teacher_attendance(
    lesson_id: UUID,
    body: TeacherAttendanceBody,
    user=Depends(require_user),
    conn=Depends(get_conn),
):
    return correct_teacher(conn, user, lesson_id, body.user_id, body.mark)


@router.get("/users", operation_id="listUsers", response_model=UserPage)
def users(
    q: str | None = None,
    role: str | None = None,
    status: str | None = None,
    cursor: str | None = None,
    limit: int | None = Query(default=None, ge=1, le=100),
    user=Depends(require_user),
    conn=Depends(get_conn),
):
    return catalog.list_users(conn, user, q, role, status, cursor, limit)


@router.post("/users", operation_id="createUser", status_code=201, response_model=AdminUser)
def create_user(body: StaffUserWrite, user=Depends(require_user), conn=Depends(get_conn)):
    return catalog.create_user(conn, user, body)


@router.get("/users/{user_id}", operation_id="getUser", response_model=AdminUser)
def get_user(user_id: UUID, user=Depends(require_user), conn=Depends(get_conn)):
    user.require("users.manage")
    return catalog._user_row(conn, user_id)


@router.patch("/users/{user_id}", operation_id="updateUser", response_model=AdminUser)
def update_user(user_id: UUID, body: StaffUserUpdate, user=Depends(require_user), conn=Depends(get_conn)):
    return catalog.update_user(conn, user, user_id, body)


@router.post("/users/{user_id}/block", operation_id="blockUser", response_model=AdminUser)
def block_user(user_id: UUID, user=Depends(require_user), conn=Depends(get_conn)):
    return catalog.block_user(conn, user, user_id)


@router.post("/users/{user_id}/unblock", operation_id="unblockUser", response_model=AdminUser)
def unblock_user(user_id: UUID, user=Depends(require_user), conn=Depends(get_conn)):
    return catalog.unblock_user(conn, user, user_id)


@router.get("/permissions", operation_id="listPermissions", response_model=list[PermissionInfo])
def permissions(user=Depends(require_user), conn=Depends(get_conn)):
    return catalog.list_permissions(conn, user)


@router.put("/users/{user_id}/permissions", operation_id="replaceUserPermissions", response_model=AdminUser)
def replace_permissions(user_id: UUID, body: PermissionReplace, user=Depends(require_user), conn=Depends(get_conn)):
    return catalog.replace_permissions(conn, user, user_id, body.permissions)


@router.get("/rating-formula", operation_id="getRatingFormula", response_model=RatingFormula)
def formula(user=Depends(require_user), conn=Depends(get_conn)):
    return catalog.get_formula(conn, user)


@router.put("/rating-formula", operation_id="replaceRatingFormula", response_model=RatingFormula)
def replace_formula(body: RatingFormulaWrite, user=Depends(require_user), conn=Depends(get_conn)):
    return catalog.replace_formula(conn, user, body)


@router.get("/certificate-types", operation_id="listAdminCertificateTypes", response_model=list[CertificateType])
def certificate_types(user=Depends(require_user), conn=Depends(get_conn)):
    user.require("settings.manage")
    return desk.certificate_types(conn, user, include_disabled=True)


@router.post("/certificate-types", operation_id="createCertificateType", status_code=201, response_model=CertificateType)
def create_certificate_type(body: CertificateTypeWrite, user=Depends(require_user), conn=Depends(get_conn)):
    return catalog.save_certificate_type(conn, user, body)


@router.patch("/certificate-types/{type_id}", operation_id="updateCertificateType", response_model=CertificateType)
def update_certificate_type(type_id: UUID, body: CertificateTypeWrite, user=Depends(require_user), conn=Depends(get_conn)):
    return catalog.save_certificate_type(conn, user, body, type_id)


@router.get("/contracts", operation_id="listAdminContracts", response_model=list[Contract])
def contracts(
    student_id: UUID | None = Query(default=None, alias="studentId"),
    user=Depends(require_user),
    conn=Depends(get_conn),
):
    user.require("contracts.manage")
    return desk.list_contracts(conn, user, student_id)


@router.post("/contracts", operation_id="createContract", status_code=201, response_model=Contract)
def create_contract(body: ContractWrite, user=Depends(require_user), conn=Depends(get_conn)):
    return catalog.create_contract(conn, user, body)


@router.post("/contracts/{contract_id}/entries", operation_id="createLedgerEntry", status_code=201, response_model=LedgerEntry)
def ledger(contract_id: UUID, body: LedgerWrite, user=Depends(require_user), conn=Depends(get_conn)):
    return catalog.create_ledger(conn, user, contract_id, body)


@router.get("/scholarships", operation_id="listScholarships", response_model=list[ScholarshipGrant])
def scholarships(
    student_id: UUID | None = Query(default=None, alias="studentId"),
    user=Depends(require_user),
    conn=Depends(get_conn),
):
    return catalog.list_scholarships(conn, user, student_id)


@router.post("/scholarships", operation_id="createScholarship", status_code=201, response_model=ScholarshipGrant)
def create_scholarship(body: ScholarshipWrite, user=Depends(require_user), conn=Depends(get_conn)):
    return catalog.create_scholarship(conn, user, body)


@router.post(
    "/scholarships/{grant_id}/payouts",
    operation_id="createScholarshipPayout",
    status_code=201,
    response_model=ScholarshipPayout,
)
def payout(grant_id: UUID, body: ScholarshipPayoutWrite, user=Depends(require_user), conn=Depends(get_conn)):
    return catalog.create_payout(conn, user, grant_id, body)


@router.get("/corrections", operation_id="listCorrections", response_model=list[ProfileCorrection])
def corrections(status: str | None = None, user=Depends(require_user), conn=Depends(get_conn)):
    return catalog.list_admin_corrections(conn, user, status)


@router.post("/corrections/{correction_id}/decision", operation_id="decideCorrection", response_model=ProfileCorrection)
def decide(correction_id: UUID, body: CorrectionDecision, user=Depends(require_user), conn=Depends(get_conn)):
    return catalog.decide_correction(conn, user, correction_id, body.decision)


@router.post("/imports", operation_id="createImport", response_model=ImportBatch)
def create_import(
    domain: str = Form(),
    file: UploadFile = File(...),
    mode: str = Form("insert_only"),
    dry_run: bool = Form(True, alias="dryRun"),
    user=Depends(require_user),
    conn=Depends(get_conn),
):
    return imports.create_import(conn, user, domain, mode, dry_run, file.filename or "import.csv", file.file.read())


@router.get("/imports/{batch_id}", operation_id="getImport", response_model=ImportBatch)
def get_import(batch_id: UUID, user=Depends(require_user), conn=Depends(get_conn)):
    return imports.get_import(conn, user, batch_id)


@router.post("/imports/{batch_id}/apply", operation_id="applyImport", response_model=ImportBatch)
def apply_import(batch_id: UUID, user=Depends(require_user), conn=Depends(get_conn)):
    return imports.apply_import(conn, user, batch_id)


@router.get("/audit", operation_id="listAudit", response_model=AuditPage)
def audit(
    cursor: str | None = None,
    limit: int | None = Query(default=None, ge=1, le=100),
    entity_type: str | None = Query(default=None, alias="entityType"),
    user=Depends(require_user),
    conn=Depends(get_conn),
):
    return catalog.list_audit(conn, user, cursor, limit, entity_type)
