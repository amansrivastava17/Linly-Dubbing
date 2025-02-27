from fastapi import FastAPI, BackgroundTasks, HTTPException, UploadFile, File, Form
from celery import Celery
from celery.result import AsyncResult
from pydantic import BaseModel
from typing import Optional, List
from fastapi.responses import FileResponse
import os
from tools.do_everything import do_everything

app = FastAPI(
    title="LUMI Translation API",
    description="A service for translating video audio between multiple languages with speaker diarization support.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure Celery
celery = Celery(
    'tasks',
    broker=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('REDIS_URL', 'redis://localhost:6379/0')
)

# Set multiprocessing start method to 'spawn' for CUDA compatibility
celery.conf.update(
    worker_pool='solo',  # Use solo pool to avoid multiprocessing issues
    task_serializer='pickle',  # Required for complex objects
    accept_content=['pickle', 'json'],  # Accept pickle serialization
    worker_prefetch_multiplier=1,  # Process one task at a time
    task_track_started=True,  # Track when tasks are started
    task_time_limit=3600,  # Set 1 hour timeout for tasks
    task_soft_time_limit=3300,  # Set soft timeout 55 minutes
    worker_max_tasks_per_child=50,  # Restart worker after 50 tasks
    worker_concurrency=1  # One worker per GPU
)

class VideoRequest(BaseModel):
    root_folder: str = "output"
    url: str
    num_videos: int = 5
    resolution: str = "1080p"
    demucs_model: str = "htdemucs_ft"
    device: str = "cuda"
    shifts: int = 5
    asr_method: str = "WhisperX"
    whisper_model: str = "large-v2"
    batch_size: int = 32
    diarization: bool = False
    whisper_min_speakers: int = 1
    whisper_max_speakers: int = 5
    translation_method: str = "OpenAI"
    translation_target_language: str = "English"
    tts_method: str = "xtts"
    tts_target_language: str = "English"
    voice: str = "zh-CN-XiaoxiaoNeural"
    subtitles: bool = True
    speed_up: float = 1.0
    fps: int = 30
    background_music: Optional[str] = None
    bgm_volume: float = 0.5
    video_volume: float = 1.0
    target_resolution: str = "1080p"
    max_workers: int = 3
    max_retries: int = 5

class TranslationResponse(BaseModel):
    """Response model for translation tasks"""
    task_id: str
    status: str
    download_url: str = None
    failure_reason: str = None

    class Config:
        schema_extra = {
            "example": {
                "task_id": "task_12345",
                "status": "processing",
                "download_url": "/download/translated.mp4",
                "failure_reason": None
            }
        }

@celery.task(name='process_video', bind=True)
def process_video(self, params: dict):
    try:
        status, output_video = do_everything(**params)
        if output_video:
            return {'status': status, 'output_path': output_video}
        return {'status': status, 'error': 'No output video generated'}
    except Exception as e:
        self.update_state(state='FAILURE', meta={'exc_message': str(e)})
        raise


@app.post("/v1/translate", 
    response_model=TranslationResponse,
    summary="Submit a video translation task",
    description="Upload a video file and specify translation languages. Returns a task ID for tracking progress.",
    response_description="Translation task details with task ID and initial status",
    tags=["translation"])
async def translate_video(
    video: UploadFile = File(..., description="The video file to translate"),
    source_lang: str = Form("zh", description="Source language code (e.g., 'zh' for Chinese)"),
    target_lang: str = Form("en", description="Target language code (e.g., 'en' for English)")
):
    # Save uploaded file
    temp_dir = "/data/input"
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, video.filename)
    
    with open(temp_path, "wb") as buffer:
        content = await video.read()
        buffer.write(content)

    params = {
        "root_folder" = "/data/input", 
        "url": temp_path,
        "translation_method": "OpenAI", 
        # translation_method = 'Google Translate', translation_target_language = '简体中文',
        )
    
    # Submit translation task
    task = process_video.delay(params)

    return TranslationResponse(
        task_id=task.id,
        status="processing"
    )

@app.get("/status/{task_id}", 
    response_model=TranslationResponse,
    summary="Check translation task status",
    description="Get the current status of a translation task using its task ID.",
    response_description="Current status of the translation task",
    tags=["translation"])
async def get_task_status(task_id: str):
    task_result = AsyncResult(task_id, app=celery)

    if task_result.failed():
        status = "failed"
        failure_reason = None
        if task_result.info:
            failure_reason = task_result.info.get('exc_message', 'Unknown error')
        return TranslationResponse(
            task_id=task_id,
            status=status,
            failure_reason=failure_reason
        )
    elif task_result.successful():
        status = "completed"
        # Get the output path from the task result
        result = task_result.result
        if isinstance(result, dict) and 'output_path' in result:
            download_url = f"/download/{os.path.basename(result['output_path'])}"
            return TranslationResponse(task_id=task_id, status=status, download_url=download_url)
    elif task_result.state == 'PENDING':
        status = "pending"
    else:
        status = task_result.state.lower()

    return TranslationResponse(task_id=task_id, status=status)

@app.get("/download/{filename}")
async def download_translated_video(filename: str):
    file_path = os.path.join("/data/output", filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path=file_path, filename=filename, media_type="video/mp4")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)