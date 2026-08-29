# AWAITING VERIFICATION

## **THIS IS PURGATORY. NOTHING IN HERE IS TRUSTED.**

## **Every document in this directory CLAIMS to be complete. None of those claims has been checked.**

## **A DIFFERENT agent or person than the one who wrote it must verify the claim before it moves anywhere.**

---

### What this directory is NOT

- **NOT** an owner inbox. The owner is not the reviewer of first resort.
- **NOT** a queue of pending owner decisions.
- **NOT** a place to park work you didn't finish. Unfinished work stays in the active docs.
- **NOT** evidence that anything described inside it actually works.

### The flow

```
agent claims "done"  ->  docs/awaiting-verification/  ->  verified by someone else
                                                            |
                                        pass -> promoted to the live docs
                                        fail -> corrected, or -> to_be_deleted/
```

### If you are the verifying agent

You must be a **different** agent than the author. Check the claim against the **repository and the
running system**, not against the document's own narrative. A document asserting `STATUS: PASS` is
the thing under test — it is not proof of itself.

Record the outcome, and record the ruling in `docs/DECISION_LOG.md` in the same change (**D-096**).

### If you are the authoring agent

Putting a document here does not close your task. It opens a review.

### Never

Never delete from here. Failed items move to repo-root `to_be_deleted/` for owner review.
