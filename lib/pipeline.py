"""Orchestrates one end-to-end refresh cycle: fetch -> dedup -> enrich -> store."""

from . import sources, dedup, enrich, db

MAX_NEW_ITEMS_PER_REFRESH = 24  # cost/latency control — raise once you've checked API spend


def refresh(profile, sources_cfg):
    """Runs one full refresh cycle. Returns a status dict for display in the UI:
    {fetch_status, raw_count, deduped_count, enriched_count, errors, skipped_no_key}
    """
    db.init_db()

    raw_items, fetch_status = sources.fetch_all(sources_cfg)

    existing_urls, existing_titles = db.get_existing_urls_and_titles()
    deduped = dedup.dedup(raw_items, existing_urls, existing_titles)
    deduped = deduped[:MAX_NEW_ITEMS_PER_REFRESH]

    result = dict(fetch_status=fetch_status, raw_count=len(raw_items),
                  deduped_count=len(deduped), enriched_count=0, errors=[])

    if not deduped:
        db.log_refresh(0, fetch_status)
        return result

    try:
        enriched, enrich_errors = enrich.enrich_batch(deduped, profile)
        result["errors"].extend(enrich_errors)
        if enriched:
            db.upsert_updates(enriched)
        result["enriched_count"] = len(enriched)
    except RuntimeError as e:
        result["errors"].append(str(e))

    db.log_refresh(result["enriched_count"], fetch_status)
    return result
