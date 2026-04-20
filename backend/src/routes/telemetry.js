import { Router } from 'express';
import { asyncHandler } from '../utils/helpers.js';
import { ingestTelemetry } from '../controllers/telemetryController.js';

const router = Router();

router.post('/ingest', asyncHandler(ingestTelemetry));

export default router;
