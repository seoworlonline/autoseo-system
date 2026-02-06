"""
AutoSEO - FastAPI Backend
AI-powered website generation and deployment platform
"""

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import os
import asyncio
from functools import lru_cache

# Database
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, select, func
from contextlib import asynccontextmanager

# OpenAI
from openai import AsyncOpenAI

# Settings
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    openai_api_key: str = ""
    database_url: str = "postgresql+asyncpg://autoseo:autoseo_secret@postgres/autoseo_db"
    redis_url: str = "redis://redis:6379"
    secret_key: str = "your-secret-key"
    environment: str = "development"
    
    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()

# Database setup
Base = declarative_base()
engine = None
async_session_maker = None

class Site(Base):
    __tablename__ = "sites"
    
    id = Column(Integer, primary_key=True, index=True)
    domain = Column(String, index=True)
    title = Column(String)
    keyword = Column(String, index=True)
    content = Column(Text)
    meta_description = Column(String)
    meta_tags = Column(JSON)
    cloud_provider = Column(String)
    cloud_url = Column(String)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    seo_score = Column(Integer, default=0)
    analytics = Column(JSON, default=dict)

@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine, async_session_maker
    settings = get_settings()
    
    engine = create_async_engine(
        settings.database_url,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        echo=False
    )
    async_session_maker = async_sessionmaker(engine, expire_on_commit=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield
    
    await engine.dispose()

app = FastAPI(
    title="AutoSEO API",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class SiteGenerateRequest(BaseModel):
    keyword: str = Field(..., min_length=2, max_length=100)
    title: Optional[str] = None
    language: str = "en"
    tone: str = "professional"
    word_count: int = 1500
    include_faq: bool = True
    cloud_provider: str = "aws"
    custom_domain: Optional[str] = None

class SiteResponse(BaseModel):
    id: int
    domain: str
    title: str
    keyword: str
    status: str
    cloud_url: Optional[str]
    seo_score: int
    created_at: datetime

async def get_db():
    async with async_session_maker() as session:
        yield session

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@app.post("/api/sites/generate", response_model=SiteResponse)
async def generate_site(
    request: SiteGenerateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Generate a new AI website"""
    domain = request.custom_domain or f"{request.keyword.replace(' ', '-')}-{datetime.now().strftime('%H%M%S')}.auto-seo.app"
    
    site = Site(
        domain=domain,
        title=request.title or request.keyword,
        keyword=request.keyword,
        cloud_provider=request.cloud_provider,
        status="pending"
    )
    
    db.add(site)
    await db.commit()
    await db.refresh(site)
    
    # Start background generation
    background_tasks.add_task(process_site_generation, site.id, request)
    
    return site

async def process_site_generation(site_id: int, request: SiteGenerateRequest):
    """Background task to generate and deploy site"""
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    
    async with async_session_maker() as db:
        result = await db.execute(select(Site).where(Site.id == site_id))
        site = result.scalar_one()
        site.status = "generating"
        await db.commit()
        
        try:
            # Generate content with OpenAI
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{
                    "role": "system",
                    "content": f"Create SEO content for: {request.keyword}. Return JSON with title, meta_description, content."
                }, {
                    "role": "user",
                    "content": f"Write a comprehensive article about {request.keyword}. Include headings, FAQs, and optimize for SEO."
                }],
                temperature=0.7
            )
            
            content_text = response.choices[0].message.content
            
            # Generate simple HTML
            html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>{request.keyword.title()}</title>
    <meta name="description" content="Comprehensive guide about {request.keyword}">
    <style>
        body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; line-height: 1.6; }}
        h1 {{ color: #333; }}
        .content {{ margin-top: 20px; }}
    </style>
</head>
<body>
    <h1>{request.keyword.title()}</h1>
    <div class="content">
        {content_text.replace(chr(10), '<br>')}
    </div>
    <footer style="margin-top: 40px; color: #666; font-size: 0.9em;">
        <p>&copy; {datetime.now().year} - Generated by AutoSEO</p>
    </footer>
</body>
</html>
            """
            
            # For demo: save to a simple file location (in production, deploy to cloud)
            site.content = html
            site.cloud_url = f"https://demo.autoseo.app/site/{site_id}"
            site.status = "deployed"
            site.seo_score = 85  # Simplified scoring
            site.analytics = {
                "word_count": len(content_text.split()),
                "deployment_time": datetime.utcnow().isoformat()
            }
            
            await db.commit()
            
        except Exception as e:
            site.status = "failed"
            site.analytics = {"error": str(e)}
            await db.commit()

@app.get("/api/sites", response_model=List[SiteResponse])
async def list_sites(db: AsyncSession = Depends(get_db)):
    """List all generated sites"""
    result = await db.execute(select(Site).order_by(Site.created_at.desc()))
    sites = result.scalars().all()
    return sites

@app.get("/api/sites/{site_id}")
async def get_site(site_id: int, db: AsyncSession = Depends(get_db)):
    """Get site details"""
    result = await db.execute(select(Site).where(Site.id == site_id))
    site = result.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return site

@app.get("/api/analytics/dashboard")
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    """Get dashboard statistics"""
    total = await db.execute(select(func.count(Site.id)))
    deployed = await db.execute(select(func.count(Site.id)).where(Site.status == "deployed"))
    avg_score = await db.execute(select(func.avg(Site.seo_score)).where(Site.status == "deployed"))
    
    recent = await db.execute(
        select(Site).order_by(Site.created_at.desc()).limit(5)
    )
    
    return {
        "overview": {
            "total_sites": total.scalar(),
            "deployed_sites": deployed.scalar(),
            "average_seo_score": round(avg_score.scalar() or 0, 1)
        },
        "recent_sites": [
            {
                "id": s.id,
                "domain": s.domain,
                "status": s.status,
                "created_at": s.created_at
            } for s in recent.scalars()
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)