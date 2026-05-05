<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { Bot, ClipboardCheck, FileJson, SearchCheck, Upload } from "lucide-vue-next";

import { confirmSourceImport, extractQuestions, importAiJson, importJson, previewSource } from "../api";
import type { ImportPayload, ImportResult } from "../types";

const jsonText = ref("");
const sourceText = ref("");
const sourceUrl = ref("");
const aiText = ref("");
const updateExisting = ref(false);
const legalConfirmation = ref(true);
const useReasoning = ref(false);
const loading = ref(false);
const draft = ref<ImportPayload | null>(null);
const result = ref<ImportResult | null>(null);
const preview = ref<null | {
  content_excerpt: string;
  content_length: number;
  truncated: boolean;
  compliance_notice: string;
}>(null);

const examForm = reactive({
  exam_name: "网络工程师",
  level: "中级",
  year: new Date().getFullYear(),
  season: "上半年",
  paper_type: "上午综合知识",
  source_name: "自整理",
  source_url: "",
  is_memory_version: false,
  remark: ""
});

const draftText = computed(() => (draft.value ? JSON.stringify(draft.value, null, 2) : ""));

function parseJsonInput(): ImportPayload | null {
  try {
    return JSON.parse(jsonText.value) as ImportPayload;
  } catch (error) {
    ElMessage.error("JSON 格式不正确");
    return null;
  }
}

async function runJsonImport() {
  const payload = parseJsonInput();
  if (!payload) return;
  loading.value = true;
  try {
    result.value = await importJson(payload, updateExisting.value);
    ElMessage.success("导入完成");
  } catch (error) {
    ElMessage.error("导入失败");
  } finally {
    loading.value = false;
  }
}

async function runPreview() {
  loading.value = true;
  try {
    preview.value = await previewSource({
      text: sourceText.value || undefined,
      url: sourceUrl.value || undefined
    });
    ElMessage.success("预览完成");
  } catch (error) {
    ElMessage.error("预览失败");
  } finally {
    loading.value = false;
  }
}

async function runConfirmImport() {
  loading.value = true;
  try {
    draft.value = await confirmSourceImport({
      text: sourceText.value || undefined,
      url: sourceUrl.value || undefined,
      legal_confirmation: legalConfirmation.value,
      exam: { ...examForm },
      use_reasoning_model: useReasoning.value
    });
    ElMessage.success("AI 草稿已生成");
  } catch (error) {
    ElMessage.error("AI 结构化失败");
  } finally {
    loading.value = false;
  }
}

async function runAiExtract() {
  if (!aiText.value.trim()) {
    ElMessage.warning("请填写待整理文本");
    return;
  }
  loading.value = true;
  try {
    draft.value = await extractQuestions({
      text: aiText.value,
      exam: { ...examForm },
      use_reasoning_model: useReasoning.value
    });
    ElMessage.success("AI 草稿已生成");
  } catch (error) {
    ElMessage.error("AI 结构化失败");
  } finally {
    loading.value = false;
  }
}

