import axios from "axios";

import type {
  FavoriteItem,
  ImportPayload,
  ImportResult,
  OverviewStats,
  PracticeResult,
  Question,
  TagItem,
  WrongRecord,
  WrongTagStat,
  YearStat
} from "./types";

export const api = axios.create({
  baseURL: "/api",
  timeout: 120000
});

export interface QuestionFilters {
  year?: number;
  season?: string;
  paper_type?: string;
  knowledge_area?: string;
  tag?: string;
  difficulty?: number;
  keyword?: string;
  question_type?: string;
  is_verified?: boolean;
  has_answer?: boolean;
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

export async function fetchTags() {
  return (await api.get<TagItem[]>("/tags")).data;
}

export async function fetchQuestions(filters: QuestionFilters = {}) {
  return (await api.get<Question[]>("/questions", { params: compactParams(filters) })).data;
}

export async function fetchRandomQuestions(limit = 10) {
  return (await api.get<Question[]>("/practice/random", { params: { limit } })).data;
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
