import { notFound } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { getProperty } from "@/lib/api";
import ScoreBadge from "@/components/ScoreBadge";
import PropertyDetailTabs from "@/components/PropertyDetailTabs";

export default async function PropertyDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  let property;
  try {
    property = await getProperty(id);
  } catch {
    notFound();
  }

  return (
    <div className="space-y-6">
      <Link
        href="/properties"
        className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700"
      >
        <ArrowLeft size={16} />
        Back to list
      </Link>

      <div className="bg-white rounded-xl border border-slate-200 p-6">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-xl font-bold text-slate-900">
              {property.address}
            </h1>
            {property.eircode && (
              <p className="text-slate-500 text-sm mt-1">{property.eircode}</p>
            )}
          </div>
          <ScoreBadge score={property.propensity_score} size="lg" />
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 px-6">
        <PropertyDetailTabs property={property} />
      </div>
    </div>
  );
}
