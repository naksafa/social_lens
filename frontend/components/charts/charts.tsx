"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  Line,
  LineChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";

import { compact, num, seriesColor, titleCase } from "@/lib/format";

const AXIS = { stroke: "var(--viz-axis)", fontSize: 11, tickLine: false, axisLine: false } as const;

type Formatter = (v: number) => string;

interface TooltipRow {
  name?: string | number;
  value?: number | string | (number | string)[];
  color?: string;
  dataKey?: string | number;
  payload?: Record<string, unknown>;
}

function ChartTooltip({
  active,
  payload,
  label,
  format,
  labelFormat,
}: {
  active?: boolean;
  payload?: TooltipRow[];
  label?: string | number;
  format: Formatter;
  labelFormat?: (l: string) => string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border bg-popover px-3 py-2 text-xs text-popover-foreground shadow-md">
      {label !== undefined && (
        <p className="mb-1 font-medium">{labelFormat ? labelFormat(String(label)) : String(label)}</p>
      )}
      {payload.map((p) => (
        <div key={String(p.dataKey)} className="flex items-center gap-2">
          <span aria-hidden className="size-2 rounded-full" style={{ background: p.color }} />
          <span className="text-muted-foreground">{p.name}</span>
          <span className="ml-auto pl-3 font-medium tabular-nums">
            {typeof p.value === "number" ? format(p.value) : String(p.value ?? "—")}
          </span>
        </div>
      ))}
    </div>
  );
}

export interface LineSeries {
  key: string;
  label: string;
  color: string;
  dashed?: boolean;
}

