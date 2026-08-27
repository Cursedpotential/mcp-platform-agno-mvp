// Package temporal implements the n8n <-> Temporal transport for
// engine/uiw.UniversalImportWorkflow's two n8n-backed Activities
// (select_parser_activity, execute_parser_activity — see
// docker/n8n/workflows/universal-import/README.md). It registers the real
// UniversalImportWorkflow — not a workflow of its own — and provides the
// small authenticated HTTP surface n8n's start/decision/preview workflows
// call, since n8n has no native Temporal client.
//
//	n8n "start" webhook  -> this package's HTTP starter -> Temporal client
//	  -> engine/uiw.UniversalImportWorkflow
//	       -> select_parser_activity  -> n8n "select" webhook  -> engine/runtimeapi (Go parser)
//	       -> [human preview hold: a real Signal + Query + Timer, entirely
//	           inside UniversalImportWorkflow — see engine/uiw/preview.go]
//	       -> n8n "decision" webhook -> this package's HTTP starter -> Signal
//	       -> execute_parser_activity -> n8n "execute" webhook -> engine/runtimeapi (Go parser)
//	       -> the other 21 canon stages (registered with these two by the
//	          sole production worker in engine/uiwworker)
//
// The preview hold deliberately lives inside UniversalImportWorkflow itself,
// as a genuine Temporal Signal/Query/Timer, rather than as an Activity-level
// trick in this package: only a workflow-level hold is durable across a
// worker restart or a replica change, because Temporal replays the
// workflow's own history to resume it, independent of any one worker
// process. An earlier Activity-async-completion design that tried to do
// this at the Activity boundary (with an in-process hold store) could not
// give that guarantee and was rejected — see
// to_be_deleted/temporal-holds.go.obsolete for why, kept for history.
//
// Every wire type this package's Activities send over HTTP mirrors the
// compact StageRequest/StageResult contract already implemented by the n8n
// workflows and engine/runtimeapi/parser_activities.go: request_id,
// source_version_ref, declared_format, refs on the way in; stage, status,
// ref, receipt_ref on the way out. Nothing here re-implements parsing,
// persistence, the runtime HTTP handler, or the workflow's own orchestration.
// Those stay owned by engine/activities, engine/runtimeapi, and engine/uiw;
// engine/uiwworker only composes their concrete production adapters.
package temporal
