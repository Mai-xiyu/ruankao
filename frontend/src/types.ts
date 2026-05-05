export interface Exam {
  id: number;
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
  is_verified: boolean;
  created_at: string;
  updated_at: string;
}

export interface TagItem {
  id: number;
  name: string;
  category?: string | null;
  created_at: string;
}

export interface OverviewStats {
  exams: number;
  questions: number;
  tags: number;
  favorites: number;
  wrong_records: number;
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

