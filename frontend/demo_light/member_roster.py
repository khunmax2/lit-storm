"""Small, deterministic roster filters and pagination for the member page."""

PAGE_SIZE = 10


def filter_members(profiles, query="", role="all", status="all"):
    needle = query.strip().casefold()
    return [row for row in profiles if (
        (not needle or needle in (row.get("display_name") or "").casefold()
         or needle in (row.get("email") or "").casefold())
        and (role == "all" or row.get("role") == role)
        and (status == "all" or bool(row.get("is_active", True)) == (status == "active"))
    )]


def page_members(profiles, page, page_size=PAGE_SIZE):
    pages = max(1, (len(profiles) + page_size - 1) // page_size)
    page = min(max(int(page), 1), pages)
    return profiles[(page - 1) * page_size:page * page_size], page, pages
