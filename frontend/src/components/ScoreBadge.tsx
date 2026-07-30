import clsx from "clsx";

/** Barevný odznak skóre pravděpodobnosti prodeje (0-100). */
export default function ScoreBadge({
  score,
  size = "md",
}: {
  score: number;
  size?: "sm" | "md" | "lg";
}) {
  const level =
    score >= 60 ? "high" : score >= 35 ? "medium" : score >= 15 ? "low" : "minimal";

  const colors: Record<string, string> = {
    high: "bg-red-100 text-red-700 border-red-300",
    medium: "bg-orange-100 text-orange-700 border-orange-300",
    low: "bg-yellow-100 text-yellow-800 border-yellow-300",
    minimal: "bg-slate-100 text-slate-600 border-slate-300",
  };

  const sizes: Record<string, string> = {
    sm: "text-xs px-2 py-0.5",
    md: "text-sm px-2.5 py-1",
    lg: "text-lg px-4 py-2",
  };

  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 rounded-full border font-semibold",
        colors[level],
        sizes[size]
      )}
      title="Propensity Score - probability of sale"
    >
      {score.toFixed(0)}%
    </span>
  );
}

export function scoreColor(score: number): string {
  if (score >= 60) return "#dc2626"; // červená
  if (score >= 35) return "#ea580c"; // oranžová
  if (score >= 15) return "#ca8a04"; // žlutá
  return "#64748b"; // šedá
}
