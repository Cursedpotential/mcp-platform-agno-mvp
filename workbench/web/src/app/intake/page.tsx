// Byline: Claude Code · Sonnet (agent) · 2026-07-20
/**
 * Intake — the renamed Files page. Upload is folded in here (no more
 * standalone /upload route — see _stale/upload-page-pre-c1/ for the retired
 * route file) and the Promote buttons are gone (owner rejected the
 * upload->promote blind-box UX); each row's action is now "Start run ->",
 * which opens the New-run dialog prefilled with that staged file.
 */
import { UploadForm } from "@/components/upload/upload-form";
import { IntakeTable } from "@/components/intake/intake-table";

export default function IntakePage() {
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold tracking-tight">Intake</h1>
      <UploadForm />
      <IntakeTable />
    </div>
  );
}
