/** Invalidate synchronously before starting a review of changed inputs. */
export function createReviewState() {
  let revision = 0;
  let current = { status: "not_reviewed", review: null };
  return {
    invalidate() {
      revision += 1;
      current = { status: "pending", review: null };
      return revision;
    },
    accept(revisionOfRequest, review) {
      if (revisionOfRequest !== revision) return false;
      current = { status: "requires_human_review", review };
      return true;
    },
    snapshot() { return structuredClone(current); },
  };
}
