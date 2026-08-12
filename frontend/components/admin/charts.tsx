"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { EmptyState, ErrorState } from "@/components/feedback/states";
import { Skeleton } from "@/components/ui/skeleton";

type ChartShellProps = {
  title: string;
  isLoading?: boolean;
  isError?: boolean;
  isEmpty?: boolean;
  onRetry?: () => void;
  emptyMessage?: string;
  children: React.ReactNode;
};

export function ChartShell({
  title,
  isLoading,
  isError,
  isEmpty,
  onRetry,
  emptyMessage = "No data for this period yet.",
  children,
}: ChartShellProps) {
  return (
    <section className="rounded-xl border border-border/60 bg-card/40 p-4" aria-labelledby={`chart-${title}`}>
      <h3 id={`chart-${title}`} className="font-display text-xl text-champagne">
        {title}
      </h3>
      <div className="mt-4 h-64 w-full">
        {isLoading ? <Skeleton className="h-full w-full" /> : null}
        {isError ? <ErrorState title="Chart unavailable" onRetry={onRetry} /> : null}
        {!isLoading && !isError && isEmpty ? <EmptyState title="No data" message={emptyMessage} /> : null}
        {!isLoading && !isError && !isEmpty ? children : null}
      </div>
    </section>
  );
}

export function AnalyticsLineChart({
  data,
  xKey,
  yKey,
  yFormatter,
}: {
  data: Array<Record<string, string | number | null>>;
  xKey: string;
  yKey: string;
  yFormatter?: (value: number) => string;
}) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data}>
        <CartesianGrid stroke="oklch(0.3 0.02 55)" strokeDasharray="3 3" />
        <XAxis dataKey={xKey} tick={{ fill: "oklch(0.72 0.02 75)", fontSize: 12 }} />
        <YAxis
          tick={{ fill: "oklch(0.72 0.02 75)", fontSize: 12 }}
          tickFormatter={yFormatter}
        />
        <Tooltip
          contentStyle={{
            background: "oklch(0.18 0.014 55)",
            border: "1px solid oklch(0.3 0.02 55)",
            borderRadius: 8,
          }}
        />
        <Line type="monotone" dataKey={yKey} stroke="oklch(0.78 0.11 85)" strokeWidth={2} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

export function AnalyticsBarChart({
  data,
  xKey,
  yKey,
}: {
  data: Array<Record<string, string | number | null>>;
  xKey: string;
  yKey: string;
}) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data}>
        <CartesianGrid stroke="oklch(0.3 0.02 55)" strokeDasharray="3 3" />
        <XAxis dataKey={xKey} tick={{ fill: "oklch(0.72 0.02 75)", fontSize: 12 }} />
        <YAxis tick={{ fill: "oklch(0.72 0.02 75)", fontSize: 12 }} />
        <Tooltip
          contentStyle={{
            background: "oklch(0.18 0.014 55)",
            border: "1px solid oklch(0.3 0.02 55)",
            borderRadius: 8,
          }}
        />
        <Bar dataKey={yKey} fill="oklch(0.78 0.11 85)" radius={[6, 6, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
