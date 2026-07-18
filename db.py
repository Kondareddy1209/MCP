from sqlmodel import SQLModel, create_engine, Session, text

# ✅ CLEAN DB RESET — single source of truth
# Only itsyou_clean.db must be used everywhere in this project
DATABASE_URL = "sqlite:///./itsyou_clean.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30},
    echo=False
)

def init_db():
    SQLModel.metadata.create_all(engine)
    with engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL;"))
        conn.execute(text("PRAGMA synchronous=NORMAL;"))
        conn.execute(text("PRAGMA cache_size=-2000;"))  # ~2MB cache size
        conn.execute(text("PRAGMA temp_store=MEMORY;"))
        conn.commit()

def get_session():
    with Session(engine) as session:
        yield session
