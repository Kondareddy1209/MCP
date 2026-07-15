from sqlmodel import SQLModel, create_engine, Session

# ✅ CLEAN DB RESET — single source of truth
# Only itsyou_clean.db must be used everywhere in this project
DATABASE_URL = "sqlite:///./itsyou_clean.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False
)

def init_db():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
