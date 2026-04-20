import { Router } from 'express';
import {
  ingestTelemetry,
  queryTelemetry,
  getStudentDetail,
} from '../controllers/telemetryController.js';
import { asyncHandler } from '../utils/helpers.js';

const router = Router();

router.post('/ingest', asyncHandler(ingestTelemetry));
router.get('/query', asyncHandler(queryTelemetry));
router.get('/student/:rollNo', asyncHandler(getStudentDetail));

export default router;
