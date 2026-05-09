import axios from "axios";

import type {
  AuthState,
  CleanupReport,
  FavoriteItem,
  GroupedSubjects,
  ImportBatch,
  ImportPayload,
  ImportResult,
  LevelStat,
  OverviewStats,
  PracticeResult,
  Question,
  Subject,
  TagItem,
  WrongRecord,
  WrongTagStat,
  YearStat
} from "./types";

export const api = axios.create({
  baseURL: "/api",
  timeout: 120000,
  withCredentials: true
});

export interface QuestionFilters {
  subject_id?: number;
  year?: number;
  season?: string;
  paper_type?: string;
  level?: string;
  exam_name?: string;
  knowledge_area?: string;
  tag?: string;
  difficulty?: number;
  keyword?: string;
  question_type?: string;
  is_verified?: boolean;
  has_answer?: boolean;
  quality_status?: string;
  source_provider?: string;
  limit?: number;
  offset?: number;
}

function compactParams<T extends object>(params: T): Partial<T> {
  return Object.fromEntries(
    Object.entries(params).filter(([, value]) => value !== "" && value !== null && value !== undefined)
  ) as Partial<T>;
}

export async function fetchOverview() {
  return (await api.get<OverviewStats>("/stats/overview")).data;
}

export async function fetchQuestionsByYear() {
  return (await api.get<YearStat[]>("/stats/questions-by-year")).data;
}

export async function fetchWrongByTag() {
  return (await api.get<WrongTagStat[]>("/stats/wrong-by-tag")).data;
}

export async function fetchStatsByLevel() {
  return (await api.get<LevelStat[]>("/stats/by-level")).data;
}

export async function fetchSubjects(level?: string) {
  return (await api.get<Subject[]>("/subjects", { params: compactParams({ level }) })).data;
}

export async function fetchGroupedSubjects() {
  return (await api.get<GroupedSubjects>("/subjects/grouped")).data;
}

export async function fetchTags() {
  return (await api.get<TagItem[]>("/tags")).data;
}

export async function fetchQuestions(filters: QuestionFilters = {}) {
  return (await api.get<Question[]>("/questions", { params: compactParams(filters) })).data;
}

export async function fetchRandomQuestions(limit = 10, subject_id?: number, level?: string) {
  return (await api.get<Question[]>("/practice/random", { params: compactParams({ limit, subject_id, level }) })).data;
}

export async function fetchQuestionsByTag(tag: string, limit = 20) {
  return (await api.get<Question[]>(`/practice/by-tag/${encodeURIComponent(tag)}`, { params: { limit } })).data;
}

export async function fetchWrongPractice(limit = 20) {
  return (await api.get<Question[]>("/practice/wrong", { params: { limit } })).data;
}

export async function submitAnswer(question_id: number, user_answer: string, duration_seconds: number) {
  return (await api.post<PracticeResult>("/practice/submit", { question_id, user_answer, duration_seconds })).data;
}

export async function authMe() {
  return (await api.get<AuthState>("/auth/me")).data;
}

export async function register(payload: { username: string; password: string; email?: string; display_name?: string }) {
  return (await api.post<AuthState>("/auth/register", payload)).data;
}

export async function login(payload: { username: string; password: string }) {
  return (await api.post<AuthState>("/auth/login", payload)).data;
}

export async function logout() {
  return (await api.post<{ ok: boolean }>("/auth/logout")).data;
}

export async function guestSession() {
  return (await api.post<AuthState>("/auth/guest-session")).data;
}

export async function importJson(payload: ImportPayload, updateExisting: boolean) {
  return (
    await api.post<ImportResult>("/import/json", payload, { params: { update_existing: updateExisting } })
  ).data;
}

export async function importAiJson(payload: ImportPayload, updateExisting: boolean) {
  return (
    await api.post<ImportResult>("/import/ai-json", payload, { params: { update_existing: updateExisting } })
  ).data;
}

export async function importAiGenerated(payload: ImportPayload, updateExisting: boolean) {
  return (
    await api.post<ImportResult>("/import/ai-generated", payload, { params: { update_existing: updateExisting } })
  ).data;
}

export async function previewSource(payload: { text?: string; url?: string }) {
  return (await api.post("/sources/preview", payload)).data as {
    content_excerpt: string;
    content_length: number;
    truncated: boolean;
    needs_confirmation: boolean;
    compliance_notice: string;
  };
}

export async function confirmSourceImport(payload: {
  text?: string;
  url?: string;
  legal_confirmation: boolean;
  exam?: ImportPayload["exam"];
  use_reasoning_model?: boolean;
}) {
  return (await api.post<ImportPayload>("/sources/confirm-import", payload)).data;
}

export async function extractQuestions(payload: {
  text: string;
  exam?: ImportPayload["exam"];
  use_reasoning_model?: boolean;
}) {
  return (await api.post<ImportPayload>("/ai/extract-questions", payload)).data;
}

export async function generateQuestions(payload: {
  exam: ImportPayload["exam"];
  question_count: number;
  question_types: string[];
  difficulty: number;
  knowledge_areas: string[];
  tags: string[];
  source_text?: string;
  extra_requirements?: string;
  use_reasoning_model?: boolean;
}) {
  return (await api.post<ImportPayload>("/ai/generate-questions", payload)).data;
}

export async function improveAnalysis(payload: {
  stem: string;
  answer?: string | null;
  analysis?: string | null;
  use_reasoning_model?: boolean;
}) {
  return (await api.post<{ analysis: string }>("/ai/improve-analysis", payload)).data;
}

export async function suggestTags(payload: {
  stem: string;
  answer?: string | null;
  analysis?: string | null;
  use_reasoning_model?: boolean;
}) {
  return (
    await api.post<{ knowledge_area?: string; difficulty: number; tags: string[] }>("/ai/suggest-tags", payload)
  ).data;
}

export async function cleanupPreview() {
  return (await api.post<CleanupReport>("/admin/cleanup/preview")).data;
}

export async function cleanupApply(mode: "isolate" | "delete") {
  return (await api.post<CleanupReport>("/admin/cleanup/apply", { confirm: true, mode, backup: true })).data;
}

export async function fetchImportBatches() {
  return (await api.get<ImportBatch[]>("/admin/import-batches")).data;
}

export async function addFavorite(questionId: number) {
  return (await api.post<FavoriteItem>(`/favorites/${questionId}`)).data;
}

export async function removeFavorite(questionId: number) {
  await api.delete(`/favorites/${questionId}`);
}

export async function fetchFavorites() {
  return (await api.get<FavoriteItem[]>("/favorites")).data;
}

export async function fetchWrongRecords() {
  return (await api.get<WrongRecord[]>("/records/wrong")).data;
}

export async function markReviewed(recordId: number) {
  return (await api.post<{ record_id: number; reviewed: boolean }>(`/records/${recordId}/reviewed`)).data;
}
