import clsx from "clsx";

export default function StatCard({
  label,
  value,
  hint,
  accent,
}: {
  label: string;
  value: string | number;
  hint?: string;
  accent?: "indigo" | "red" | "orange" | "slate";
}) {
  const accentClasses: Record<string, string> = {
    indigo: "text-indigo-600",
    red: "text-red-600",
    orange: "text-orange-600",
    slate: "text-slate-700",
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
      <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">
        {label}
      </p>
      <p
        className={clsx(
          "text-2xl font-bold mt-1",
          accentClasses[accent ?? "slate"]
        )}
      >
        {value}
      </p>
      {hint && <p className="text-xs text-slate-400 mt-1">{hint}</p>}
    </div>
  );
}
