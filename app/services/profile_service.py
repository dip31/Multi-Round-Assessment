"""
Service for EDI5 Identity & Role Profiles.
"""

from typing import Optional
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.profile import StudentProfile, FacultyProfile, TPOProfile, UserResume
from app.schemas.profile import (
    StudentProfileUpdate,
    StudentProfileResponse,
    PlacementEligibility,
    FacultyProfileUpdate,
    FacultyProfileResponse,
    TPOProfileUpdate,
    TPOProfileResponse,
    UserProfileResponse,
    UserResumeResponse,
)


class ProfileService:
    @staticmethod
    def get_or_create_student_profile(db: Session, user_id: int) -> StudentProfile:
        profile = db.query(StudentProfile).filter(StudentProfile.user_id == user_id).first()
        if not profile:
            profile = StudentProfile(user_id=user_id)
            db.add(profile)
            db.commit()
            db.refresh(profile)
        return profile

    @staticmethod
    def get_or_create_faculty_profile(db: Session, user_id: int) -> FacultyProfile:
        profile = db.query(FacultyProfile).filter(FacultyProfile.user_id == user_id).first()
        if not profile:
            profile = FacultyProfile(user_id=user_id)
            db.add(profile)
            db.commit()
            db.refresh(profile)
        return profile

    @staticmethod
    def get_or_create_tpo_profile(db: Session, user_id: int) -> TPOProfile:
        profile = db.query(TPOProfile).filter(TPOProfile.user_id == user_id).first()
        if not profile:
            profile = TPOProfile(user_id=user_id)
            db.add(profile)
            db.commit()
            db.refresh(profile)
        return profile

    @staticmethod
    def _to_student_response(sp: StudentProfile, default_name: Optional[str] = None) -> StudentProfileResponse:
        skills = sp.skills_json if isinstance(sp.skills_json, list) else []
        cgpa = float(sp.cgpa or 0.0)
        backlogs = int(sp.backlogs_count or 0)

        if backlogs > 0:
            eligibility = PlacementEligibility(
                status="attention_required",
                label="Attention Required",
                badge_variant="amber",
                message=f"{backlogs} active backlog(s) pending clearance before drive registration.",
                is_eligible=False,
            )
        elif cgpa >= 7.0:
            eligibility = PlacementEligibility(
                status="tier_1_eligible",
                label="Eligible (Tier-1 Drives)",
                badge_variant="emerald",
                message="Eligible for premium Tier-1 product companies & campus placement drives.",
                is_eligible=True,
            )
        elif cgpa >= 6.0:
            eligibility = PlacementEligibility(
                status="standard_eligible",
                label="Eligible (Standard Drives)",
                badge_variant="sky",
                message="Eligible for standard campus recruitment and IT drives.",
                is_eligible=True,
            )
        else:
            eligibility = PlacementEligibility(
                status="criteria_pending",
                label="Criteria Pending",
                badge_variant="slate",
                message="CGPA below standard drive cutoff (6.0). Strengthen profile via practice rounds.",
                is_eligible=False,
            )

        return StudentProfileResponse(
            id=sp.id,
            user_id=sp.user_id,
            full_name=sp.full_name or default_name,
            roll_number=sp.roll_number,
            department=sp.department,
            cgpa=sp.cgpa,
            graduation_year=sp.graduation_year,
            backlogs_count=sp.backlogs_count,
            institution=sp.institution,
            target_role=sp.target_role,
            skills=skills,
            phone_number=sp.phone_number or sp.mobile_no,
            mobile_no=sp.mobile_no or sp.phone_number,
            college_email_id=sp.college_email_id,
            gender=sp.gender,
            date_of_birth=sp.date_of_birth,
            nationality=sp.nationality or "Indian",
            tenth_marks=sp.tenth_marks,
            twelfth_marks=sp.twelfth_marks,
            bio=sp.bio,
            placement_eligibility=eligibility,
            created_at=sp.created_at,
            updated_at=sp.updated_at,
        )

    @classmethod
    def get_full_profile(cls, db: Session, user: User) -> UserProfileResponse:
        student_resp: Optional[StudentProfileResponse] = None
        faculty_resp: Optional[FacultyProfileResponse] = None
        tpo_resp: Optional[TPOProfileResponse] = None

        if user.role == "student":
            sp = cls.get_or_create_student_profile(db, user.id)
            student_resp = cls._to_student_response(sp, default_name=user.name)
        elif user.role == "faculty":
            fp = cls.get_or_create_faculty_profile(db, user.id)
            faculty_resp = FacultyProfileResponse(
                id=fp.id,
                user_id=fp.user_id,
                department=fp.department,
                designation=fp.designation,
                institution=fp.institution,
                employee_id=fp.employee_id,
                bio=fp.bio,
                created_at=fp.created_at,
                updated_at=fp.updated_at,
            )
        elif user.role == "tpo":
            tp = cls.get_or_create_tpo_profile(db, user.id)
            tpo_resp = TPOProfileResponse(
                id=tp.id,
                user_id=tp.user_id,
                institution=tp.institution,
                designation=tp.designation,
                contact_email=tp.contact_email,
                contact_phone=tp.contact_phone,
                bio=tp.bio,
                created_at=tp.created_at,
                updated_at=tp.updated_at,
            )

        resumes_resp = None
        if user.role == "student":
            user_resumes = (
                db.query(UserResume)
                .filter(UserResume.user_id == user.id)
                .order_by(UserResume.id.desc())
                .all()
            )
            resumes_resp = [
                UserResumeResponse(
                    id=r.id,
                    user_id=r.user_id,
                    cv_name=r.cv_name,
                    cv_type=r.cv_type,
                    file_name=r.file_name,
                    file_size=r.file_size,
                    parsed_skills=r.parsed_skills if isinstance(r.parsed_skills, list) else [],
                    parsed_projects=r.parsed_projects if isinstance(r.parsed_projects, list) else [],
                    uploaded_at=r.uploaded_at,
                )
                for r in user_resumes
            ]

        return UserProfileResponse(
            id=user.id,
            name=user.name,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            is_verified=user.is_verified,
            created_at=user.created_at,
            student_profile=student_resp,
            faculty_profile=faculty_resp,
            tpo_profile=tpo_resp,
            resumes=resumes_resp,
        )

    @classmethod
    def update_student_profile(
        cls, db: Session, user_id: int, payload: StudentProfileUpdate
    ) -> StudentProfileResponse:
        sp = cls.get_or_create_student_profile(db, user_id)
        update_data = payload.model_dump(exclude_unset=True)

        user = db.query(User).filter(User.id == user_id).first()
        if "full_name" in update_data and update_data["full_name"]:
            if user:
                user.name = update_data["full_name"]

        if "mobile_no" in update_data and update_data["mobile_no"]:
            sp.phone_number = update_data["mobile_no"]

        if "skills" in update_data:
            sp.skills_json = update_data.pop("skills")

        for key, value in update_data.items():
            if hasattr(sp, key) and value is not None:
                setattr(sp, key, value)

        db.commit()
        db.refresh(sp)
        if user:
            db.refresh(user)

        return cls._to_student_response(sp, default_name=user.name if user else None)

    @classmethod
    def update_faculty_profile(
        cls, db: Session, user_id: int, payload: FacultyProfileUpdate
    ) -> FacultyProfileResponse:
        fp = cls.get_or_create_faculty_profile(db, user_id)
        for key, value in payload.model_dump(exclude_unset=True).items():
            if hasattr(fp, key) and value is not None:
                setattr(fp, key, value)

        db.commit()
        db.refresh(fp)
        return FacultyProfileResponse.model_validate(fp)

    @classmethod
    def update_tpo_profile(
        cls, db: Session, user_id: int, payload: TPOProfileUpdate
    ) -> TPOProfileResponse:
        tp = cls.get_or_create_tpo_profile(db, user_id)
        for key, value in payload.model_dump(exclude_unset=True).items():
            if hasattr(tp, key) and value is not None:
                setattr(tp, key, value)

        db.commit()
        db.refresh(tp)
        return TPOProfileResponse.model_validate(tp)
