# Render Resume OOM Diagnosis

## Confirmed Render Evidence

The Render Web Service reports:

```text
[MEMORY] before resume processing: rss=674.6 MB
```

The service memory limit is 512 MB. The process is killed immediately afterward.
Therefore, the service exceeds its memory limit before synchronous resume processing,
before RAG retrieval, and before the BGE embedding model is used.

## Resume Processing Findings

The resume path is:

```text
POST /api/v1/interview/resume/upload-async
  -> async_resume_router
  -> SyncResumeProcessor (DEPLOYMENT_MODE=demo)
  -> ResumeProcessor
  -> parse_resume
  -> Groq extraction
  -> RAG retriever
  -> BGE embedding + FAISS search
  -> Groq question pool generation
  -> database save
```

The local BGE model remains a significant resume-time risk:

- `sentence-transformers` and `torch` are dependencies.
- `BAAI/bge-base-en-v1.5` is constructed lazily in `embedding_service.py`.
- It is loaded only when the first RAG query calls `embed_text()`.
- It is not loaded twice; the existing module-level singleton is reused.
- The FAISS index is approximately 200 KB.
- The metadata file is approximately 31 KB with 65 entries.
- Retrieval is limited to `k=8` and returns at most five documents.
- Resume vector indexing is disabled.

Because the Render baseline is already 674.6 MB before resume processing, BGE
cannot explain the initial baseline by itself. Its memory impact must be measured
separately after the startup issue is understood.

## Startup Import Chain

The application imports routers eagerly:

```text
app.main
  -> app.api.v1.router
  -> advanced_proctoring_router
  -> phone_detection_service
```

`phone_detection_service.py` imports these libraries at module scope:

- `cv2`
- `ultralytics.YOLO`

The module defines `_MODEL = None`, and YOLO weights are constructed only inside
`get_yolo_model()`. Importing the module does not call `YOLO(...)`.

The application lifespan calls `get_yolo_model()` only when
`SKIP_HEAVY_STARTUP` is false. When heavy warmups are skipped, YOLO weights and
inference should not run during startup. However, importing OpenCV and Ultralytics
can still load native libraries and PyTorch-related runtime components, increasing
baseline RSS.

The startup message:

```text
[Startup] Heavy model warmups skipped for fast local auth/login startup
```

means that explicit embedding, FAISS, and YOLO warmup calls are skipped. It does
not prevent module-scope imports performed while routers are imported.

## Heavy Library Inventory

| Component | Import/construction location | Startup status |
|---|---|---|
| OpenCV (`cv2`) | `app/services/phone_detection_service.py` | Imported during router import |
| Ultralytics | `app/services/phone_detection_service.py` | Imported during router import |
| YOLO weights | `get_yolo_model()` in `phone_detection_service.py` | Not constructed when heavy warmup is skipped |
| PyTorch | Transitive dependency of ML libraries | May be loaded by imports |
| SentenceTransformer | `app/services/embedding_service.py` | Lazy; first RAG request unless warmup enabled |
| BGE weights | `get_embedding_model()` | Lazy; not startup-loaded when warmup is skipped |
| FAISS | `app/services/retriever_service.py` | Lazy; loaded by `load_kb()` |
| Local Whisper | Not present | Not used |
| Groq Whisper | `GroqService.transcribe_audio()` | Remote API only |
| TensorFlow | No application import found | Not identified |
| librosa | No application import found | Not identified |

## Startup Memory Diagnostics

The following RSS checkpoints were added using the standard library and report MB:

```text
[MEMORY] startup: early
[MEMORY] startup: after authentication/session modules
[MEMORY] startup: before CV/YOLO imports
[MEMORY] startup: after OpenCV import
[MEMORY] startup: after Ultralytics import
[MEMORY] startup: after coding/proctoring modules
[MEMORY] startup: after interview modules
[MEMORY] startup: after app imports
[MEMORY] startup: after router initialization
[MEMORY] startup: after CV/YOLO initialization
[MEMORY] startup: after audio initialization
[MEMORY] startup: after RAG initialization
[MEMORY] startup: after embedding initialization
[MEMORY] startup: application ready
```

Resume-stage checkpoints already present are:

```text
[MEMORY] before resume processing
[MEMORY] after PDF extraction
[MEMORY] after skill/project extraction
[MEMORY] before RAG
[MEMORY] after RAG
[MEMORY] before Groq
[MEMORY] after Groq
[MEMORY] before DB save
[MEMORY] after DB save
[MEMORY] before embedding model load
[MEMORY] after embedding model load
```

The embedding checkpoints are inside the existing `_model is None` branch, so
diagnostics do not force model reinitialization or duplicate loading.

## Local Measurements

The local environment reached these checkpoints before failing on an unrelated
binary compatibility issue:

```text
startup: early                         14.7 MB
startup: after authentication/session modules   75.9 MB
startup: before CV/YOLO imports        80.0 MB
```

Local startup then failed because the installed OpenCV binary was built against
NumPy 1.x while the environment contains NumPy 2.x:

```text
AttributeError: _ARRAY_API not found
ImportError: numpy.core.multiarray failed to import
```

This prevented local measurement after OpenCV and Ultralytics imports.

## Tests Run

Passed:

```text
21 passed
```

- `tests/test_demo_resume_processing.py`
- `tests/test_deployment_mode.py`

Passed:

```text
3 passed
```

- `tests/test_proctoring.py`
- `tests/test_proctoring_logger.py`

Computer-vision tests could not collect locally because of the NumPy/OpenCV
binary mismatch.

## Current Conclusion

The confirmed baseline problem is startup memory, not resume RAG memory:

1. Render is already at 674.6 MB before resume processing.
2. BGE is lazy and should not be loaded before the first RAG request when heavy
   warmups are skipped.
3. FAISS is small and lazy.
4. YOLO weights are not constructed during skipped warmup.
5. OpenCV and Ultralytics are imported eagerly through the advanced-proctoring
   router.
6. The OpenCV/Ultralytics/PyTorch import chain is the leading startup-memory
   suspect.

The next Render deployment should compare:

```text
startup: before CV/YOLO imports
startup: after OpenCV import
startup: after Ultralytics import
startup: application ready
```

The largest RSS delta identifies the startup component responsible for the
baseline increase.

## Not Implemented

The following changes were intentionally not made:

- No lightweight RAG retrieval path
- No lazy-import optimization
- No CORS changes
- No PostgreSQL, Redis, Celery, GCS, or Groq changes
- No deployment-mode changes
- No database migration/schema changes
- No Render instance upgrade
- No commit or push
