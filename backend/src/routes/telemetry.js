import { Router } from 'express';
import { asyncHandler } from '../utils/helpers.js';
import {
	ingestTelemetry,
	getTelemetryQuery,
	getStudentTelemetry,
} from '../controllers/telemetryController.js';

const router = Router();

router.post('/ingest', asyncHandler(ingestTelemetry));
router.get('/query', asyncHandler(getTelemetryQuery));
router.get('/student/:rollNo', asyncHandler(getStudentTelemetry));

export default router;
