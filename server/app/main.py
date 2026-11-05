
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from app.database.session import engine

app = FastAPI(
    title="Camera Intelligence API",
    description="AI-powered CCTV monitoring and analytics platform",
    version="1.0.0"
)

# Frontend development access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "message": "Camera Intelligence API is running",
        "status": "online"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "application": "Camera Intelligence",
        "version": "1.0.0"
    }

@app.get("/health/database")
def database_health():

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {
            "status": "connected",
            "database": "PostgreSQL",
            "message": "Database connection successful"
        }

    except SQLAlchemyError:
        return {
            "status": "disconnected",
            "database": "PostgreSQL",
            "message": "Database connection failed"
        }



@app.post("/test/database-write")
def database_write():

    with engine.begin() as connection:
        connection.execute(
            text("""
                CREATE TABLE IF NOT EXISTS connection_test (
                    id SERIAL PRIMARY KEY,
                    message VARCHAR(255)
                )
            """)
        )

        connection.execute(
            text("""
                INSERT INTO connection_test (message)
                VALUES (:message)
            """),
            {"message": "Camera Intelligence database connected"}
        )

    return {"status": "success", "message": "Data inserted successfully"}


@app.get("/test/database-read")
def database_read():

    with engine.connect() as connection:
        result = connection.execute(
            text("SELECT * FROM connection_test ORDER BY id DESC LIMIT 5")
        )

        return [
            {"id": row.id, "message": row.message}
            for row in result
        ]