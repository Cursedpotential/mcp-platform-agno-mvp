# Plan Feedback

I've reviewed this plan and have 5 pieces of feedback:

## 1. Feedback on: "My recommendation: Store full UUIDv7 everywhere. If you want short display IDs for the UI (like EV-a1b2c3d4), add a computed short_id column or a display helper function — but NEVER use truncated UUIDs as actual identifiers. For externalId fields in readers (Face"
> ok 

## 2. Feedback on: "t"
> ok

## 3. Feedback on: "MySQL auto-increment IDs (Tier 5): MySQL handles app metadata (users, API keys). Auto-increment is appropriate here — these aren't evidence records."
> Do we consider implementing a index inside of one of the databases probably Mysql listing each hash and UUID and file name

## 4. Feedback on: "Existing data: No migration needed. UUIDv4 values already in the database are valid UUIDs — they just won't be chronologically sortable. New records will be UUIDv7. This is fine for a system still in development.
"
> There shouldn't be any existing data unless it's just an example or a stub or a test I'd like to know what it is and if it is legitimate it needs to get a proper ID not stay on version 4

## 5. Feedback on: "
"
> Pig agents that use GLM 5 for some of the deployment make sure that the drizzle schemas and the Python D do and any graph QL utilizes the skills necessary to do the job

---