/** Time-series line chart with crosshair tooltip. One y-axis only. */
export function TrendChart({
  data,
  series,
  format = compact,
  height = 240,
}: {
  data: Record<string, unknown>[];
  series: LineSeries[];
  format?: Formatter;
  height?: number;
}) {
  return (
    <div>
      {series.length > 1 && (
        <div className="mb-2 flex flex-wrap gap-3 text-xs text-muted-foreground">
          {series.map((s) => (
            <span key={s.key} className="flex items-center gap-1.5">
              <svg width="16" height="6" aria-hidden>
                <line x1="0" y1="3" x2="16" y2="3" stroke={s.color} strokeWidth="2" strokeDasharray={s.dashed ? "4 3" : undefined} />
              </svg>
              {s.label}
            </span>
          ))}
        </div>
      )}
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} stroke="var(--viz-grid)" />
          <XAxis dataKey="label" {...AXIS} minTickGap={24} />
          <YAxis {...AXIS} width={48} tickFormatter={(v: number) => format(v)} />
          <Tooltip
            cursor={{ stroke: "var(--viz-axis)", strokeDasharray: "3 3" }}
            content={<ChartTooltip format={format} />}
          />
          {series.map((s) => (
            <Line
              key={s.key}
              type="monotone"
              dataKey={s.key}
              name={s.label}
              stroke={s.color}
              strokeWidth={2}
              strokeDasharray={s.dashed ? "4 3" : undefined}
              strokeOpacity={s.dashed ? 0.7 : 1}
              dot={false}
              activeDot={{ r: 4, strokeWidth: 2, stroke: "var(--viz-surface)" }}
              connectNulls={false}
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export interface BarRow {
  label: string;
  value: number | null;
  low?: boolean;
  count?: number;
}

/** Horizontal bars for comparing groups on one metric. Low-sample groups are faded and marked. */
export function HBarChart({
  rows,
  color,
  format = (v) => num(v, 2),
  height,
}: {
  rows: BarRow[];
  color: string;
  format?: Formatter;
  height?: number;
}) {
  const data = rows.filter((r) => r.value !== null);
  if (!data.length) return <p className="py-8 text-center text-sm text-muted-foreground">No data</p>;
  return (
    <ResponsiveContainer width="100%" height={height ?? Math.max(120, data.length * 34 + 16)}>
      <BarChart data={data} layout="vertical" margin={{ top: 4, right: 56, bottom: 4, left: 4 }} barCategoryGap={6}>
        <XAxis type="number" hide domain={[0, "dataMax"]} />
        <YAxis type="category" dataKey="label" {...AXIS} width={110} stroke="var(--foreground)" />
        <Tooltip
          cursor={{ fill: "var(--muted)", opacity: 0.5 }}
          content={({ active, payload }) => {
            const row = payload?.[0]?.payload as BarRow | undefined;
            if (!active || !row) return null;
            return (
              <div className="rounded-lg border bg-popover px-3 py-2 text-xs shadow-md">
                <p className="font-medium">{row.label}</p>
                <p className="tabular-nums">{row.value !== null ? format(row.value) : "—"}</p>
                {row.count !== undefined && (
                  <p className="text-muted-foreground">
                    {row.count} posts{row.low ? " · small sample" : ""}
                  </p>
                )}
              </div>
            );
          }}
        />
        <Bar dataKey="value" radius={[0, 4, 4, 0]} isAnimationActive={false} maxBarSize={22}>
          {data.map((r) => (
            <Cell key={r.label} fill={color} fillOpacity={r.low ? 0.4 : 1} />
          ))}
          <LabelList
            dataKey="value"
            position="right"
            className="fill-muted-foreground text-[11px]"
            formatter={(v: unknown) => (typeof v === "number" ? format(v) : "")}
          />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

/** Vertical columns (e.g. day of week). */
export function ColumnChart({
  rows,
  color,
  format = (v) => num(v, 2),
  height = 200,
}: {
  rows: BarRow[];
  color: string;
  format?: Formatter;
  height?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={rows} margin={{ top: 16, right: 8, bottom: 0, left: 0 }} barCategoryGap={8}>
        <CartesianGrid vertical={false} stroke="var(--viz-grid)" />
        <XAxis dataKey="label" {...AXIS} />
        <YAxis {...AXIS} width={40} tickFormatter={(v: number) => format(v)} />
        <Tooltip
          cursor={{ fill: "var(--muted)", opacity: 0.5 }}
          content={({ active, payload }) => {
            const row = payload?.[0]?.payload as BarRow | undefined;
            if (!active || !row) return null;
            return (
              <div className="rounded-lg border bg-popover px-3 py-2 text-xs shadow-md">
                <p className="font-medium">{row.label}</p>
                <p className="tabular-nums">{row.value !== null ? format(row.value) : "—"}</p>
                {row.count !== undefined && <p className="text-muted-foreground">{row.count} posts</p>}
              </div>
            );
          }}
        />
        <Bar dataKey="value" radius={[4, 4, 0, 0]} isAnimationActive={false} maxBarSize={36}>
          {rows.map((r) => (
            <Cell key={r.label} fill={color} fillOpacity={r.low ? 0.4 : 1} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

/** 100% stacked horizontal bars (content mix per platform) with a shared legend. */
export function MixChart({ rows, order }: { rows: { label: string; mix: Record<string, number> }[]; order: string[] }) {
  const keysPresent = order.filter((k) => rows.some((r) => (r.mix[k] ?? 0) > 0));
  const data = rows.map((r) => ({ label: r.label, ...Object.fromEntries(keysPresent.map((k) => [k, r.mix[k] ?? 0])) }));
  return (
    <div>
      <div className="mb-2 flex flex-wrap gap-3 text-xs text-muted-foreground">
        {keysPresent.map((k) => (
          <span key={k} className="flex items-center gap-1.5">
            <span aria-hidden className="size-2.5 rounded-sm" style={{ background: seriesColor(order.indexOf(k)) }} />
            {titleCase(k)}
          </span>
        ))}
      </div>
      <ResponsiveContainer width="100%" height={rows.length * 40 + 12}>
        <BarChart data={data} layout="vertical" stackOffset="expand" margin={{ top: 0, right: 8, bottom: 0, left: 4 }}>
          <XAxis type="number" hide />
          <YAxis type="category" dataKey="label" {...AXIS} width={90} stroke="var(--foreground)" />
          <Tooltip
            cursor={{ fill: "var(--muted)", opacity: 0.5 }}
            content={<ChartTooltip format={(v) => `${num(v, 1)}%`} labelFormat={(l) => l} />}
          />
          {keysPresent.map((k) => (
            <Bar
              key={k}
              dataKey={k}
              name={titleCase(k)}
              stackId="mix"
              fill={seriesColor(order.indexOf(k))}
              stroke="var(--background)"
              strokeWidth={2}
              isAnimationActive={false}
              maxBarSize={24}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Scatter (e.g. video duration vs completion). */
export function ScatterPlot({
  points,
  color,
  xLabel,
  yLabel,
  height = 240,
}: {
  points: { x: number; y: number }[];
  color: string;
  xLabel: string;
  yLabel: string;
  height?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ScatterChart margin={{ top: 8, right: 12, bottom: 16, left: 0 }}>
        <CartesianGrid stroke="var(--viz-grid)" />
        <XAxis
          type="number"
          dataKey="x"
          name={xLabel}
          {...AXIS}
          label={{ value: xLabel, position: "insideBottom", offset: -8, fill: "var(--viz-axis)", fontSize: 11 }}
        />
        <YAxis type="number" dataKey="y" name={yLabel} {...AXIS} width={40} />
        <ZAxis range={[64, 64]} />
        <Tooltip
          cursor={{ strokeDasharray: "3 3" }}
          content={({ active, payload }) => {
            const p = payload?.[0]?.payload as { x: number; y: number } | undefined;
            if (!active || !p) return null;
            return (
              <div className="rounded-lg border bg-popover px-3 py-2 text-xs shadow-md tabular-nums">
                <p>
                  {xLabel}: <b>{num(p.x)}</b>
                </p>
                <p>
                  {yLabel}: <b>{num(p.y, 1)}</b>
                </p>
              </div>
            );
          }}
        />
        <Scatter data={points} fill={color} fillOpacity={0.75} stroke="var(--viz-surface)" strokeWidth={1} isAnimationActive={false} />
      </ScatterChart>
    </ResponsiveContainer>
  );
}
