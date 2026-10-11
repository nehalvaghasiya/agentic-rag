import { formatBytes, formatIsoDate } from "../../../utils/format";
import { Card, CardContent, CardDescription, CardTitle } from "../../ui/Card";

function StatCard({ label, value }) {
  return (
    <Card>
      <CardContent className="px-4 py-4">
        <CardDescription className="text-xs">{label}</CardDescription>
        <CardTitle className="mt-2 text-sm">{value}</CardTitle>
      </CardContent>
    </Card>
  );
}

export function StatGrid({ stats }) {
  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
      <StatCard label="Total Size" value={formatBytes(stats.totalSize)} />
      <StatCard label="File Count" value={String(stats.fileCount)} />
      <StatCard label="Ranking Strategy" value={stats.rankingStrategy} />
      <StatCard label="Embedding Model" value={stats.embeddingModel} />
      <StatCard label="Chunking Strategy" value={stats.chunkingStrategy} />
      <StatCard label="Last Modified" value={formatIsoDate(stats.lastModified)} />
    </div>
  );
}
