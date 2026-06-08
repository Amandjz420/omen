"""Report routes (mounted under /api/).

The report download endpoint (``GET /api/valuations/{id}/report``) lives on the
ValuationViewSet since it hangs off a valuation. This module is reserved for
future report-management endpoints (invoice/dispatch/receipt) once those wire to
the legacy system.
"""

urlpatterns: list = []
