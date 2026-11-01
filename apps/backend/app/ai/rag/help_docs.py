"""Help center and policy content indexed for Vibe AI."""
HELP_DOCS: dict[str, tuple[str, str]] = {
    "help-account": ("Your account", (
        "To create a RedStarVibe account you need an email address and must be at least 13 years old. We email you a "
        "6 digit code to verify the address. You can log in with your password, with a one time email code, or with "
        "Google when it is enabled. Change your display name, bio, website and avatar in Settings."
    )),
    "help-privacy": ("Privacy and private accounts", (
        "A private account means only followers you approve can see your posts and stories. Turn it on in Settings. "
        "When you switch from private to public, all pending follow requests are accepted. Blocking someone removes "
        "follows in both directions, and they can no longer find your profile or message you."
    )),
    "help-posts": ("Posts, reels and stories", (
        "A post can contain up to 10 photos or videos with a caption, hashtags, mentions and a location. Photos can be "
        "up to 20 MB. Post videos can be up to 10 minutes and reels up to 90 seconds. Location data inside your photos "
        "is removed automatically when you upload. Stories disappear after 24 hours; add them to a highlight to keep "
        "them on your profile. You can see who viewed your story. Save a post as a draft or schedule it for later."
    )),
    "help-messages": ("Messages and calls", (
        "Direct messages support 1:1 and group chats with typing indicators and seen receipts. Audio and video calls "
        "start from a conversation. Group video calls support up to 8 people, and audio calls up to 32. Call media is "
        "encrypted in transit and never passes through our API servers."
    )),
    "help-safety": ("Safety and reporting", (
        "Report a post, comment, story, message or account from its menu. Reports go to our moderation team and "
        "automated checks also screen new content. Accounts that break the rules can be suspended. We take child "
        "safety seriously and scan uploads against known abuse hash lists."
    )),
    "help-data": ("Your data", (
        "Download a copy of your data at any time from Settings. Deleting your account schedules permanent removal "
        "after 30 days; log in and choose restore before then to cancel. Multi factor authentication with an "
        "authenticator app is available in Settings."
    )),
}
