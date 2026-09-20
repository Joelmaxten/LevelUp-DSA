def iso_utc(dt):
    """
    ISO-8601 string for a model timestamp. The created_at / uploaded_at columns
    default to datetime.utcnow() (naive UTC), so append "Z" to make that explicit -
    otherwise browsers would parse the value as local time.
    """
    return dt.isoformat() + "Z" if dt else None
