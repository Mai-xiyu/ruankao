export type LevelName = "高级" | "中级" | "初级";

export interface Subject {
  id: number;
  level: LevelName | string;
  name: string;
  code: string;
  enabled: boolean;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export type GroupedSubjects = Record<LevelName, Subject[]>;

export interface User {
  id: number;
  username: string;
  email?: string | null;
  display_name?: string | null;
  role: string;
  is_active: boolean;
  created_at: string;
}

export interface AuthState {
  authenticated: boolean;
  guest_session_id?: string | null;
  user?: User | null;
  expires_at?: string;
}

export interface Exam {
  id: number;
  subject_id?: number | null;
  subject?: Subject | null;
  exam_name: string;
  level: string;
  year: number;
  season: string;
  paper_type: string;
  source_name?: string | null;
  source_url?: string | null;
  is_memory_version: boolean;
  remark?: string | null;
  created_at: string;
  updated_at: string;
}

export interface Question {
  id: number;
  exam_id: number;
  question_no: string;
  question_type: string;
  stem: string;
  options_json?: Record<string, string> | null;
  answer?: string | null;
  analysis?: string | null;
  difficulty: number;
  knowledge_area?: string | null;
  tags_json: string[];
  source_hash: string;
  source_provider?: string | null;
  source_question_id?: string | null;
  source_url?: string | null;
  quality_status: string;
  requires_image: boolean;
  is_verified: boolean;
  images: QuestionImage[];
  created_at: string;
  updated_at: string;
}

export interface QuestionImage {
  id: number;
  image_path: string;
  image_type: string;
  caption?: string | null;
  created_at: string;
}

export interface TagItem {
  id: number;
  name: string;
  category?: string | null;
  created_at: string;
}

export interface OverviewStats {
  subjects: number;
  exams: number;
  questions: number;
  usable_questions: number;
  tags: number;
  users: number;
  favorites: number;
  wrong_records: number;
}

export interface LevelStat {
  level: string;
  subject_id: number;
  subject_name: string;
  question_count: number;
}

export interface YearStat {
  year: number;
  question_count: number;
}

export interface WrongTagStat {
  tag: string;
  wrong_count: number;
}

export interface ImportPayload {
  exam: {
    subject_id?: number | null;
    exam_name: string;
    level: string;
    year: number;
    season: string;
    paper_type: string;
    source_name?: string;
    source_url?: string;
    is_memory_version?: boolean;
    remark?: string;
  };
  questions: Array<{
    question_no: string;
    question_type: string;
    stem: string;
    options?: Record<string, string> | null;
    answer?: string | null;
    analysis?: string | null;
    difficulty: number;
    knowledge_area?: string | null;
    tags: string[];
    source_provider?: string | null;
    source_question_id?: string | null;
    source_url?: string | null;
    quality_status?: string;
    requires_image?: boolean;
    is_verified?: boolean;
  }>;
}

export interface ImportResult {
  batch_id: number;
  total_count: number;
  success_count: number;
  failed_count: number;
  skipped_count: number;
  updated_count: number;
  errors: string[];
}

export interface ImportBatch {
  id: number;
  source_file: string;
  source_type: string;
  total_count: number;
  success_count: number;
  failed_count: number;
  error_log?: string | null;
  created_at: string;
}

export interface CleanupReport {
  total_questions: number;
  candidate_count: number;
  by_reason: Record<string, number>;
  backup_file?: string | null;
  applied: boolean;
  mode?: string | null;
}

export interface PracticeResult {
  record_id: number;
  question_id: number;
  is_correct: boolean;
  correct_answer?: string | null;
  analysis?: string | null;
  knowledge_area?: string | null;
  tags: string[];
}

export interface FavoriteItem {
  id: number;
  user_id?: number | null;
  guest_session_id?: string | null;
  question_id: number;
  created_at: string;
  question?: Question | null;
}

export interface WrongRecord {
  record_id: number;
  question_id: number;
  user_answer?: string | null;
  reviewed: boolean;
  answered_at: string;
  question?: Question | null;
}
