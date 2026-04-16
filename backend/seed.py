import asyncio
import uuid
from app.database import engine, Base, AsyncSessionLocal
from app.models.user import User
from app.core.security import hash_password

async def init_db():
    print("Initializing Database...")
    async with engine.begin() as conn:
        # For SQLite, we want to drop if exists or just create
        # We'll just create.
        await conn.run_sync(Base.metadata.create_all)
    print("Tables created.")

    async with AsyncSessionLocal() as db:
        # Check if doctor1 exists
        from sqlalchemy import select
        res = await db.execute(select(User).where(User.email == "doctor1@example.com"))
        user = res.scalars().first()
        
        if not user:
            print("Creating default user: doctor1@example.com / pass123")
            new_user = User(
                id=uuid.uuid4(),
                email="doctor1@example.com",
                password_hash=hash_password("pass123"),
                full_name="Dr. Demo User",
                role="doctor"
            )
            db.add(new_user)
            await db.commit()
            print("User created.")
        else:
            print("Default user already exists.")
            new_user = user

        # Check if any patients exist
        from app.models.patient import Patient
        res = await db.execute(select(Patient).where(Patient.primary_doctor_id == new_user.id))
        patient = res.scalars().first()

        if not patient:
            print(f"Creating test patient for doctor {new_user.email}...")
            new_patient = Patient(
                id=uuid.uuid4(),
                patient_code="PT-001",
                full_name="Alex Johnson",
                gender="Non-binary",
                diagnosis_notes="Standard test case for psychiatric biomarker detection.",
                primary_doctor_id=new_user.id
            )
            db.add(new_patient)
            await db.commit()
            print("Test patient created.")
        else:
            print("Test patient already exists.")

if __name__ == "__main__":
    asyncio.run(init_db())