async function importDraft() {
  if (!draft.value) return;
  loading.value = true;
  try {
    result.value = await importAiJson(draft.value, updateExisting.value);
    ElMessage.success("AI 草稿已导入");
  } catch (error) {
    ElMessage.error("草稿导入失败");
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <section class="split">
    <div class="panel">
      <div class="panel-header">
        <div>
          <h2>导入工作台</h2>
          <p>JSON、来源预览和 DeepSeek v4 结构化</p>
        </div>
        <el-switch v-model="updateExisting" active-text="更新重复题" />
      </div>
      <div class="panel-body">
        <el-tabs>
          <el-tab-pane label="JSON">
            <el-input
              v-model="jsonText"
              class="editor"
              type="textarea"
              :rows="18"
              placeholder="粘贴符合后端格式的 JSON"
            />
            <div class="tag-row" style="margin-top: 14px">
              <el-button type="primary" :icon="Upload" :loading="loading" @click="runJsonImport">导入 JSON</el-button>
            </div>
          </el-tab-pane>

          <el-tab-pane label="来源预览">
            <el-form label-position="top">
              <el-form-item label="URL">
                <el-input v-model="sourceUrl" placeholder="https://..." />
              </el-form-item>
              <el-form-item label="文本">
                <el-input v-model="sourceText" type="textarea" :rows="8" placeholder="粘贴合法取得的题目文本" />
              </el-form-item>
              <el-checkbox v-model="legalConfirmation">确认来源为自整理、公开授权或合法取得</el-checkbox>
              <div class="tag-row" style="margin-top: 14px">
                <el-button :icon="SearchCheck" :loading="loading" @click="runPreview">预览</el-button>
                <el-button type="primary" :icon="ClipboardCheck" :loading="loading" @click="runConfirmImport">
                  生成草稿
                </el-button>
              </div>
            </el-form>
          </el-tab-pane>

          <el-tab-pane label="AI 文本">
            <el-form label-position="top">
              <div class="toolbar" style="margin-bottom: 12px">
                <el-input v-model="examForm.exam_name" placeholder="考试名称" />
                <el-input v-model="examForm.level" placeholder="级别" />
                <el-input-number v-model="examForm.year" :min="1990" :max="2100" controls-position="right" />
                <el-select v-model="examForm.season">
                  <el-option label="上半年" value="上半年" />
                  <el-option label="下半年" value="下半年" />
                </el-select>
                <el-select v-model="examForm.paper_type">
                  <el-option label="上午综合知识" value="上午综合知识" />
                  <el-option label="下午案例分析" value="下午案例分析" />
                </el-select>
                <el-switch v-model="useReasoning" active-text="推理模型" />
              </div>
              <el-input v-model="aiText" type="textarea" :rows="12" placeholder="粘贴合法来源文本，AI 只生成未校对草稿" />
              <div class="tag-row" style="margin-top: 14px">
                <el-button type="primary" :icon="Bot" :loading="loading" @click="runAiExtract">AI 结构化</el-button>
              </div>
            </el-form>
          </el-tab-pane>
        </el-tabs>
      </div>
    </div>

    <div class="grid">
      <div class="panel">
        <div class="panel-header">
          <div>
            <h2>预览 / 草稿</h2>
            <p>{{ draft ? `${draft.questions.length} 道草稿题` : "等待输入" }}</p>
          </div>
          <el-button :icon="FileJson" :disabled="!draft" :loading="loading" @click="importDraft">导入草稿</el-button>
        </div>
        <div class="panel-body">
          <div v-if="preview" class="answer-result" style="margin-bottom: 12px">
            <p class="muted">{{ preview.compliance_notice }}</p>
            <p>长度：{{ preview.content_length }} 字，{{ preview.truncated ? "已截断" : "未截断" }}</p>
          </div>
          <pre v-if="draft" class="json-preview">{{ draftText }}</pre>
          <el-empty v-else description="暂无草稿" />
        </div>
      </div>

      <div class="panel">
        <div class="panel-header">
          <div>
            <h2>导入结果</h2>
            <p>批次记录由后端保存</p>
          </div>
        </div>
        <div class="panel-body">
          <el-empty v-if="!result" description="暂无结果" />
          <el-descriptions v-else :column="1" border>
            <el-descriptions-item label="批次">{{ result.batch_id }}</el-descriptions-item>
            <el-descriptions-item label="总数">{{ result.total_count }}</el-descriptions-item>
            <el-descriptions-item label="新增">{{ result.success_count }}</el-descriptions-item>
            <el-descriptions-item label="更新">{{ result.updated_count }}</el-descriptions-item>
            <el-descriptions-item label="跳过">{{ result.skipped_count }}</el-descriptions-item>
            <el-descriptions-item label="失败">{{ result.failed_count }}</el-descriptions-item>
          </el-descriptions>
        </div>
      </div>
    </div>
  </section>
</template>

