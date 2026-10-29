import { z } from 'zod';

export const UserSchema = z.object({
  id: z.string(),
  email: z.string().email(),
  full_name: z.string().nullable().optional(),
  avatar_url: z.string().nullable().optional(),
  class_level: z.number().nullable().optional(),
  board: z.string()
});

export const DocumentSchema = z.object({
  id: z.string(),
  title: z.string(),
  subject: z.string().nullable().optional(),
  class_level: z.number().nullable().optional(),
  original_filename: z.string().optional(),
  size_bytes: z.number().optional(),
  page_count: z.number().nullable().optional(),
  chunk_count: z.number().optional(),
  status: z.string(),
  created_at: z.string().nullable().optional()
});

export const DocumentStatusSchema = z.object({
  document_id: z.string(),
  status: z.string(),
  page_count: z.number().nullable().optional(),
  ocr_page_count: z.number().optional(),
  job: z.object({
    status: z.string().nullable().optional(),
    stage: z.string().nullable().optional(),
    progress_pct: z.number().optional(),
    last_completed_page: z.number().optional(),
    error: z.string().nullable().optional()
  }).nullable().optional()
});

export const StudyNoteSchema = z.object({
  id: z.string(),
  document_id: z.string(),
  title: z.string(),
  content_md: z.string(),
  math_invalid: z.boolean().optional(),
  created_at: z.string().optional()
});

export const FlashcardSchema = z.object({
  id: z.string(),
  document_id: z.string(),
  front: z.string(),
  back: z.string(),
  tags: z.array(z.string()).optional(),
  ease_factor: z.number().optional(),
  interval_days: z.number().optional(),
  repetitions: z.number().optional(),
  due_at: z.string().optional()
});

export const CheatSheetSchema = z.object({
  id: z.string(),
  title: z.string(),
  content_md: z.string(),
  formula_count: z.number(),
  math_invalid: z.boolean().optional(),
  created_at: z.string().optional()
});

export const QuestionSchema = z.object({
  id: z.string(),
  q_no: z.number(),
  section: z.string(),
  q_type: z.string(),
  marks: z.number(),
  question_md: z.string(),
  options: z.array(z.string()).nullable().optional(),
  difficulty: z.string().nullable().optional()
});

export const QuizSchema = z.object({
  id: z.string(),
  subject: z.string(),
  class_level: z.number(),
  mode: z.string(),
  total_marks: z.number(),
  questions: z.array(QuestionSchema)
});

export const StepEvaluationSchema = z.object({
  expected_step: z.string(),
  awarded: z.number(),
  max: z.number(),
  matched_evidence: z.string().nullable().optional(),
  missing_or_wrong: z.string().nullable().optional()
});

export const EvaluationResultSchema = z.object({
  evaluation_id: z.string().optional(),
  awarded_marks: z.number(),
  max_marks: z.number(),
  percentage: z.number(),
  steps: z.array(StepEvaluationSchema),
  feedback_md: z.string(),
  model_answer_md: z.string(),
  how_to_gain_marks: z.array(z.string()).optional(),
  mistake_category: z.string().nullable().optional()
});

export const RoadmapTaskSchema = z.object({
  id: z.string(),
  topic_id: z.string(),
  topic_title: z.string(),
  task_type: z.string(),
  est_minutes: z.number(),
  priority_score: z.number(),
  completed: z.boolean()
});

export const RoadmapResponseSchema = z.object({
  date: z.string(),
  tasks: z.array(RoadmapTaskSchema)
});

export const CoverageReportSchema = z.object({
  report_id: z.string().optional(),
  score: z.number(),
  total_topics: z.number(),
  covered_count: z.number().optional(),
  missing_count: z.number().optional(),
  missing_topics: z.array(z.any()).optional()
});
