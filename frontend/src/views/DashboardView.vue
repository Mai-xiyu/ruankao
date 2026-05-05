<script setup lang="ts">
import * as echarts from "echarts";
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { AlertTriangle, BookMarked, Database, Heart, Tags } from "lucide-vue-next";

import { fetchOverview, fetchQuestionsByYear, fetchWrongByTag } from "../api";
import type { OverviewStats, WrongTagStat, YearStat } from "../types";

const loading = ref(false);
const stats = ref<OverviewStats>({ exams: 0, questions: 0, tags: 0, favorites: 0, wrong_records: 0 });
const yearStats = ref<YearStat[]>([]);
const wrongTags = ref<WrongTagStat[]>([]);
const chartRef = ref<HTMLDivElement | null>(null);

const statItems = [
  { key: "exams", label: "考试", icon: BookMarked },
  { key: "questions", label: "题目", icon: Database },
  { key: "tags", label: "标签", icon: Tags },
  { key: "favorites", label: "收藏", icon: Heart },
  { key: "wrong_records", label: "错题记录", icon: AlertTriangle }
] as const;

function drawChart() {
  if (!chartRef.value) return;
  const chart = echarts.init(chartRef.value);
  const sorted = [...yearStats.value].sort((a, b) => a.year - b.year);
  chart.setOption({
    color: ["#2d6f64"],
    grid: { left: 36, right: 16, top: 24, bottom: 28 },
    xAxis: { type: "category", data: sorted.map((item) => String(item.year)), axisTick: { show: false } },
    yAxis: { type: "value", minInterval: 1, splitLine: { lineStyle: { color: "#e8e9e2" } } },
    tooltip: { trigger: "axis" },
    series: [
      {
        type: "bar",
        data: sorted.map((item) => item.question_count),
        barWidth: 28,
        itemStyle: { borderRadius: [4, 4, 0, 0] }
      }
    ]
  });
  window.addEventListener("resize", () => chart.resize(), { once: true });
}

async function load() {
  loading.value = true;
  try {
    const [overview, byYear, wrongByTag] = await Promise.all([
      fetchOverview(),
      fetchQuestionsByYear(),
      fetchWrongByTag()
    ]);
    stats.value = overview;
    yearStats.value = byYear;
    wrongTags.value = wrongByTag;
    drawChart();
  } catch (error) {
    ElMessage.error("读取概览失败");
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <section v-loading="loading" class="grid">
    <div class="stat-strip">
      <div v-for="item in statItems" :key="item.key" class="stat-item">
        <div class="tag-row">
          <component :is="item.icon" :size="18" />
          <p class="stat-label">{{ item.label }}</p>
        </div>
        <p class="stat-value">{{ stats[item.key] }}</p>
      </div>
    </div>

    <div class="grid two">
      <div class="panel">
        <div class="panel-header">
          <div>
            <h2>年份题量</h2>
            <p>按考试年份统计题目数量</p>
          </div>
          <el-button :icon="null" @click="load">刷新</el-button>
        </div>
        <div class="panel-body">
          <div ref="chartRef" class="chart" />
        </div>
      </div>

      <div class="panel">
        <div class="panel-header">
          <div>
            <h2>错题标签</h2>
            <p>按知识点查看复盘压力</p>
          </div>
        </div>
        <div class="panel-body">
          <el-empty v-if="!wrongTags.length" description="暂无错题记录" />
          <el-table v-else :data="wrongTags" size="small">
            <el-table-column prop="tag" label="标签" />
            <el-table-column prop="wrong_count" label="错题数" width="100" align="right" />
          </el-table>
        </div>
      </div>
    </div>
  </section>
</template>

