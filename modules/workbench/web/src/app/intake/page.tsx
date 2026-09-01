// Byline: Claude Code · Sonnet (agent) · 2026-07-20
// Byline: Codex · GPT-5 · 2026-08-28 (production UIW intake surface)
/**
 * Intake — the renamed Files page. Upload is folded in here (no more
 * standalone /upload route — see _stale/upload-page-pre-c1/ for the retired
 * route file) and the Promote buttons are gone (owner rejected the
 * upload->promote blind-box UX); each row's action is now "Start run ->",
 * which opens the New-run dialog prefilled with that staged file.
 */
import { UnifiedIntake } from "@/components/intake/unified-intake";

export default function IntakePage() {
  return <UnifiedIntake />;
}
