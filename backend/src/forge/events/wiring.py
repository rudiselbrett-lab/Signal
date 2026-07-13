"""Event → async subscriber wiring.

The single place where cross-context reactions are declared. Called once at
process start (API and workers alike).
"""

from forge.events.bus import subscribe_task

_wired = False


def register_subscribers() -> None:
    global _wired
    if _wired:
        return
    _wired = True
    subscribe_task("article.discovered", "forge.enrichment.score_article")
    subscribe_task("article.saved", "forge.enrichment.extract_knowledge")
    subscribe_task("article.enriched", "forge.enrichment.embed_article")
    # Later phases append here:
    #   article.read   → forge.reviews.generate_items, forge.analytics.record_read
