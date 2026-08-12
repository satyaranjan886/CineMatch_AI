"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { RequireStaff } from "@/components/auth/require-staff";
import {
  AnalyticsBarChart,
  AnalyticsLineChart,
  ChartShell,
} from "@/components/admin/charts";
import { ErrorState } from "@/components/feedback/states";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import * as analyticsApi from "@/lib/api/analytics";

function formatRate(value: number | null | undefined) {
  if (value == null) return "—";
  return `${(value * 100).toFixed(1)}%`;
}

function formatDuration(seconds: number | null | undefined) {
  if (seconds == null) return "—";
  const mins = Math.round(seconds / 60);
  if (mins < 60) return `${mins}m`;
  return `${(mins / 60).toFixed(1)}h`;
}

function MetricCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-border/60 bg-card/40 p-4">
      <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">{label}</p>
      <p className="mt-2 font-display text-3xl text-foreground">{value}</p>
    </div>
  );
}

function DashboardContent() {
  const queryClient = useQueryClient();
  const dashboardQuery = useQuery({
    queryKey: ["analytics-dashboard"],
    queryFn: () => analyticsApi.fetchAnalyticsDashboard(14),
  });

  const refreshMutation = useMutation({
    mutationFn: () => analyticsApi.refreshAnalyticsSnapshot(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["analytics-dashboard"] });
    },
  });

  if (dashboardQuery.isLoading) {
    return (
      <div className="mx-auto max-w-7xl space-y-4 px-4 py-10">
        <Skeleton className="h-10 w-64" />
        <div className="grid gap-4 md:grid-cols-3">
          {Array.from({ length: 9 }).map((_, index) => (
            <Skeleton key={index} className="h-24 w-full" />
          ))}
        </div>
      </div>
    );
  }

  if (dashboardQuery.isError || !dashboardQuery.data) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-10">
        <ErrorState
          title="Dashboard unavailable"
          message="Could not load analytics aggregates."
          onRetry={() => void dashboardQuery.refetch()}
        />
      </div>
    );
  }

  const data = dashboardQuery.data;
  const metrics = data.metrics;
  const evaluation = data.ml.evaluation ?? {};
  const timeseries = data.timeseries.map((row) => ({
    ...row,
    ctr_pct: row.recommendation_ctr == null ? null : Number((row.recommendation_ctr * 100).toFixed(2)),
    cache_pct: row.cache_hit_rate == null ? null : Number((row.cache_hit_rate * 100).toFixed(2)),
  }));

  return (
    <div className="mx-auto max-w-7xl space-y-10 px-4 py-10 sm:px-6 lg:px-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-primary">Admin</p>
          <h1 className="mt-2 font-display text-4xl text-foreground">Analytics dashboard</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            As of {data.as_of} · computed {new Date(data.computed_at).toLocaleString()}
          </p>
        </div>
        <Button
          type="button"
          variant="outline"
          disabled={refreshMutation.isPending}
          onClick={() => refreshMutation.mutate()}
        >
          {refreshMutation.isPending ? "Refreshing…" : "Refresh snapshot"}
        </Button>
      </header>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <MetricCard label="Total Users" value={metrics.total_users} />
        <MetricCard label="Active Users (30d)" value={metrics.active_users} />
        <MetricCard label="Movies" value={metrics.movies} />
        <MetricCard label="Interactions" value={metrics.interactions} />
        <MetricCard label="Recommendations Served" value={metrics.recommendations_served} />
        <MetricCard label="Recommendation CTR" value={formatRate(metrics.recommendation_ctr)} />
        <MetricCard label="Watch Completion" value={formatRate(metrics.watch_completion)} />
        <MetricCard
          label="Avg Session Duration"
          value={formatDuration(metrics.average_session_duration_seconds)}
        />
        <MetricCard label="Cache Hit Rate" value={formatRate(metrics.cache_hit_rate)} />
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <ChartShell
          title="DAU"
          isEmpty={timeseries.every((row) => !row.dau)}
          emptyMessage="No daily active user history in snapshots yet."
        >
          <AnalyticsLineChart data={timeseries} xKey="date" yKey="dau" />
        </ChartShell>
        <ChartShell
          title="Recommendations served"
          isEmpty={timeseries.every((row) => !row.recommendations_served)}
        >
          <AnalyticsLineChart data={timeseries} xKey="date" yKey="recommendations_served" />
        </ChartShell>
        <ChartShell
          title="Recommendation CTR (%)"
          isEmpty={timeseries.every((row) => row.ctr_pct == null)}
        >
          <AnalyticsLineChart data={timeseries} xKey="date" yKey="ctr_pct" />
        </ChartShell>
        <ChartShell
          title="Cache hit rate (%)"
          isEmpty={timeseries.every((row) => row.cache_pct == null)}
        >
          <AnalyticsLineChart data={timeseries} xKey="date" yKey="cache_pct" />
        </ChartShell>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <ChartShell
          title="Recommendations by algorithm"
          isEmpty={(data.recommendation.by_algorithm ?? []).length === 0}
        >
          <AnalyticsBarChart
            data={data.recommendation.by_algorithm.map((row) => ({
              algorithm: row.algorithm,
              count: row.count,
            }))}
            xKey="algorithm"
            yKey="count"
          />
        </ChartShell>
        <ChartShell title="Top genres" isEmpty={(data.users.top_genres ?? []).length === 0}>
          <AnalyticsBarChart
            data={data.users.top_genres.map((row) => ({
              genre: row.genre,
              count: row.count,
            }))}
            xKey="genre"
            yKey="count"
          />
        </ChartShell>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        <MetricCard label="DAU" value={data.users.dau} />
        <MetricCard label="WAU" value={data.users.wau} />
        <MetricCard label="MAU" value={data.users.mau} />
        <MetricCard label="New users" value={data.users.new_users} />
        <MetricCard label="Returning users" value={data.users.returning_users} />
        <MetricCard
          label="Rec conversion"
          value={formatRate(data.recommendation.recommendation_conversion)}
        />
      </section>

      <section className="grid gap-4 lg:grid-cols-3">
        <TopList title="Top recommended" rows={data.recommendation.top_recommended_movies} />
        <TopList title="Top clicked" rows={data.recommendation.top_clicked_recommendations} />
        <TopList title="Top completed" rows={data.recommendation.top_completed_recommendations} />
      </section>

      <section className="rounded-xl border border-border/60 bg-card/40 p-5">
        <h2 className="font-display text-2xl text-champagne">ML analytics</h2>
        <dl className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <dt className="text-xs uppercase tracking-wide text-muted-foreground">Current model</dt>
            <dd className="mt-1 text-foreground">{data.ml.current_model_version ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-muted-foreground">Training date</dt>
            <dd className="mt-1 text-foreground">
              {data.ml.training_date ? new Date(data.ml.training_date).toLocaleString() : "—"}
            </dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-muted-foreground">Eval model</dt>
            <dd className="mt-1 text-foreground">
              {evaluation.model_name
                ? `${evaluation.model_name} (${evaluation.model_version})`
                : "—"}
            </dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-muted-foreground">Evaluated users</dt>
            <dd className="mt-1 text-foreground">{evaluation.evaluated_users ?? "—"}</dd>
          </div>
        </dl>
        <div className="mt-6 grid gap-4 sm:grid-cols-3">
          <MetricCard
            label="Precision@10"
            value={formatMetricAtK(evaluation.precision_at_k, "10")}
          />
          <MetricCard label="Recall@10" value={formatMetricAtK(evaluation.recall_at_k, "10")} />
          <MetricCard label="NDCG@10" value={formatMetricAtK(evaluation.ndcg_at_k, "10")} />
        </div>
      </section>

      <p className="text-xs text-muted-foreground">{data.notes}</p>
    </div>
  );
}

function formatMetricAtK(map: Record<string, number> | undefined, k: string) {
  if (!map || map[k] == null) return "—";
  return Number(map[k]).toFixed(4);
}

function TopList({
  title,
  rows,
}: {
  title: string;
  rows: Array<{ movie_id: string; title: string; count: number }>;
}) {
  return (
    <div className="rounded-xl border border-border/60 bg-card/40 p-4">
      <h3 className="font-display text-xl text-champagne">{title}</h3>
      {rows.length === 0 ? (
        <p className="mt-3 text-sm text-muted-foreground">No events recorded yet.</p>
      ) : (
        <ol className="mt-3 space-y-2">
          {rows.map((row) => (
            <li key={`${title}-${row.movie_id}`} className="flex items-center justify-between gap-3 text-sm">
              <span className="truncate text-foreground">{row.title}</span>
              <span className="text-muted-foreground">{row.count}</span>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

export default function AdminAnalyticsPage() {
  return (
    <RequireStaff>
      <DashboardContent />
    </RequireStaff>
  );
}
