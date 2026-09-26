import fnmatch


def source_allowed(agent, entry):
    """Return whether current feed metadata permits an agent to use an entry."""
    if agent is None:
        return True

    allow_list = (
        agent.get("allow_list")
        if agent.get("allow_list") is not None
        else agent.get("whitelist")
    )
    deny_list = (
        agent["deny_list"]
        if agent.get("deny_list") is not None
        else agent.get("blacklist")
    )
    category_deny_list = agent.get("category_deny_list")
    feed = entry.get("feed") or {}
    category_data = feed.get("category") or {}
    category = category_data.get("title")
    site_url = feed.get("site_url")

    # Missing metadata must not bypass a configured rule. Empty deny lists do
    # not require metadata because they deny nothing.
    if category_deny_list:
        if not category:
            return False
        if any(fnmatch.fnmatch(category, pattern) for pattern in category_deny_list):
            return False

    # Preserve the legacy precedence: a configured allow list supersedes the
    # URL deny list, while category denials always win.
    if allow_list is not None:
        if not site_url:
            return False
        return any(fnmatch.fnmatch(site_url, pattern) for pattern in allow_list)

    if deny_list is not None:
        if deny_list and not site_url:
            return False
        return not any(
            fnmatch.fnmatch(site_url or "", pattern) for pattern in deny_list
        )

    return True


def filter_entry(config, agent, entry):
    start_with_list = [name[1]["title"] for name in config.agents.items()]
    style_block = [name[1]["style_block"] for name in config.agents.items()]
    [start_with_list.append("<blockquote>") for i in style_block if i]

    if not source_allowed(agent[1], entry):
        return False

    # filter, if not content starts with start flag
    return not entry.get("content", "").startswith(tuple(start_with_list))
